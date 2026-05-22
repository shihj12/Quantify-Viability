"""Render annotated images: original view + translucent positive-pixel overlay.

``render_overlay_rgb`` is Qt-free and shared by the review-gallery thumbnails
and the PNG export. ``save_annotated_png`` adds a burned-in caption and writes
a lossless PNG.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..core import image_io
from ..core.measure import (EXCLUDE_RGBA, OVERLAY_ALPHA, OVERLAY_COLORS,
                            apply_threshold, exclusion_mask)


def _tint(rgb: np.ndarray, mask: np.ndarray, colour, alpha: float) -> None:
    """Blend *colour* into *rgb* where *mask* is True (in place)."""
    for c in range(3):
        chan = rgb[..., c]
        chan[mask] = chan[mask] * (1.0 - alpha) + colour[c] * alpha


def render_display_rgb(raw: np.ndarray, brightness: float = 0.0,
                       contrast: float = 1.0) -> np.ndarray:
    """Return the plain display view as an HxWx3 uint8 RGB image — no overlay.

    This is the "before" image for QC: exactly what ``render_overlay_rgb``
    starts from, minus the positive-pixel tint.
    """
    base = image_io.auto_stretch(raw)
    disp = image_io.apply_display(base, brightness, contrast)
    return np.stack([disp, disp, disp], axis=-1)


def render_overlay_rgb(raw: np.ndarray, threshold: int, channel: str,
                       brightness: float = 0.0, contrast: float = 1.0,
                       exclusions=None) -> np.ndarray:
    """Return an HxWx3 uint8 RGB image: the display view with positive pixels
    tinted and any exclusion boxes filled gray."""
    rgb = render_display_rgb(raw, brightness, contrast).astype(np.float32)

    excl = exclusion_mask(raw.shape, exclusions)
    positive = apply_threshold(raw, threshold)
    counted = positive & ~excl if excl is not None else positive

    _tint(rgb, counted, OVERLAY_COLORS.get(channel, OVERLAY_COLORS["Green"]),
          OVERLAY_ALPHA / 255.0)
    if excl is not None:
        _tint(rgb, excl, EXCLUDE_RGBA, EXCLUDE_RGBA[3] / 255.0)

    return np.clip(rgb, 0, 255).astype(np.uint8)


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                       # very old Pillow
        return ImageFont.load_default()


def save_annotated_png(raw: np.ndarray, threshold: int, channel: str,
                       caption: str, out_path: str,
                       brightness: float = 0.0, contrast: float = 1.0,
                       exclusions=None) -> None:
    """Render the annotated image with a caption banner and save it as PNG."""
    rgb = render_overlay_rgb(raw, threshold, channel, brightness, contrast,
                             exclusions)
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)

    font = _load_font(max(14, img.width // 70))
    bbox = draw.textbbox((0, 0), caption, font=font)
    pad = 6
    draw.rectangle([(0, 0), (bbox[2] + 2 * pad, bbox[3] + 2 * pad)],
                   fill=(0, 0, 0))
    draw.text((pad, pad), caption, fill=(255, 255, 255), font=font)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
