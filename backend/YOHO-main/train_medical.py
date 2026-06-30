import os

import numpy as np
import torch
import argparse  # 用于解析命令行参数
import torch.backends.cudnn as cudnn  # CUDA深度学习加速库
import torch.optim as optim  # 优化器
from torch.utils.data import DataLoader  # 数据加载器

from nets.unet import Unet  # 导入UNet模型
from nets.unet_training import weights_init  # 模型权重初始化
from utils.callbacks import LossHistory  # 损失记录工具
from utils.dataloader_medical import UnetDataset, unet_dataset_collate  # 医学数据集加载器
from utils.utils_fit import fit_one_epoch_no_val  # 单轮训练函数（无验证集）

# 创建命令行参数解析器
parser = argparse.ArgumentParser()
parser.add_argument("--png_name", default="dummy", help="输入图像名称")
args = parser.parse_args()

if __name__ == "__main__":
    # ---------------------- 基础配置 ----------------------
    # 是否使用CUDA加速
    Cuda = True

    # 分类类别数（背景+目标）
    num_classes = 2

    # 主干网络选择（ResNet34）
    backbone = "resnet34"

    # 是否使用预训练权重（此处使用主干网络预训练权重）
    # - 若model_path已设置则pretrained无效
    # - 若model_path未设置且pretrained=True：仅加载主干权重
    # - 若model_path未设置且pretrained=False：完全随机初始化
    pretrained = True

    # 模型权重路径（留空表示不加载完整模型）
    model_path = ""

    # 输入图像尺寸 [高度, 宽度]
    input_shape = [256, 256]

    # ---------------------- 训练阶段参数 ----------------------
    # 冻结阶段（只训练解码器）
    Init_Epoch = 0  # 起始训练轮次
    Freeze_Epoch = 20  # 冻结训练总轮次
    Freeze_batch_size = 32  # 冻结阶段批大小
    Freeze_lr = 1e-3  # 冻结阶段学习率

    # 解冻阶段（训练全部网络）
    UnFreeze_Epoch = 30  # 总训练轮次
    Unfreeze_batch_size = 32  # 解冻阶段批大小
    Unfreeze_lr = 3e-5  # 解冻阶段学习率

    # 数据集路径
    VOCdevkit_path = "Medical_Datasets"

    # 损失函数配置
    dice_loss = False  # 是否使用Dice损失
    focal_loss = False  # 是否使用Focal Loss
    cls_weights = np.array([1, 1], np.float32)  # 类别权重（背景和前景）

    # 训练策略
    Freeze_Train = True  # 是否先冻结训练再解冻
    num_workers = 2  # 数据加载线程数
    comb_edge = True  # 是否考虑边缘信息

    # 数据集名称（用于保存权重文件）
    dataset_name = "EEC"

    # ── 从 config.json 覆盖训练参数 ─────────────────────────────
    import json as _json
    try:
        with open("config.json") as _f:
            _tc = _json.load(_f).get("training", {})
            Freeze_Epoch = _tc.get("freeze_epochs", Freeze_Epoch)
            UnFreeze_Epoch = _tc.get("unfreeze_epochs", UnFreeze_Epoch)
            Freeze_batch_size = _tc.get("freeze_batch_size", Freeze_batch_size)
            Unfreeze_batch_size = _tc.get("unfreeze_batch_size", Unfreeze_batch_size)
            Freeze_lr = _tc.get("freeze_lr", Freeze_lr)
            Unfreeze_lr = _tc.get("unfreeze_lr", Unfreeze_lr)
    except Exception:
        pass

    # ---------------------- 模型初始化 ----------------------
    model = Unet(
        num_classes=num_classes,
        pretrained=pretrained,
        backbone=backbone
    ).train()  # 创建UNet模型并设为训练模式

    # 如果不用预训练，则自定义初始化权重
    if not pretrained:
        weights_init(model)

    # 加载完整模型权重（如果有指定路径）
    if model_path != "":
        print("加载权重 {}.".format(model_path))
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model_dict = model.state_dict()
        pretrained_dict = torch.load(model_path, map_location=device)
        # 过滤形状不匹配的权重
        pretrained_dict = {
            k: v
            for k, v in pretrained_dict.items()
            if np.shape(model_dict[k]) == np.shape(v)
        }
        model_dict.update(pretrained_dict)
        model.load_state_dict(model_dict)

    # 启用多GPU训练（如果可用）
    model_train = model.train()
    if Cuda:
        model_train = torch.nn.DataParallel(model)
        cudnn.benchmark = True  # 启用CUDA加速
        model_train = model_train.cuda()
        # 初始化损失记录器（保存到logs/目录）
        loss_history = LossHistory("logs/", val_loss_flag=False)

    # ---------------------- 数据加载 ----------------------
    # 读取训练集划分文件
    with open(
            os.path.join(VOCdevkit_path, "ImageSets/Segmentation/train.txt"), "r"
    ) as f:
        train_lines = f.readlines()

    # ==================== 冻结阶段训练 ====================
    if True:
        batch_size = Freeze_batch_size
        lr = Freeze_lr
        start_epoch = Init_Epoch
        end_epoch = Freeze_Epoch

        # 计算每轮迭代步数
        epoch_step = len(train_lines) // batch_size
        if epoch_step == 0:
            raise ValueError(
                f"Dataset too small to train. "
                f"Need at least {batch_size} images, but only {len(train_lines)} found in train.txt. "
                f"Please generate more data (settings > sample_count) and rebuild the index."
            )

        # 初始化优化器和学习率调度器
        optimizer = optim.Adam(model_train.parameters(), lr)
        lr_scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.96)

        # 创建数据集和数据加载器
        train_dataset = UnetDataset(
            train_lines, input_shape, num_classes, True, VOCdevkit_path
        )
        gen = DataLoader(
            train_dataset,
            shuffle=True,
            batch_size=batch_size,
            num_workers=num_workers,
            pin_memory=True,
            drop_last=True,
            collate_fn=unet_dataset_collate,  # 自定义批次组合函数
        )

        # 冻结主干网络（只训练解码器）
        if Freeze_Train:
            model.freeze_backbone()

        # 开始训练循环
        for epoch in range(start_epoch, end_epoch):
            fit_one_epoch_no_val(
                model_train,  # 训练模型
                model,  # 原始模型（用于保存权重）
                loss_history,  # 损失记录器
                optimizer,  # 优化器
                epoch,  # 当前轮次
                epoch_step,  # 每轮迭代次数
                gen,  # 数据加载器
                end_epoch,  # 总轮次
                Cuda,  # 是否使用CUDA
                dice_loss,  # Dice损失开关
                focal_loss,  # Focal Loss开关
                cls_weights,  # 类别权重
                num_classes,  # 类别数
                comb_edge,  # 边缘考虑开关
                args.png_name,  # 输入图像名（用于日志）
                dataset_name,  # 数据集名（用于保存权重）
            )
            lr_scheduler.step()  # 更新学习率

    # ==================== 解冻阶段训练 ====================
    if True:
        batch_size = Unfreeze_batch_size
        lr = Unfreeze_lr
        start_epoch = Freeze_Epoch
        end_epoch = UnFreeze_Epoch

        epoch_step = len(train_lines) // batch_size
        if epoch_step == 0:
            raise ValueError(
                f"Dataset too small to train. "
                f"Need at least {batch_size} images, but only {len(train_lines)} found in train.txt. "
                f"Please generate more data (settings > sample_count) and rebuild the index."
            )

        # 重新初始化优化器（学习率改变）
        optimizer = optim.Adam(model_train.parameters(), lr)
        lr_scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.96)

        # 数据加载器（与冻结阶段相同）
        train_dataset = UnetDataset(
            train_lines, input_shape, num_classes, True, VOCdevkit_path
        )
        gen = DataLoader(
            train_dataset,
            shuffle=True,
            batch_size=batch_size,
            num_workers=num_workers,
            pin_memory=True,
            drop_last=True,
            collate_fn=unet_dataset_collate,
        )

        # 解冻主干网络（训练全部参数）
        if Freeze_Train:
            model.unfreeze_backbone()

        # 训练循环
        for epoch in range(start_epoch, end_epoch):
            fit_one_epoch_no_val(
                model_train,
                model,
                loss_history,
                optimizer,
                epoch,
                epoch_step,
                gen,
                end_epoch,
                Cuda,
                dice_loss,
                focal_loss,
                cls_weights,
                num_classes,
                comb_edge,
                args.png_name,
                dataset_name,
            )
            lr_scheduler.step()