# index.html 模块索引

## HTML 结构

| 区域 | 行号 | 说明 |
|------|------|------|
| CSS Design Tokens | 13-1230 | :root 变量、组件样式、布局 |
| Header | 1931-1962 | Logo、设置按钮、窗口控制 |
| Sidebar | 1967-2045 | 患者列表 + 工作流导航 |
| Dashboard 模块 | 2051-2177 | 患者信息横幅、图片网格、Before/After、报告 |
| Upload 模块 | 2180-2217 | 图片拖拽上传 + 预览（冗余，考虑移除） |
| ROI 标注模块 | 2221-2279 | 全宽 Canvas 工作区 |
| 交互式标注模块 | 2281-2319 | 全宽 Canvas 工作区 |
| 数据集生成模块 | 2321-2361 | 数据集生成、索引、导出 |
| 模型训练模块 | 2363-2420 | 训练面板、进度条、模型选择 |
| 预测模块 | 2422-2456 | 预测面板、模型选择 |
| 设置 Modal | 2461-2535 | 设置弹窗 |
| 患者 Modal | 2537-2588 | 新建/编辑患者弹窗 |
| Toast 容器 | 2590-2592 | 通知提示容器 |

## JavaScript 函数索引

### 初始化 (2594-2605)
| 函数 | 行号 | 说明 |
|------|------|------|
| `isElectron` | 2597 | Electron 运行时检测 |

### ROI Canvas 绘制 (2607-2996)
| 函数 | 行号 | 说明 |
|------|------|------|
| `roiState` | 2610-2627 | ROI 状态对象（points, scale, zoom 等） |
| `roiToggleReverse()` | 2629 | 反转 ROI 开关 |
| `roiInitCanvas(image)` | 2634 | 初始化 ROI Canvas，加载历史 ROI |
| `roiRecalcLayout()` | 2679 | 重新计算 Canvas 布局/缩放 |
| `roiZoom(delta)` | 2699 | 缩放 ±20% |
| `roiRedraw()` | 2710 | 绘制 Canvas（图像 + 多边形 + 预览线） |
| `roiHandleMouseMove(e)` | 2793 | 鼠标移动（预览线） |
| `roiHandleMouseLeave()` | 2802 | 鼠标离开 Canvas |
| `roiCanvasToImage()` | 2808 | Canvas 坐标 → 图像坐标 |
| `roiIsInsideImage()` | 2815 | 检查坐标是否在图像内 |
| `roiHandleCanvasClick(e)` | 2822 | 点击添加多边形顶点/闭合 |
| `roiHandleContextMenu(e)` | 2852 | 右键撤销 |
| `roiUndo()` | 2857 | 撤销最后一个点 |
| `roiClear()` | 2866 | 清除所有点 |
| `roiSmooth()` | 2874 | Savitzky-Golay 平滑轮廓 |
| `updateRoiButtons()` | 2898 | 更新按钮状态（禁用/启用） |
| `updateRoiHint()` | 2907 | 更新底部提示文字 |
| `saveRoiAndNext()` | 2923 | **保存 ROI mask PNG + 数据 → 进入标注** |

### 交互式标注 Canvas (2996-3385)
| 函数 | 行号 | 说明 |
|------|------|------|
| `labelingState` | 2999-3030 | 标注状态对象 |
| `labelingToggleReverse()` | 3032 | 反转开关 |
| `labelingZoom(delta)` | 3038 | 缩放 |
| `labelingRecalcLayout()` | 3045 | 布局计算 |
| `labelingRedraw()` | 3063 | 绘制（图像 + ROI 叠加 + 采样圈） |
| `labelingHandleCanvasClick(e)` | 3128 | 放置采样圈 |
| `labelingHandleContextMenu(e)` | 3168 | 右键撤销 |
| `labelingHandleMouseMove(e)` | 3181 | 鼠标移动 |
| `labelingHandleMouseUp()` | 3199 | 结束拖动 |
| `labelingUndo()` | 3210 | 撤销 |
| `labelingClear()` | 3222 | 清除所有 |
| `labelingFinishPhase()` | 3230 | 完成采样 → 进入数据集生成 |
| `updateLabelingButtons()` | 3257 | 更新按钮状态 |
| `updateLabelingHint()` | 3264 | 更新提示 |
| `labelingLoadImage(path)` | 3343 | 加载图像 + ROI 叠加 + 历史采样 |

### 调试工具 (3264-3385)
| 函数 | 行号 | 说明 |
|------|------|------|
| `roiUpdateDebug()` | 3281 | 更新 ROI 调试信息 |
| `labelingUpdateDebug()` | 3295 | 更新标注调试信息 |
| `roiToggleDebug()` | 3313 | 切换 ROI 调试栏 |
| `labelingToggleDebug()` | 3319 | 切换标注调试栏 |
| `patchRedraw()` | 3326 | 自动更新调试信息在重绘时 |

### 模块切换 (3392-3433)
| 函数 | 行号 | 说明 |
|------|------|------|
| `switchModule(moduleName)` | 3392 | 切换模块 + 加载工作区图片 |
| `open设置Panel()` | 3431 | 打开设置弹窗 |

### Hash 路由 + IPC (3435-3530)
| 函数 | 行号 | 说明 |
|------|------|------|
| `handleHashChange()` | 3438 | hash 路由处理 |
| `initModule()` | 3469 | 初始化模块（默认 Dashboard） |
| Electron IPC 事件 | 3534 | files-opened, navigate, action 等 |

### 上传 (3537-3676)
| 函数 | 行号 | 说明 |
|------|------|------|
| `upload图像数()` | 3537 | 文件选择 |
| `processFiles()` | 3573 | 处理拖拽文件 |
| `addUploadPreviews()` | 3586 | 添加上传预览 |
| `renderPreviews()` | 3608 | 渲染预览缩略图 |

### Toast / Modal (3678-3724)
| 函数 | 行号 | 说明 |
|------|------|------|
| `showToast(message, type)` | 3681 | 通知提示 |
| `openModal(id)` | 3705 | 打开 Modal |
| `closeModal(id)` | 3710 | 关闭 Modal |

### Python 后端桥接 (3726-3759)
| 函数 | 行号 | 说明 |
|------|------|------|
| `getCurrentPngName()` | 3729 | 获取当前图像名 |
| `onPythonOutput(callback)` | 3737 | 监听 Python stdout |
| `runPythonScript(scriptName, args)` | 3746 | 运行 Python 脚本 |

### 训练 / 预测 / 数据集 (3761-3885)
| 函数 | 行号 | 说明 |
|------|------|------|
| `startTraining()` | 3764 | 开始训练（调用 train_medical.py） |
| `runPrediction()` | 3816 | 运行预测（调用 predict.py） |
| `generateDataset()` | 3861 | 生成数据集（调用 recreate_sample_3.0.py） |

### StorageAdapter — 数据层 (3887-3990)
| 方法 | 说明 |
|------|------|
| `get/setData()` | localStorage 读写 |
| `getPatients()` | 获取所有患者 |
| `getPatient(id)` | 获取单个患者 |
| `addPatient(data)` | 新增患者 |
| `addCheck(patientId, data)` | 新增检查记录 |
| `addImages(patientId, checkId, names)` | 批量添加图像 |
| `updateImage(patientId, checkId, imageId, data)` | 更新图像状态 |
| `updatePatient(patientId, data)` | 更新患者状态 |
| `reset()` | 重新加载数据 |
| `_load()/_save()` | localStorage 底层读写 |

### PatientManager — 业务逻辑 (3994-4101)
| 方法 | 行号 | 说明 |
|------|------|------|
| `getSelectedPatient/Image()` | — | 获取选中患者/图像 |
| `selectPatient(id)` | 4059 | 选中患者 → 渲染 Dashboard |
| `selectImage(imageId)` | 4068 | 选中图像 |
| `startWorkflow()` | 4072 | 进入工作流模式 |
| `exitWorkflow()` | 4083 | 退出工作流 → 返回 Dashboard |
| `completePrediction(imageId, result)` | 4089 | 完成预测 → 更新数据 → 退出工作流 |
| `updateImageStatus(imageId, status)` | — | 更新图像状态 |

### 渲染函数 (4103-4282)
| 函数 | 行号 | 说明 |
|------|------|------|
| `renderPatientList()` | 4106 | 渲染侧边栏患者列表 |
| `renderDashboard()` | 4138 | 渲染 Dashboard（横幅 + 图片网格 + 对比 + 报告） |
| `renderReport(patient)` | 4252 | 渲染患者报告表格 |
| `updateDashboardStats()` | 4283 | 更新统计数字 |

### 患者 CRUD (4300-4371)
| 函数 | 行号 | 说明 |
|------|------|------|
| `openPatientModal()` | 4300 | 打开新建患者弹窗 |
| `savePatient()` | 4304 | 保存患者数据 |
| `editPatient()` | 4330 | 编辑患者 |
| `add图像数ToPatient()` | 4337 | 添加图像到当前患者 |
| `updatePatientStatusAfterAdd()` | 4364 | 添加后更新状态 |

### 工作流控制 (4373-4425)
| 函数 | 行号 | 说明 |
|------|------|------|
| `setWorkflowMode(enabled)` | 4376 | 切换侧边栏（患者列表 / 工作流） |
| `updateWorkflowBackBtn()` | 4400 | 显示/隐藏返回按钮 |
| `loadImageIntoWorkflow(image)` | 4409 | 加载图像到工作流 Canvas |
| `startWorkflow()` | 4419 | 调用 PatientManager.startWorkflow |
| `exitWorkflow()` | 4423 | 调用 PatientManager.exitWorkflow |

### 报告 / Demo 数据 (4427-4520)
| 函数 | 行号 | 说明 |
|------|------|------|
| `generateReport()` | 4430 | 生成报告（前端模拟） |
| `exportReport()` | 4435 | 导出报告（前端模拟） |
| `initDemoData()` | 4443 | 初始化 3 个示例患者 |

## Python 后端文件

| 文件 | 路径 | 说明 |
|------|------|------|
| `pipeline.py` | `backend/YOHO-main/pipeline.py` | 管道编排（run_roi_prep, run_dataset, run_train, run_predict） |
| `recreate_sample_3.0.py` | `backend/YOHO-main/recreate_sample_3.0.py` | 合成数据集生成 |
| `train_medical.py` | `backend/YOHO-main/train_medical.py` | 两阶段模型训练 |
| `predict.py` | `backend/YOHO-main/predict.py` | 预测入口（调用 unet.py） |
| `unet.py` | `backend/YOHO-main/unet.py` | UNet 模型包装类 |
| `voc_annotation_medical.py` | `backend/YOHO-main/voc_annotation_medical.py` | 生成 train/val/test 索引 |
| `config.json` | `backend/YOHO-main/config.json` | 训练参数配置 |

## 数据目录

| 目录 | 用途 |
|------|------|
| `backend/YOHO-main/img/` | 原始内镜图像 |
| `backend/YOHO-main/img_out/` | 预测结果输出 |
| `backend/YOHO-main/Dataset/EEC/EEC_test_dataset_label/` | ROI mask PNG |
| `backend/YOHO-main/Medical_Datasets/Images/` | 合成训练图像 |
| `backend/YOHO-main/Medical_Datasets/Labels/` | 分割标签 |
| `backend/YOHO-main/Medical_Datasets/edges/` | 边缘标签 |
| `backend/YOHO-main/logs/` | 模型权重 (.pth) + 损失日志 |
| `backend/EEC_save_sample_13.0/` | 采样 PKL 数据 |