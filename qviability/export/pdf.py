"""QC PDF export — one page per image, the original beside the marked version.

A flip-through visual record for final quality control: on each page the
reviewer sees the plain image ("Before") and exactly which pixels the chosen
threshold counted ("After"), side by side. The rendering reuses the same
display pipeline as the annotated PNGs, so the PDF matches what was exported.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..core import image_io
from ..core.project import ImageEntry, Project
from . import annotate

# Page geometry, in pixels (saved at 150 DPI -> ~10 x 7 inch landscape).
PAGE_W, PAGE_H = 1500, 1060
MARGIN = 40
GUTTER = 28
HEADER_H = 84               # room for the two header text lines
LABEL_H = 32                # room for the "Before" / "After" panel labels

PAGE_BG = (255, 255, 255)
PANEL_BG = (24, 24, 24)
PANEL_BORDER = (170, 170, 170)
INK = (20, 20, 20)
SUBINK = (95, 95, 95)


def _fmt_int(n: float) -> str:
    return f"{round(n):,}"


def _panel(rgb: np.ndarray, box_w: int, box_h: int) -> Image.Image:
    """Scale *rgb* to fit a box (aspect preserved) on a dark panel background."""
    panel = Image.new("RGB", (box_w, box_h), PANEL_BG)
    img = Image.fromarray(np.ascontiguousarray(rgb))
    img.thumbnail((box_w, box_h), Image.Resampling.LANCZOS)
    panel.paste(img, ((box_w - img.width) // 2, (box_h - img.height) // 2))
    return panel


def render_qc_page(project: Project, entry: ImageEntry) -> Image.Image | None:
    """Render one QC page for *entry*.

    Returns None if the image cannot be read or *entry* has no threshold yet.
    """
    if entry.threshold is None:
        return None
    try:
        raw = image_io.get_processed(entry.path, project.subtract_background,
                                     project.radius_for(entry.channel))
    except Exception:                                  # noqa: BLE001
        return None

    before = annotate.render_display_rgb(
        raw, entry.brightness, entry.contrast)
    after = annotate.render_overlay_rgb(
        raw, entry.threshold, entry.channel,
        entry.brightness, entry.contrast, entry.exclusions)

    page = Image.new("RGB", (PAGE_W, PAGE_H), PAGE_BG)
    draw = ImageDraw.Draw(page)

    # Header --------------------------------------------------------------
    title_font = annotate._load_font(30)
    sub_font = annotate._load_font(20)
    label_font = annotate._load_font(22)

    draw.text((MARGIN, MARGIN), entry.display_name, fill=INK, font=title_font)

    m = entry.measurement
    parts = [entry.channel, f"threshold {entry.threshold}"]
    if m:
        parts.append(f"positive area {m.positive_area_pct:.2f}%")
        parts.append(f"integrated intensity {_fmt_int(m.integrated_intensity)}")
    if project.subtract_background:
        parts.append("background subtracted")
    draw.text((MARGIN, MARGIN + 40), "     ".join(parts),
              fill=SUBINK, font=sub_font)

    # Two panels ----------------------------------------------------------
    panel_top = MARGIN + HEADER_H + LABEL_H
    panel_h = PAGE_H - panel_top - MARGIN
    panel_w = (PAGE_W - 2 * MARGIN - GUTTER) // 2

    for i, (label, rgb) in enumerate((("Before  (original)", before),
                                      ("After  (marked = counted)", after))):
        x0 = MARGIN + i * (panel_w + GUTTER)
        draw.text((x0, MARGIN + HEADER_H), label, fill=INK, font=label_font)
        page.paste(_panel(rgb, panel_w, panel_h), (x0, panel_top))
        draw.rectangle([x0, panel_top, x0 + panel_w - 1,
                        panel_top + panel_h - 1], outline=PANEL_BORDER, width=1)

    return page


def save_pdf(pages: list[Image.Image], out_path: str) -> None:
    """Write *pages* as a single multi-page PDF at *out_path*."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(str(out), "PDF", save_all=True,
                  append_images=pages[1:], resolution=150.0)
