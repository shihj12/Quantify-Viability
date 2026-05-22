"""Verify the core pipeline handles 16-bit images correctly."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2                                                           # noqa: E402
import numpy as np                                                  # noqa: E402

from qviability.core import autothreshold, image_io, measure         # noqa: E402


def main() -> int:
    # Synthetic 16-bit image: dark background + a few bright blobs,
    # filling only part of the 16-bit range (a realistic sensor).
    rng = np.random.default_rng(0)
    img = rng.integers(200, 800, size=(400, 500), dtype=np.uint16)
    yy, xx = np.mgrid[0:400, 0:500]
    for cy, cx in ((100, 120), (250, 300), (320, 90)):
        blob = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * 35 ** 2))
        img = np.clip(img + (blob * 9000).astype(np.uint16), 0, 65535)
    img = img.astype(np.uint16)

    path = os.path.join(tempfile.gettempdir(), "qv_16bit.tif")
    cv2.imwrite(path, img)

    raw = image_io.load_image(path)
    assert raw.dtype == np.uint16, f"expected uint16, got {raw.dtype}"
    assert image_io.bit_depth(raw) == 16
    maxval = image_io.max_value(raw)
    print(f"  loaded 16-bit image: dtype={raw.dtype} max_value={maxval}")
    assert 800 < maxval <= 65535

    fine = max(1, round(maxval / 255))
    print(f"  arrow-key fine step scales to {fine} (not 1)")
    assert fine > 1, "16-bit step did not scale up"

    for method in autothreshold.METHOD_NAMES:
        t = autothreshold.auto_threshold(raw, maxval, method)
        assert 0 <= t <= maxval, f"{method} threshold {t} out of range"
        m = measure.measure(raw, t, method)
        print(f"  {method:11s} thr={t:6d}  area%={m.positive_area_pct:7.3f}")

    base = image_io.auto_stretch(raw)
    disp = image_io.apply_display(base, 0.0, 1.0)
    assert disp.dtype == np.uint8 and disp.max() > 0
    print(f"  16-bit -> 8-bit display ok (range [{disp.min()},{disp.max()}])")

    os.remove(path)
    print("16-BIT SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
