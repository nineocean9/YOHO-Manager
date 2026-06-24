from __future__ import annotations

import json
import math
import pickle
import random
import itertools
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from pipeline import PipelinePaths, run_build_index, run_full_pipeline, run_generate_dataset, run_predict, run_roi_prep, run_train


# ──────────────────────────────────────────────────────────────────────
# 全局配色 & 字体设计令牌 (Design Tokens)
# 参考: PetCare Clinic — 医疗青 + 暖珊瑚点缀
# ──────────────────────────────────────────────────────────────────────
class Theme:
    # 主背景
    BG_APP        = "#f8fafb"     # 极浅灰白底 — 参考诊所页面柔和底色
    BG_CARD       = "#ffffff"     # 卡片白
    BG_HEADER     = "#1a2f3f"     # 深蓝灰头部
    BG_HEADER_ACC = "#243b4d"     # 头部辅色
    BG_HEADER_GRAD= "#1a5c7a"     # 头部渐变辅色
    BG_HOVER      = "#e8f6f3"     # 悬停浅青高亮
    BG_INPUT      = "#f8fafd"     # 输入框背景
    BG_LOG        = "#0f1a26"     # 日志深色背景
    BG_DIVIDER    = "#e2e8f0"     # 分割线 - 浅灰

    # 文字
    FG_TITLE      = "#1a2f3f"
    FG_BODY       = "#334155"
    FG_MUTED      = "#64748b"
    FG_INV        = "#ffffff"     # 反白
    FG_INV_MUTED  = "#94a3b8"
    FG_LOG        = "#e2e8f0"

    # 主色 — 医疗青 (与诊所页一致)
    PRIMARY       = "#0891b2"     # 医疗青
    PRIMARY_DARK  = "#067190"     # 深青
    PRIMARY_LIGHT = "#e0f7fa"     # 浅青背景
    SECONDARY     = "#e8927c"     # 暖珊瑚 (参考诊所页 Emergency 按钮)
    SECONDARY_LIGHT = "#fde8e2"
    SUCCESS       = "#16a34a"
    SUCCESS_LIGHT = "#dcfce7"
    WARNING       = "#f59e0b"
    WARNING_LIGHT = "#fef3c7"
    DANGER        = "#dc2626"
    DANGER_LIGHT  = "#fee2e2"
    ACCENT        = "#14b8a6"     # 青绿点缀

    # 字体
    FONT_HEADER   = ("Microsoft YaHei UI", 17, "bold")
    FONT_SUB      = ("Microsoft YaHei UI", 10)
    FONT_SECTION  = ("Microsoft YaHei UI", 11, "bold")
    FONT_BODY     = ("Microsoft YaHei UI", 10)
    FONT_SMALL    = ("Microsoft YaHei UI", 9)
    FONT_MONO     = ("Consolas", 10)
    FONT_BTN      = ("Microsoft YaHei UI", 10)
    FONT_BTN_BOLD = ("Microsoft YaHei UI", 10, "bold")
    FONT_BADGE    = ("Microsoft YaHei UI", 9, "bold")


# ──────────────────────────────────────────────────────────────────────
# 通用 UI 组件
# ──────────────────────────────────────────────────────────────────────
class HoverButton(tk.Label):
    """带悬停反馈的扁平按钮 (用 Label 模拟以便完全控制配色)."""

    def __init__(self, master, text, command, *,
                 bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                 hover_bg=Theme.BG_HOVER, hover_fg=None,
                 font=None, anchor="w", padx=14, pady=10,
                 icon="", **kwargs):
        display = f"{icon}  {text}" if icon else text
        super().__init__(master, text=display, bg=bg, fg=fg,
                         font=font or Theme.FONT_BTN,
                         anchor=anchor, padx=padx, pady=pady,
                         cursor="hand2", **kwargs)
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._hover_fg = hover_fg or fg
        self._command = command
        self._enabled = True
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e):
        if self._enabled:
            self.config(bg=self._hover_bg, fg=self._hover_fg)

    def _on_leave(self, _e):
        if self._enabled:
            self.config(bg=self._bg, fg=self._fg)

    def _on_click(self, _e):
        if self._enabled and self._command:
            self._command()


class PrimaryButton(HoverButton):
    """主操作大按钮."""

    def __init__(self, master, text, command, *, icon="", **kwargs):
        super().__init__(
            master, text, command,
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            hover_bg=Theme.PRIMARY_DARK, hover_fg=Theme.FG_INV,
            font=Theme.FONT_BTN_BOLD,
            anchor="center", padx=18, pady=12,
            icon=icon, **kwargs,
        )


class StepButton(tk.Frame):
    """带编号的步骤按钮 (左侧序号圆 + 文字)."""

    def __init__(self, master, step_no, title, command, *, icon=""):
        super().__init__(master, bg=Theme.BG_CARD, cursor="hand2")
        self._command = command

        # 编号徽章
        self.badge = tk.Label(
            self, text=str(step_no),
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            font=Theme.FONT_BADGE, width=3, pady=4,
        )
        self.badge.pack(side="left", padx=(10, 0), pady=8)

        # 文字 + 图标
        display = f"{icon}  {title}" if icon else title
        self.text = tk.Label(
            self, text=display,
            bg=Theme.BG_CARD, fg=Theme.FG_BODY,
            font=Theme.FONT_BTN, anchor="w", padx=10, pady=8,
        )
        self.text.pack(side="left", fill="x", expand=True)

        for w in (self, self.badge, self.text):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._click)

    def _enter(self, _e):
        self.config(bg=Theme.BG_HOVER)
        self.badge.config(bg=Theme.PRIMARY_DARK, fg=Theme.FG_INV)
        self.text.config(fg=Theme.PRIMARY_DARK)

    def _leave(self, _e):
        self.config(bg=Theme.BG_CARD)
        self.badge.config(bg=Theme.PRIMARY, fg=Theme.FG_INV)
        self.text.config(fg=Theme.FG_BODY)

    def _click(self, _e):
        if self._command:
            self._command()

    def mark_done(self):
        """标记该步骤为已完成 (变绿)."""
        self.badge.config(bg=Theme.SUCCESS_LIGHT, fg=Theme.SUCCESS, text="✓")


class Card(tk.Frame):
    """带细边框的卡片容器 (模拟阴影)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, bg=Theme.BG_DIVIDER, **kwargs)
        self.inner = tk.Frame(self, bg=Theme.BG_CARD)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)


class Badge(tk.Label):
    """状态徽章."""

    STYLES = {
        "primary": (Theme.PRIMARY_LIGHT, Theme.PRIMARY),
        "success": (Theme.SUCCESS_LIGHT, Theme.SUCCESS),
        "warning": (Theme.WARNING_LIGHT, Theme.WARNING),
        "danger":  (Theme.DANGER_LIGHT,  Theme.DANGER),
        "muted":   ("#e2e8f0", Theme.FG_MUTED),
    }

    def __init__(self, master, text, kind="primary", **kwargs):
        bg, fg = self.STYLES.get(kind, self.STYLES["primary"])
        super().__init__(master, text=text, bg=bg, fg=fg,
                         font=Theme.FONT_BADGE, padx=10, pady=3,
                         **kwargs)


# ──────────────────────────────────────────────────────────────────────
# ROI 标注子窗口
# ──────────────────────────────────────────────────────────────────────
class RoiEditor(tk.Frame):
    def __init__(self, master: tk.Misc, image_path: Path, roi_path: Path, on_saved, on_back=None) -> None:
        super().__init__(master, bg=Theme.BG_APP)
        self.image_path = image_path
        self.roi_path = roi_path
        self.on_saved = on_saved
        self.on_back = on_back
        self.points: list[tuple[int, int]] = []
        self.original = Image.open(image_path).convert("RGB")
        self.is_closed = False
        self.close_threshold = 18
        self.photo = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.smooth_iterations = tk.IntVar(value=2)
        self.blur_radius = tk.DoubleVar(value=2.0)
        self.expand_pixels = tk.IntVar(value=2)
        self.hover_point: tuple[int, int] | None = None
        self.hint_text = tk.StringVar(value="点击添加轮廓点，闭合后保存 ROI")

        # ── 顶部导航条 ──
        header = tk.Frame(self, bg=Theme.BG_CARD, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        HoverButton(header, "返回", self._go_back, icon="←",
                    bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                    hover_bg=Theme.BG_HOVER, hover_fg=Theme.PRIMARY,
                    anchor="center", padx=12, pady=6,
                    font=Theme.FONT_BTN).pack(side="left", padx=(10, 4), pady=6)
        tk.Label(header, text="✏ ROI 标注",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(side="left", pady=6)
        tk.Label(header, text=f"{image_path.name}",
                 bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL).pack(side="left", padx=(8, 0), pady=6)
        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # ── 工具栏卡片 ──
        toolbar_card = Card(self)
        toolbar_card.pack(fill="x", padx=10, pady=(14, 8))
        toolbar = toolbar_card.inner

        tk.Label(toolbar, text="🛠  工具", bg=Theme.BG_CARD,
                 fg=Theme.FG_MUTED, font=Theme.FONT_SMALL,
                 padx=14, pady=4).pack(side="left", pady=10)

        for icon, txt, cmd in [
            ("↶", "撤销", self._undo),
            ("⊘", "清空", self._clear),
            ("〜", "轮廓平滑", self._smooth_points),
        ]:
            HoverButton(toolbar, txt, cmd, icon=icon,
                        bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                        hover_bg=Theme.BG_HOVER, hover_fg=Theme.PRIMARY,
                        anchor="center", padx=14, pady=8,
                        font=Theme.FONT_BTN).pack(side="left", padx=4, pady=8)

        HoverButton(
            toolbar, "保存 ROI", self._save, icon="💾",
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            hover_bg=Theme.PRIMARY_DARK, hover_fg=Theme.FG_INV,
            anchor="center", padx=20, pady=8,
            font=Theme.FONT_BTN_BOLD,
        ).pack(side="right", padx=10, pady=8)

        # ── 控制条卡片 ──
        ctrl_card = Card(self)
        ctrl_card.pack(fill="x", padx=10, pady=(0, 8))
        controls = ctrl_card.inner

        def slider_block(parent, label, var, frm, to):
            blk = tk.Frame(parent, bg=Theme.BG_CARD)
            tk.Label(blk, text=label, bg=Theme.BG_CARD,
                     fg=Theme.FG_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
            inner = tk.Frame(blk, bg=Theme.BG_CARD)
            inner.pack(fill="x")
            ttk.Scale(inner, from_=frm, to=to, variable=var,
                      orient="horizontal", length=150).pack(side="left")
            val_lbl = tk.Label(inner, textvariable=tk.StringVar(),
                               bg=Theme.PRIMARY_LIGHT, fg=Theme.PRIMARY,
                               font=Theme.FONT_BADGE, width=4, pady=2)
            val_lbl.pack(side="left", padx=(8, 0))
            # 同步显示
            def sync(*_):
                v = var.get()
                if isinstance(v, float):
                    val_lbl.config(text=f"{v:.1f}")
                else:
                    val_lbl.config(text=str(int(v)))
            var.trace_add("write", sync)
            sync()
            return blk

        slider_block(controls, "平滑次数", self.smooth_iterations, 0, 6).pack(
            side="left", padx=14, pady=10)
        slider_block(controls, "边缘柔化", self.blur_radius, 0, 6).pack(
            side="left", padx=14, pady=10)
        slider_block(controls, "外扩像素", self.expand_pixels, 0, 12).pack(
            side="left", padx=14, pady=10)

        # ── 提示徽章 ──
        hint_frame = tk.Frame(controls, bg=Theme.BG_CARD)
        hint_frame.pack(side="right", padx=16, pady=10)
        tk.Label(hint_frame, text="💡", bg=Theme.BG_CARD,
                 fg=Theme.SECONDARY, font=("Segoe UI", 14)).pack(side="left")
        tk.Label(hint_frame, textvariable=self.hint_text,
                 bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                 font=Theme.FONT_SMALL).pack(side="left", padx=(4, 0))

        # ── 画布区 ──
        canvas_card = Card(self)
        canvas_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.canvas = tk.Canvas(canvas_card.inner, bg="#cbd9eb",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Configure>", lambda _event: self._render())

        self._load_existing_roi()
        self._render()

    def _load_existing_roi(self) -> None:
        self.points = []
        self.is_closed = False
        if not self.roi_path.exists():
            return
        mask = Image.open(self.roi_path).convert("L")
        bbox = mask.getbbox()
        if not bbox:
            return
        left, top, right, bottom = bbox
        samples = []
        width, height = mask.size
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        step = 6
        max_radius = int(max(width, height))
        for angle in range(0, 360, step):
            rad = math.radians(angle)
            hit = None
            for radius in range(max_radius, 0, -1):
                x = int(center_x + math.cos(rad) * radius)
                y = int(center_y + math.sin(rad) * radius)
                if 0 <= x < width and 0 <= y < height and mask.getpixel((x, y)) > 0:
                    hit = (x, y)
            if hit is not None:
                samples.append(hit)
        simplified = []
        for point in samples:
            if not simplified:
                simplified.append(point)
                continue
            prev = simplified[-1]
            if abs(point[0] - prev[0]) + abs(point[1] - prev[1]) > 8:
                simplified.append(point)
        if len(simplified) >= 3:
            self.points = simplified
            self.is_closed = True

    def _go_back(self) -> None:
        if self.on_back:
            self.on_back()

    def _render(self) -> None:
        canvas_w = max(self.canvas.winfo_width(), 400)
        canvas_h = max(self.canvas.winfo_height(), 300)
        image = self.original.copy()
        image.thumbnail((canvas_w - 20, canvas_h - 20))
        self.scale_x = self.original.width / image.width
        self.scale_y = self.original.height / image.height
        self.offset_x = (canvas_w - image.width) // 2
        self.offset_y = (canvas_h - image.height) // 2

        overlay = image.convert("RGBA")
        draw = ImageDraw.Draw(overlay)
        if self.points:
            scaled_points = [(int(x / self.scale_x), int(y / self.scale_y)) for x, y in self.points]
            if self.is_closed and len(scaled_points) >= 3:
                draw.polygon(scaled_points, fill=(37, 99, 235, 72))
            for index, point in enumerate(scaled_points):
                radius = 6 if index == 0 else 4
                fill = "#16a34a" if index == 0 else "#2563eb"
                if self.hover_point is not None and index == 0 and not self.is_closed:
                    radius = 9
                    fill = "#22c55e"
                draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=fill)
            if len(scaled_points) > 1:
                line_points = scaled_points + [scaled_points[0]] if self.is_closed else scaled_points
                draw.line(line_points, fill="#ef4444", width=3)
            if self.hover_point is not None and not self.is_closed and len(scaled_points) >= 2:
                hover_scaled = (int(self.hover_point[0] / self.scale_x), int(self.hover_point[1] / self.scale_y))
                draw.line([scaled_points[-1], hover_scaled], fill="#f59e0b", width=2)
        self.photo = ImageTk.PhotoImage(overlay)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.photo)

    def _to_original_coords(self, event_x: int, event_y: int) -> tuple[int, int] | None:
        display_w = int(self.original.width / self.scale_x)
        display_h = int(self.original.height / self.scale_y)
        x = event_x - self.offset_x
        y = event_y - self.offset_y
        if 0 <= x < display_w and 0 <= y < display_h:
            return int(x * self.scale_x), int(y * self.scale_y)
        return None

    def _on_click(self, event) -> None:
        point = self._to_original_coords(event.x, event.y)
        if point is None or self.is_closed:
            return
        if len(self.points) >= 3 and self._is_near_start(point):
            self.is_closed = True
            self.hover_point = None
            self.hint_text.set("轮廓已闭合，可平滑后保存")
        else:
            self.points.append(point)
            if len(self.points) == 1:
                self.hint_text.set("继续添加轮廓点以完成标注")
        self._render()

    def _on_motion(self, event) -> None:
        point = self._to_original_coords(event.x, event.y)
        self.hover_point = point
        if point is None:
            self.hint_text.set("将鼠标移至图像上进行标注")
            self._render()
            return
        if self.is_closed:
            self._render()
            return
        if len(self.points) < 3:
            self.hint_text.set("继续添加轮廓点（至少 3 个点）")
            self._render()
            return
        if self._is_near_start(point):
            self.hint_text.set("点击绿色起点附近以闭合 ROI")
        else:
            self.hint_text.set("继续添加轮廓点，到达起点后闭合")
        self._render()

    def _is_near_start(self, point: tuple[int, int]) -> bool:
        start_x, start_y = self.points[0]
        dx = point[0] - start_x
        dy = point[1] - start_y
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= self.close_threshold * max(self.scale_x, self.scale_y)

    def _undo(self) -> None:
        if self.is_closed:
            self.is_closed = False
            self.hint_text.set("已取消闭合，可继续编辑")
            self._render()
            return
        if self.points:
            self.points.pop()
            if not self.points:
                self.hint_text.set("点击添加轮廓点以开始标注")
            self._render()

    def _clear(self) -> None:
        self.points.clear()
        self.is_closed = False
        self.hover_point = None
        self.hint_text.set("点击添加轮廓点以开始标注")
        self._render()

    def _smooth_points(self) -> None:
        if not self.is_closed or len(self.points) < 4:
            self.hint_text.set("请先闭合 ROI，再进行轮廓平滑")
            return
        points = self.points[:]
        for _ in range(int(self.smooth_iterations.get())):
            refined = []
            for index, point in enumerate(points):
                prev_point = points[index - 1]
                next_point = points[(index + 1) % len(points)]
                refined.append((
                    int((prev_point[0] + point[0] * 2) / 3),
                    int((prev_point[1] + point[1] * 2) / 3),
                ))
                refined.append((
                    int((point[0] * 2 + next_point[0]) / 3),
                    int((point[1] * 2 + next_point[1]) / 3),
                ))
            points = refined
        self.points = points
        self.hint_text.set("轮廓已平滑")
        self._render()

    def _save(self) -> None:
        if not self.is_closed or len(self.points) < 3:
            messagebox.showerror("ROI 未闭合", "请先回到起点闭合轮廓,再保存 ROI", parent=self.winfo_toplevel())
            return
        mask = Image.new("L", self.original.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(self.points, fill=255)

        expand = int(self.expand_pixels.get())
        if expand > 0:
            for _ in range(expand):
                mask = mask.filter(ImageFilter.MaxFilter(3))

        blur = float(self.blur_radius.get())
        if blur > 0:
            soft_mask = mask.filter(ImageFilter.GaussianBlur(radius=blur))
            mask = soft_mask.point(lambda value: 255 if value >= 80 else 0)

        self.roi_path.parent.mkdir(parents=True, exist_ok=True)
        mask.save(self.roi_path)
        self.hint_text.set("ROI 已保存")
        self._load_existing_roi()
        if self.on_saved:
            self.on_saved(self.roi_path)


# ──────────────────────────────────────────────────────────────────────
# 交互式采样子窗口
# ──────────────────────────────────────────────────────────────────────
class SamplingEditor(tk.Frame):
    """交互式采样工具.左键放置/扩大圆形,右键缩小,S 保存,B 撤销,Q 结束阶段."""

    def __init__(self, master: tk.Misc, image_path: Path, sample_dir: Path, on_finished, on_back=None) -> None:
        super().__init__(master, bg=Theme.BG_APP)

        self.image_path = image_path
        self.sample_dir = sample_dir
        self.on_finished = on_finished
        self.on_back = on_back

        self.original = Image.open(image_path).convert("RGB")
        self.cv_img = cv2.cvtColor(np.array(self.original), cv2.COLOR_RGB2BGR)
        self.sp = self.cv_img.shape

        # 采样状态
        self.cent: list[tuple[int, int]] = []
        self.ind: dict[int, dict[int, tuple[int, int]]] = {}
        self.tind: dict[int, dict[int, tuple[int, int]]] = {}
        self.cnd: dict[int, dict[int, list[tuple[int, int]]]] = {}
        self.tcnd: dict[int, dict[int, list[tuple[int, int]]]] = {}
        self.rnd: dict[int, int] = {}
        self.trnum = 0
        self.num_class = 0
        self.bg = 0
        self.start = 1
        self.sid = 0
        self.point1 = (0, 0)
        self.r_min = max(int(max(self.sp[0], self.sp[1]) / 256 * 8), 6)
        if self.r_min % 2 != 0:
            self.r_min += 1
        self.r_max = 4 * self.r_min
        self.r = self.r_min
        self.randlist = list(itertools.product(range(self.sp[1]), range(self.sp[0])))
        self.colors = [
            (255, 0, 0), (0, 128, 0), (0, 128, 128), (128, 0, 0),
            (128, 0, 128), (128, 128, 0), (128, 128, 128), (0, 0, 64),
            (0, 192, 0), (192, 0, 0), (0, 128, 64), (128, 0, 192),
            (192, 128, 0), (64, 0, 0), (64, 128, 0), (0, 64, 0),
            (128, 64, 0), (0, 192, 128), (128, 192, 0), (0, 64, 128),
            (128, 64, 12),
        ]

        self.slic_lines = self._compute_slic_overlay()

        self.scale_x = 1.0
        self.scale_y = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.hover_pos: tuple[int, int] | None = None
        self.photo = None
        self.hint_text = tk.StringVar(value="在病灶区域点击放置圆形，按 S 保存采样")

        self._build_ui()
        self.winfo_toplevel().bind("<Key>", self._on_key)
        self.focus_set()
        self._load_existing_sample()
        self._render()

    def _load_existing_sample(self) -> bool:
        pkl_dir = self.sample_dir
        required = ["cent.pkl", "ind.pkl", "cnd.pkl", "tcnd.pkl", "tind.pkl", "sp.pkl", "trnum.pkl", "rnd.pkl"]
        if not all((pkl_dir / f).exists() for f in required):
            return False
        try:
            with open(pkl_dir / "cent.pkl", "rb") as f: self.cent = pickle.load(f)
            with open(pkl_dir / "ind.pkl", "rb") as f: self.ind = pickle.load(f)
            with open(pkl_dir / "cnd.pkl", "rb") as f: self.cnd = pickle.load(f)
            with open(pkl_dir / "tcnd.pkl", "rb") as f: self.tcnd = pickle.load(f)
            with open(pkl_dir / "tind.pkl", "rb") as f: self.tind = pickle.load(f)
            with open(pkl_dir / "sp.pkl", "rb") as f: self.sp = pickle.load(f)
            with open(pkl_dir / "trnum.pkl", "rb") as f: self.trnum = pickle.load(f)
            with open(pkl_dir / "rnd.pkl", "rb") as f: self.rnd = pickle.load(f)

            total = len(self.cent)
            self.sid = total
            if self.trnum > 0:
                bg_count = total - self.trnum
                self.num_class = bg_count
                self.bg = 1
            else:
                self.num_class = total
                self.bg = 0
            self._update_phase_label()
            self.hint_text.set(f"已加载 {total} 个采样点")
            return True
        except Exception:
            self.cent.clear()
            self.ind.clear()
            self.cnd.clear()
            self.tcnd.clear()
            self.tind.clear()
            self.rnd.clear()
            self.trnum = 0
            self.num_class = 0
            self.bg = 0
            self.sid = 0
            return False

    def _compute_slic_overlay(self) -> Image.Image:
        try:
            slic = cv2.ximgproc.createSuperpixelSLIC(self.cv_img, region_size=48, ruler=20.0)
            slic.iterate(10)
            mask = slic.getLabelContourMask()
            arr = np.zeros((self.sp[0], self.sp[1], 4), dtype=np.uint8)
            arr[mask > 0] = [160, 160, 160, 120]
            return Image.fromarray(arr, "RGBA")
        except AttributeError:
            return Image.new("RGBA", (self.sp[1], self.sp[0]), (0, 0, 0, 0))

    def _build_ui(self) -> None:
        # ── 顶部导航条 ──
        header = tk.Frame(self, bg=Theme.BG_CARD, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        HoverButton(header, "返回", self._go_back, icon="←",
                    bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                    hover_bg=Theme.BG_HOVER, hover_fg=Theme.PRIMARY,
                    anchor="center", padx=12, pady=6,
                    font=Theme.FONT_BTN).pack(side="left", padx=(10, 4), pady=6)
        tk.Label(header, text="◎ 交互采样",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(side="left", pady=6)
        tk.Label(header, text=f"{self.image_path.name}",
                 bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL).pack(side="left", padx=(8, 0), pady=6)

        # 阶段进度指示器 (右侧)
        self.phase_indicator = tk.Label(
            header, text="● 阶段 1/2 · 病灶采样",
            bg=Theme.BG_CARD, fg=Theme.PRIMARY,
            font=Theme.FONT_BTN_BOLD,
        )
        self.phase_indicator.pack(side="right", padx=16, pady=6)
        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # ── 工具栏卡片 ──
        toolbar_card = Card(self)
        toolbar_card.pack(fill="x", padx=10, pady=(14, 8))
        toolbar = toolbar_card.inner

        # 当前模式徽章 (左)
        mode_frame = tk.Frame(toolbar, bg=Theme.BG_CARD)
        mode_frame.pack(side="left", padx=16, pady=10)
        tk.Label(mode_frame, text="当前模式", bg=Theme.BG_CARD,
                 fg=Theme.FG_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        self.phase_badge = Badge(mode_frame, "🔵 病灶采样  (0个)", "primary")
        self.phase_badge.pack(pady=(2, 0))

        # 操作按钮 (右)
        for icon, txt, cmd, kind in [
            ("↶", "撤销 (B)", self._undo, "muted"),
            ("⊘", "清空", self._clear, "muted"),
        ]:
            HoverButton(toolbar, txt, cmd, icon=icon,
                        bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                        hover_bg=Theme.BG_HOVER, hover_fg=Theme.PRIMARY,
                        anchor="center", padx=14, pady=8,
                        font=Theme.FONT_BTN).pack(side="left", padx=4, pady=10)

        HoverButton(
            toolbar, "完成 (Q)", self._finish_phase, icon="✓",
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            hover_bg=Theme.PRIMARY_DARK, hover_fg=Theme.FG_INV,
            anchor="center", padx=16, pady=8,
            font=Theme.FONT_BTN_BOLD,
        ).pack(side="right", padx=8, pady=10)
        HoverButton(
            toolbar, "保存 (S)", self._save_sample, icon="💾",
            bg=Theme.SECONDARY, fg=Theme.FG_INV,
            hover_bg="#d4775f", hover_fg=Theme.FG_INV,
            anchor="center", padx=16, pady=8,
            font=Theme.FONT_BTN_BOLD,
        ).pack(side="right", padx=4, pady=10)

        # ── 半径控制 + 帮助卡片 ──
        ctrl_card = Card(self)
        ctrl_card.pack(fill="x", padx=10, pady=(0, 8))
        ctrl = ctrl_card.inner

        rad_frame = tk.Frame(ctrl, bg=Theme.BG_CARD)
        rad_frame.pack(side="left", padx=16, pady=10)
        tk.Label(rad_frame, text="采样半径", bg=Theme.BG_CARD,
                 fg=Theme.FG_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        rad_inner = tk.Frame(rad_frame, bg=Theme.BG_CARD)
        rad_inner.pack()
        self.radius_label = tk.Label(
            rad_inner, text=str(self.r),
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            font=("Microsoft YaHei UI", 13, "bold"),
            width=4, pady=4,
        )
        self.radius_label.pack(side="left")
        tk.Label(rad_inner, text=f"  px   (范围 {self.r_min} ~ {self.r_max})",
                 bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL).pack(side="left")

        # 快捷键提示
        help_frame = tk.Frame(ctrl, bg=Theme.BG_CARD)
        help_frame.pack(side="left", padx=20, pady=10)
        for k, desc in [("左键", "放置/扩大"), ("右键", "缩小"),
                         ("S", "保存"), ("B", "撤销"), ("Q", "完成")]:
            kb = tk.Frame(help_frame, bg=Theme.BG_CARD)
            kb.pack(side="left", padx=4)
            tk.Label(kb, text=k, bg="#e2e8f0", fg=Theme.FG_BODY,
                     font=("Microsoft YaHei UI", 8, "bold"),
                     padx=6, pady=2).pack(side="left")
            tk.Label(kb, text=desc, bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                     font=Theme.FONT_SMALL).pack(side="left", padx=(3, 0))

        # 提示文字 (右)
        hint_frame = tk.Frame(ctrl, bg=Theme.BG_CARD)
        hint_frame.pack(side="right", padx=16, pady=10)
        tk.Label(hint_frame, text="💡", bg=Theme.BG_CARD,
                 fg=Theme.WARNING, font=("Segoe UI", 14)).pack(side="left")
        tk.Label(hint_frame, textvariable=self.hint_text,
                 bg=Theme.BG_CARD, fg=Theme.FG_BODY,
                 font=Theme.FONT_SMALL).pack(side="left", padx=(4, 0))

        # ── 画布 ──
        canvas_card = Card(self)
        canvas_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.canvas = tk.Canvas(canvas_card.inner, bg="#cbd9eb",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Configure>", lambda _e: self._render())

    def _go_back(self) -> None:
        if self.on_back:
            self.on_back()

    def _to_original(self, ex: int, ey: int) -> tuple[int, int] | None:
        dw, dh = int(self.sp[1] / self.scale_x), int(self.sp[0] / self.scale_y)
        x, y = ex - self.offset_x, ey - self.offset_y
        if 0 <= x < dw and 0 <= y < dh:
            return int(x * self.scale_x), int(y * self.scale_y)
        return None

    def _render(self) -> None:
        cw = max(self.canvas.winfo_width(), 400)
        ch = max(self.canvas.winfo_height(), 300)
        img = self.original.copy()
        img.thumbnail((cw - 20, ch - 20))
        self.scale_x = self.sp[1] / img.width
        self.scale_y = self.sp[0] / img.height
        self.offset_x = (cw - img.width) // 2
        self.offset_y = (ch - img.height) // 2

        overlay = img.convert("RGBA")
        draw = ImageDraw.Draw(overlay)

        slic_resized = self.slic_lines.resize(img.size, Image.NEAREST)
        slic_arr = np.array(slic_resized)
        if slic_arr.ndim == 2:
            pass
        elif slic_arr.ndim == 3 and slic_arr.shape[2] == 4:
            overlay = Image.alpha_composite(overlay, Image.fromarray(slic_arr, "RGBA"))
        draw = ImageDraw.Draw(overlay)

        for i, c in enumerate(self.cent):
            sx, sy = int(c[0] / self.scale_x), int(c[1] / self.scale_y)
            col = self.colors[i % len(self.colors)]
            sr = int((self.ind.get(i + 1, {}).get(1, (self.r_min, 1))[0]) / self.scale_x)
            draw.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=col + (100,), outline=col, width=2)
            draw.text((sx + sr + 4, sy - 8), str(i + 1), fill=col)

        if self.start == 0 and self.point1 != (0, 0):
            sx = int(self.point1[0] / self.scale_x)
            sy = int(self.point1[1] / self.scale_y)
            sr = int(self.r / self.scale_x)
            draw.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), outline="#ef4444", width=3)

        if self.hover_pos and self.start == 1:
            hx = int(self.hover_pos[0] / self.scale_x)
            hy = int(self.hover_pos[1] / self.scale_y)
            hr = int(self.r_min / self.scale_x)
            draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), outline="#f59e0b", width=2)

        self.photo = ImageTk.PhotoImage(overlay)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.photo)

    def _on_click(self, event) -> None:
        pt = self._to_original(event.x, event.y)
        if pt is None:
            return
        if self.start == 1:
            self.point1 = pt
            self.r = self.r_min
            self.start = 0
            self.hint_text.set(f"继续点击扩大半径 (当前 {self.r}px)")
        elif self.r < self.r_max:
            self.r += 1
            self.hint_text.set(f"半径: {self.r}px")
        self.radius_label.config(text=str(self.r))
        self._render()

    def _on_right_click(self, event) -> None:
        if self.start == 0 and self.r > self.r_min:
            self.r -= 1
            self.radius_label.config(text=str(self.r))
            self.hint_text.set(f"半径: {self.r}px")
            self._render()

    def _on_motion(self, event) -> None:
        self.hover_pos = self._to_original(event.x, event.y)
        self._render()

    def _on_key(self, event) -> None:
        k = event.char.lower()
        if k == "s":
            self._save_sample()
        elif k == "b":
            self._undo()
        elif k == "q":
            self._finish_phase()

    def _save_sample(self) -> None:
        if self.start != 0:
            self.hint_text.set("请先点击放置圆形再保存")
            return
        self.sid += 1
        self.num_class += 1
        self.cent.append(self.point1)
        nms_dir = self.sample_dir / "nms"
        src_dir = self.sample_dir / "source"
        nms_dir.mkdir(parents=True, exist_ok=True)
        src_dir.mkdir(parents=True, exist_ok=True)

        idx, tidx, cidx, tcidx, sr, _ = self._sample(self.point1, self.r, self.sid, 4, self.bg)
        self.ind[self.num_class] = idx
        self.tind[self.num_class] = tidx
        self.cnd[self.num_class] = cidx
        self.tcnd[self.num_class] = tcidx
        self.rnd[self.num_class] = sr

        self.start = 1
        ph = "病灶" if self.bg == 0 else "背景"
        self.hint_text.set(f"已保存第 {self.num_class} 个 {ph} 采样点")
        self._update_phase_label()
        self._render()

    def _sample(self, poi, rad, sid, step=4, mode=0):
        r_min = self.r_min if mode == 0 else self.r_min * 2 - 1
        r_max = self.r_max
        cv = 255 if mode == 0 else 128
        dic, tdic, c_ind, t_ind = {}, {}, {}, {}
        lst = list(range(r_max, r_min - 1, -step))
        sr = max(math.ceil((r_max - rad) / step), 2)
        if rad in lst:
            lst.remove(rad)
        lst.insert(0, rad)
        nms_dir, src_dir = str(self.sample_dir / "nms"), str(self.sample_dir / "source")

        scale = 0
        for R in lst:
            scale += 1
            sp = pow(math.ceil(rad / R), 2)
            dic[scale] = (R, sp)
            tdic[scale] = (R, sp)
            area = np.zeros(self.sp, dtype=np.uint8)
            if R > rad:
                p_new = [(self.sp[1] // 2, self.sp[0] // 2)]
            else:
                cv2.circle(area, poi, rad - R, (255, 255, 255), -1)
                idx = np.nonzero(area == 255)
                pl = list(zip(idx[1], idx[0]))
                p_new = pl if len(pl) <= sp else random.sample(pl, sp)
            c_ind[scale] = p_new
            t_ind[scale] = p_new

            for i, c in enumerate(p_new):
                m = np.zeros(self.sp, dtype=np.uint8)
                cv2.circle(m, c, R, (cv, cv, cv), -1)
                cv2.imwrite(f"{src_dir}/c-{sid}-{scale}-{i+1}.png", m)
                sc = self.cv_img.copy()
                sc[m == 0] = 0
                cv2.imwrite(f"{nms_dir}/c-{sid}-{scale}-{i+1}.png", sc)
                rt = R // 2
                mt, me = self._tri(c, rt, cv)
                mt = mt - me
                cv2.imwrite(f"{src_dir}/t-{sid}-{scale}-{i+1}.png", mt)
                sct = self.cv_img.copy()
                sct[mt == 0] = 0
                cv2.imwrite(f"{nms_dir}/t-{sid}-{scale}-{i+1}.png", sct)
        return dic, tdic, c_ind, t_ind, sr, []

    def _tri(self, center, rt, col):
        pic = np.zeros(self.sp, np.uint8)
        cv2.circle(pic, center, rt, (255, 255, 255), -1)
        edge = np.zeros(self.sp, np.uint8)
        gray = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        cts, _ = cv2.findContours(binary, 1, 2)
        if cts:
            trg = np.array(cv2.minEnclosingTriangle(np.array(cts[0], np.float32))[1], np.int32)
            cv2.fillPoly(pic, [trg], (col, col, col))
            cv2.polylines(edge, [trg], True, (1, 1, 1), 1)
        return pic, edge

    def _undo(self) -> None:
        if self.num_class == 0:
            self.hint_text.set("无可撤销的采样点")
            return
        self.cent.pop()
        for d in [self.ind, self.tind, self.cnd, self.tcnd, self.rnd]:
            d.pop(self.num_class, None)
        self.num_class -= 1
        self.sid -= 1
        self.start = 1
        self._update_phase_label()
        self.hint_text.set(f"已撤销，剩余 {self.num_class} 个")
        self._render()

    def _clear(self) -> None:
        self.cent.clear()
        self.ind.clear()
        self.tind.clear()
        self.cnd.clear()
        self.tcnd.clear()
        self.rnd.clear()
        self.num_class = 0
        self.sid = 0
        self.start = 1
        self.bg = 0
        self.trnum = 0
        self._update_phase_label()
        self.hint_text.set("已清空")
        self._render()

    def _finish_phase(self) -> None:
        if self.bg == 0:
            if self.num_class == 0:
                self.hint_text.set("请至少保存一个病灶采样点")
                return
            self.trnum = self.num_class
            self.bg = 1
            self.num_class = 0
            self.sid = 0
            self.start = 1
            self._update_phase_label()
            self.hint_text.set("病灶采样完成，请在背景区域采样后按 Q 结束")
            self._render()
        else:
            self._save_pkl()
            if self.on_finished:
                self.on_finished(self.sample_dir)

    def _save_pkl(self) -> None:
        self.sample_dir.mkdir(parents=True, exist_ok=True)
        for name, obj in [
            ("cent.pkl", self.cent),
            ("ind.pkl", self.ind),
            ("cnd.pkl", self.cnd),
            ("tcnd.pkl", self.tcnd),
            ("tind.pkl", self.tind),
            ("sp.pkl", self.sp),
            ("trnum.pkl", self.trnum),
            ("rnd.pkl", self.rnd),
        ]:
            with open(self.sample_dir / name, "wb") as f:
                pickle.dump(obj, f)

    def _update_phase_label(self) -> None:
        if self.bg == 0:
            self.phase_badge.config(
                text=f"🔵 病灶采样  ({self.num_class}个)",
                bg=Theme.PRIMARY_LIGHT, fg=Theme.PRIMARY,
            )
            self.phase_indicator.config(text="● 阶段 1/2 · 病灶采样",
                                        fg=Theme.PRIMARY)
        else:
            self.phase_badge.config(
                text=f"🟡 背景采样  ({self.num_class}个)",
                bg=Theme.WARNING_LIGHT, fg=Theme.WARNING,
            )
            self.phase_indicator.config(text="● 阶段 2/2 · 背景采样",
                                        fg=Theme.WARNING)


# ──────────────────────────────────────────────────────────────────────
# 主窗口
# ──────────────────────────────────────────────────────────────────────
class YOHODesktop(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.paths = PipelinePaths()
        self.paths.ensure()
        self.title("YOHO Desktop · 单机病变分割工作台")
        self.geometry("1440x900")
        self.minsize(1240, 800)
        self.configure(bg=Theme.BG_APP)

        self.case_name = tk.StringVar(value="dummy")
        self.status_text = tk.StringVar(value="准备就绪")
        self.case_status = tk.StringVar(value="尚未选择病例")
        self.step_buttons: dict[str, StepButton] = {}

        self._build_ttk_style()
        self._build_layout()

    # ── ttk 样式 (用于内置 widgets 如 Scale / Progressbar / Entry) ──
    def _build_ttk_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=Theme.BG_CARD)
        style.configure("TLabel", background=Theme.BG_CARD,
                        foreground=Theme.FG_BODY, font=Theme.FONT_BODY)
        style.configure("TEntry", padding=8, fieldbackground=Theme.BG_INPUT,
                        bordercolor=Theme.BG_DIVIDER, relief="flat")
        style.configure("TButton", padding=8, font=Theme.FONT_BTN)
        style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor="#e2e8f0", bordercolor="#e2e8f0",
            background=Theme.PRIMARY, lightcolor=Theme.PRIMARY,
            darkcolor=Theme.PRIMARY_DARK, thickness=10,
        )
        style.configure(
            "TLabelframe",
            background=Theme.BG_CARD,
            foreground=Theme.FG_TITLE,
            bordercolor=Theme.BG_DIVIDER,
        )
        style.configure(
            "TLabelframe.Label",
            background=Theme.BG_CARD,
            foreground=Theme.FG_TITLE,
            font=Theme.FONT_SECTION,
        )

    # ── 布局 ──
    def _build_layout(self) -> None:
        # 主体: 左侧步骤 + 右侧日志/信息
        body = tk.Frame(self, bg=Theme.BG_APP)
        body.pack(fill="both", expand=True, padx=18, pady=(12, 8))
        self._build_sidebar(body)
        self._build_main_panel(body)
        # 底部状态栏
        self._build_status_bar()

    def _build_sidebar(self, parent) -> None:
        sidebar_card = Card(parent)
        sidebar_card.pack(side="left", fill="y", padx=(0, 14))
        side = sidebar_card.inner
        side.configure(width=320)
        side.pack_propagate(False)

        # ── Logo 区块 ──
        logo_frame = tk.Frame(side, bg=Theme.BG_CARD)
        logo_frame.pack(fill="x", padx=16, pady=(18, 0))
        icon_bg = tk.Frame(logo_frame, bg=Theme.PRIMARY, width=32, height=32)
        icon_bg.pack(side="left", padx=(0, 10))
        icon_bg.pack_propagate(False)
        tk.Label(icon_bg, text="Y", bg=Theme.PRIMARY, fg=Theme.FG_INV,
                 font=("Segoe UI", 15, "bold")).pack(expand=True)
        text_block = tk.Frame(logo_frame, bg=Theme.BG_CARD)
        text_block.pack(side="left")
        tk.Label(text_block, text="YOHO",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        tk.Label(text_block, text="病变分割工作台",
                 bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL).pack(anchor="w")

        ttk.Separator(side, orient="horizontal").pack(fill="x", padx=16, pady=(14, 10))

        # ── 病例区块 ──
        case_section = tk.Frame(side, bg=Theme.BG_CARD)
        case_section.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(case_section, text="📁  病例",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(anchor="w")
        tk.Label(case_section, textvariable=self.case_status,
                 bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL).pack(anchor="w", pady=(2, 8))

        # 病例输入框 (带美化容器)
        entry_wrap = tk.Frame(case_section, bg=Theme.BG_INPUT, highlightthickness=1,
                              highlightbackground=Theme.BG_DIVIDER, highlightcolor=Theme.PRIMARY)
        entry_wrap.pack(fill="x")
        tk.Label(entry_wrap, text="ID", bg=Theme.BG_INPUT, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL, padx=10).pack(side="left")
        tk.Entry(entry_wrap, textvariable=self.case_name, relief="flat",
                 bg=Theme.BG_INPUT, fg=Theme.FG_BODY,
                 font=Theme.FONT_BODY, bd=0).pack(side="left", fill="x",
                                                  expand=True, ipady=8, padx=4)

        # 选择图像按钮 — 诊所页面的按钮风格 (青色 + 白字)
        HoverButton(
            case_section, "选择内镜图像", self._pick_image, icon="🖼",
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            hover_bg=Theme.PRIMARY_DARK, hover_fg=Theme.FG_INV,
            anchor="center", padx=12, pady=10,
            font=Theme.FONT_BTN_BOLD,
        ).pack(fill="x", pady=(10, 0))

        ttk.Separator(side, orient="horizontal").pack(fill="x", padx=16, pady=14)

        # 工作流标题
        tk.Label(side, text="工作流",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(
            anchor="w", padx=16)

        # 步骤按钮 — 参考诊所页面的服务卡片风格
        steps_def = [
            (1, "标注 ROI", "✏️", self._open_roi_editor, "roi"),
            (2, "检查 ROI", "🔍", self._run_roi_check, "roi_check"),
            (3, "交互采样", "🎯", self._run_sample, "sample"),
            (4, "生成训练集", "📦", self._run_dataset, "dataset"),
            (5, "生成索引", "📑", self._run_index, "index"),
            (6, "开始训练", "🚀", self._run_train, "train"),
            (7, "开始预测", "🔮", self._run_predict, "predict"),
        ]
        for no, title, icon, cmd, key in steps_def:
            btn = StepButton(side, no, title, cmd, icon=icon)
            btn.pack(fill="x", padx=14, pady=3)
            self.step_buttons[key] = btn

        # 一键运行 + 设置
        ttk.Separator(side, orient="horizontal").pack(fill="x", padx=16, pady=(14, 10))
        PrimaryButton(
            side, "一键全流程运行", self._run_all, icon="⚡",
        ).pack(fill="x", padx=14)
        HoverButton(
            side, "参数设置", self._open_settings, icon="⚙",
            bg=Theme.BG_CARD, fg=Theme.FG_BODY,
            hover_bg=Theme.BG_HOVER, hover_fg=Theme.PRIMARY,
            anchor="center", padx=12, pady=10,
        ).pack(fill="x", padx=14, pady=(8, 8))
        HoverButton(
            side, "打开 ROI 目录", self._open_roi_dir, icon="📂",
            bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
            hover_bg=Theme.BG_HOVER, hover_fg=Theme.FG_BODY,
            anchor="center", padx=12, pady=8,
            font=Theme.FONT_SMALL,
        ).pack(fill="x", padx=14, pady=(0, 16))

    def _build_main_panel(self, parent) -> None:
        # ── 可切换的右侧容器 ──
        self._right_container = tk.Frame(parent, bg=Theme.BG_APP)
        self._right_container.pack(side="left", fill="both", expand=True)
        self._active_editor = None

        # ── 默认视图 (预览 + 日志) ──
        self._default_view = tk.Frame(self._right_container, bg=Theme.BG_APP)
        self._default_view.pack(fill="both", expand=True)
        right = self._default_view

        # ── 图像预览区 (上方 ~60%) ──
        preview_card = Card(right)
        preview_card.pack(fill="both", expand=True, pady=(0, 10))
        preview_inner = preview_card.inner

        preview_header = tk.Frame(preview_inner, bg=Theme.BG_CARD, height=36)
        preview_header.pack(fill="x", padx=2)
        preview_header.pack_propagate(False)
        tk.Label(preview_header, text="🔬  图像预览",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(side="left", padx=20, pady=8)
        self._preview_name = tk.Label(
            preview_header, text="未加载",
            bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
            font=Theme.FONT_SMALL,
        )
        self._preview_name.pack(side="left", padx=(8, 0), pady=8)

        ttk.Separator(preview_inner, orient="horizontal").pack(fill="x")

        self._preview_canvas = tk.Canvas(
            preview_inner, bg="#eef2f7", highlightthickness=0,
        )
        self._preview_canvas.pack(fill="both", expand=True, padx=2, pady=2)
        self._preview_photo = None  # keep reference

        # ── 日志区 (下方 ~40%) ──
        log_card = Card(right)
        log_card.pack(fill="both", expand=False, ipady=0)
        # 给日志区固定高度
        log_card.configure(height=260)
        log_card.pack_propagate(False)
        log_inner = log_card.inner

        log_header = tk.Frame(log_inner, bg=Theme.BG_CARD, height=42)
        log_header.pack(fill="x", padx=2)
        log_header.pack_propagate(False)

        tk.Label(log_header, text="📋  日志",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(side="left", padx=20, pady=12)

        # 状态指示（替代统计卡）
        self._status_badge = tk.Label(
            log_header, textvariable=self.status_text,
            bg=Theme.PRIMARY_LIGHT, fg=Theme.PRIMARY,
            font=Theme.FONT_BADGE, padx=10, pady=3,
        )
        self._status_badge.pack(side="left", padx=(8, 0), pady=10)

        HoverButton(
            log_header, "", self._clear_log, icon="🗑",
            bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
            hover_bg=Theme.BG_HOVER, hover_fg=Theme.DANGER,
            anchor="center", padx=10, pady=6,
            font=Theme.FONT_SMALL,
        ).pack(side="right", padx=10, pady=8)

        ttk.Separator(log_inner, orient="horizontal").pack(fill="x")

        # 日志文本框 (深色主题)
        log_wrap = tk.Frame(log_inner, bg=Theme.BG_LOG)
        log_wrap.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(log_wrap, bg=Theme.BG_LOG,
                                 troughcolor="#1e293b", activebackground=Theme.PRIMARY)
        scrollbar.pack(side="right", fill="y")

        self.log = tk.Text(
            log_wrap, wrap="word", relief="flat",
            bg=Theme.BG_LOG, fg=Theme.FG_LOG,
            insertbackground=Theme.FG_LOG,
            font=Theme.FONT_MONO,
            padx=16, pady=12,
            yscrollcommand=scrollbar.set,
        )
        self.log.pack(fill="both", expand=True)
        scrollbar.config(command=self.log.yview)

        # 日志彩色 tag
        self.log.tag_configure("time",    foreground="#64748b")
        self.log.tag_configure("info",    foreground="#60a5fa")
        self.log.tag_configure("success", foreground="#4ade80",
                               font=(Theme.FONT_MONO[0], Theme.FONT_MONO[1], "bold"))
        self.log.tag_configure("warning", foreground="#fbbf24")
        self.log.tag_configure("error",   foreground="#f87171",
                               font=(Theme.FONT_MONO[0], Theme.FONT_MONO[1], "bold"))
        self.log.tag_configure("step",    foreground="#a78bfa",
                               font=(Theme.FONT_MONO[0], Theme.FONT_MONO[1], "bold"))

        self._append_log("YOHO 已就绪", level="success")
        self.log.configure(state="disabled")

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bg=Theme.BG_HEADER_ACC, height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Label(
            bar, text=f"{self.paths.project_root}",
            bg=Theme.BG_HEADER_ACC, fg=Theme.FG_INV_MUTED,
            font=Theme.FONT_SMALL,
        ).pack(side="left", padx=16, pady=6)
        tk.Label(
            bar, text="YOHO v1.0 · MIT",
            bg=Theme.BG_HEADER_ACC, fg=Theme.FG_INV_MUTED,
            font=Theme.FONT_SMALL,
        ).pack(side="right", padx=16, pady=6)

    # ── 日志 ──
    def _append_log(self, text: str, level: str = "info") -> None:
        self.after(0, self._do_append_log, text, level)

    def _do_append_log(self, text: str, level: str = "info") -> None:
        self.log.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] ", "time")

        icon_map = {
            "info":    "ℹ",
            "success": "✓",
            "warning": "⚠",
            "error":   "✗",
            "step":    "▶",
        }
        icon = icon_map.get(level, "•")
        self.log.insert("end", f"{icon} ", level)
        self.log.insert("end", text.rstrip() + "\n", level)
        self.log.see("end")
        self.log.configure(state="disabled")
        self.status_text.set(text[:80])

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._append_log("日志已清空", level="info")

    # ── 文件操作 ──
    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(self.paths.image_dir),
            filetypes=[("Image", "*.png;*.jpg;*.jpeg")])
        if path:
            selected = Path(path)
            target = self.paths.image_dir / (selected.stem + ".png")
            if selected.suffix.lower() != ".png":
                Image.open(selected).convert("RGB").save(target)
            elif selected.resolve() != target.resolve():
                Image.open(selected).convert("RGB").save(target)
            self.case_name.set(selected.stem)
            self.case_status.set(f"当前病例: {selected.stem}")
            self._append_log(f"已选择图像: {target}", level="success")
            self._update_preview(target)

    def _update_preview(self, image_path: Path) -> None:
        """在右侧预览区加载并显示病例图像."""
        try:
            self._preview_canvas.update_idletasks()
            cw = max(self._preview_canvas.winfo_width(), 400)
            ch = max(self._preview_canvas.winfo_height(), 300)
            img = Image.open(image_path).convert("RGB")
            img.thumbnail((cw - 20, ch - 20))
            self._preview_photo = ImageTk.PhotoImage(img)
            self._preview_canvas.delete("all")
            ox = (cw - img.width) // 2
            oy = (ch - img.height) // 2
            self._preview_canvas.create_image(ox, oy, anchor="nw",
                                               image=self._preview_photo)
            self._preview_name.config(text=image_path.name)
        except Exception:
            self._preview_canvas.delete("all")
            self._preview_name.config(text="加载失败")

    def _open_roi_dir(self) -> None:
        self._append_log(f"ROI 目录: {self.paths.roi_dir}", level="info")

    def _show_default_view(self) -> None:
        if self._active_editor is not None:
            self._active_editor.pack_forget()
            self._active_editor.destroy()
            self._active_editor = None
        self._default_view.pack(fill="both", expand=True)

    def _show_editor(self, editor: tk.Frame) -> None:
        self._default_view.pack_forget()
        if self._active_editor is not None:
            self._active_editor.pack_forget()
            self._active_editor.destroy()
        self._active_editor = editor
        editor.pack(in_=self._right_container, fill="both", expand=True)

    def _open_roi_editor(self) -> None:
        image_path = self.paths.image_path(self.case_name.get())
        if not image_path.exists():
            messagebox.showerror("缺少图像", f"请先准备内镜图像: {image_path}")
            return
        roi_path = self.paths.roi_path(self.case_name.get())
        editor = RoiEditor(self._right_container, image_path, roi_path,
                           self._on_roi_saved, on_back=self._show_default_view)
        self._show_editor(editor)

    def _on_roi_saved(self, roi_path: Path) -> None:
        self._append_log(f"ROI 已保存: {roi_path}", level="success")
        self.step_buttons["roi"].mark_done()
        self._show_default_view()

    def _run_roi_check(self) -> None:
        result = run_roi_prep(self.case_name.get(), logger=lambda t: self._append_log(t, "info"))
        if result.code != 0:
            self._append_log(result.output, level="error")
            messagebox.showerror("ROI 检查失败", result.output)
        else:
            self._append_log(result.output, level="success")
            self.step_buttons["roi_check"].mark_done()

    def _run_sample(self) -> None:
        case = self.case_name.get()
        image_path = self.paths.image_path(case)
        sample_dir = self.paths.sample_case_dir(case)
        if not image_path.exists():
            messagebox.showerror("缺少图像", f"请先准备内镜图像: {image_path}")
            return
        roi_path = self.paths.roi_path(case)
        if roi_path.exists():
            sample_dir.mkdir(parents=True, exist_ok=True)
            editor = SamplingEditor(self._right_container, image_path, sample_dir,
                                    self._on_sample_done, on_back=self._show_default_view)
            self._show_editor(editor)
        else:
            messagebox.showerror("缺少 ROI", f"请先标注 ROI:\n{roi_path}")

    def _on_sample_done(self, sample_dir: Path) -> None:
        self._append_log(f"交互采样完成: {sample_dir}", level="success")
        self.step_buttons["sample"].mark_done()
        self._show_default_view()

    def _run_step_async(self, step_fn, step_name, error_title, done_key=None):
        self._append_log(f"开始执行: {step_name}", level="step")
        def task():
            try:
                result = step_fn()
                self.after(0, self._handle_step_result, result, step_name, error_title, done_key)
            except Exception as e:
                self.after(0, lambda: self._append_log(f"{step_name} 异常: {e}", level="error"))
                self.after(0, lambda: messagebox.showerror(error_title, str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _handle_step_result(self, result, step_name, error_title, done_key=None):
        if result.code != 0:
            self._append_log(f"{step_name} 失败: {result.output}", level="error")
            messagebox.showerror(error_title, result.output)
        else:
            self._append_log(f"{step_name} 完成 ✓", level="success")
            if done_key and done_key in self.step_buttons:
                self.step_buttons[done_key].mark_done()

    def _run_dataset(self) -> None:
        case = self.case_name.get()
        self._append_log("开始生成训练集...", level="step")

        dlg = tk.Toplevel(self)
        dlg.title("生成训练集")
        dlg.geometry("400x160")
        dlg.configure(bg=Theme.BG_CARD)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        # 顶部色条
        tk.Frame(dlg, bg=Theme.PRIMARY, height=4).pack(fill="x")

        tk.Label(dlg, text="📦  生成训练集",
                 bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                 font=Theme.FONT_SECTION).pack(pady=(20, 4))
        tk.Label(dlg, text="正在处理，请稍候",
                 bg=Theme.BG_CARD, fg=Theme.FG_MUTED,
                 font=Theme.FONT_SMALL).pack()

        pb = ttk.Progressbar(dlg, length=360, mode="determinate",
                             style="Modern.Horizontal.TProgressbar")
        pb.pack(pady=14)
        pct_var = tk.StringVar(value="0%")
        tk.Label(dlg, textvariable=pct_var, bg=Theme.BG_CARD,
                 fg=Theme.PRIMARY,
                 font=("Microsoft YaHei UI", 13, "bold")).pack()

        def _update_progress(current: int, total: int) -> None:
            self.after(0, _do_update, current, total)

        def _do_update(current: int, total: int) -> None:
            pct = min(int(current / total * 100), 100)
            pb["value"] = pct
            pct_var.set(f"{pct}%")
            if pct >= 100:
                try:
                    dlg.destroy()
                except tk.TclError:
                    pass

        def _on_done():
            try:
                dlg.destroy()
            except tk.TclError:
                pass

        def task():
            try:
                result = run_generate_dataset(
                    case, logger=lambda t: self._append_log(t, "info"),
                    progress_callback=_update_progress)
                self.after(0, _on_done)
                self.after(0, self._handle_step_result, result, "生成训练集", "生成失败", "dataset")
            except Exception as e:
                self.after(0, _on_done)
                self.after(0, lambda: self._append_log(f"生成失败: {e}", level="error"))
                self.after(0, lambda: messagebox.showerror("生成失败", str(e)))

        threading.Thread(target=task, daemon=True).start()

    def _run_index(self) -> None:
        self._run_step_async(
            lambda: run_build_index(logger=lambda t: self._append_log(t, "info")),
            "生成索引", "索引失败", "index")

    def _run_train(self) -> None:
        case = self.case_name.get()
        self._run_step_async(
            lambda: run_train(case, logger=lambda t: self._append_log(t, "info")),
            "训练", "训练失败", "train")

    def _run_predict(self) -> None:
        case = self.case_name.get()
        self._run_step_async(
            lambda: run_predict(case, logger=lambda t: self._append_log(t, "info")),
            "预测", "预测失败", "predict")

    # ── 参数设置 ──
    @property
    def _config_path(self) -> Path:
        return self.paths.project_root / "config.json"

    def _load_config(self) -> dict:
        try:
            with open(self._config_path) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self, data: dict) -> None:
        with open(self._config_path, "w") as f:
            json.dump(data, f, indent=2)

    def _open_settings(self) -> None:
        cfg = self._load_config()
        dlg = tk.Toplevel(self)
        dlg.title("参数设置")
        dlg.geometry("560x600")
        dlg.minsize(560, 560)
        dlg.configure(bg=Theme.BG_APP)
        dlg.transient(self)
        dlg.grab_set()

        # 顶部标题条
        header = tk.Frame(dlg, bg=Theme.BG_HEADER, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        icon_lbl = tk.Frame(header, bg=Theme.PRIMARY, width=28, height=28)
        icon_lbl.pack(side="left", padx=(20, 10), pady=14)
        icon_lbl.pack_propagate(False)
        tk.Label(icon_lbl, text="⚙", bg=Theme.PRIMARY, fg=Theme.FG_INV,
                 font=("Segoe UI", 14)).pack(expand=True)
        tk.Label(header, text="参数设置",
                 bg=Theme.BG_HEADER, fg=Theme.FG_INV,
                 font=("Microsoft YaHei UI", 14, "bold")).pack(side="left", pady=16)

        # 可滚动区
        body = tk.Frame(dlg, bg=Theme.BG_APP)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        canvas = tk.Canvas(body, bg=Theme.BG_APP, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        main = tk.Frame(canvas, bg=Theme.BG_APP)
        main.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw", width=500)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 配置卡片公用样式
        def section_card(title, icon):
            sec = Card(main)
            sec.pack(fill="x", pady=(0, 12))
            inner = sec.inner
            head = tk.Frame(inner, bg=Theme.BG_CARD)
            head.pack(fill="x", padx=14, pady=(12, 6))
            tk.Label(head, text=f"{icon}  {title}",
                     bg=Theme.BG_CARD, fg=Theme.FG_TITLE,
                     font=Theme.FONT_SECTION).pack(anchor="w")
            return inner

        def row_field(parent, label, var):
            row = tk.Frame(parent, bg=Theme.BG_CARD)
            row.pack(fill="x", padx=14, pady=6)
            tk.Label(row, text=label, bg=Theme.BG_CARD,
                     fg=Theme.FG_BODY, font=Theme.FONT_BODY,
                     width=22, anchor="w").pack(side="left")

            wrap = tk.Frame(row, bg=Theme.BG_INPUT, highlightthickness=1,
                            highlightbackground=Theme.BG_DIVIDER)
            wrap.pack(side="left", fill="x", expand=True)
            tk.Entry(wrap, textvariable=var, relief="flat",
                     bg=Theme.BG_INPUT, fg=Theme.FG_BODY,
                     font=Theme.FONT_BODY, bd=0).pack(fill="x",
                                                      ipady=6, padx=8)

        # 数据集
        grp1 = section_card("数据集生成", "📦")
        sv_sample = tk.StringVar(value=str(cfg.get("dataset", {}).get("sample_count", 50)))
        row_field(grp1, "样本数 (number)", sv_sample)
        tk.Frame(grp1, bg=Theme.BG_CARD, height=10).pack()

        # 训练
        grp2 = section_card("训练参数", "🚀")
        tc = cfg.get("training", {})
        fields = [
            ("冻结阶段轮数", "freeze_epochs", "20"),
            ("解冻阶段轮数 (总计)", "unfreeze_epochs", "30"),
            ("冻结阶段批大小", "freeze_batch_size", "32"),
            ("解冻阶段批大小", "unfreeze_batch_size", "32"),
            ("冻结阶段学习率", "freeze_lr", "0.001"),
            ("解冻阶段学习率", "unfreeze_lr", "3e-5"),
        ]
        vars_ = {}
        for label, key, default in fields:
            v = tk.StringVar(value=str(tc.get(key, default)))
            vars_[key] = v
            row_field(grp2, label, v)
        tk.Frame(grp2, bg=Theme.BG_CARD, height=10).pack()

        # 预测
        grp3 = section_card("预测", "🔮")
        sv_epoch = tk.StringVar(value=str(cfg.get("prediction", {}).get("model_epoch", "30")))
        row_field(grp3, "模型轮次", sv_epoch)
        tk.Frame(grp3, bg=Theme.BG_CARD, height=10).pack()

        # 底部按钮区
        btn_bar = tk.Frame(dlg, bg=Theme.BG_APP)
        btn_bar.pack(fill="x", padx=18, pady=(0, 16))

        def _do_save():
            try:
                new_cfg = {
                    "dataset": {"sample_count": int(sv_sample.get())},
                    "training": {k: _parse_num(vars_[k].get()) for k in vars_},
                    "prediction": {"model_epoch": int(sv_epoch.get())},
                }
                self._save_config(new_cfg)
                dlg.destroy()
                self._append_log("参数已保存至 config.json", level="success")
            except Exception as e:
                messagebox.showerror("保存失败", f"{type(e).__name__}: {e}", parent=dlg)

        HoverButton(
            btn_bar, "保存设置", _do_save, icon="💾",
            bg=Theme.PRIMARY, fg=Theme.FG_INV,
            hover_bg=Theme.PRIMARY_DARK, hover_fg=Theme.FG_INV,
            anchor="center", padx=20, pady=10,
            font=Theme.FONT_BTN_BOLD,
        ).pack(side="right", padx=4)
        HoverButton(
            btn_bar, "取消", dlg.destroy,
            bg=Theme.BG_CARD, fg=Theme.FG_BODY,
            hover_bg=Theme.DANGER_LIGHT, hover_fg=Theme.DANGER,
            anchor="center", padx=20, pady=10,
        ).pack(side="right", padx=4)

    def _run_all(self) -> None:
        case = self.case_name.get()
        self._append_log("全流程开始", level="step")
        def task():
            try:
                for result in run_full_pipeline(case, logger=lambda t: self._append_log(t, "info")):
                    if result.code != 0:
                        raise RuntimeError(f"{result.step}: {result.output}")
                    self.after(0, lambda r=result: self._append_log(
                        f"✓ {r.step} 完成", level="success"))
                self.after(0, lambda: self._append_log(
                    "全流程完成", level="success"))
                self.after(0, lambda: messagebox.showinfo("完成", "全流程执行完成。"))
            except Exception as exc:
                self.after(0, lambda: self._append_log(
                    f"全流程失败: {exc}", level="error"))
                self.after(0, lambda: messagebox.showerror("执行失败", str(exc)))
        threading.Thread(target=task, daemon=True).start()


def _parse_num(s: str):
    """解析整数或科学计数法浮点数."""
    s = s.strip()
    if "e" in s or "E" in s:
        return float(s)
    if "." in s:
        return float(s)
    return int(s)


if __name__ == "__main__":
    YOHODesktop().mainloop()
