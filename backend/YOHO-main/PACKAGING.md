# YOHO Desktop 打包说明

## 启动
- 双击 `YOHO-main/run_desktop.bat`
- 或执行 `python YOHO-main/app.py`

## 打包为 exe
在 `YOHO-main` 目录执行：

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name YOHO-Desktop app.py
```

生成结果位于：
- `YOHO-main/dist/YOHO-Desktop.exe`

## 使用流程
1. 将内镜图像放入 `YOHO-main/img/`，或在桌面程序内直接选择图像
2. 在桌面程序中点击“标注 ROI”，直接绘制多边形并保存到 `YOHO-main/Dataset/EEC/EEC_test_dataset_label/`
3. 点击“检查 ROI”确认掩膜已就绪
4. 再执行交互采样、生成训练集、训练、预测，或直接点击“一键运行`

## 说明
- ROI 已内置在桌面程序中，不必再依赖外部标注工具。
- 标注器支持轮廓平滑、边缘柔化和轻微外扩，可减少手工多边形产生的笔直锐利边缘。
- 训练、预测、采样均在本机完成，不依赖外部服务。
