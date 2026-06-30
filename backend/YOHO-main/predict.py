import argparse
import os
from pathlib import Path

from PIL import Image

from unet import Unet


def predict_case(png_name: str, image_dir: str = "img", save_dir: str = "img_out", model_path: str = None):
    image_dir_path = Path(image_dir)
    save_dir_path = Path(save_dir)
    img_name = f"{png_name}.png"
    image_path = image_dir_path / img_name

    if model_path:
        unet = Unet(png_name=png_name, model_path=model_path)
    else:
        unet = Unet(png_name=png_name)
    image = Image.open(image_path)
    result_image = unet.detect_image(image, img_name, png_name)
    save_dir_path.mkdir(parents=True, exist_ok=True)
    save_path = save_dir_path / img_name
    result_image.save(save_path)
    return save_path


parser = argparse.ArgumentParser()
parser.add_argument("--png_name", default="dummy", help="Input image name")
parser.add_argument("--model_path", default=None, help="Custom model weight path (overrides default)")
args = parser.parse_args()

if __name__ == "__main__":
    predict_case(args.png_name, model_path=args.model_path)
