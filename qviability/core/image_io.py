"""Image loading and display normalization.

Images are loaded as raw single-channel numpy arrays (uint8 or uint16) — the
*raw* dtype is preserved so thresholding and measurement run on real pixel
values. Display normalization (brightness/contrast) is a separate, purely
cosmetic step that never feeds back into measurement.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

import cv2
import numpy as np
from skimage.restoration import rolling_ball

SUPPORTED_EXTS = {".tif", ".tiff", ".jpg", ".jpeg", ".png"}

BG_RADIUS = 50          # rolling-ball radius (ImageJ "Subtract Background" default)

# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------
def _natural_key(name: str):
    """Sort key so Baf1.2 comes before Baf1.10."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def scan_folder(folder: str) -> list[Path]:
    """Return supported image files in *folder*, natural-sorted, non-recursive."""
    p = Path(folder)
    if not p.is_dir():
        return []
    files = [f for f in p.iterdir()
             if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]
    files.sort(key=lambda f: _natural_key(f.name))
    return files


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_image(path: str) -> np.ndarray:
    """Load *path* as a raw single-channel ndarray (uint8 or uint16).

    RGB/RGBA inputs are converted to grayscale. Float or other dtypes are
    min-max scaled into uint16. Raises RuntimeError on unreadable files.
    """
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"Could not read image: {path}")

    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if img.dtype == np.uint8 or img.dtype == np.uint16:
        return img

    # Unusual dtype (float, int32, ...) — scale into uint16.
    f = img.astype(np.float64)
    lo, hi = float(f.min()), float(f.max())
    if hi <= lo:
        return np.zeros(img.shape, dtype=np.uint16)
    return np.clip((f - lo) / (hi - lo) * 65535.0, 0, 65535).astype(np.uint16)


def bit_depth(arr: np.ndarray) -> int:
    """8 for uint8 images, 16 otherwise."""
    return 8 if arr.dtype == np.uint8 else 16


def max_value(arr: np.ndarray) -> int:
    """Upper bound for the threshold range of *arr*.

    8-bit images use the full 0-255 range (the convention the user knows from
    ImageJ). 16-bit images use their actual maximum so the threshold range and
    histogram stay meaningful for sensors that only fill part of the range.
    """
    if arr.dtype == np.uint8:
        return 255
    m = int(arr.max())
    return max(m, 1)


# ---------------------------------------------------------------------------
# Display normalization (cosmetic only — never used for measurement)
# ---------------------------------------------------------------------------
def auto_stretch(arr: np.ndarray) -> np.ndarray:
    """Percentile-stretch *arr* to a float32 image in [0, 1] for viewing.

    Uses the 0.5 / 99.5 percentiles so dim fluorescence images are visible by
    default. The result is the brightness=0, contrast=1 base view.
    """
    lo = float(np.percentile(arr, 0.5))
    hi = float(np.percentile(arr, 99.5))
    if hi <= lo:
        lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        hi = lo + 1.0
    norm = (arr.astype(np.float32) - lo) / (hi - lo)
    return np.clip(norm, 0.0, 1.0)


def raw_display(arr: np.ndarray, maxval: int) -> np.ndarray:
    """Map raw pixel values linearly to a uint8 image for the unprocessed
    preview — no contrast stretch, no gamma.

    For 8-bit images this is the raw pixels themselves; 16-bit images are
    linearly scaled by *maxval* so they fit an 8-bit screen.
    """
    if arr.dtype == np.uint8:
        return arr
    scaled = arr.astype(np.float32) / max(1, maxval) * 255.0
    return np.clip(scaled, 0, 255).astype(np.uint8)


def apply_display(base: np.ndarray, brightness: float = 0.0,
                  contrast: float = 1.0) -> np.ndarray:
    """Apply brightness/contrast to an auto-stretched *base*, return uint8.

    brightness shifts levels (range roughly -1..1); contrast scales them
    around mid-gray (range roughly 0.1..4.0).
    """
    out = (base - 0.5) * contrast + 0.5 + brightness
    out = np.clip(out, 0.0, 1.0)
    return (out * 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------
# Optional pre-processing: rolling-ball background subtraction
# ---------------------------------------------------------------------------
def subtract_background(arr: np.ndarray, radius: int = BG_RADIUS) -> np.ndarray:
    """Rolling-ball background subtraction (like ImageJ's "Subtract Background").

    Removes smoothly-varying background / uneven illumination. The ball is
    rolled on a downscaled copy for speed — the background is smooth, so this
    closely matches the full-resolution result (ImageJ does the same).
    """
    shrink = 4 if min(arr.shape[:2]) >= 256 else 1
    if shrink > 1:
        small = cv2.resize(arr, (arr.shape[1] // shrink, arr.shape[0] // shrink),
                           interpolation=cv2.INTER_AREA)
        bg_small = rolling_ball(small, radius=max(1, radius // shrink))
        background = cv2.resize(bg_small.astype(np.float32),
                                (arr.shape[1], arr.shape[0]),
                                interpolation=cv2.INTER_LINEAR)
    else:
        background = rolling_ball(arr, radius=radius).astype(np.float32)
    result = arr.astype(np.float32) - background
    np.clip(result, 0, None, out=result)
    return result.astype(arr.dtype)


# ---------------------------------------------------------------------------
# Small LRU cache so re-visiting images during tuning/review is instant
# ---------------------------------------------------------------------------
class _ImageCache:
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self._store: "OrderedDict[str, np.ndarray]" = OrderedDict()

    def get(self, path: str) -> np.ndarray:
        if path in self._store:
            self._store.move_to_end(path)
            return self._store[path]
        arr = load_image(path)
        self._store[path] = arr
        if len(self._store) > self.capacity:
            self._store.popitem(last=False)
        return arr

    def clear(self) -> None:
        self._store.clear()


_CACHE = _ImageCache()
_PROC_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()


def get_image(path: str) -> np.ndarray:
    """Load *path* (cached). Raises RuntimeError on unreadable files."""
    return _CACHE.get(path)


def get_processed(path: str, subtract: bool,
                  radius: int = BG_RADIUS) -> np.ndarray:
    """The working image for *path*: the raw image, or the background-
    subtracted image when *subtract* is True. Cached."""
    raw = get_image(path)
    if not subtract:
        return raw
    key = (path, radius)
    if key in _PROC_CACHE:
        _PROC_CACHE.move_to_end(key)
        return _PROC_CACHE[key]
    result = subtract_background(raw, radius)
    _PROC_CACHE[key] = result
    if len(_PROC_CACHE) > 8:
        _PROC_CACHE.popitem(last=False)
    return result


def clear_cache() -> None:
    _CACHE.clear()
    _PROC_CACHE.clear()
