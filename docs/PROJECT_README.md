# YOHO (You Only Have One)

**Single-Image-Based Deep Learning for Segmentation of Early Esophageal Cancer Lesions**

[![arXiv](https://img.shields.io/badge/arXiv-2306.05912-b31b1b.svg)](https://arxiv.org/abs/2306.05912)
[![GitHub](https://img.shields.io/badge/GitHub-lhaippp/YOHO-green.svg)](https://github.com/lhaippp/YOHO)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. 项目简介

YOHO 是一种基于**单张图像**的早期食管癌（EEC）病变分割深度学习方法。其核心思想是 **"一图一网络"（You Only Have One）**——仅用患者的一张内镜图像，通过交互式采样 → 合成训练集 → 训练 UNet → 预测，实现病变分割。

### 核心创新

- **单图像学习**：整个训练集从一张图合成，保护患者隐私，避免泛化问题
- **边缘感知架构**：UNet 同时输出分割掩码 + 多尺度边缘预测 + Laplacian 边界精炼
- **合成数据生成**：通过多尺度几何变换（仿射、旋转、缩放）从单次标注生成 1600 张训练样本
- **组合损失函数**：BCE + Dice + 边缘损失 + 边界一致性损失

### 论文

```bibtex
@misc{li2023singleimagebased,
      title={Single-Image-Based Deep Learning for Segmentation of Early Esophageal Cancer Lesions},
      author={Haipeng Li and Dingrui Liu and Yu Zeng and Shuaicheng Liu and Tao Gan and Nini Rao and Jinlin Yang and Bing Zeng},
      year={2023},
      eprint={2306.05912},
      archivePrefix={arXiv},
      primaryClass={eess.IV}
}
```

- GitHub: [https://github.com/lhaippp/YOHO](https://github.com/lhaippp/YOHO)
- 论文: [https://arxiv.org/abs/2306.05912](https://arxiv.org/abs/2306.05912)
- EEC-2022 测试集: [Google Drive](https://drive.google.com/file/d/1NeuGRLbicY2awAUW44uQl6BMu8S5feVy/view?usp=sharing) (MIT License)

---

## 2. 完整目录结构

```
YOHO/                                  ← 项目根目录
│
├── YOHO-main/                         ★ 核心代码
│   ├── Python 脚本
│   │   ├── Start.py                   端到端流水线（批处理）
│   │   ├── interaction7_record_sample_3.0.py  交互式采样（人工步骤）
│   │   ├── recreate_sample_3.0.py     合成训练集生成 ★
│   │   ├── voc_annotation_medical.py  数据集索引生成
│   │   ├── train_medical.py           训练脚本
│   │   ├── predict.py                 预测脚本
│   │   └── unet.py                    UNet 预测封装类
│   │
│   ├── nets/                          网络模块
│   │   ├── unet.py                    核心 UNet 模型（分割 + 边缘 + 边界）
│   │   ├── unet_training.py           损失函数
│   │   ├── resnet34.py                ResNet-34 主干（默认）
│   │   ├── resnet.py                  ResNet-50 主干（可选）
│   │   ├── resnet101_frn.py           ResNet-101 + FRN（可选）
│   │   └── vgg.py                     VGG-16 主干（可选）
│   │
│   ├── utils/                         工具模块
│   │   ├── dataloader_medical.py      数据集加载
│   │   ├── utils_fit.py               训练循环（组合损失）
│   │   ├── utils_metrics.py           评估指标（mIoU, F-score）
│   │   ├── utils.py                   图像预处理
│   │   └── callbacks.py               Loss 曲线记录
│   │
│   ├── model_data/
│   │   └── resnet34-333f7ec4.pth      ResNet-34 预训练权重（必要）
│   │
│   ├── img/                           输入图像目录
│   ├── Medical_Datasets/              训练集（运行自动生成）
│   ├── logs/                          训练权重和 Loss 记录
│   ├── seg/                           中间合成数据
│   ├── results/                       预测结果
│   └── img_out/                       预测结果
│
├── Dataset/EEC/
│   └── EEC_test_dataset_label/        ROI 掩膜（recreate 读取）
│
├── EEC_save_sample_13.0/              交互采样 PKL 数据（recreate 读取）
│   ├── 1/
│   ├── 5/
│   ├── 7/
│   └── dummy/
│
└── EEC/                               测试数据集
    ├── test/                          测试集原图
    └── test mask/                     测试集真值标签
```

---

## 3. 完整工作流程

整个流水线从一张内镜图像出发，最终得到病变分割结果，分为 5 个阶段：

### 阶段 1：ROI 绘制（人工）

使用 **labelme**（v3.16.7）在图像上绘制 ROI 多边形，保存到 `Dataset/EEC/EEC_test_dataset_label/`。

- 如果病灶面积 < 50-60%：ROI 圈住**病灶区域**
- 如果病灶面积 > 60%：ROI 圈住**正常组织**区域（预测时会取补）

ROI 只是粗略的范围约束，不需要精细勾勒边缘。

### 阶段 2：交互式采样（人工）

运行 `interaction7_record_sample_3.0.py`，打开 OpenCV 图形界面：

1. 左键点击放置**圆形**采样点，调整半径
2. 支持**三角形**采样（直角三角和正交三角）
3. SLIC 超像素（`region_size=48`）辅助定位
4. 先采**前景**（病灶），按 `q` 结束后采**背景**（正常组织）
5. 每保存一个采样点，自动生成多尺度 patches

输出 8 个 PKL 文件到 `EEC_save_sample_13.0/{图像名}/`：

| 文件 | 内容 |
|------|------|
| `cent.pkl` | 超像素聚类中心坐标 |
| `ind.pkl` | 圆形采样索引（尺度/数量） |
| `tind.pkl` | 三角形采样索引 |
| `cnd.pkl` | 圆形中心点坐标列表 |
| `tcnd.pkl` | 三角形中心点坐标列表 |
| `sp.pkl` | 图像形状 (H, W, C) |
| `trnum.pkl` | 前景采样点数量 |
| `rnd.pkl` | 第一尺度颜色映射 |

### 阶段 3：合成训练集生成（自动）

运行 `recreate_sample_3.0.py --png_name {name}`，核心代码在 `Label` 类中：

1. **加载 PKL 采样数据**
2. **生成合成样本**（`creat()` 方法）：
   - 随机选择采样点、尺度和类型（圆/三角）
   - 施加仿射变换（平移、旋转 0-360°、缩放）
   - 通过 `local_()` + `Cal_area_circle()` 检测重叠，重叠则重试
   - 每张图放置 `max(8, len(cind))` 个 patch
3. **两阶段生成**：共 `400 × 4 - 1 = 1599` 张合成图 + 1 张原图 = **1600** 张
4. **图像合成**（`comb()`）：将 patches 融合回原图背景
5. **生成标签**（`creat_seg()`）：分割标签 + 边缘标签，结合 ROI 约束

输出：
```
Medical_Datasets/
├── Images/       ← 1600 张合成图 (.jpg)
├── Labels/       ← 1600 张分割标签 (.png)
└── edges/        ← 1600 张边缘标签 (.png)
```

### 阶段 4：训练（自动）

运行 `train_medical.py --png_name {name}`。

**模型架构**（[nets/unet.py](nets/unet.py)）：

```
输入图像 (256×256)
    │
    ├─ ResNet34 编码器 → 5 层多尺度特征
    │
    ├─ 解码器路径 (up_concat4 → 3 → 2 → 1)
    │   └─ up_conv + final Conv → 输出①：分割掩码
    │
    ├─ 多尺度边缘分支 (5 个尺度 → Combine 融合)
    │   └─ 输出②：边缘预测
    │
    └─ Laplacian 边界精炼 (convlp → convu → convf → convd)
        └─ 输出③：精炼边界
```

**训练配置**：

| 参数 | 冻结阶段 | 解冻阶段 |
|------|---------|---------|
| 轮次 | 0-19 (20轮) | 20-29 (10轮) |
| 学习率 | 1e-3 | 3e-5 |
| 批大小 | 32 | 32 |
| 训练参数 | 仅解码器 | 全部网络 |
| 调度器 | StepLR (γ=0.96) | StepLR (γ=0.96) |

**组合损失**（[utils/utils_fit.py](utils/utils_fit.py)）：
```
loss = 0.8 × BCE_Loss(分割, 标签)     # 类别平衡交叉熵
     + 0.2 × Dice_Loss(分割, 标签)     # Dice 系数
     + BCE_Loss(边缘预测, 边缘标签)     # 边缘监督
     + 0.2 × CBL_Loss(边界, 预测)       # Laplacian 边界一致性
```

权重保存：`logs/EEC-{png_name}-ep030.pth`

### 阶段 5：预测（自动）

运行 `predict.py --png_name {name}`，调用 [unet.py](unet.py) 中的 `Unet` 封装类：

1. **加载模型**：读取 `logs/EEC-{png_name}-ep030.pth`
2. **预处理**：letterbox 缩放至 256×256，归一化 [0,1]
3. **推理**：模型返回 `(final, feat_out_sp, boundary)`
4. **后处理**：
   - sigmoid → 阈值 0.5 二值化
   - 特殊处理：硬编码的 32 张图像取补（`pr = 1 - pr`）
   - 裁剪 padding，恢复到原图尺寸
5. **轮廓绘制**：OpenCV 查找轮廓 → `approxPolyDP` 简化 → 绘制半透明红色边线
6. **保存**：`results/{name}.png` + `img_out/{name}.png`

### 端到端批处理

运行 `Start.py` 自动遍历 `./img/` 下所有图像：

```bash
python Start.py
```

等价于对每张图依次执行：

```bash
python recreate_sample_3.0.py --png_name {name}
python voc_annotation_medical.py
python train_medical.py --png_name {name}
python predict.py --png_name {name}
```

---

## 4. 使用指南

### 环境依赖

| 包 | 用途 |
|---|------|
| `torch` | 深度学习框架 |
| `torchvision` | 预训练权重 |
| `numpy` | 数值计算 |
| `opencv-python` | 图像处理、SLIC、轮廓 |
| `Pillow` | 图像读写 |
| `matplotlib` | Loss/指标绘图 |
| `tqdm` | 进度条 |
| `scipy` | Savitzky-Golay 平滑 |

安装：

```bash
pip install torch torchvision numpy opencv-python pillow matplotlib tqdm scipy
```

### 对新图像的完整操作步骤

1. **准备 ROI 掩膜**
   ```bash
   # 安装 labelme
   pip install labelme
   labelme  # 打开 GUI，在病灶区域画多边形，保存为 {图像名}.png
   ```
   将 ROI 放到 `Dataset/EEC/EEC_test_dataset_label/{图像名}.png`

2. **放入输入图像**
   将内镜图放到 `YOHO-main/img/{图像名}.png`

3. **交互式采样**
   ```bash
   cd YOHO-main
   python interaction7_record_sample_3.0.py
   ```
   按提示在图像上画圆/三角标记病灶和背景。

4. **或直接运行端到端流水线**
   ```bash
   cd YOHO-main
   python Start.py
   ```

### 基于已有采样数据（dummy 示例）

如果你只是想测试代码能否跑通：

```bash
cd YOHO-main
python recreate_sample_3.0.py --png_name dummy
python voc_annotation_medical.py
python train_medical.py --png_name dummy
python predict.py --png_name dummy
```

---

## 5. 关键设计细节

### 5.1 ROI 取补逻辑

在 [unet.py:229-233](unet.py) 中，对以下 32 张图像取补：

```
6, 7, 21, 22, 23, 24, 26, 27, 45, 46, 47, 48, 49, 50, 55,
74, 76, 77, 107, 108, 112, 113, 114, 115, 121, 127, 133,
134, 135, 136, 137, 138
```

原因是这些图的病灶面积 > 60%，ROI 画在正常组织上，需要用 `pr = 1 - pr` 得到正确的病灶分割。

### 5.2 合成数据生成参数

在 [recreate_sample_3.0.py:18](recreate_sample_3.0.py)：

```python
number = 400  # 控制生成数量：number × 4 - 1 = 1599 张
```

### 5.3 训练超参数

在 [train_medical.py](train_medical.py)：

| 变量 | 值 | 说明 |
|------|-----|------|
| `input_shape` | [256, 256] | 输入分辨率 |
| `num_classes` | 2 | 背景 + 前景 |
| `backbone` | resnet34 | 主干网络 |
| `Freeze_Epoch` | 20 | 冻结阶段轮次 |
| `UnFreeze_Epoch` | 30 | 总轮次 |
| `Freeze_lr` | 1e-3 | 冻结阶段学习率 |
| `Unfreeze_lr` | 3e-5 | 解冻阶段学习率 |
| `comb_edge` | True | 启用边缘损失 |

### 5.4 类别平衡 BCE

在 [nets/unet_training.py](nets/unet_training.py) 的 `BCE_Loss()` 中：

- 背景权重 = `fg / (bg + fg) × 1.1`
- 前景权重 = `bg / (bg + fg)`

### 5.5 边缘预测 Combine 模块

在 [nets/unet.py:206-222](nets/unet.py) 中，`Combine` 类使用 **softmax 注意力机制**融合 5 个尺度的边缘预测，自动学习每个空间位置应该信任哪个尺度。

---

## 6. 常见问题

### Q：没有 ROI 掩膜怎么办？
A：ROI 需要手动用 labelme 绘制。如果只是想跑通流程，可以用已有的 `dummy.png` 和配套采样数据。

### Q：训练时显存不足？
A：可以减小 `Freeze_batch_size` 和 `Unfreeze_batch_size`，或减小 `input_shape`。

### Q：如何在自己的数据集上使用？
A：除了 EEC 食管癌数据，YOHO 的"一图一网络"思想可用于任何医学图像分割场景。需要：① ROI 掩膜 ② 交互采样 ③ 运行流水线。

### Q：预测结果不理想？
A：可以尝试：① 增加 `number`（生成更多合成数据） ② 增加训练轮次 ③ 调整损失权重 ④ 确保交互采样覆盖了病变的多样性。

### Q：代码中 `Seg/` 和 `seg/` 有什么区别？
A：`Seg/`（根目录，大写 S）是旧版交互工具的输出目录，`seg/`（YOHO-main 内，小写 s）是当前 `recreate_sample_3.0.py` 的中间输出目录。

---

## 7. 许可证

MIT License - 详见 [LICENSE](LICENSE)
