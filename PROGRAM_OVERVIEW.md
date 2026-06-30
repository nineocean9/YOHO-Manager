# YOHO-Manager 程序说明文档

## 1. 项目概述

**YOHO-Manager** 是一个基于 Electron 的桌面医疗影像 AI 平台，集成了 YOHO（You Only Have One）食管早癌分割系统。它将"图片驱动"流程改造为"患者驱动"流程，让软件具备临床实用能力。

- **前端**：Electron + 原生 HTML/CSS/JS（单文件 `renderer/index.html`，4779 行）
- **后端**：Python + PyTorch（YOHO-main 目录）
- **设计风格**：Soft UI Evolution × Healthcare 青蓝配色
- **仓库**：https://github.com/nineocean9/YOHO-Manager

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 桌面壳 | Electron 33 |
| 前端 | 原生 HTML/CSS/JS，无框架 |
| 字体 | Figtree（标题）+ Noto Sans（正文） |
| IPC 桥 | contextBridge + preload.js |
| 后端 | Python 3.8 + PyTorch + OpenCV |
| 数据存储 | localStorage（前端）+ 文件系统（后端） |

## 3. 目录结构

```
F:\YOHO-Manager\
├── main.js                    Electron 主进程
├── preload.js                 IPC 安全桥接
├── package.json               打包配置
├── assets/                    图标资源
├── renderer/
│   └── index.html             单文件前端（HTML+CSS+JS）
├── backend/
│   └── YOHO-main/             Python 后端
│       ├── app.py             原始 Tkinter GUI（未用）
│       ├── pipeline.py        管道编排
│       ├── interaction7_record_sample_3.0.py  交互采样（带 CLI）
│       ├── recreate_sample_3.0.py             合成数据集生成
│       ├── train_medical.py                   模型训练
│       ├── predict.py                         预测
│       ├── unet.py                            UNet 模型
│       ├── save_sampling.py                   采样数据保存
│       ├── config.json                        训练参数
│       ├── nets/                              网络结构
│       ├── utils/                             工具函数
│       ├── img/                               原始图像
│       ├── img_out/                           预测结果
│       ├── logs/                              模型权重
│       ├── Medical_Datasets/                  合成训练集
│       └── Dataset/EEC/                       ROI mask
└── EEC_save_sample_13.0/                      采样 PKL 数据
```

## 4. 前端架构（renderer/index.html）

### 4.1 设计系统
- **配色**：主色 `#0891B2` 青蓝，强调色 `#059669` 翠绿，背景 `#ECFEFF`
- **阴影**：带主色调的多层柔和阴影（非纯黑）
- **圆角**：8–24px 分层
- **动画**：150–300ms cubic-bezier，尊重 `prefers-reduced-motion`
- **图标**：纯 SVG 内联，2px 描边，无 Emoji
- **无障碍**：WCAG AA+，ARIA 标签，键盘导航

### 4.2 页面布局

```
┌────────────────────────────────────────────┐
│  Header（Logo + 设置 + 窗口控制）           │
├──────────┬─────────────────────────────────┤
│ Sidebar  │  Content Area                   │
│ 患者列表  │  Dashboard / 工作流模块          │
│ 工作流    │                                 │
└──────────┴─────────────────────────────────┘
```

### 4.3 核心模块

| 模块 | 说明 |
|------|------|
| **Dashboard** | 患者信息横幅、图像网格、Before/After 对比、报告 |
| **ROI 标注** | 全宽 Canvas 多边形绘制，缩放、平滑、保存 mask |
| **交互式标注** | Canvas 圆形采样点放置，反转 ROI 开关 |
| **数据集生成** | 调用 Python 生成合成训练集，进度条 |
| **模型训练** | 调用 Python 训练，双进度条（epoch + batch） |
| **预测** | 调用 Python 预测，返回 Dashboard 显示结果 |
| **设置** | 数据集生成数量、导出格式、GPU、暗色模式 |

### 4.4 数据流

```
用户操作 → PatientManager（业务逻辑）
        → StorageAdapter（数据层，localStorage）
        → renderDashboard()（UI 渲染）

工作流按钮 → runPythonScript() → IPC → main.js spawn
          → Python 脚本 → stdout/stderr → 进度条
```

### 4.5 关键对象

- **`StorageAdapter`**：localStorage CRUD（患者、检查、图像）
- **`PatientManager`**：业务逻辑（选中、工作流模式、完成预测）
- **`roiState` / `labelingState`**：Canvas 绘制状态
- **`runPythonScript()`**：Python 后端桥接

## 5. 后端架构（YOHO-main）

### 5.1 YOHO 工作流

```
原始图像 → ROI标注 → 交互采样 → 合成1600张 → 训练UNet → 预测分割
  (1张)    (mask)   (PKL)    (数据集)     (30 epoch)  (结果图)
```

### 5.2 Python 脚本

| 脚本 | CLI 参数 | 输入 | 输出 |
|------|---------|------|------|
| `interaction7_record_sample_3.0.py` | `--coords --name --img-path` | 采样坐标 | 8 PKL + nms/source 图 |
| `recreate_sample_3.0.py` | `--png_name --sample_count` | ROI + PKL | Medical_Datasets/ |
| `voc_annotation_medical.py` | 无 | 数据集 Labels | train/val/test txt |
| `train_medical.py` | `--png_name` | 数据集 | logs/*.pth |
| `predict.py` | `--png_name` | 图像 + 权重 | img_out/*.png |

## 6. 数据存储

| 数据 | 存储位置 |
|------|---------|
| 患者档案 | localStorage `yoho-patient-db` |
| ROI 多边形点 | localStorage + mask PNG 写入磁盘 |
| 采样点坐标 | localStorage + PKL 写入磁盘 |
| 训练数据集 | `Medical_Datasets/` |
| 模型权重 | `logs/EEC-*-ep*.pth` |
| 预测结果 | `img_out/` |

## 7. 工作流模式

软件有两种模式：
- **Dashboard 模式**：左侧显示患者列表，右侧显示患者信息和图像
- **工作流模式**：选中图像点"开始处理"后，左侧切换为 ROI/标注/数据集/训练/预测导航

预测完成后自动返回 Dashboard，显示 Before/After 对比。

## 8. 已知限制

- Python 依赖无法打包进 exe（PyTorch 2GB+）
- 需用户自行安装 Python + 依赖
- 路径含中文时 `cv2.imwrite` 失败（已移至 F 盘规避）
- localStorage 容量有限（约 5-10MB）

## 9. 验证方式

1. `npm start` 启动 Electron 应用
2. 或 `npx live-server renderer --port=1530` 浏览器预览
3. 检查患者列表、图像网格、ROI 标注、训练、预测全流程