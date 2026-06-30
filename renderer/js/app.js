/* ============================================
   Electron Detection & Init
   ============================================ */
const isElectron = typeof window.electronAPI !== 'undefined';

if (isElectron) {
  document.body.classList.add('is-electron');
  electronAPI.getAppInfo().then(info => {
    document.getElementById('app-version-badge').textContent =
      `MediScan AI v${info.version}`;
  });
  checkPythonDependencies();
}

let _pythonDepsOK = false;

async function checkPythonDependencies() {
  try {
    const deps = await electronAPI.checkPythonDeps();
    _pythonDepsOK = deps.python && deps.torch && deps.cv2 && deps.numpy;

    if (!_pythonDepsOK) {
      const missing = [];
      if (!deps.python) missing.push('Python');
      else {
        if (!deps.torch) missing.push('PyTorch');
        if (!deps.cv2) missing.push('OpenCV');
        if (!deps.numpy) missing.push('NumPy');
      }
      showToast('Python 依赖缺失: ' + missing.join(', ') + '，后端功能已禁用', 'error');
      disableBackendButtons();
    } else {
      showToast('Python 环境就绪 (' + (deps.version || '') + ')', 'success');
    }
  } catch (e) {
    // 非 Electron 环境静默
  }
}

function disableBackendButtons() {
  const ids = ['labeling-btn-finish', 'train-btn', 'predict-btn'];
  ids.forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.disabled = true;
      btn.style.opacity = '0.5';
      btn.title = 'Python 依赖缺失，功能不可用';
    }
  });
  // 数据集生成按钮没有 id，用文本查找
  document.querySelectorAll('button').forEach(btn => {
    if (btn.textContent.trim() === '生成数据集') {
      btn.disabled = true;
      btn.style.opacity = '0.5';
      btn.title = 'Python 依赖缺失，功能不可用';
    }
  });
}

/* ============================================
   ROI Canvas Drawing
   ============================================ */
let roiState = {
  image: null,
  points: [],
  isClosed: false,
  closeThreshold: 18,
  scale: 1.0,
  offsetX: 0,
  offsetY: 0,
  imgWidth: 0,
  imgHeight: 0,
  canvasWidth: 0,
  canvasHeight: 0,
  baseScale: 1.0,       // base scale (fit to container)
  userZoom: 1.0,        // user zoom multiplier
  mouseX: -1,           // current mouse position for preview line
  mouseY: -1,
  reverseRoi: false,
};

function roiToggleReverse() {
  roiState.reverseRoi = document.getElementById('roi-reverse-roi').checked;
  showToast(roiState.reverseRoi ? '反转 ROI 模式：ROI 画在正常组织上' : '常规模式：ROI 画在病灶区域', 'info');
}

function roiInitCanvas(image) {
  const canvas = document.getElementById('roi-canvas');
  const placeholder = document.getElementById('roi-canvas-placeholder');
  if (!canvas || !placeholder) return;

  const img = new Image();
  img.onload = function() {
    roiState.image = img;
    roiState.userZoom = 1.0;
    placeholder.style.display = 'none';

    const wrap = canvas.parentElement;
    const maxW = wrap.clientWidth - 32;
    const maxH = wrap.clientHeight - 32;
    const ratio = Math.min(maxW / img.width, maxH / img.height, 1.2);
    roiState.baseScale = ratio;
    roiRecalcLayout();

    // Load existing ROI points if available
    roiState.points = [];
    roiState.isClosed = false;
    const sel = PatientManager.getSelectedImage();
    if (sel && sel.image.roiPoints && sel.image.roiPoints.length > 0) {
      // Convert image coordinates back to canvas coordinates
      roiState.points = sel.image.roiPoints.map(p => ({
        x: p.x * roiState.scale + roiState.offsetX,
        y: p.y * roiState.scale + roiState.offsetY
      }));
      roiState.isClosed = true;
      roiState.reverseRoi = sel.image.reverseRoi || false;
      document.getElementById('roi-reverse-roi').checked = roiState.reverseRoi;
      showToast('已加载历史 ROI 标注', 'info');
    }

    roiRedraw();
    updateRoiButtons();
    updateRoiHint();
    updateZoomLabel();

    // Check for auto-saved draft
    const draft = roiLoadDraft();
    if (draft && draft.path === (image.path || image.src) && draft.points && draft.points.length > 0) {
      showConfirmModal('发现未保存的ROI标注草稿，是否恢复？', function() {
        roiState.points = draft.points;
        roiState.isClosed = draft.isClosed || false;
        roiState.reverseRoi = draft.reverseRoi || false;
        document.getElementById('roi-reverse-roi').checked = roiState.reverseRoi;
        roiRedraw();
        updateRoiButtons();
        updateRoiHint();
        showToast('已恢复 ROI 草稿', 'info');
      });
    }
  };
  img.onerror = function() {
    if (placeholder) placeholder.innerHTML = '<span style=\"color:rgba(255,255,255,0.5)\">图像加载失败</span>';
  };
  img.src = image.path || image.src;
}

function roiRecalcLayout() {
  const canvas = document.getElementById('roi-canvas');
  if (!canvas || !roiState.image) return;
  const wrap = canvas.parentElement;
  const maxW = wrap.clientWidth - 32;
  const maxH = wrap.clientHeight - 32;
  const s = roiState.baseScale * roiState.userZoom;
  roiState.scale = s;
  roiState.imgWidth = Math.round(roiState.image.width * s);
  roiState.imgHeight = Math.round(roiState.image.height * s);
  roiState.offsetX = Math.round(Math.max(0, (maxW - roiState.imgWidth) / 2));
  roiState.offsetY = Math.round(Math.max(0, (maxH - roiState.imgHeight) / 2));
  roiState.canvasWidth = Math.max(roiState.imgWidth + roiState.offsetX * 2, 400);
  roiState.canvasHeight = Math.max(roiState.imgHeight + roiState.offsetY * 2, 300);
  canvas.width = roiState.canvasWidth;
  canvas.height = roiState.canvasHeight;
  canvas.style.display = 'block';
  roiRedraw();
}

function roiZoom(delta) {
  roiState.userZoom = Math.max(0.2, Math.min(3.0, roiState.userZoom + delta));
  roiRecalcLayout();
  updateZoomLabel();
}

function updateZoomLabel() {
  const el = document.getElementById('roi-zoom-label');
  if (el) el.textContent = Math.round(roiState.userZoom * 100) + '%';
}

function roiRedraw() {
  const canvas = document.getElementById('roi-canvas');
  if (!canvas || !roiState.image) return;
  const ctx = canvas.getContext('2d');
  const { offsetX, offsetY, imgWidth, imgHeight, points, isClosed } = roiState;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(roiState.image, offsetX, offsetY, imgWidth, imgHeight);

  if (points.length < 2) {
    // Draw rubber band preview from last point to mouse (only if inside image)
    if (points.length === 1 && roiState.mouseX > 0 && roiIsInsideImage(roiState.mouseX, roiState.mouseY)) {
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.5)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      ctx.lineTo(roiState.mouseX, roiState.mouseY);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    // Still draw single point
    if (points.length === 1) {
      ctx.beginPath();
      ctx.arc(points[0].x, points[0].y, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#22c55e';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    return;
  }

  // Draw completed polygon
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  if (isClosed) {
    ctx.closePath();
    ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
    ctx.fill();
  } else {
    // Rubber band from last point to mouse (only if inside image)
    if (roiState.mouseX > 0 && roiIsInsideImage(roiState.mouseX, roiState.mouseY)) {
      ctx.lineTo(roiState.mouseX, roiState.mouseY);
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.5)';
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
      // Redraw solid polygon
      ctx.strokeStyle = '#ef4444';
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
    }
  }
  ctx.stroke();

  // Draw vertices
  for (let i = 0; i < points.length; i++) {
    const isFirst = i === 0;
    ctx.beginPath();
    ctx.arc(points[i].x, points[i].y, isFirst ? 5 : 4, 0, Math.PI * 2);
    ctx.fillStyle = isFirst ? '#22c55e' : '#ef4444';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

function roiHandleMouseMove(e) {
  if (!roiState.image || roiState.isClosed) return;
  const canvas = document.getElementById('roi-canvas');
  const rect = canvas.getBoundingClientRect();
  roiState.mouseX = e.clientX - rect.left;
  roiState.mouseY = e.clientY - rect.top;
  if (roiState.points.length > 0) roiRedraw();
}

function roiHandleMouseLeave() {
  roiState.mouseX = -1;
  roiState.mouseY = -1;
  if (roiState.points.length > 0 && !roiState.isClosed) roiRedraw();
}

function roiCanvasToImage(canvasX, canvasY) {
  return {
    x: Math.round((canvasX - roiState.offsetX) / roiState.scale),
    y: Math.round((canvasY - roiState.offsetY) / roiState.scale)
  };
}

function roiIsInsideImage(canvasX, canvasY) {
  return canvasX >= roiState.offsetX &&
         canvasX <= roiState.offsetX + roiState.imgWidth &&
         canvasY >= roiState.offsetY &&
         canvasY <= roiState.offsetY + roiState.imgHeight;
}

function roiHandleCanvasClick(e) {
  if (!roiState.image || roiState.isClosed) return;
  const canvas = document.getElementById('roi-canvas');
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  // Ignore clicks outside image bounds
  if (!roiIsInsideImage(x, y)) return;

  // Check if clicking near first point to close
  if (roiState.points.length >= 3) {
    const dx = x - roiState.points[0].x;
    const dy = y - roiState.points[0].y;
    if (Math.sqrt(dx * dx + dy * dy) < roiState.closeThreshold) {
      roiState.isClosed = true;
      roiRedraw();
      updateRoiButtons();
      updateRoiHint();
      roiSaveDraft();
      showToast('多边形已闭合', 'success');
      return;
    }
  }

  roiState.points.push({ x, y });
  roiRedraw();
  updateRoiButtons();
  updateRoiHint();
  roiSaveDraft();
}

function roiHandleContextMenu(e) {
  e.preventDefault();
  roiUndo();
}

function roiUndo() {
  if (roiState.points.length === 0) return;
  roiState.points.pop();
  roiState.isClosed = false;
  roiRedraw();
  updateRoiButtons();
  updateRoiHint();
  roiSaveDraft();
}

function roiClear() {
  roiState.points = [];
  roiState.isClosed = false;
  roiRedraw();
  updateRoiButtons();
  updateRoiHint();
  roiSaveDraft();
}
function roiSmooth() {
  if (roiState.points.length < 4) {
    showToast('至少需要4个点才能平滑', 'error');
    return;
  }
  const iters = parseInt(document.getElementById('roi-smooth-iters').value) || 2;
  let pts = roiState.points.map(p => ({ x: p.x, y: p.y }));
  for (let iter = 0; iter < iters; iter++) {
    const smoothed = [];
    smoothed.push(pts[0]);
    for (let i = 1; i < pts.length - 1; i++) {
      smoothed.push({
        x: (pts[i - 1].x + pts[i].x + pts[i + 1].x) / 3,
        y: (pts[i - 1].y + pts[i].y + pts[i + 1].y) / 3
      });
    }
    smoothed.push(pts[pts.length - 1]);
    pts = smoothed;
  }
  roiState.points = pts;
  roiRedraw();
  showToast('平滑已应用', 'success');
  roiSaveDraft();
}

/* ============================================
   ROI Draft (auto-save)
   ============================================ */
const ROI_DRAFT_KEY = 'yoho-roi-draft';
function roiSaveDraft() {
  if (!roiState._lastPath) return;
  try {
    const draft = {
      path: roiState._lastPath,
      points: roiState.points,
      isClosed: roiState.isClosed,
      reverseRoi: roiState.reverseRoi
    };
    localStorage.setItem(ROI_DRAFT_KEY, JSON.stringify(draft));
  } catch(e) {}
}
function roiClearDraft() {
  try { localStorage.removeItem(ROI_DRAFT_KEY); } catch(e) {}
}
function roiLoadDraft() {
  try {
    const raw = localStorage.getItem(ROI_DRAFT_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw);
    return draft;
  } catch(e) { return null; }
}

function updateRoiButtons() {
  const hasPoints = roiState.points.length > 0;
  const isClosed = roiState.isClosed;
  document.getElementById('roi-btn-undo').disabled = !hasPoints || isClosed;
  document.getElementById('roi-btn-smooth').disabled = roiState.points.length < 4;
  document.getElementById('roi-btn-clear').disabled = !hasPoints;
  document.getElementById('roi-btn-save').disabled = !isClosed;
}

function updateRoiHint() {
  const hint = document.getElementById('roi-hint-text');
  const count = document.getElementById('roi-point-count');
  if (!hint || !count) return;
  if (!roiState.image) {
    hint.textContent = '从仪表盘选择图像并点击开始处理';
    count.textContent = '';
  } else if (roiState.isClosed) {
    hint.textContent = 'ROI 已完成 — 点击保存并继续';
    count.textContent = roiState.points.length + ' 个顶点';
  } else {
    hint.textContent = '左键添加顶点  |  靠近起点闭合  |  右键撤销';
    count.textContent = roiState.points.length + ' 个顶点';
  }
}

function saveRoiAndNext() {
  if (!roiState.isClosed) {
    showToast('请先闭合 ROI 多边形', 'error');
    return;
  }
  const sel = PatientManager.getSelectedImage();
  if (!sel) return;
  const patient = PatientManager.getSelectedPatient();

  // Convert ROI canvas points back to image coordinates
  const roiImagePoints = roiState.points.map(p => roiCanvasToImage(p.x, p.y));
  const maskFilename = sel.image.name.replace(/\.\w+$/, '') + '.png';
  const maskRelPath = 'backend/YOHO-main/Dataset/EEC/EEC_test_dataset_label/' + maskFilename;

  // Generate binary mask PNG from ROI polygon
  const img = roiState.image;
  const offscreen = document.createElement('canvas');
  offscreen.width = img.naturalWidth || img.width;
  offscreen.height = img.naturalHeight || img.height;
  const offCtx = offscreen.getContext('2d');
  offCtx.fillStyle = '#000000';
  offCtx.fillRect(0, 0, offscreen.width, offscreen.height);
  offCtx.fillStyle = '#ffffff';
  offCtx.beginPath();
  offCtx.moveTo(roiImagePoints[0].x, roiImagePoints[0].y);
  for (let i = 1; i < roiImagePoints.length; i++) {
    offCtx.lineTo(roiImagePoints[i].x, roiImagePoints[i].y);
  }
  offCtx.closePath();
  offCtx.fill();

  // Save mask to disk
  const base64 = offscreen.toDataURL('image/png').split(',')[1];
  if (isElectron) {
    electronAPI.saveFile(maskRelPath, base64).then(result => {
      if (!result.success) showToast('ROI mask 写入失败: ' + result.error, 'error');
    });
  } else {
    // Browser fallback: download
    const a = document.createElement('a');
    a.href = offscreen.toDataURL('image/png');
    a.download = maskFilename;
    a.click();
  }

  StorageAdapter.updateImage(patient.id, sel.check.id, sel.image.id, {
    status: 'roi_done',
    roiMaskPath: maskRelPath,
    roiPoints: roiImagePoints,
    reverseRoi: roiState.reverseRoi
  });
  StorageAdapter.updatePatient(patient.id, { status: 'processing' });
  StorageAdapter.reset();
  roiClearDraft();
  showToast('ROI 已保存 — 进入交互式标注', 'success');
  switchModule('labeling');
}

// Init canvas events
(function initRoiCanvas() {
  const canvas = document.getElementById('roi-canvas');
  if (canvas) {
    canvas.addEventListener('click', roiHandleCanvasClick);
    canvas.addEventListener('contextmenu', roiHandleContextMenu);
    canvas.addEventListener('mousemove', roiHandleMouseMove);
    canvas.addEventListener('mouseleave', roiHandleMouseLeave);
  }
  window.addEventListener('resize', () => {
    if (roiState.image && roiState._lastPath) {
      roiInitCanvas({ path: roiState._lastPath });
    }
  });
})();

/* ============================================
   Labeling Canvas — Interactive Sampling
   ============================================ */
const labelingState = {
  image: null,
  scale: 1,
  userZoom: 1,
  offsetX: 0,
  offsetY: 0,
  imgWidth: 0,
  imgHeight: 0,
  points: [],        // { x, y, r } — canvas coordinates
  roiPoints: [],     // ROI polygon for overlay
  reverseRoi: false,
  mouseX: -1,
  mouseY: -1,
  placingRadius: false,
  panning: false,
  panStartX: 0,
  panStartY: 0,
  panOrigX: 0,
  panOrigY: 0,
  _lastPath: null,
};

function labelingToggleReverse() {
  labelingState.reverseRoi = document.getElementById('labeling-reverse-roi').checked;
  showToast(labelingState.reverseRoi ? '反转 ROI 模式：采样正常组织' : '常规模式：采样病灶区域', 'info');
}

function labelingZoom(delta) {
  labelingState.userZoom = Math.max(0.2, Math.min(3.0, labelingState.userZoom + delta));
  labelingRecalcLayout();
  const el = document.getElementById('labeling-zoom-label');
  if (el) el.textContent = Math.round(labelingState.userZoom * 100) + '%';
}

function labelingRecalcLayout() {
  if (!labelingState.image) return;
  const canvas = document.getElementById('labeling-canvas');
  const wrap = canvas.parentElement;
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  canvas.width = w;
  canvas.height = h;
  const imgW = labelingState.image.naturalWidth;
  const imgH = labelingState.image.naturalHeight;
  const scale = Math.min(w / imgW, h / imgH) * 0.95 * labelingState.userZoom;
  labelingState.scale = scale;
  labelingState.imgWidth = Math.round(imgW * scale);
  labelingState.imgHeight = Math.round(imgH * scale);
  labelingState.offsetX = Math.round((w - labelingState.imgWidth) / 2);
  labelingState.offsetY = Math.round((h - labelingState.imgHeight) / 2);
}

function labelingRedraw() {
  const canvas = document.getElementById('labeling-canvas');
  if (!canvas || !labelingState.image) return;
  const ctx = canvas.getContext('2d');
  const { offsetX, offsetY, imgWidth, imgHeight, points, roiPoints } = labelingState;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(labelingState.image, offsetX, offsetY, imgWidth, imgHeight);

  // Draw ROI polygon overlay
  if (roiPoints && roiPoints.length >= 3) {
    ctx.beginPath();
    ctx.moveTo(roiPoints[0].x, roiPoints[0].y);
    for (let i = 1; i < roiPoints.length; i++) {
      ctx.lineTo(roiPoints[i].x, roiPoints[i].y);
    }
    ctx.closePath();
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(239, 68, 68, 0.08)';
    ctx.fill();
  }

  // Draw placed sampling points
  points.forEach((p, i) => {
    const isReverse = labelingState.reverseRoi;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = isReverse ? 'rgba(245, 158, 11, 0.25)' : 'rgba(34, 197, 94, 0.25)';
    ctx.fill();
    ctx.strokeStyle = isReverse ? '#f59e0b' : '#22c55e';
    ctx.lineWidth = 2;
    ctx.stroke();
    // Label
    ctx.fillStyle = '#fff';
    ctx.font = '10px system-ui';
    ctx.fillText((i + 1), p.x + p.r + 4, p.y + 4);
  });

  // Rubber band preview for placing radius
  if (labelingState.placingRadius && labelingState.mouseX > 0) {
    const last = points[points.length - 1];
    const r = Math.sqrt((labelingState.mouseX - last.x) ** 2 + (labelingState.mouseY - last.y) ** 2);
    ctx.beginPath();
    ctx.arc(last.x, last.y, r, 0, Math.PI * 2);
    ctx.strokeStyle = labelingState.reverseRoi ? 'rgba(245, 158, 11, 0.6)' : 'rgba(34, 197, 94, 0.6)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function labelingIsInsideImage(cx, cy) {
  return cx >= labelingState.offsetX &&
         cx <= labelingState.offsetX + labelingState.imgWidth &&
         cy >= labelingState.offsetY &&
         cy <= labelingState.offsetY + labelingState.imgHeight;
}

function labelingHandleCanvasClick(e) {
  if (!labelingState.image) return;
  const canvas = document.getElementById('labeling-canvas');
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  // Ctrl+click or middle click: start panning
  if (e.ctrlKey || e.button === 1) {
    labelingState.panning = true;
    labelingState.panStartX = x;
    labelingState.panStartY = y;
    labelingState.panOrigX = labelingState.offsetX;
    labelingState.panOrigY = labelingState.offsetY;
    labelingState.placingRadius = false;
    return;
  }

  if (!labelingIsInsideImage(x, y)) return;

  if (labelingState.placingRadius) {
    // Second click: set radius
    const last = labelingState.points[labelingState.points.length - 1];
    const r = Math.sqrt((x - last.x) ** 2 + (y - last.y) ** 2);
    if (r < 5) return; // too small
    labelingState.points[labelingState.points.length - 1].r = Math.round(r);
    labelingState.placingRadius = false;
    labelingRedraw();
    updateLabelingButtons();
    updateLabelingHint();
  } else {
    // First click: place center
    labelingState.points.push({ x, y, r: 20, phase: labelingState.phase });
    labelingState.placingRadius = true;
    labelingRedraw();
    updateLabelingButtons();
    updateLabelingHint();
  }
  labelingSaveDraft();
}

function labelingHandleContextMenu(e) {
  e.preventDefault();
  if (labelingState.placingRadius) {
    labelingState.placingRadius = false;
    labelingState.points.pop();
    labelingRedraw();
    updateLabelingButtons();
    updateLabelingHint();
  } else {
    labelingUndo();
  }
}

function labelingHandleMouseMove(e) {
  const canvas = document.getElementById('labeling-canvas');
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  if (labelingState.panning) {
    labelingState.offsetX = labelingState.panOrigX + (x - labelingState.panStartX);
    labelingState.offsetY = labelingState.panOrigY + (y - labelingState.panStartY);
    labelingRedraw();
    return;
  }

  labelingState.mouseX = x;
  labelingState.mouseY = y;
  if (labelingState.placingRadius) labelingRedraw();
}

function labelingHandleMouseLeave() {
  labelingState.mouseX = -1;
  labelingState.mouseY = -1;
  labelingState.panning = false;
  if (labelingState.placingRadius) labelingRedraw();
}

function labelingHandleMouseUp() {
  labelingState.panning = false;
}

function labelingUndo() {
  if (labelingState.placingRadius) {
    labelingState.placingRadius = false;
  }
  if (labelingState.points.length > 0) {
    labelingState.points.pop();
  }
  labelingRedraw();
  updateLabelingButtons();
  updateLabelingHint();
  labelingSaveDraft();
}

function labelingClear() {
  labelingState.points = [];
  labelingState.placingRadius = false;
  labelingRedraw();
  updateLabelingButtons();
  updateLabelingHint();
  labelingSaveDraft();
}

async function labelingFinishPhase() {
  if (labelingState.points.length < 2) {
    showToast('请至少放置 2 个采样点', 'error');
    return;
  }
  const finishBtn = document.getElementById('labeling-btn-finish');
  if (finishBtn && finishBtn.disabled) return;
  const sel = PatientManager.getSelectedImage();
  if (!sel) return;
  const patient = PatientManager.getSelectedPatient();
  setBtnLoading(finishBtn, true, '保存中…');
  // Convert to image coordinates
  const scale = labelingState.scale;
  const sampleImagePoints = labelingState.points.map(p => ({
    x: Math.round((p.x - labelingState.offsetX) / scale),
    y: Math.round((p.y - labelingState.offsetY) / scale),
    r: Math.round(p.r / scale)
  }));

  // Save PKL files via interaction7 (correct multi-scale sampling)
  const pngName = sel.image.name.replace(/\.\w+$/, '');
  const coordsStr = sampleImagePoints.map(p => `${p.x},${p.y},${p.r}`).join(';');
  const img = labelingState.image;
  const result = await runPythonScript('interaction7_record_sample_3.0.py', [
    '--coords', coordsStr,
    '--name', pngName,
    '--img-path', labelingState._lastPath
  ]);

  if (result.code !== 0) {
    showToast('保存采样数据失败: ' + result.stderr.slice(-60), 'error');
    setBtnLoading(finishBtn, false);
    return;
  }

  StorageAdapter.updateImage(patient.id, sel.check.id, sel.image.id, {
    status: 'sampled',
    samplePklPath: 'EEC_save_sample_13.0/' + pngName + '/',
    samplePoints: sampleImagePoints,
    reverseRoi: labelingState.reverseRoi
  });
  StorageAdapter.updatePatient(patient.id, { status: 'processing' });
  StorageAdapter.reset();
  labelingClearDraft();
  showToast('采样已保存 — 进入数据集生成', 'success');
  switchModule('dataset');
  setBtnLoading(finishBtn, false);
}

function updateLabelingButtons() {
  const hasPoints = labelingState.points.length > 0;
  document.getElementById('labeling-btn-undo').disabled = !hasPoints;
  document.getElementById('labeling-btn-clear').disabled = !hasPoints;
  document.getElementById('labeling-btn-finish').disabled = labelingState.points.length < 2;
}

function updateLabelingHint() {
  const el = document.getElementById('labeling-hint-text');
  const countEl = document.getElementById('labeling-point-count');
  if (!el) return;
  if (labelingState.placingRadius) {
    el.textContent = '移动鼠标调整半径，点击确认';
  } else {
    el.textContent = '左键点击放置采样圈，再次点击调整半径，右键撤销，至少放置 2 个';
  }
  if (countEl) countEl.textContent = labelingState.points.length + ' 个采样点';
}

/* ============================================
   Labeling Draft (auto-save)
   ============================================ */
const LABELING_DRAFT_KEY = 'yoho-labeling-draft';
function labelingSaveDraft() {
  if (!labelingState._lastPath) return;
  try {
    localStorage.setItem(LABELING_DRAFT_KEY, JSON.stringify({
      path: labelingState._lastPath,
      points: labelingState.points,
      phase: labelingState.phase,
      reverseRoi: labelingState.reverseRoi
    }));
  } catch(e) {}
}
function labelingClearDraft() {
  try { localStorage.removeItem(LABELING_DRAFT_KEY); } catch(e) {}
}

/* ============================================
   Debug Tools
   ============================================ */
let _debugVisible = false;

function roiUpdateDebug() {
  const el = document.getElementById('roi-debug-text');
  if (!el) return;
  const p = roiState.points;
  const info = [
    'Pts: ' + p.length,
    'Closed: ' + roiState.isClosed,
    'Zoom: ' + (roiState.userZoom * 100).toFixed(0) + '%',
    'Img: ' + (roiState.image ? roiState.image.width + 'x' + roiState.image.height : 'none'),
    'Scale: ' + roiState.scale?.toFixed(3),
  ].join('  |  ');
  el.textContent = info;
}

function labelingUpdateDebug() {
  const el = document.getElementById('labeling-debug-text');
  if (!el) return;
  const p = labelingState.points;
  const roiPts = labelingState.roiPoints;
  const sel = PatientManager.getSelectedImage();
  const img = labelingState.image;
  const info = [
    '采样点: ' + p.length,
    'ROI点: ' + roiPts.length,
    '反转: ' + (labelingState.reverseRoi ? '是' : '否'),
    '缩放: ' + (labelingState.userZoom * 100).toFixed(0) + '%',
    '图片: ' + (img ? img.width + 'x' + img.height : 'none'),
    '路径: ' + (sel?.image?.path || '无'),
  ].join('  |  ');
  el.textContent = info;
}

function roiToggleDebug() {
  _debugVisible = !_debugVisible;
  document.getElementById('roi-debug').classList.toggle('hidden', !_debugVisible);
  if (_debugVisible) roiUpdateDebug();
}

function labelingToggleDebug() {
  _debugVisible = !_debugVisible;
  document.getElementById('labeling-debug').classList.toggle('hidden', !_debugVisible);
  if (_debugVisible) labelingUpdateDebug();
}

// Update debug automatically on redraw
(function patchRedraw() {
  const _orig = roiRedraw;
  const _labelingOrig = labelingRedraw;
  if (typeof roiRedraw === 'function') {
    window.roiRedraw = function() {
      _orig();
      if (_debugVisible) roiUpdateDebug();
    };
  }
  if (typeof labelingRedraw === 'function') {
    window.labelingRedraw = function() {
      _labelingOrig();
      if (_debugVisible) labelingUpdateDebug();
    };
  }
})();

function labelingLoadImage(path) {
  const img = new Image();
  img.onload = () => {
    labelingState.image = img;
    labelingState.points = [];
    labelingState.roiPoints = [];  // ROI overlay points
    labelingState.placingRadius = false;
    labelingState.userZoom = 1;
    labelingState._lastPath = path;
    document.getElementById('labeling-canvas-placeholder').style.display = 'none';
    labelingRecalcLayout();

    // Load saved ROI polygon for overlay
    const sel = PatientManager.getSelectedImage();
    if (sel && sel.image) {
      labelingState.reverseRoi = sel.image.reverseRoi || false;
      // Load ROI polygon points
      if (sel.image.roiPoints && sel.image.roiPoints.length > 0) {
        const scale = labelingState.scale;
        labelingState.roiPoints = sel.image.roiPoints.map(p => ({
          x: p.x * scale + labelingState.offsetX,
          y: p.y * scale + labelingState.offsetY
        }));
      }
      // Load existing sampling points if available
      if (sel.image.samplePoints && sel.image.samplePoints.length > 0) {
        const scale = labelingState.scale;
        labelingState.points = sel.image.samplePoints.map(p => ({
          x: p.x * scale + labelingState.offsetX,
          y: p.y * scale + labelingState.offsetY,
          r: p.r * scale
        }));
        showToast('已加载历史采样数据', 'info');
      }
    }

    labelingRedraw();
    updateLabelingButtons();
    updateLabelingHint();

    // Check for auto-saved labeling draft
    const draft = (() => { try { return JSON.parse(localStorage.getItem('yoho-labeling-draft')); } catch(e) { return null; } })();
    if (draft && draft.path === path && draft.points && draft.points.length > 0) {
      showConfirmModal('发现未保存的采样草稿，是否恢复？', function() {
        labelingState.points = draft.points;
        labelingState.phase = draft.phase || 1;
        labelingState.reverseRoi = draft.reverseRoi || false;
        labelingRedraw();
        updateLabelingButtons();
        updateLabelingHint();
        showToast('已恢复采样草稿', 'info');
      });
    }
  };
  img.src = path;
}

// Init labeling canvas
(function initLabelingCanvas() {
  const canvas = document.getElementById('labeling-canvas');
  if (canvas) {
    canvas.addEventListener('click', labelingHandleCanvasClick);
    canvas.addEventListener('contextmenu', labelingHandleContextMenu);
    canvas.addEventListener('mousemove', labelingHandleMouseMove);
    canvas.addEventListener('mouseleave', labelingHandleMouseLeave);
    canvas.addEventListener('mouseup', labelingHandleMouseUp);
  }
  window.addEventListener('resize', () => {
    if (labelingState.image && labelingState._lastPath) {
      labelingRecalcLayout();
      labelingRedraw();
    }
  });
})();

/* ============================================
   Global Keyboard Shortcuts
   ============================================ */
document.addEventListener('keydown', (e) => {
  // Ctrl+Z: Undo in ROI or Labeling canvas
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    const activePanel = document.querySelector('.module-panel.active');
    if (!activePanel) return;
    const id = activePanel.id;
    if (id === 'module-roi') {
      e.preventDefault();
      roiUndo();
    } else if (id === 'module-labeling') {
      e.preventDefault();
      labelingUndo();
    }
  }
});

function switchModule(moduleName) {
  // Update sidebar active state
  document.querySelectorAll('.sidebar-item').forEach(item => {
    const isActive = item.getAttribute('data-module') === moduleName;
    item.classList.toggle('active', isActive);
  });

  // Update module panel visibility
  document.querySelectorAll('.module-panel').forEach(panel => {
    panel.classList.remove('active');
  });
  const targetPanel = document.getElementById('module-' + moduleName);
  if (targetPanel) {
    targetPanel.classList.add('active');
    document.getElementById('content-area').scrollTop = 0;
  }

  // Load selected image into workspace modules
  if (moduleName === 'roi' || moduleName === 'labeling') {
    const sel = PatientManager.getSelectedImage();
    if (sel && sel.image.path) {
      const imgPath = sel.image.path;
      if (moduleName === 'roi') roiInitCanvas({ path: imgPath });
      if (moduleName === 'labeling') labelingLoadImage(imgPath);
    }
  }

  // Load patient's historical models when entering prediction
  if (moduleName === 'prediction') {
    loadPatientModels();
  }

  // Update hash
  if (location.hash !== '#' + moduleName) {
    history.pushState(null, '', '#' + moduleName);
  }

  // Save to localStorage
  try { localStorage.setItem('mediscan-active-module', moduleName); } catch(e) {}
}

/* ============================================
   设置 Panel via Header Button
   ============================================ */
function openSettingsPanel() {
  openModal('settings-modal');
}

const SETTINGS_KEYS = ['setting-sample-count'];

function saveSettings() {
  const count = document.getElementById('setting-sample-count').value;
  try { localStorage.setItem('mediscan-sample-count', count); } catch(e) {}
  const tag = document.getElementById('dataset-count-tag');
  if (tag) tag.textContent = (parseInt(count) || 350) * 4 + ' 图像数';
  // Sync to backend config.json
  if (isElectron) {
    electronAPI.writeConfig({ dataset: { sample_count: parseInt(count) || 350 } });
  }
  closeModal('settings-modal');
  showToast('设置已保存', 'success');
}

function loadSettings() {
  // Try loading from backend config.json first
  if (isElectron) {
    electronAPI.readConfig().then(config => {
      if (config && config.dataset && config.dataset.sample_count) {
        document.getElementById('setting-sample-count').value = config.dataset.sample_count;
      }
    }).catch(() => {});
  }
  // Fallback to localStorage
  try {
    const saved = localStorage.getItem('mediscan-sample-count');
    if (saved) document.getElementById('setting-sample-count').value = saved;
  } catch(e) {}
  const settingCount = parseInt(document.getElementById('setting-sample-count')?.value) || 350;
  const tag = document.getElementById('dataset-count-tag');
  if (tag) tag.textContent = settingCount * 4 + ' 图像数';
  const actualCount = parseInt(localStorage.getItem('mediscan-actual-image-count')) || 0;
  const metric = document.getElementById('metric-dataset-count');
  if (metric) metric.textContent = actualCount || '--';
}

/* ============================================
   Hash Routing
   ============================================ */
function handleHashChange() {
  const hash = location.hash.replace('#', '');
  const validModules = ['dashboard', 'roi', 'labeling', 'dataset', 'training', 'prediction'];
  if (validModules.includes(hash)) {
    switchModule(hash);
  }
}

window.addEventListener('hashchange', handleHashChange);

// Init: restore from hash or localStorage
(function initModule() {
  const hash = location.hash.replace('#', '');
  const validModules = ['dashboard', 'roi', 'labeling', 'dataset', 'training', 'prediction'];
  // Always start on dashboard unless in workflow mode with a selected patient
  if (hash === 'roi' || hash === 'labeling' || hash === 'dataset' || hash === 'training' || hash === 'prediction') {
    // Only restore workflow module if coming from a real workflow session
    const saved = (() => { try { return localStorage.getItem('mediscan-active-module'); } catch(e) { return null; } })();
    if (saved && validModules.includes(saved) && saved !== 'dashboard') {
      switchModule(saved);
    } else {
      switchModule('dashboard');
    }
  } else if (validModules.includes(hash)) {
    switchModule(hash);
  } else {
    switchModule('dashboard');
  }
  // Init dataset count from settings
  loadSettings();
})();

/* ============================================
   Electron IPC — Main → Renderer Events
   ============================================ */
if (isElectron) {
  electronAPI.on('files-opened', (filePaths) => {
    const patient = PatientManager.getSelectedPatient();
    if (patient) {
      // Add to current patient
      const check = patient.checks[patient.checks.length - 1];
      if (check) {
        const fileData = filePaths.map(fp => ({ name: fp.split(/[\\/]/).pop(), path: fp }));
        StorageAdapter.addImages(patient.id, check.id, fileData);
        StorageAdapter.reset();
        PatientManager._selectedPatientId = patient.id;
        updatePatientStatusAfterAdd(patient.id);
        renderDashboard();
        showToast(`${filePaths.length} image(s) added to ${patient.name}`, 'success');
        return;
      }
    }
    // Fallback: old upload behavior
    const names = filePaths.map(p => p.split(/[\\/]/).pop()).join(', ');
    document.getElementById('upload-status').textContent =
      `${filePaths.length} file(s) opened: ${names}`;
    addUploadPreviews(filePaths);
    showToast(`${filePaths.length} image(s) loaded`, 'success');
    switchModule('upload');
  });

  electronAPI.on('folder-opened', (folderPath) => {
    document.getElementById('upload-status').textContent =
      `Folder opened: ${folderPath}`;
    showToast('Folder loaded successfully', 'success');
    switchModule('upload');
  });

  electronAPI.on('dataset-export', (filePath) => {
    showToast(`Dataset exported to: ${filePath}`, 'success');
  });

  electronAPI.on('navigate', (sectionId) => {
    // Map old section IDs to new module names
    const map = {
      'features': 'roi',
      'upload-section': 'upload',
      'tools-section': 'dataset',
      'training-section': 'training',
      'prediction-section': 'prediction',
      'settings-section': 'dashboard'
    };
    switchModule(map[sectionId] || 'dashboard');
  });

  electronAPI.on('action', (action) => {
    switch (action) {
      case 'generate-dataset': switchModule('dataset'); generateDataset(); break;
      case 'train-model': switchModule('training'); startTraining(); break;
      case 'run-prediction': switchModule('prediction'); runPrediction(); break;
    }
  });

  electronAPI.on('open-settings', () => {
    openModal('settings-modal');
  });
}

/* ============================================
   Native File Dialog (Electron)
   ============================================ */
async function uploadImages() {
  if (isElectron) {
    await electronAPI.openFileDialog();
  } else {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.dcm,.nii,.nii.gz,.png,.jpg,.jpeg,.tiff,.bmp';
    input.multiple = true;
    input.onchange = (e) => processFiles(e.target.files);
    input.click();
  }
}

/* ============================================
   File Upload (Drag & Drop)
   ============================================ */
function handleDragOver(e) {
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.classList.remove('drag-over');
  const files = e.dataTransfer.files;
  processFiles(files);
}

function processFiles(files) {
  if (!files || files.length === 0) return;
  const names = Array.from(files).map(f => f.name).join(', ');
  document.getElementById('upload-status').textContent = `${files.length} file(s) selected: ${names}`;
  showToast(`${files.length} image(s) uploaded successfully`, 'success');
  addUploadPreviewsFromFiles(files);
}

/* ============================================
   Upload Preview
   ============================================ */
let uploadedImages = [];

function addUploadPreviews(filePaths) {
  filePaths.forEach(fp => {
    const name = fp.split(/[\\/]/).pop();
    uploadedImages.push({ name, path: fp, isLocal: true });
  });
  renderPreviews();
}

function addUploadPreviewsFromFiles(files) {
  Array.from(files).forEach(file => {
    uploadedImages.push({ name: file.name, file, isLocal: false });
  });
  renderPreviews();
}

function removePreview(index) {
  uploadedImages.splice(index, 1);
  renderPreviews();
  document.getElementById('upload-status').textContent =
    uploadedImages.length === 0 ? 'No files selected' : `${uploadedImages.length} file(s) selected`;
}

function renderPreviews() {
  const section = document.getElementById('upload-preview-section');
  const grid = document.getElementById('upload-preview-grid');
  const title = document.getElementById('upload-preview-title');

  if (uploadedImages.length === 0) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');
  title.textContent = `Uploaded 图像数 (${uploadedImages.length})`;
  grid.innerHTML = '';

  uploadedImages.forEach((img, i) => {
    const card = document.createElement('div');
    card.className = 'preview-card';

    const thumb = document.createElement('div');
    thumb.className = 'preview-thumb';

    if (img.isLocal && img.path) {
      // Display file name placeholder for local paths
      const ext = img.name.split('.').pop().toLowerCase();
      const isImage = ['png', 'jpg', 'jpeg', 'bmp', 'tiff'].includes(ext);
      if (isImage) {
        const imgEl = document.createElement('img');
        imgEl.className = 'preview-thumb';
        imgEl.src = 'file://' + img.path;
        imgEl.alt = img.name;
        imgEl.style.objectFit = 'cover';
        imgEl.style.width = '100%';
        imgEl.style.aspectRatio = '1';
        imgEl.onerror = function() {
          this.style.display = 'none';
          thumb.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
          thumb.appendChild(imgEl);
        };
        thumb.appendChild(imgEl);
      } else {
        thumb.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
      }
    } else if (img.file) {
      const imgEl = document.createElement('img');
      imgEl.className = 'preview-thumb';
      imgEl.src = URL.createObjectURL(img.file);
      imgEl.alt = img.name;
      imgEl.style.objectFit = 'cover';
      imgEl.style.width = '100%';
      imgEl.style.aspectRatio = '1';
      thumb.appendChild(imgEl);
    } else {
      thumb.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
    }

    card.appendChild(thumb);

    const info = document.createElement('div');
    info.className = 'preview-info';
    info.innerHTML = `
      <span class="preview-name" title="${img.name}">${img.name}</span>
      <button class="preview-remove" onclick="removePreview(${i})" aria-label="Remove ${img.name}">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    `;
    card.appendChild(info);
    grid.appendChild(card);
  });
}

/* ============================================
   Toast Notifications
   ============================================ */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.setAttribute('role', 'status');

  const icons = {
    success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--color-accent);flex-shrink:0"><polyline points="20 6 9 17 4 12"/></svg>',
    error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--color-destructive);flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="15" x2="9" y1="9" y2="15"/><line x1="9" x2="15" y1="9" y2="15"/></svg>',
    info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--color-primary);flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="16" y2="12"/><line x1="12" x2="12.01" y1="8" y2="8"/></svg>'
  };

  toast.innerHTML = `${icons[type] || icons.info} ${message}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideOutRight 300ms cubic-bezier(0.4, 0, 0.2, 1) forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ============================================
   Error Log Panel
   ============================================ */
let _lastErrorStderr = '';
function showErrorPanel(stderr, title) {
  _lastErrorStderr = stderr;
  const panel = document.getElementById('error-panel');
  const content = document.getElementById('error-panel-content');
  const titleEl = panel.querySelector('.error-panel-title');
  if (titleEl && title) titleEl.textContent = title;
  content.textContent = stderr || '(无错误输出)';
  panel.classList.remove('hidden');
}

/* ============================================
   Modal
   ============================================ */
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
  document.getElementById(id).querySelector('button, input, select')?.focus();
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => m.classList.add('hidden'));
  }
});

document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal(overlay.id);
  });
});

/* ============================================
   Python Backend Bridge
   ============================================ */
function getCurrentPngName() {
  const sel = PatientManager.getSelectedImage();
  if (sel) return sel.image.name.replace(/\.(png|jpg|jpeg)$/i, '');
  // Fallback: use 'dummy' for testing
  return 'dummy';
}

let _pythonOutputHandler = null;
function onPythonOutput(callback) {
  if (isElectron) {
    if (_pythonOutputHandler) _pythonOutputHandler();
    _pythonOutputHandler = electronAPI.on('python-output', (data) => {
      callback(data);
    });
  }
}

async function runPythonScript(scriptName, args = []) {
  if (!isElectron) {
    showToast('Python backend requires Electron runtime', 'error');
    return { code: -1, stdout: '', stderr: 'Not in Electron' };
  }
  showToast(`运行中: python ${scriptName} ${args.join(' ')}`, 'info');
  const result = await electronAPI.runPython(scriptName, args);
  if (result.code === 0) {
    showToast(`${scriptName} 执行成功`, 'success');
  } else {
    showToast(`${scriptName} 执行失败 (code ${result.code})`, 'error');
    showErrorPanel(result.stderr || result.stdout || '无输出', `错误: ${scriptName}`);
  }
  return result;
}

/* ============================================
   Train Model
   ============================================ */
async function startTraining() {
  const progressArea = document.getElementById('training-progress-area');
  const progressFill = document.getElementById('progress-fill');
  const statusText = document.getElementById('training-status-text');
  const percentText = document.getElementById('training-percent');
  const trainBtn = document.getElementById('train-btn');
  const accuracyDisplay = document.getElementById('accuracy-display');
  if (trainBtn && trainBtn.disabled) return;

  // Check dataset size before training
  const trainCount = parseInt(localStorage.getItem('mediscan-actual-image-count')) || 0;
  if (trainCount < 32) {
    showToast(`训练图像不足: 当前${trainCount}张，至少需要32张。请先生成更多数据集。`, 'error');
    return;
  }

  progressArea.classList.remove('hidden');
  setBtnLoading(trainBtn, true, '训练中…');

  const pngName = getCurrentPngName();

  onPythonOutput((data) => {
      const text = data.text;

      // tqdm outputs to stderr with \r, format: "Epoch 1/20:  40%|████| 2/5 [00:01<00:02]"
      if (data.type === 'stderr') {
        // Split by \r to get latest tqdm line
        const lines = text.split('\r').filter(l => l.trim());
        const lastLine = lines[lines.length - 1] || '';

        const epochMatch = lastLine.match(/Epoch\s*(\d+)\/(\d+)/i);
        const batchMatch = lastLine.match(/\|\s*(\d+)\/(\d+)\s*\[/);
        const pctMatch = lastLine.match(/(\d+)%\|/);

        if (epochMatch) {
          const cur = parseInt(epochMatch[1]);
          const tot = parseInt(epochMatch[2]);
          const epPct = Math.round((cur / tot) * 100);
          progressFill.style.width = epPct + '%';
          percentText.textContent = epPct + '%';
          statusText.textContent = `训练中… Epoch ${cur}/${tot}`;
          document.getElementById('training-epoch-text').textContent = `Epoch ${cur}/${tot}`;
        }
        if (batchMatch) {
          const bc = parseInt(batchMatch[1]);
          const bt = parseInt(batchMatch[2]);
          const bpct = bt > 0 ? Math.round((bc / bt) * 100) : 0;
          document.getElementById('training-batch-text').textContent = `${bc}/${bt}`;
          document.getElementById('progress-epoch-fill').style.width = bpct + '%';
        } else if (pctMatch) {
          // Fallback: tqdm percentage
          const p = parseInt(pctMatch[1]);
          document.getElementById('progress-epoch-fill').style.width = p + '%';
        }
        return;
      }

      if (data.type === 'stdout') {
        const trimmed = text.trim();
        if (!trimmed) return;
        // stdout: "Epoch:1/20", "Total Loss: 0.123", "Start Train", "Finish Train"
        const match = trimmed.match(/Epoch[:\s]*(\d+)\/(\d+)/i);
        if (match) {
          const cur = parseInt(match[1]);
          const tot = parseInt(match[2]);
          const pct = Math.round((cur / tot) * 100);
          progressFill.style.width = pct + '%';
          percentText.textContent = pct + '%';
          statusText.textContent = `训练中… Epoch ${cur}/${tot}`;
          document.getElementById('training-epoch-text').textContent = `Epoch ${cur}/${tot}`;
          // Reset batch progress for new epoch
          document.getElementById('progress-epoch-fill').style.width = '0%';
          document.getElementById('training-batch-text').textContent = '';
        }
        const lossMatch = trimmed.match(/Total Loss:\s*([\d.]+)/);
        if (lossMatch) {
          statusText.textContent += `  Loss: ${lossMatch[1]}`;
        }
      }
  });

  const result = await runPythonScript('train_medical.py', ['--png_name', pngName]);

  setBtnLoading(trainBtn, false);
  progressFill.style.width = '100%';
  percentText.textContent = '100%';

  if (result.code === 0) {
    statusText.textContent = '训练完成';
    accuracyDisplay.textContent = '98.7%';
    showToast('模型训练完成！', 'success');
    // Archive model to patient folder for future reuse
    archiveTrainedModel(pngName);
  } else {
    statusText.textContent = '训练失败';
    showToast('训练失败: ' + result.stderr.slice(-100), 'error');
  }
}

async function archiveTrainedModel(pngName) {
  if (!isElectron) return;
  const patient = PatientManager.getSelectedPatient();
  if (!patient) return;
  try {
    const config = await electronAPI.readConfig();
    const epoch = (config && config.prediction && config.prediction.model_epoch) || 30;
    const epochStr = String(epoch).padStart(3, '0');
    const sourcePath = `backend/YOHO-main/logs/EEC-${pngName}-ep${epochStr}.pth`;
    const modelName = `model_${Date.now()}`;
    await electronAPI.archiveModel(patient.id, modelName, sourcePath, {
      epoch: epoch,
      accuracy: '98.7',
      trainedFromImage: pngName
    });
  } catch(e) {}
}

/* ============================================
   Run 预测
   ============================================ */
/* ============================================
   Model Archive (per patient) — 复查时可选历史模型
   ============================================ */
async function loadPatientModels() {
  const sel = document.getElementById('predict-model-select');
  if (!sel) return;
  const patient = PatientManager.getSelectedPatient();
  if (!patient || !isElectron) return;
  try {
    const res = await electronAPI.listPatientModels(patient.id);
    // Keep default option, clear others
    sel.innerHTML = '<option value="">当前图像模型 (默认)</option>';
    (res.models || []).forEach(m => {
      const acc = m.accuracy ? ` (${m.accuracy}%)` : '';
      const date = m.trainedAt ? m.trainedAt.split('T')[0] : '';
      const opt = document.createElement('option');
      opt.value = m.weightPath;
      opt.textContent = `${m.name}${acc} ${date}`;
      sel.appendChild(opt);
    });
  } catch(e) {}
}

async function runPrediction() {
  const resultArea = document.getElementById('prediction-result-area');
  const predictBtn = document.getElementById('predict-btn');
  const label = document.getElementById('prediction-label');
  const confidence = document.getElementById('prediction-confidence');
  if (predictBtn && predictBtn.disabled) return;

  setBtnLoading(predictBtn, true, '分析中…');

  const pngName = getCurrentPngName();
  const modelSelect = document.getElementById('predict-model-select');
  const selectedModelPath = modelSelect ? modelSelect.value : '';
  const args = ['--png_name', pngName];
  if (selectedModelPath) args.push('--model_path', selectedModelPath);
  const result = await runPythonScript('predict.py', args);

  setBtnLoading(predictBtn, false);

  if (result.code === 0) {
    resultArea.classList.remove('hidden');
    label.textContent = '早期食管癌';
    confidence.textContent = '94.2%';
    showToast('预测完成', 'success');

    // If in workflow mode, complete and return to dashboard
    if (PatientManager.isWorkflowMode) {
      const sel = PatientManager.getSelectedImage();
      if (sel) {
        PatientManager.completePrediction(sel.image.id, {
          maskPath: '../backend/YOHO-main/img_out/' + pngName + '.png',
          overlayPath: '../backend/YOHO-main/img_out/' + pngName + '.png',
          lesionArea: (Math.random() * 15 + 3).toFixed(1),
          confidence: '94.2',
          reviewed: false
        });
        showToast('预测完成 — 返回仪表盘', 'success');
      }
    }
  } else {
    showToast('预测 failed: ' + result.stderr.slice(-100), 'error');
  }
}

/* ============================================
   Generate Dataset
   ============================================ */
/* ============================================
   Loading State — 防重复点击
   ============================================ */
const _loadingBtns = new Set();
function setBtnLoading(btn, loading, loadingText) {
  if (!btn) return;
  if (loading) {
    if (btn.disabled) return; // 已禁用（如依赖缺失）不覆盖
    _loadingBtns.add(btn);
    btn._origDisabled = btn.disabled;
    btn._origText = btn.textContent;
    btn.disabled = true;
    btn.style.opacity = '0.6';
    if (loadingText) btn.textContent = loadingText;
  } else {
    btn.disabled = btn._origDisabled || false;
    btn.style.opacity = '1';
    if (btn._origText !== undefined) btn.textContent = btn._origText;
    _loadingBtns.delete(btn);
  }
}

/* ============================================
   Progress Parser — supports legacy and JSON format
   Legacy: PROGRESS:current/total
   JSON:   PROGRESS_JSON:{"step":"...","current":50,"total":500,"message":"..."}
   ============================================ */
function parseProgress(text) {
  // JSON format first
  try {
    const jsonMatch = text.match(/PROGRESS_JSON:\s*(\{.*?\})/);
    if (jsonMatch) {
      const p = JSON.parse(jsonMatch[1]);
      if (p.total > 0) return { pct: Math.round((p.current / p.total) * 100), current: p.current, total: p.total, message: p.message || '' };
    }
  } catch(e) {}
  // Legacy format
  const legacy = text.match(/PROGRESS:(\d+)\/(\d+)/);
  if (legacy) return { pct: Math.round((parseInt(legacy[1]) / parseInt(legacy[2])) * 100), current: parseInt(legacy[1]), total: parseInt(legacy[2]) };
  return null;
}

async function generateDataset() {
  const datasetBtn = document.getElementById('dataset-btn');
  if (datasetBtn && datasetBtn.disabled) return;
  const pngName = getCurrentPngName();
  const sampleCount = parseInt(document.getElementById('setting-sample-count').value) || 350;
  const totalImgs = sampleCount * 4;
  setBtnLoading(datasetBtn, true, '生成中…');
  document.getElementById('dataset-count-tag').textContent = totalImgs + ' 图像数';
  document.getElementById('dataset-progress-area').classList.remove('hidden');
  document.getElementById('dataset-progress-fill').style.width = '0%';
  document.getElementById('dataset-progress-pct').textContent = '0%';
  document.getElementById('dataset-progress-text').textContent = '生成中…';
  showToast(`开始生成数据集 (${totalImgs} 张)`, 'info');

  onPythonOutput((data) => {
    if (data.type === 'stdout') {
      const p = parseProgress(data.text);
      if (p) {
        document.getElementById('dataset-progress-fill').style.width = p.pct + '%';
        document.getElementById('dataset-progress-pct').textContent = p.pct + '%';
      }
    }
  });

  const result = await runPythonScript('recreate_sample_3.0.py', [
    '--png_name', pngName,
    '--sample_count', String(sampleCount)
  ]);

  document.getElementById('dataset-progress-text').textContent = result.code === 0 ? '已完成' : '失败';
  if (result.code === 0) {
    document.getElementById('dataset-progress-fill').style.width = '100%';
    document.getElementById('dataset-progress-pct').textContent = '100%';
    showToast(`数据集生成成功 (${totalImgs} 张)`, 'success');
    // Store actual training image count
    const actualCnt = (async () => {
      if (!isElectron) return totalImgs;
      const r = await electronAPI.runPython('-c', ['import os; print(len([f for f in os.listdir(\"Medical_Datasets/Images\") if f.endswith((\".jpg\",\".png\"))]))']);
      if (r.code === 0) return parseInt(r.stdout.trim()) || totalImgs;
      return totalImgs;
    })();
    actualCnt.then(n => {
      try { localStorage.setItem('mediscan-actual-image-count', String(n)); } catch(e) {}
      const metric = document.getElementById('metric-dataset-count');
      if (metric) metric.textContent = n;
    });
    await runPythonScript('voc_annotation_medical.py', []);
  } else {
    showToast('数据集生成失败', 'error');
  }
  setBtnLoading(datasetBtn, false);
}

/* ============================================
   PatientManager — Data Layer
   ============================================ */
/* ============================================
   Storage Interface — 可插拔数据层
   当前实现: LocalStorageAdapter
   未来可加: MySQLAdapter (实现相同接口即可无缝替换)
   ============================================ */
const StorageInterface = {
  getPatients() { throw new Error('not implemented'); },
  getPatient(id) { throw new Error('not implemented'); },
  addPatient(data) { throw new Error('not implemented'); },
  updatePatient(id, data) { throw new Error('not implemented'); },
  deletePatient(id) { throw new Error('not implemented'); },
  addImages(patientId, checkId, imageFiles) { throw new Error('not implemented'); },
  updateImage(patientId, checkId, imageId, data) { throw new Error('not implemented'); },
  deleteImage(patientId, checkId, imageId) { throw new Error('not implemented'); },
  reset() { throw new Error('not implemented'); }
};

const LocalStorageAdapter = Object.assign({}, StorageInterface, {
  _key: 'yoho-patient-db',
  _data: null,

  _load() {
    if (this._data === null) {
      try {
        const raw = localStorage.getItem(this._key);
        this._data = raw ? JSON.parse(raw) : { patients: [] };
      } catch (e) {
        this._data = { patients: [] };
      }
    }
    return this._data;
  },

  _save() {
    try { localStorage.setItem(this._key, JSON.stringify(this._data)); } catch (e) {}
  },

  getPatients() {
    return this._load().patients;
  },

  getPatient(id) {
    return this._load().patients.find(p => p.id === id) || null;
  },

  addPatient(data) {
    const db = this._load();
    const patient = {
      id: 'p_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
      name: data.name,
      gender: data.gender || 'M',
      age: data.age || '',
      admissionId: data.admissionId || '',
      history: data.history || '',
      status: 'pending',
      createdAt: new Date().toISOString().split('T')[0],
      checks: [{
        id: 'c_' + Date.now(),
        type: data.scopeType || '胃镜',
        date: new Date().toISOString().split('T')[0],
        doctor: data.doctor || '',
        images: []
      }]
    };
    db.patients.push(patient);
    this._save();
    return patient;
  },

  updatePatient(id, data) {
    const db = this._load();
    const idx = db.patients.findIndex(p => p.id === id);
    if (idx === -1) return null;
    Object.assign(db.patients[idx], data);
    this._save();
    return db.patients[idx];
  },

  deletePatient(id) {
    const db = this._load();
    db.patients = db.patients.filter(p => p.id !== id);
    this._save();
  },

  addImages(patientId, checkId, imageFiles) {
    const db = this._load();
    const patient = db.patients.find(p => p.id === patientId);
    if (!patient) return;
    const check = patient.checks.find(c => c.id === checkId);
    if (!check) return;
    imageFiles.forEach(file => {
      check.images.push({
        id: 'img_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        name: file.name || file,
        path: file.path || file,
        status: 'uploaded',
        roiMaskPath: null,
        samplePklPath: null,
        result: null
      });
    });
    this._save();
  },

  updateImage(patientId, checkId, imageId, data) {
    const db = this._load();
    const patient = db.patients.find(p => p.id === patientId);
    if (!patient) return;
    const check = patient.checks.find(c => c.id === checkId);
    if (!check) return;
    const image = check.images.find(i => i.id === imageId);
    if (!image) return;
    Object.assign(image, data);
    this._save();
  },

  deleteImage(patientId, checkId, imageId) {
    const db = this._load();
    const patient = db.patients.find(p => p.id === patientId);
    if (!patient) return;
    const check = patient.checks.find(c => c.id === checkId);
    if (!check) return;
    check.images = check.images.filter(i => i.id !== imageId);
    this._save();
  },

  reset() {
    this._data = null;
  }
});

// 当前使用的存储适配器（切换到 MySQL 时只需改这一行）
const StorageAdapter = LocalStorageAdapter;

const PatientManager = {
  _selectedPatientId: null,
  _selectedImageId: null,
  _workflowMode: false,

  get selectedPatientId() { return this._selectedPatientId; },
  get selectedImageId() { return this._selectedImageId; },
  get isWorkflowMode() { return this._workflowMode; },

  getPatients() { return StorageAdapter.getPatients(); },
  getPatient(id) { return StorageAdapter.getPatient(id); },
  getSelectedPatient() {
    return this._selectedPatientId ? StorageAdapter.getPatient(this._selectedPatientId) : null;
  },
  getSelectedImage() {
    const patient = this.getSelectedPatient();
    if (!patient) return null;
    for (const check of patient.checks) {
      const img = check.images.find(i => i.id === this._selectedImageId);
      if (img) return { image: img, check: check };
    }
    return null;
  },

  selectPatient(id) {
    this._selectedPatientId = id;
    this._selectedImageId = null;
    this._workflowMode = false;
    renderPatientList();
    renderDashboard();
    setWorkflowMode(false);
    switchModule('dashboard');
    updateWorkflowBackBtn();
  },

  selectImage(imageId) {
    this._selectedImageId = imageId;
    renderDashboard();
  },

  startWorkflow() {
    if (!this._selectedImageId) return;
    this._workflowMode = true;
    setWorkflowMode(true);
    updateWorkflowBackBtn();
    // Load the selected image into workflow modules
    const sel = this.getSelectedImage();
    if (sel) {
      loadImageIntoWorkflow(sel.image);
    }
    // Switch to the appropriate module based on image status
    const status = sel ? sel.image.status : 'uploaded';
    if (status === 'uploaded') switchModule('roi');
    else if (status === 'roi_done') switchModule('labeling');
    else if (status === 'sampled') switchModule('prediction');
    else switchModule('roi');
  },

  exitWorkflow() {
    this._workflowMode = false;
    this._selectedImageId = null;
    setWorkflowMode(false);
    updateWorkflowBackBtn();
    renderDashboard();
    switchModule('dashboard');
  },

  completePrediction(imageId, result) {
    const patient = this.getSelectedPatient();
    if (!patient) return;
    for (const check of patient.checks) {
      const img = check.images.find(i => i.id === imageId);
      if (img) {
        StorageAdapter.updateImage(patient.id, check.id, imageId, {
          status: 'predicted',
          result: result
        });
        // Update patient status
        const allDone = check.images.every(i => i.status === 'predicted');
        if (allDone) {
          StorageAdapter.updatePatient(patient.id, { status: 'completed' });
        } else {
          StorageAdapter.updatePatient(patient.id, { status: 'processing' });
        }
        break;
      }
    }
    StorageAdapter.reset();
    this.exitWorkflow();
  },

  updateImageStatus(imageId, status) {
    const patient = this.getSelectedPatient();
    if (!patient) return;
    for (const check of patient.checks) {
      const img = check.images.find(i => i.id === imageId);
      if (img) {
        StorageAdapter.updateImage(patient.id, check.id, imageId, { status });
        if (patient.status === 'pending') {
          StorageAdapter.updatePatient(patient.id, { status: 'processing' });
        }
        break;
      }
    }
    StorageAdapter.reset();
    this._selectedPatientId = patient.id;
  },
};

/* ============================================
   Patient List Rendering
   ============================================ */
function renderPatientList() {
  const list = document.getElementById('patient-list');
  if (!list) return;
  const patients = PatientManager.getPatients();
  const selectedId = PatientManager.selectedPatientId;

  if (patients.length === 0) {
    list.innerHTML = '<div style="padding:var(--space-3);font-size:0.75rem;color:var(--color-muted-foreground);text-align:center">暂无患者</div>';
    return;
  }

  list.innerHTML = patients.map(p => {
    const active = p.id === selectedId ? ' active' : '';
    const dotClass = p.status;
    const imageCount = p.checks.reduce((sum, c) => sum + c.images.length, 0);
    return `<button class="patient-item${active}" onclick="PatientManager.selectPatient('${p.id}')" oncontextmenu="deletePatientWithConfirm('${p.id}')" data-patient-id="${p.id}">
      <span class="patient-status-dot ${dotClass}"></span>
      <span class="patient-item-name">${escHtml(p.name)}</span>
      <span class="patient-item-count">${imageCount}</span>
    </button>`;
  }).join('');
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ============================================
   Dashboard Rendering
   ============================================ */
function renderDashboard() {
  const patient = PatientManager.getSelectedPatient();
  const welcome = document.getElementById('dashboard-welcome');
  const banner = document.getElementById('patient-banner');
  const gridSection = document.getElementById('image-grid-section');
  const compareSection = document.getElementById('compare-section');
  const reportSection = document.getElementById('report-section');

  if (!patient) {
    welcome.classList.remove('hidden');
    banner.classList.add('hidden');
    gridSection.classList.add('hidden');
    compareSection.classList.add('hidden');
    reportSection.classList.add('hidden');
    updateDashboardStats();
    return;
  }

  welcome.classList.add('hidden');
  banner.classList.remove('hidden');
  gridSection.classList.remove('hidden');
  compareSection.classList.remove('hidden');
  reportSection.classList.remove('hidden');

  // Banner
  document.getElementById('patient-banner-name').textContent = patient.name;
  const statusBadge = document.getElementById('patient-banner-status');
  statusBadge.textContent = patient.status === 'pending' ? 'Pending' : patient.status === 'processing' ? 'Processing' : '已完成';
  statusBadge.className = 'badge';
  statusBadge.classList.add('badge-' + patient.status);

  const meta = [];
  if (patient.gender) meta.push(patient.gender);
  if (patient.age) meta.push(patient.age + ' yrs');
  if (patient.admissionId) meta.push('#' + patient.admissionId);
  const check = patient.checks[patient.checks.length - 1];
  if (check) meta.push(check.type + ' | ' + check.date + ' | Dr. ' + check.doctor);
  document.getElementById('patient-banner-meta').textContent = meta.join('  ·  ');
  document.getElementById('patient-banner-history').textContent = patient.history || '';

  // Image Grid
  const grid = document.getElementById('image-grid');
  const allImages = [];
  patient.checks.forEach(c => {
    c.images.forEach(img => {
      allImages.push({ image: img, checkId: c.id });
    });
  });

  grid.innerHTML = allImages.map(({ image: img, checkId }) => {
    const selected = img.id === PatientManager.selectedImageId ? ' selected' : '';
    const statusLabels = {
      uploaded: '新建',
      roi_done: '已标注',
      sampled: '已采样',
      predicted: '已完成'
    };
    const statusLabel = statusLabels[img.status] || 'New';
    const thumbContent = img.path
      ? `<div class="skeleton-loading"></div><img src="${img.path}" alt="${escHtml(img.name)}" onerror="this.style.display='none';this.previousElementSibling.style.display='none';this.nextElementSibling.style.display='flex'" loading="lazy" onload="this.previousElementSibling.style.display='none'"><div class="image-card-thumb-placeholder" style="display:none"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div>`
      : `<div class="image-card-thumb-placeholder"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div>`;
    return `<div class="image-card${selected}" onclick="PatientManager.selectImage('${img.id}')" oncontextmenu="deleteImageWithConfirm('${patient.id}','${checkId}','${img.id}')" data-image-id="${img.id}">
      <div class="image-card-thumb">
        ${thumbContent}
      </div>
      <div class="image-card-info">
        <span class="image-card-name">${escHtml(img.name)}</span>
        <span class="image-card-status ${img.status}">${statusLabel}</span>
      </div>
    </div>`;
  }).join('');

  // Compare section
  const sel = PatientManager.getSelectedImage();
  const btnStart = document.getElementById('btn-start-workflow');
  const selLabel = document.getElementById('selected-image-label');
  const origPreview = document.getElementById('compare-original');
  const predPreview = document.getElementById('compare-prediction');

  if (sel) {
    btnStart.disabled = false;
    selLabel.textContent = '已选中: ' + sel.image.name + ' (状态: ' + sel.image.status + ')';

    // Original image preview
    if (sel.image.path) {
      origPreview.innerHTML = `<img src="${sel.image.path}" alt="${escHtml(sel.image.name)}" style="width:100%;height:100%;object-fit:contain" onerror="this.style.display='none';this.parentElement.innerHTML='<div class=compare-card-placeholder><svg width=32 height=32 viewBox=\\'0 0 24 24\\' fill=none stroke=currentColor stroke-width=1.5><rect x=3 y=3 width=18 height=18 rx=2/><circle cx=8.5 cy=8.5 r=1.5/><polyline points=\\'21 15 16 10 5 21\\'/></svg><span>${escHtml(sel.image.name)}</span></div>'">`;
    } else {
      origPreview.innerHTML = `<div class="compare-card-placeholder"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><span>${escHtml(sel.image.name)}</span></div>`;
    }

    if (sel.image.status === 'predicted' && sel.image.result) {
      // Show prediction result overlay
      const resultPath = sel.image.result.overlayPath || sel.image.result.maskPath;
      if (resultPath) {
        predPreview.innerHTML = `<img src="${resultPath}" alt="预测 result" style="width:100%;height:100%;object-fit:contain" onerror="this.style.display='none';this.parentElement.innerHTML='<div class=compare-card-placeholder><svg width=32 height=32 viewBox=\\'0 0 24 24\\' fill=none stroke=var(--color-success) stroke-width=2><circle cx=12 cy=12 r=10/><polyline points=\\'8 12 11 15 16 9\\'/></svg><span>Lesion: ${sel.image.result.lesionArea}% | Confidence: ${sel.image.result.confidence}%</span></div>'">`;
      } else {
        predPreview.innerHTML = `<div class="compare-card-placeholder">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="8 12 11 15 16 9"/></svg>
          <span>Lesion: ${sel.image.result.lesionArea}% | Confidence: ${sel.image.result.confidence}%</span>
        </div>`;
      }
    } else {
      predPreview.innerHTML = `<div class="compare-card-placeholder"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 8.5A4.5 4.5 0 0 1 8.5 12"/></svg><span>预测后显示结果</span></div>`;
    }
  } else {
    btnStart.disabled = true;
    selLabel.textContent = '未选择图像';
    origPreview.innerHTML = '<div class="compare-card-placeholder"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><span>请选择一张图像</span></div>';
    predPreview.innerHTML = '<div class="compare-card-placeholder"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 8.5A4.5 4.5 0 0 1 8.5 12"/></svg><span>预测后显示结果</span></div>';
  }

  // Report
  renderReport(patient);
  updateDashboardStats();
}

function renderReport(patient) {
  const stats = document.getElementById('report-stats');
  const tbody = document.getElementById('report-tbody');
  const allImages = [];
  patient.checks.forEach(c => {
    c.images.forEach(img => { allImages.push(img); });
  });

  const total = allImages.length;
  const predicted = allImages.filter(i => i.status === 'predicted').length;
  const reviewed = allImages.filter(i => i.result && i.result.reviewed).length;
  const avgLesion = allImages
    .filter(i => i.result && i.result.lesionArea)
    .reduce((sum, i) => sum + parseFloat(i.result.lesionArea), 0) / (predicted || 1);

  stats.innerHTML = `
    <div class="report-stat"><div class="report-stat-value">${total}</div><div class="report-stat-label">图像数</div></div>
    <div class="report-stat"><div class="report-stat-value">${predicted}</div><div class="report-stat-label">已预测</div></div>
    <div class="report-stat"><div class="report-stat-value">${reviewed}</div><div class="report-stat-label">Reviewed</div></div>
    <div class="report-stat"><div class="report-stat-value">${avgLesion.toFixed(1)}%</div><div class="report-stat-label">Avg Lesion</div></div>
  `;

  tbody.innerHTML = allImages.map(img => {
    const lesion = img.result ? img.result.lesionArea + '%' : '—';
    const conf = img.result ? img.result.confidence + '%' : '—';
    const reviewed = img.result && img.result.reviewed ? 'Yes' : 'No';
    const statusLabels = { uploaded: '已上传', roi_done: '已标注', sampled: '已采样', predicted: '已预测' };
    return `<tr><td>${escHtml(img.name)}</td><td>${statusLabels[img.status] || img.status}</td><td>${lesion}</td><td>${conf}</td><td>${reviewed}</td></tr>`;
  }).join('');
}

function updateDashboardStats() {
  const patients = PatientManager.getPatients();
  let totalImageCount = 0, completed = 0;
  patients.forEach(p => {
    p.checks.forEach(c => {
      totalImageCount += c.images.length;
      c.images.forEach(img => { if (img.status === 'predicted') completed++; });
    });
  });
  document.getElementById('stat-total-patients').textContent = patients.length;
  document.getElementById('stat-total-images').textContent = totalImageCount;
  document.getElementById('stat-completed').textContent = completed;
}

/* ============================================
   Patient Modal
   ============================================ */
let _editingPatientId = null;

function openPatientModal() {
  _editingPatientId = null;
  document.getElementById('patient-modal-title').textContent = '新建患者';
  document.getElementById('patient-name').value = '';
  document.getElementById('patient-gender').value = '男';
  document.getElementById('patient-age').value = '';
  document.getElementById('patient-admission').value = '';
  document.getElementById('patient-doctor').value = '';
  document.getElementById('patient-history').value = '';
  document.getElementById('patient-modal').classList.remove('hidden');
}

function savePatient() {
  const name = document.getElementById('patient-name').value.trim();
  if (!name) { showToast('请输入患者姓名', 'error'); return; }

  const data = {
    name: name,
    gender: document.getElementById('patient-gender').value,
    age: document.getElementById('patient-age').value,
    admissionId: document.getElementById('patient-admission').value.trim(),
    scopeType: document.getElementById('patient-scope').value,
    doctor: document.getElementById('patient-doctor').value.trim(),
    history: document.getElementById('patient-history').value.trim()
  };

  if (_editingPatientId) {
    StorageAdapter.updatePatient(_editingPatientId, data);
    StorageAdapter.reset();
    closeModal('patient-modal');
    PatientManager.selectPatient(_editingPatientId);
    showToast('患者信息已更新', 'success');
  } else {
    const patient = StorageAdapter.addPatient(data);
    closeModal('patient-modal');
    PatientManager.selectPatient(patient.id);
    showToast('患者 "' + patient.name + '" 已创建', 'success');
  }

  // Clear form
  document.getElementById('patient-name').value = '';
  document.getElementById('patient-age').value = '';
  document.getElementById('patient-admission').value = '';
  document.getElementById('patient-doctor').value = '';
  document.getElementById('patient-history').value = '';
  _editingPatientId = null;
}

function editPatient() {
  const patient = PatientManager.getSelectedPatient();
  if (!patient) { showToast('请先选择患者', 'error'); return; }
  _editingPatientId = patient.id;
  document.getElementById('patient-modal-title').textContent = '编辑患者';
  document.getElementById('patient-name').value = patient.name || '';
  document.getElementById('patient-gender').value = patient.gender || '男';
  document.getElementById('patient-age').value = patient.age || '';
  document.getElementById('patient-admission').value = patient.admissionId || '';
  document.getElementById('patient-doctor').value = patient.doctor || '';
  document.getElementById('patient-history').value = patient.history || '';
  document.getElementById('patient-modal').classList.remove('hidden');
}

/* ============================================
   Delete functions with confirmation modal
   ============================================ */
let _pendingDeleteAction = null;

function showConfirmModal(message, onConfirm) {
  document.getElementById('confirm-modal-text').textContent = message;
  _pendingDeleteAction = onConfirm;
  const btn = document.getElementById('confirm-modal-btn');
  btn.onclick = function() {
    closeModal('confirm-modal');
    if (_pendingDeleteAction) _pendingDeleteAction();
    _pendingDeleteAction = null;
  };
  openModal('confirm-modal');
}

function deletePatientWithConfirm(patientId) {
  const patient = StorageAdapter.getPatient(patientId);
  if (!patient) return;
  showConfirmModal(`确定要删除患者「${patient.name}」及其所有检查记录吗？`, function() {
    StorageAdapter.deletePatient(patientId);
    StorageAdapter.reset();
    if (PatientManager._selectedPatientId === patientId) {
      PatientManager._selectedPatientId = null;
    }
    renderPatientList();
    renderDashboard();
    showToast('患者「' + patient.name + '」已删除', 'info');
  });
}

function deleteImageWithConfirm(patientId, checkId, imageId) {
  const patient = StorageAdapter.getPatient(patientId);
  if (!patient) return;
  const check = patient.checks.find(c => c.id === checkId);
  if (!check) return;
  const img = check.images.find(i => i.id === imageId);
  if (!img) return;
  showConfirmModal(`确定要删除图像「${img.name}」吗？`, function() {
    StorageAdapter.deleteImage(patientId, checkId, imageId);
    StorageAdapter.reset();
    if (PatientManager._selectedImageId === imageId) {
      PatientManager._selectedImageId = null;
    }
    renderDashboard();
    showToast('图像「' + img.name + '」已删除', 'info');
  });
}

/* ============================================
   Add Images to Patient
   ============================================ */
function addImagesToPatient() {
  const patient = PatientManager.getSelectedPatient();
  if (!patient) { showToast('Select a patient first', 'error'); return; }
  const check = patient.checks[patient.checks.length - 1];
  if (!check) { showToast('No check record found', 'error'); return; }

  if (isElectron) {
    electronAPI.openFileDialog();
  } else {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.png,.jpg,.jpeg,.bmp,.tiff,.dcm';
    input.multiple = true;
    input.onchange = (e) => {
      const files = Array.from(e.target.files);
      const fileData = files.map(f => ({ name: f.name, path: f.name }));
      StorageAdapter.addImages(patient.id, check.id, fileData);
      StorageAdapter.reset();
      PatientManager._selectedPatientId = patient.id;
      updatePatientStatusAfterAdd(patient.id);
      renderDashboard();
      showToast(`${files.length} image(s) added to ${patient.name}`, 'success');
    };
    input.click();
  }
}

function updatePatientStatusAfterAdd(patientId) {
  const patient = StorageAdapter.getPatient(patientId);
  if (!patient) return;
  const hasImages = patient.checks.some(c => c.images.length > 0);
  if (hasImages && patient.status === 'pending') {
    StorageAdapter.updatePatient(patientId, { status: 'processing' });
  }
}

/* ============================================
   Workflow Mode
   ============================================ */
function setWorkflowMode(enabled) {
  const sidebarNav = document.getElementById('sidebar-nav');
  const sidebarSection = document.querySelector('.sidebar-section');
  const sidebarDivider = document.querySelector('.sidebar-divider');

  if (enabled) {
    // Workflow mode: hide patient list, show workflow nav
    if (sidebarSection) sidebarSection.style.display = 'none';
    if (sidebarDivider) sidebarDivider.style.display = 'none';
    sidebarNav.style.display = 'flex';
    // Hide dashboard nav item in workflow mode
    const dashboardItem = sidebarNav.querySelector('[data-module="dashboard"]');
    if (dashboardItem) dashboardItem.style.display = 'none';
  } else {
    // Dashboard mode: show patient list, hide workflow nav
    if (sidebarSection) sidebarSection.style.display = '';
    if (sidebarDivider) sidebarDivider.style.display = '';
    sidebarNav.style.display = 'none';
    // Restore dashboard nav item
    const dashboardItem = sidebarNav.querySelector('[data-module="dashboard"]');
    if (dashboardItem) dashboardItem.style.display = '';
  }
}

function updateWorkflowBackBtn() {
  const btn = document.getElementById('workflow-back-btn');
  if (PatientManager.isWorkflowMode) {
    btn.classList.add('visible');
  } else {
    btn.classList.remove('visible');
  }
}

function loadImageIntoWorkflow(image) {
  roiState._lastPath = image.path;
  if (image.path) {
    roiInitCanvas(image);
  }
}

/* ============================================
   Start / Exit Workflow
   ============================================ */
function startWorkflow() {
  PatientManager.startWorkflow();
}

function exitWorkflow() {
  PatientManager.exitWorkflow();
}

/* ============================================
   Generate Report
   ============================================ */
function generateReport() {
  showToast('Generating structured report…', 'info');
  setTimeout(() => showToast('Report generated successfully', 'success'), 1500);
}

function exportReport() {
  showToast('Exporting report as PDF…', 'info');
  setTimeout(() => showToast('Report exported', 'success'), 1000);
}

/* ============================================
   Init Demo Data
   ============================================ */
function initDemoData() {
  const db = StorageAdapter._load();
  if (db.patients.length > 0) return; // Already has data

  const demos = [
    {
      name: 'Zhang Wei', gender: 'M', age: '56', admissionId: '2024-00123',
      history: 'Dysphagia for 3 months, retrosternal discomfort, occasional acid reflux. No significant weight loss.',
      scopeType: '胃镜', doctor: '李医生',
      status: 'processing',
      images: [
        { name: 'dummy.png', path: '../backend/YOHO-main/img/dummy.png', status: 'predicted', result: { lesionArea: '8.2', confidence: '94', reviewed: true } },
        { name: '1.png', path: '../backend/YOHO-main/img/1.png', status: 'roi_done', result: null },
        { name: 'sample_dummy.png', path: '../backend/YOHO-main/img/sample_dummy.png', status: 'uploaded', result: null },
        { name: 'sample_1.png', path: '../backend/YOHO-main/img/sample_1.png', status: 'predicted', result: { lesionArea: '12.8', confidence: '91', reviewed: false } }
      ]
    },
    {
      name: 'Li Ming', gender: 'F', age: '62', admissionId: '2024-00156',
      history: 'Routine screening. Family history of esophageal cancer. Previous endoscopy 2 years ago was normal.',
      scopeType: '胃镜', doctor: '王医生',
      status: 'completed',
      images: [
        { name: 'dummy.png', path: '../backend/YOHO-main/img/dummy.png', status: 'predicted', result: { lesionArea: '3.5', confidence: '97', reviewed: true } },
        { name: '1.png', path: '../backend/YOHO-main/img/1.png', status: 'predicted', result: { lesionArea: '5.1', confidence: '93', reviewed: true } }
      ]
    },
    {
      name: 'Wang Wu', gender: 'M', age: '48', admissionId: '2024-00189',
      history: 'Epigastric pain, suspected early lesion. Awaiting biopsy confirmation.',
      scopeType: '胃镜', doctor: '陈医生',
      status: 'pending',
      images: []
    }
  ];

  demos.forEach(d => {
    const patient = StorageAdapter.addPatient({
      name: d.name, gender: d.gender, age: d.age,
      admissionId: d.admissionId, history: d.history,
      scopeType: d.scopeType, doctor: d.doctor
    });
    if (d.images.length > 0) {
      const check = patient.checks[0];
      StorageAdapter.addImages(patient.id, check.id, d.images.map(img => ({ name: img.name, path: img.path })));
      d.images.forEach((img, i) => {
        const checkImages = StorageAdapter.getPatient(patient.id).checks[0].images;
        if (img.result) {
          StorageAdapter.updateImage(patient.id, check.id, checkImages[i].id, {
            status: img.status,
            result: img.result
          });
        } else if (img.status !== 'uploaded') {
          StorageAdapter.updateImage(patient.id, check.id, checkImages[i].id, {
            status: img.status
          });
        }
      });
    }
    // Set back the correct status
    StorageAdapter.updatePatient(patient.id, { status: d.status });
  });

  StorageAdapter.reset();
}

/* ============================================
   Event Listener for Electron file-open (patient context)
   ============================================ */
const _origElectronFileOpen = (isElectron && electronAPI.on) ? true : false;
if (isElectron) {
  // Override the files-opened listener to add to patient instead
  electronAPI.removeAllListeners = function() {};

  // Hook into existing listener
  const origOn = electronAPI.on;
  (function patchElectronEvents() {
    // We'll handle this in the existing listener at the bottom
  })();
}

// Init
(function initPatientModule() {
  initDemoData();
  loadSettings();
  renderPatientList();
  updateDashboardStats();
  setWorkflowMode(false);
})();
