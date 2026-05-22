"""Thresholding and measurement.

All math runs on the raw pixel array. ``positive`` pixels are those at or
above the threshold (``raw >= threshold``) — matching ImageJ's "dark"
auto-threshold, which selects the bright object on a dark background.

Exclusion boxes (e.g. drawn over a scale bar) remove pixels from both the
positive count *and* the total, so they never affect any measurement.
"""

from __future__ import annotations

import cv2
import numpy as np

from .project import Measurement

# Overlay tint per channel (R, G, B), drawn translucently over positive pixels.
OVERLAY_COLORS = {
    "Green": (40, 255, 70),     # green tint on green/GFP images
    "Red": (255, 40, 220),      # magenta on red/RFP images (visible on red)
}
OVERLAY_ALPHA = 115             # ~45 % opacity
EXCLUDE_RGBA = (140, 140, 140, 160)   # gray fill over excluded regions

# Bright opaque ring drawn just outside marked regions when the tuning-screen
# "highlight marks" aid is on — makes tiny blobs pop. Display only; never
# exported and never affects measurement.
OUTLINE_RGBA = (255, 230, 0, 255)     # high-visibility yellow ring


def apply_threshold(raw: np.ndarray, threshold: int) -> np.ndarray:
    """Boolean mask of positive (>= threshold) pixels."""
    return raw >= threshold


def exclusion_mask(shape, exclusions) -> np.ndarray | None:
    """Build a bool mask (True = excluded) from a list of [x, y, w, h] rects.

    Returns None when there are no exclusions so callers can keep a fast path.
    Rectangles are clamped to the image bounds.
    """
    if not exclusions:
        return None
    h, w = shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    for rect in exclusions:
        x, y, rw, rh = (int(round(v)) for v in rect)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + rw), min(h, y + rh)
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
    return mask


def measure(raw: np.ndarray, threshold: int, method: str = "Manual",
            exclude_mask: np.ndarray | None = None) -> Measurement:
    """Measure the positive region of *raw* at *threshold*.

    Computes all four candidate metrics so the ambiguous "intensity" choice
    can be made later in Excel:
      * positive_pixels       — count of pixels >= threshold
      * positive_area_pct     — that count as a percentage of the image
      * mean_intensity_positive — mean raw value of positive pixels
      * integrated_intensity  — sum of raw values of positive pixels (ImageJ RawIntDen)

    Pixels under *exclude_mask* are dropped from both the positive count and
    the total, so the percentage stays correct.
    """
    if exclude_mask is not None:
        valid = ~exclude_mask
        positive = (raw >= threshold) & valid
        total = int(valid.sum())
    else:
        positive = raw >= threshold
        total = int(raw.size)

    count = int(positive.sum())
    if count > 0:
        vals = raw[positive].astype(np.float64)
        mean_intensity = float(vals.mean())
        integrated = float(vals.sum())
    else:
        mean_intensity = 0.0
        integrated = 0.0

    return Measurement(
        threshold=int(threshold),
        positive_pixels=count,
        total_pixels=total,
        positive_area_pct=(count / total * 100.0) if total else 0.0,
        mean_intensity_positive=mean_intensity,
        integrated_intensity=integrated,
        method=method,
    )


def _outline_mask(mask: np.ndarray, thickness: int = 2) -> np.ndarray:
    """Bool ring just outside *mask* — its dilation minus itself."""
    m = mask.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dilated = cv2.dilate(m, kernel, iterations=thickness)
    return (dilated > 0) & ~mask


def overlay_rgba(positive: np.ndarray, channel: str,
                 exclude_mask: np.ndarray | None = None,
                 outline: bool = False) -> np.ndarray:
    """Build an HxWx4 uint8 RGBA overlay.

    Positive pixels get the channel tint; excluded pixels get a gray fill
    (and are never shown as positive, since they are not counted).

    When *outline* is True a bright opaque ring is drawn just outside each
    marked region — a tuning-screen aid for spotting small blobs. It is not
    used for export and does not affect any measurement.
    """
    color = OVERLAY_COLORS.get(channel, OVERLAY_COLORS["Green"])
    h, w = positive.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    counted = positive & ~exclude_mask if exclude_mask is not None else positive
    rgba[counted] = (color[0], color[1], color[2], OVERLAY_ALPHA)
    if outline and counted.any():
        rgba[_outline_mask(counted)] = OUTLINE_RGBA
    if exclude_mask is not None:
        rgba[exclude_mask] = EXCLUDE_RGBA
    return rgba
