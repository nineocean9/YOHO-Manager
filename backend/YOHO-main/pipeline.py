from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


@dataclass
class PipelinePaths:
    project_root: Path = PROJECT_ROOT
    data_root: Path = PROJECT_ROOT.parent  # YOHO/ (与原始脚本 ../ 路径对齐)
    image_dir: Path = PROJECT_ROOT / "img"
    roi_dir: Path = data_root / "Dataset" / "EEC" / "EEC_test_dataset_label"
    sample_dir: Path = data_root / "EEC_save_sample_13.0"
    dataset_dir: Path = PROJECT_ROOT / "Medical_Datasets"
    log_dir: Path = PROJECT_ROOT / "logs"
    result_dir: Path = PROJECT_ROOT / "img_out"

    def ensure(self) -> None:
        for path in [self.image_dir, self.roi_dir, self.sample_dir, self.dataset_dir, self.log_dir, self.result_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def image_path(self, png_name: str) -> Path:
        return self.image_dir / f"{png_name}.png"

    def roi_path(self, png_name: str) -> Path:
        return self.roi_dir / f"{png_name}.png"

    def sample_case_dir(self, png_name: str) -> Path:
        return self.sample_dir / png_name

    def train_image_path(self, png_name: str) -> Path:
        return self.dataset_dir / "Images" / f"{png_name}.jpg"

    def train_label_path(self, png_name: str) -> Path:
        return self.dataset_dir / "Labels" / f"{png_name}.png"

    def train_edge_path(self, png_name: str) -> Path:
        return self.dataset_dir / "edges" / f"{png_name}.png"


@dataclass
class StepResult:
    step: str
    code: int
    output: str


def _run_script(script: str, *args: str, logger: Optional[Callable[[str], None]] = None,
                progress_callback: Optional[Callable[[int, int], None]] = None) -> StepResult:
    cmd = [PYTHON, str(PROJECT_ROOT / script), *args]
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    output_lines: list[str] = []
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.rstrip()
        if line.startswith("PROGRESS:"):
            if progress_callback is not None:
                parts = line[len("PROGRESS:"):].split("/")
                if len(parts) == 2:
                    try:
                        progress_callback(int(parts[0]), int(parts[1]))
                    except ValueError:
                        pass
        else:
            output_lines.append(line)
            if logger:
                logger(line)
    proc.wait()
    output = "\n".join(output_lines)
    if logger and not output_lines:
        logger(f"{script} finished with code {proc.returncode}")
    return StepResult(script, proc.returncode, output)


def _ensure_case_ready(png_name: str) -> PipelinePaths:
    paths = PipelinePaths()
    paths.ensure()
    if not paths.image_path(png_name).exists():
        raise FileNotFoundError(f"Image not found: {paths.image_path(png_name)}")
    return paths


def run_roi_prep(png_name: str, logger: Optional[Callable[[str], None]] = None) -> StepResult:
    paths = _ensure_case_ready(png_name)
    roi_path = paths.roi_path(png_name)
    if not roi_path.exists():
        return StepResult("roi", 1, f"ROI mask not found: {roi_path}")
    return StepResult("roi", 0, str(roi_path))


def run_interactive_sampling(png_name: str, logger: Optional[Callable[[str], None]] = None) -> StepResult:
    paths = _ensure_case_ready(png_name)
    sample_dir = paths.sample_case_dir(png_name)
    required_pkl = ["cent.pkl", "ind.pkl", "cnd.pkl", "tcnd.pkl", "tind.pkl", "sp.pkl", "trnum.pkl", "rnd.pkl"]
    missing = [f for f in required_pkl if not (sample_dir / f).exists()]
    if missing:
        msg = f"采样数据缺失（请先在桌面程序完成交互采样）: {missing}"
        if logger:
            logger(msg)
        return StepResult("sample", 1, msg)
    return StepResult("sample", 0, str(sample_dir))


def run_generate_dataset(png_name: str, logger: Optional[Callable[[str], None]] = None,
                         progress_callback: Optional[Callable[[int, int], None]] = None) -> StepResult:
    _ensure_case_ready(png_name)
    return _run_script("recreate_sample_3.0.py", "--png_name", png_name, logger=logger,
                       progress_callback=progress_callback)


def run_build_index(logger: Optional[Callable[[str], None]] = None) -> StepResult:
    return _run_script("voc_annotation_medical.py", logger=logger)


def run_train(png_name: str, logger: Optional[Callable[[str], None]] = None) -> StepResult:
    _ensure_case_ready(png_name)
    return _run_script("train_medical.py", "--png_name", png_name, logger=logger)


def run_predict(png_name: str, logger: Optional[Callable[[str], None]] = None) -> StepResult:
    _ensure_case_ready(png_name)
    return _run_script("predict.py", "--png_name", png_name, logger=logger)


def run_full_pipeline(png_name: str, logger: Optional[Callable[[str], None]] = None) -> list[StepResult]:
    return [
        run_roi_prep(png_name, logger=logger),
        run_generate_dataset(png_name, logger=logger),
        run_build_index(logger=logger),
        run_train(png_name, logger=logger),
        run_predict(png_name, logger=logger),
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOHO desktop pipeline launcher")
    parser.add_argument("--png_name", default="dummy")
    parser.add_argument("--step", default="all", choices=["all", "roi", "sample", "dataset", "index", "train", "predict"])
    args = parser.parse_args()
    if args.step == "roi":
        print(run_roi_prep(args.png_name).output)
    elif args.step == "sample":
        print(run_interactive_sampling(args.png_name).output)
    elif args.step == "dataset":
        print(run_generate_dataset(args.png_name).output)
    elif args.step == "index":
        print(run_build_index().output)
    elif args.step == "train":
        print(run_train(args.png_name).output)
    elif args.step == "predict":
        print(run_predict(args.png_name).output)
    else:
        for result in run_full_pipeline(args.png_name):
            print(f"[{result.step}] exit={result.code}")
