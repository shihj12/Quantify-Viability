"""Generate rolling-ball (subtract_background) expectations for TS parity tests.

Run from the repo root with the project venv:
    ./.venv/Scripts/python.exe web/tests/parity/gen_rolling.py

Covers the no-shrink path (min dim < 256 -> bit-exact expected) and the shrink
path (min dim >= 256 -> uses cv2 resize, validated to tolerance). Arrays are
base64-packed (little-endian) to keep the fixture small. For each subtracted
image it also records the MaxEntropy threshold and positive_pixels, so the TS
test can check threshold/positive_pixels parity.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from qviability.core import autothreshold, image_io, measure  # noqa: E402

OUT = Path(__file__).resolve().parent / "expected_rolling.json"
RADII = [12, 50, 75]


def _b64(arr: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def _blobs(h: int, w: int, dt, bg0: float, bg1: float, peak: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    img = (bg0 + xx / w * (bg1 - bg0)).astype(np.float32)
    for cy, cx, r in [(h // 3, w // 3, max(3, w // 12)),
                      (2 * h // 3, 2 * w // 3, max(4, w // 10))]:
        img[(yy - cy) ** 2 + (xx - cx) ** 2 < r * r] = peak
    return img.astype(dt)


def _images() -> list[tuple[str, np.ndarray]]:
    return [
        ("u8_small", _blobs(64, 80, np.uint8, 12, 70, 240)),       # no shrink
        ("u16_small", _blobs(60, 72, np.uint16, 400, 3000, 60000)),  # no shrink
        ("u8_big", _blobs(256, 288, np.uint8, 10, 80, 250)),        # shrink @ r>=50
        ("u8_big_odd", _blobs(258, 310, np.uint8, 15, 90, 250)),    # shrink, non-divisible
    ]


def main() -> int:
    cases = []
    for name, arr in _images():
        h, w = arr.shape
        isu16 = arr.dtype == np.uint16
        entry = {
            "name": name,
            "bit_depth": 16 if isu16 else 8,
            "width": int(w),
            "height": int(h),
            "data_b64": _b64(arr),
            "radii": [],
        }
        for radius in RADII:
            sub = image_io.subtract_background(arr, radius)
            mv = image_io.max_value(sub)
            thr = autothreshold.threshold_maxentropy(sub, mv)
            m = measure.measure(sub, int(thr))
            shrink = 1
            if min(w, h) >= 256:
                shrink = max(1, min(4, radius // 8))
            entry["radii"].append({
                "radius": radius,
                "shrink": int(shrink),
                "sub_b64": _b64(sub),
                "threshold": int(thr),
                "positive_pixels": int(m.positive_pixels),
            })
        cases.append(entry)

    OUT.write_text(json.dumps({"cases": cases}))
    print(f"wrote {OUT}  ({len(cases)} images x {len(RADII)} radii)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
