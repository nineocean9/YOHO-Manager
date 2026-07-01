import colorsys
import copy
import time
import os
import cv2
import numpy as np
import torch
import argparse
import torch.nn.functional as F
from PIL import Image
from torch import nn
from PIL import Image, ImageDraw
from nets.unet import Unet as unet
from utils.utils import cvtColor, preprocess_input, resize_image

parser = argparse.ArgumentParser()
parser.add_argument("--png_name", default="dummy", help="Input image name")
parser.add_argument("--model_path", default=None, help="Custom model weight path")
args, _unknown = parser.parse_known_args()

dataset_name = "EEC"

# ── 从 config.json 读取模型轮次 ────────────────────────
import json as _json
try:
    with open("config.json") as _f:
        _model_epoch = str(_json.load(_f).get("prediction", {}).get("model_epoch", "30")).zfill(3)
except Exception:
    _model_epoch = "030"


# Note the modification of model_path and num_classes number during training
class Unet(object):
    _defaults = {
        "model_path": "logs/" + dataset_name + "-" + args.png_name + "-ep" + _model_epoch + ".pth",
        "num_classes": 2,
        "backbone": "resnet34",
        "input_shape": [256, 256],
        "blend": True,
        "cuda": True,
    }

    def __init__(self, png_name=None, **kwargs):
        self.__dict__.update(self._defaults)
        if png_name is not None:
            self.model_path = "logs/" + dataset_name + "-" + png_name + "-ep" + _model_epoch + ".pth"
        for name, value in kwargs.items():
            setattr(self, name, value)

        # Picture frames set to different colors
        if self.num_classes <= 21:
            self.colors = [
                (0, 0, 0),
                (128, 0, 0),
                (0, 128, 0),
                (128, 128, 0),
                (0, 0, 128),
                (128, 0, 128),
                (0, 128, 128),
                (128, 128, 128),
                (64, 0, 0),
                (192, 0, 0),
                (64, 128, 0),
                (192, 128, 0),
                (64, 0, 128),
                (192, 0, 128),
                (64, 128, 128),
                (192, 128, 128),
                (0, 64, 0),
                (128, 64, 0),
                (0, 192, 0),
                (128, 192, 0),
                (0, 64, 128),
                (128, 64, 12),
            ]
        else:
            hsv_tuples = [
                (x / self.num_classes, 1.0, 1.0) for x in range(self.num_classes)
            ]
            self.colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
            self.colors = list(
                map(
                    lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)),
                    self.colors,
                )
            )

        # Acquire the model
        self.generate()

    # Acquire all the classifications
    def generate(self):
        self.net = unet(
            num_classes=self.num_classes, backbone=self.backbone, mode="eval"
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net.load_state_dict(torch.load(self.model_path, map_location=device))
        self.net = self.net.eval()
        print("{} model, and classes loaded.".format(self.model_path))

        if self.cuda:
            self.net = nn.DataParallel(self.net)
            self.net = self.net.cuda()

    # Detect the image
    def detect_image(self, image, img_name, png_name):
        # image = cvtColor(image)
        #
        # # Make a backup of the input image to be used later for plotting.
        # old_img = copy.deepcopy(image)
        # orininal_h = np.array(image).shape[0]
        # orininal_w = np.array(image).shape[1]
        #
        # # Add gray bars to the image to achieve undistorted resize. can also directly resize for recognition
        # image_data, nw, nh = resize_image(
        #     image, (self.input_shape[1], self.input_shape[0])
        # )
        #
        # # Add the batch_size dimension
        # image_data = np.expand_dims(
        #     np.transpose(preprocess_input(np.array(image_data, np.float32)), (2, 0, 1)),
        #     0,
        # )
        #
        # with torch.no_grad():
        #     images = torch.from_numpy(image_data)
        #     if self.cuda:
        #         images = images.cuda()
        #
        #     #  Images are sent to the net for prediction
        #     prs, pre, b = self.net(images)
        #     pr = prs[0]
        #     pr = torch.sigmoid(pr.squeeze(0)).cpu().numpy()
        #
        #     # Kvasir
        #     # name_list = ['22', '45', '75', '100']
        #
        #     # EEC
        #     name_list = [
        #         "6",
        #         "7",
        #         "21",
        #         "22",
        #         "23",
        #         "24",
        #         "26",
        #         "27",
        #         "45",
        #         "46",
        #         "47",
        #         "48",
        #         "49",
        #         "50",
        #         "55",
        #         "74",
        #         "76",
        #         "77",
        #         "107",
        #         "108",
        #         "112",
        #         "113",
        #         "114",
        #         "115",
        #         "121",
        #         "127",
        #         "133",
        #         "134",
        #         "135",
        #         "136",
        #         "137",
        #         "138",
        #     ]
        #
        #     # retrieve the opposite
        #     if png_name in name_list:
        #         pr = 1 - pr
        #
        #     # Cut off the gray bar
        #     pr = pr[
        #         int((self.input_shape[0] - nh) // 2) : int(
        #             (self.input_shape[0] - nh) // 2 + nh
        #         ),
        #         int((self.input_shape[1] - nw) // 2) : int(
        #             (self.input_shape[1] - nw) // 2 + nw
        #         ),
        #     ]
        #
        #     # Resize the image
        #     pr = cv2.resize(
        #         pr, (orininal_w, orininal_h), interpolation=cv2.INTER_LINEAR
        #     )
        #
        #     pr[pr > 0.5] = 1
        #     pr[pr <= 0.5] = 0
        #
        # # Creates a new image and assigns colors to each pixel point according to its type
        # seg_img = np.zeros((np.shape(pr)[0], np.shape(pr)[1], 3))
        # for c in range(self.num_classes):
        #     seg_img[:, :, 0] += ((pr[:, :] == c) * (self.colors[c][0])).astype("uint8")
        #     seg_img[:, :, 1] += ((pr[:, :] == c) * (self.colors[c][1])).astype("uint8")
        #     seg_img[:, :, 2] += ((pr[:, :] == c) * (self.colors[c][2])).astype("uint8")
        #
        # # Convert the new pictures into Image form
        # image = Image.fromarray(np.uint8(seg_img))
        # image.save(
        #     "./results/"
        #     + img_name
        # )
        #
        # # Blend new images with the original images
        # if self.blend:
        #     image = Image.blend(old_img, image, 0.5)
        #
        # return image
        image = cvtColor(image)
        old_img = copy.deepcopy(image)
        orininal_h = np.array(image).shape[0]
        orininal_w = np.array(image).shape[1]

        # 图像预处理
        image_data, nw, nh = resize_image(image, (self.input_shape[1], self.input_shape[0]))
        image_data = np.expand_dims(np.transpose(preprocess_input(np.array(image_data, np.float32)), (2, 0, 1)), 0)

        with torch.no_grad():
            images = torch.from_numpy(image_data)
            if self.cuda:
                images = images.cuda()

            # 获取预测结果
            prs, pre, b = self.net(images)
            pr = prs[0]
            pr = torch.sigmoid(pr.squeeze(0)).cpu().numpy()

            # EEC数据集特殊处理
            name_list = ["6", "7", "21", "22", "23", "24", "26", "27", "45", "46", "47", "48",
                         "49", "50", "55", "74", "76", "77", "107", "108", "112", "113", "114",
                         "115", "121", "127", "133", "134", "135", "136", "137", "138"]
            if png_name in name_list:
                pr = 1 - pr

            # 裁剪填充区域
            pr = pr[int((self.input_shape[0] - nh) // 2): int((self.input_shape[0] - nh) // 2 + nh),
                 int((self.input_shape[1] - nw) // 2): int((self.input_shape[1] - nw) // 2 + nw)]

            # 恢复到原图尺寸
            pr = cv2.resize(pr, (orininal_w, orininal_h), interpolation=cv2.INTER_LINEAR)
            pr[pr > 0.5] = 1
            pr[pr <= 0.5] = 0

        # ---------------------- 关键修改部分 ----------------------
        # 将二值掩膜转换为uint8格式
        mask = (pr * 255).astype(np.uint8)

        # 边缘检测参数（可根据需要调整）
        thickness = 2  # 边缘线粗细
        edge_color = (255, 0, 0)  # 红色边缘 (BGR格式)

        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 在原图上绘制边缘
        if len(contours) > 0:
            # 创建透明图层用于绘制边缘
            edge_layer = Image.new("RGBA", (orininal_w, orininal_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(edge_layer)

            # 绘制所有轮廓
            for contour in contours:
                # 简化轮廓点（减少绘制点数量）
                epsilon = 0.002 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)

                # 转换为PIL可绘制格式
                points = [tuple(point[0]) for point in approx]
                if len(points) > 1:
                    # 闭合轮廓
                    points.append(points[0])
                    draw.line(points, fill=(255, 0, 0, 180), width=thickness)  # 半透明红色

            # 与原始图像合成
            result = old_img.convert("RGBA")
            result = Image.alpha_composite(result, edge_layer)
            result = result.convert("RGB")
        else:
            result = old_img

        # 保存结果（可选）
        if not os.path.exists("./results"):
            os.makedirs("./results")
        result.save(f"./results/{img_name}")

        return result




    def get_FPS(self, image, test_interval):
        image = cvtColor(image)

        image_data, nw, nh = resize_image(
            image, (self.input_shape[1], self.input_shape[0])
        )

        image_data = np.expand_dims(
            np.transpose(preprocess_input(np.array(image_data, np.float32)), (2, 0, 1)),
            0,
        )

        with torch.no_grad():
            images = torch.from_numpy(image_data)
            if self.cuda:
                images = images.cuda()

            pr = self.net(images)[0]

            pr = F.softmax(pr.permute(1, 2, 0), dim=-1).cpu().numpy().argmax(axis=-1)

            pr = pr[
                int((self.input_shape[0] - nh) // 2) : int(
                    (self.input_shape[0] - nh) // 2 + nh
                ),
                int((self.input_shape[1] - nw) // 2) : int(
                    (self.input_shape[1] - nw) // 2 + nw
                ),
            ]

        t1 = time.time()
        for _ in range(test_interval):
            with torch.no_grad():
                pr = self.net(images)[0]

                pr = (
                    F.softmax(pr.permute(1, 2, 0), dim=-1).cpu().numpy().argmax(axis=-1)
                )

                pr = pr[
                    int((self.input_shape[0] - nh) // 2) : int(
                        (self.input_shape[0] - nh) // 2 + nh
                    ),
                    int((self.input_shape[1] - nw) // 2) : int(
                        (self.input_shape[1] - nw) // 2 + nw
                    ),
                ]
        t2 = time.time()
        tact_time = (t2 - t1) / test_interval
        return tact_time

    def get_miou_png(self, image):
        image = cvtColor(image)
        orininal_h = np.array(image).shape[0]
        orininal_w = np.array(image).shape[1]

        image_data, nw, nh = resize_image(
            image, (self.input_shape[1], self.input_shape[0])
        )

        image_data = np.expand_dims(
            np.transpose(preprocess_input(np.array(image_data, np.float32)), (2, 0, 1)),
            0,
        )

        with torch.no_grad():
            images = torch.from_numpy(image_data)
            if self.cuda:
                images = images.cuda()

            pr = self.net(images)[0]

            pr = F.softmax(pr.permute(1, 2, 0), dim=-1).cpu().numpy()

            pr = pr[
                int((self.input_shape[0] - nh) // 2) : int(
                    (self.input_shape[0] - nh) // 2 + nh
                ),
                int((self.input_shape[1] - nw) // 2) : int(
                    (self.input_shape[1] - nw) // 2 + nw
                ),
            ]

            pr = cv2.resize(
                pr, (orininal_w, orininal_h), interpolation=cv2.INTER_LINEAR
            )

            pr = pr.argmax(axis=-1)

        image = Image.fromarray(np.uint8(pr))
        return image