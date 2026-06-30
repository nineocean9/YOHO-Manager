# YOHO-Manager 优化建议（待评估，未执行）

## 架构层面

### 1. 拆分 index.html
当前 `renderer/index.html` 是 4779 行单文件，HTML/CSS/JS 全塞一起，维护困难。
建议拆分：
- `index.html` — 纯结构
- `styles/` — CSS 拆成 `tokens.css` / `components.css` / `layout.css`
- `scripts/` — JS 拆成 `app.js` / `patient.js` / `roi.js` / `labeling.js` / `backend.js`

### 2. 数据层抽象
`StorageAdapter` 直接操作 localStorage。建议抽象为接口，方便后续接 MySQL/后端 API：
```js
const StorageAdapter = {
  getPatients(), addPatient(data), updatePatient(id, data), deletePatient(id)...
};
// 当前: LocalStorageAdapter
// 未来: MySQLAdapter 实现同一接口
```

### 3. 状态管理
`roiState` / `labelingState` / `PatientManager._xxx` 散落各处。建议用一个简单的状态机或集中 store，避免全局变量污染。

### 4. Python 依赖检测
启动时检测 Python/PyTorch 是否安装。缺失则禁用后端相关按钮（训练、预测、数据集生成），并提示用户安装。避免点了按钮才报错。

## 用户体验

### 5. 加载状态
Python 脚本运行时按钮应显示 loading 并禁用，防止重复点击。当前只有训练按钮做了，数据集生成/预测也应该做。

### 6. 错误处理
`runPythonScript` 失败时只弹 toast（截断的错误信息）。建议加一个**错误日志面板**，显示完整 stderr，方便排查 Python 报错。

### 7. 自动保存草稿
ROI/采样标注过程中自动保存草稿到 localStorage，防止崩溃或误关闭丢失进度。

### 8. 快捷键统一
当前 ROI/标注用 **右键撤销**。建议统一改成 **Ctrl+Z 撤销**（更通用），右键改为弹出右键菜单（删除、清除等）。

### 9. 图片预加载
图像网格加载大图时加骨架屏或缩略图占位，避免空白闪烁。

## 后端

### 10. PyInstaller 打包
把 Python 脚本编译成独立 exe，用户无需安装 Python。结合 `extraResources` 打包进 Electron 安装包。

### 11. 进度协议统一
所有 Python 脚本用统一格式输出进度，例如：
```
PROGRESS:{"step":"dataset","current":120,"total":1400,"msg":"生成中"}
```
JSON 格式比现在的 `PROGRESS:current/total` 更易扩展。

### 12. 配置同步
`config.json` 和前端设置当前是两套。建议双向同步：前端改设置 → 写入 config.json；Python 读 config.json。避免参数不一致。

### 13. 模型按患者归档（复查复用）
**场景**：同一患者复查时，可选择用他以前训练的模型预测新图，不跨患者复用。

**当前问题**：`predict.py` 写死用 `EEC-{png_name}-ep030.pth`，新图只能用自己训练的权重。

**改进方案**：
```
张三（患者）
├── 检查1 (2026-06-01) 图A → 训练出 model_张三_001 (ep30, acc 95%)
├── 检查2 (2026-08-15) 图B（复查）
│   ├── 选项1: 用 model_张三_001 预测（复用旧模型）
│   └── 选项2: 重新训练 → model_张三_002
```
- 模型权重存 `patients/{patient_id}/models/model_001/weight.pth` + `meta.json`
- 预测时下拉框只显示**当前患者的历史模型**
- 不显示其他患者的模型

## 数据存储方案（MySQL + 文件系统）

### 文件夹结构（UUID 规避中文）
```
data/
├── patients/
│   ├── p_1703a2b/                    ← UUID，无中文问题
│   │   ├── meta.json                 ← 患者信息（姓名存 MySQL）
│   │   ├── check_20260630_1/         ← 日期+序号，复查按时间排序
│   │   │   ├── original/             原始内镜图像
│   │   │   ├── roi/                  ROI mask + 多边形点 JSON
│   │   │   ├── sampling/             采样点 + PKL 数据
│   │   │   ├── dataset/              合成训练集（可选，体积大）
│   │   │   ├── model/                该图像训练的模型权重
│   │   │   └── prediction/           预测结果 + analysis.json
│   │   ├── models/                   ← 患者级模型归档（第13点）
│   │   │   ├── model_001/
│   │   │   └── model_002/
│   │   └── check_20260715_2/         ← 复查
│   └── p_9f3c1d/
└── datasets/                         ← 大体积合成数据集（可选单独管理）
```

### MySQL 表设计
```sql
patients(id PK, name, gender, age, admission_id, history,
         status, folder_id, created_at)

checks(id PK, patient_id FK, check_date, scope_type,
       doctor, folder_name)

images(id PK, check_id FK, filename, original_path,
       status, roi_path, roi_points_json, sample_pkl_path,
       model_path, prediction_path, lesion_area,
       confidence, reviewed)

models(id PK, patient_id FK, name, weight_path,
       epoch, accuracy, trained_from_image_id, created_at)

settings(key PK, value)
```
文件路径存**相对路径**，程序启动时拼绝对路径。

### 大体积数据策略
- 模型权重（`.pth`）+ 最终结果必存（小）
- 合成训练集（1600张/几百MB）：训练完可选清理，或单独放 `datasets/` 顶级目录

### 迁移方案
1. 加 `BackendAdapter` 接口，`LocalStorageAdapter` 和 `MySQLAdapter` 都实现它
2. 启动检测 MySQL 可用性，可用用 MySQL，否则降级 localStorage
3. 提供"localStorage → MySQL"一键迁移按钮