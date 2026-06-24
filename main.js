// ============================================
// MediScan AI — Electron Main Process
// ============================================
const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// Security: keep reference to prevent garbage collection
let mainWindow = null;
const isDev = process.argv.includes('--dev');

// ============================================
// Create the main application window
// ============================================
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'MediScan AI — Intelligent Medical Image Platform',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    backgroundColor: '#ECFEFF',
    frame: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // Load the renderer
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // Show window when ready (prevents white flash)
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (isDev) {
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ============================================
// Application Menu
// ============================================
function buildAppMenu() {
  const isMac = process.platform === 'darwin';

  const template = [
    // macOS app menu
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    }] : []),

    // File
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Images…',
          accelerator: 'CmdOrCtrl+O',
          click: () => handleFileOpen(),
        },
        {
          label: 'Open Folder…',
          accelerator: 'CmdOrCtrl+Shift+O',
          click: () => handleFolderOpen(),
        },
        { type: 'separator' },
        {
          label: 'Export Dataset…',
          accelerator: 'CmdOrCtrl+E',
          click: () => handleExportDataset(),
        },
        { type: 'separator' },
        ...(isMac ? [
          { role: 'close' },
        ] : [
          {
            label: 'Exit',
            accelerator: 'Alt+F4',
            click: () => app.quit(),
          },
        ]),
      ],
    },

    // Edit
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },

    // View
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        ...(isDev ? [{ role: 'toggleDevTools' }] : []),
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },

    // Tools
    {
      label: 'Tools',
      submenu: [
        {
          label: 'ROI Annotation Tool',
          click: () => mainWindow?.webContents.send('navigate', 'features'),
        },
        {
          label: 'Interactive Labeling',
          click: () => mainWindow?.webContents.send('navigate', 'tools-section'),
        },
        {
          label: 'Generate Dataset',
          click: () => mainWindow?.webContents.send('action', 'generate-dataset'),
        },
        { type: 'separator' },
        {
          label: 'Train Model',
          accelerator: 'CmdOrCtrl+T',
          click: () => mainWindow?.webContents.send('action', 'train-model'),
        },
        {
          label: 'Run Prediction',
          accelerator: 'CmdOrCtrl+P',
          click: () => mainWindow?.webContents.send('action', 'run-prediction'),
        },
        { type: 'separator' },
        {
          label: 'Settings…',
          accelerator: 'CmdOrCtrl+,',
          click: () => mainWindow?.webContents.send('open-settings'),
        },
      ],
    },

    // Help
    {
      label: 'Help',
      submenu: [
        {
          label: 'Documentation',
          click: () => shell.openExternal('https://mediscan.ai/docs'),
        },
        {
          label: 'About MediScan AI',
          click: () => showAboutDialog(),
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// ============================================
// Dialog Handlers
// ============================================
async function handleFileOpen() {
  if (!mainWindow) return;
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open Medical Images',
    filters: [
      { name: 'Medical Images', extensions: ['dcm', 'nii', 'nii.gz', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'] },
      { name: 'DICOM Files', extensions: ['dcm'] },
      { name: 'NIfTI Files', extensions: ['nii', 'nii.gz'] },
      { name: 'All Images', extensions: ['png', 'jpg', 'jpeg', 'tiff', 'bmp'] },
      { name: 'All Files', extensions: ['*'] },
    ],
    properties: ['openFile', 'multiSelections'],
  });

  if (!result.canceled && result.filePaths.length > 0) {
    mainWindow.webContents.send('files-opened', result.filePaths);
  }
}

async function handleFolderOpen() {
  if (!mainWindow) return;
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open Dataset Folder',
    properties: ['openDirectory'],
  });

  if (!result.canceled && result.filePaths.length > 0) {
    mainWindow.webContents.send('folder-opened', result.filePaths[0]);
  }
}

async function handleExportDataset() {
  if (!mainWindow) return;
  const result = await dialog.showSaveDialog(mainWindow, {
    title: 'Export Dataset',
    defaultPath: 'dataset-export',
    filters: [
      { name: 'COCO JSON', extensions: ['json'] },
      { name: 'YOLO Format', extensions: ['txt'] },
      { name: 'Pascal VOC XML', extensions: ['xml'] },
    ],
  });

  if (!result.canceled && result.filePath) {
    mainWindow.webContents.send('dataset-export', result.filePath);
  }
}

function showAboutDialog() {
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'About MediScan AI',
    message: 'MediScan AI v1.0.0',
    detail: 'Intelligent Medical Image Recognition Platform\n\nBuilt for radiologists, researchers, and healthcare professionals.\n\nFeatures:\n• ROI Annotation\n• Interactive Labeling\n• Dataset Generation\n• Model Training\n• Image Prediction\n\n© 2026 MediScan AI. All rights reserved.',
    buttons: ['OK'],
  });
}

// ============================================
// IPC Handlers
// ============================================
function setupIPC() {
  // File operations
  ipcMain.handle('open-file-dialog', async () => {
    await handleFileOpen();
  });

  ipcMain.handle('open-folder-dialog', async () => {
    await handleFolderOpen();
  });

  ipcMain.handle('save-dialog', async (_, defaultName) => {
    if (!mainWindow) return null;
    const result = await dialog.showSaveDialog(mainWindow, {
      title: 'Save File',
      defaultPath: defaultName || 'export',
    });
    return result.canceled ? null : result.filePath;
  });

  // Read file from disk (for image preview)
  ipcMain.handle('read-file', async (_, filePath) => {
    try {
      const data = fs.readFileSync(filePath);
      const ext = path.extname(filePath).toLowerCase();
      const mimeMap = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.dcm': 'application/dicom',
      };
      const mime = mimeMap[ext] || 'application/octet-stream';
      return { data: data.toString('base64'), mime, name: path.basename(filePath) };
    } catch (err) {
      return { error: err.message };
    }
  });

  // App info
  ipcMain.handle('get-app-info', () => ({
    version: app.getVersion(),
    name: app.getName(),
    platform: process.platform,
    arch: process.arch,
  }));

  // Window controls
  ipcMain.on('minimize-window', () => mainWindow?.minimize());
  ipcMain.on('maximize-window', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });
  ipcMain.on('close-window', () => mainWindow?.close());

  // Python bridge — run YOHO scripts
  ipcMain.handle('run-python', async (_, scriptName, args = []) => {
    const backendDir = path.join(__dirname, 'backend', 'YOHO-main');
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    return new Promise((resolve) => {
      const proc = spawn(pythonCmd, [scriptName, ...args], {
        cwd: backendDir,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => {
        const text = data.toString();
        stdout += text;
        // Forward progress to renderer
        if (mainWindow) {
          mainWindow.webContents.send('python-output', { type: 'stdout', text });
        }
      });

      proc.stderr.on('data', (data) => {
        const text = data.toString();
        stderr += text;
        if (mainWindow) {
          mainWindow.webContents.send('python-output', { type: 'stderr', text });
        }
      });

      proc.on('close', (code) => {
        resolve({ code, stdout, stderr });
      });

      proc.on('error', (err) => {
        resolve({ code: -1, stdout, stderr: err.message });
      });
    });
  });
}

// ============================================
// App Lifecycle
// ============================================
app.whenReady().then(() => {
  buildAppMenu();
  setupIPC();
  createMainWindow();

  app.on('activate', () => {
    // macOS: re-create window when dock icon clicked
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Security: deny webview creation
app.on('web-contents-created', (_, contents) => {
  contents.on('will-attach-webview', (e) => {
    e.preventDefault();
  });
});