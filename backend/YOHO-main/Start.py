from pipeline import run_full_pipeline


if __name__ == "__main__":
    import os

    img_path = "./img/"
    imgList = os.listdir(img_path)
    for imgs in imgList:
        png_name = imgs.split(".")[0]
        run_full_pipeline(png_name)
