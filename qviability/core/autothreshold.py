"""Automatic threshold seeds.

The default method is MaxEntropy (Kapur), reproducing ImageJ's
``setAutoThreshold("MaxEntropy dark")`` so each image opens at the threshold
the user is already used to. Otsu / Yen / Li / IsoData are offered for
comparison via scikit-image.
"""

from __future__ import annotations

import numpy as np
from skimage.filters import (threshold_isodata, threshold_li, threshold_otsu,
                             threshold_yen)

# Ordered for the UI dropdown; MaxEntropy first = default.
METHOD_NAMES = ["MaxEntropy", "Otsu", "Yen", "Li", "IsoData"]


def _kapur_threshold(hist: np.ndarray) -> int:
    """Kapur maximum-entropy threshold over a 256-bin histogram.

    Returns the bin index that maximizes the sum of background and foreground
    Shannon entropies — the same criterion as ImageJ's MaxEntropy.
    """
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0
    p = hist / total

    cum_p = np.cumsum(p)                      # P1(t): background mass
    with np.errstate(divide="ignore", invalid="ignore"):
        plogp = np.where(p > 0, p * np.log(p), 0.0)
    cum_plogp = np.cumsum(plogp)
    total_plogp = cum_plogp[-1]

    best_t, best_val = 0, -np.inf
    for t in range(256):
        p1 = cum_p[t]
        p2 = 1.0 - p1
        if p1 < 1e-12 or p2 < 1e-12:
            continue
        h_back = np.log(p1) - cum_plogp[t] / p1
        h_fore = np.log(p2) - (total_plogp - cum_plogp[t]) / p2
        val = h_back + h_fore
        if val > best_val:
            best_val, best_t = val, t
    return best_t


def threshold_maxentropy(arr: np.ndarray, maxval: int) -> int:
    """MaxEntropy threshold for *arr*, returned as a raw pixel value in [0, maxval]."""
    hist, _ = np.histogram(arr, bins=256, range=(0, maxval + 1))
    t_bin = _kapur_threshold(hist)
    # Kapur splits at t_bin; the bright foreground starts just above it.
    raw = (t_bin + 1) / 256.0 * (maxval + 1)
    return int(min(round(raw), maxval))


def auto_threshold(arr: np.ndarray, maxval: int, method: str = "MaxEntropy") -> int:
    """Compute an auto-threshold for *arr* using *method*.

    Always returns a sensible int in [0, maxval]; falls back to the mean if a
    method fails on a degenerate (e.g. flat) image.
    """
    try:
        if method == "MaxEntropy":
            return threshold_maxentropy(arr, maxval)
        if method == "Otsu":
            value = threshold_otsu(arr)
        elif method == "Yen":
            value = threshold_yen(arr)
        elif method == "Li":
            value = threshold_li(arr)
        elif method == "IsoData":
            value = threshold_isodata(arr)
        else:
            return threshold_maxentropy(arr, maxval)
        return int(min(max(round(float(value)), 0), maxval))
    except Exception:
        return int(min(max(round(float(arr.mean())), 0), maxval))
