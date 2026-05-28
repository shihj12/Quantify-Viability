"""Generate expected.json from the real qviability.core, for the TS parity tests.

Run from the repo root with the project venv:
    ./.venv/Scripts/python.exe web/tests/parity/generate.py

Phase 1 covers the exact-parity surface: measure(), MaxEntropy auto-threshold,
the 256-bin histogram, and auto_stretch + apply_display. Synthetic images are
small so their raw arrays can be embedded inline and reused by the TS tests,
isolating compute parity from image-decode parity.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from qviability.core import autothreshold, image_io, measure  # noqa: E402

OUT = Path(__file__).resolve().parent / "expected.json"


def _images() -> list[tuple[str, np.ndarray]]:
    rng = np.random.default_rng(12345)
    out: list[tuple[str, np.ndarray]] = []

    # 8-bit: sloped background gradient + a bright blob.
    h, w = 40, 50
    yy, xx = np.mgrid[0:h, 0:w]
    g = (20 + xx / w * 60).astype(np.float32)
    g[(yy - 20) ** 2 + (xx - 25) ** 2 < 8**2] = 230
    out.append(("u8_gradient_blob", g.astype(np.uint8)))

    # 8-bit: random texture.
    out.append(("u8_random", rng.integers(0, 256, size=(32, 48), dtype=np.uint8)))

    # 8-bit: flat (auto_stretch hi<=lo edge case).
    out.append(("u8_flat", np.full((16, 16), 12, dtype=np.uint8)))

    # 16-bit: gradient + blob, partial sensor range.
    h, w = 36, 44
    yy, xx = np.mgrid[0:h, 0:w]
    g16 = (500 + xx / w * 4000).astype(np.float32)
    g16[(yy - 18) ** 2 + (xx - 22) ** 2 < 7**2] = 9000
    out.append(("u16_gradient_blob", g16.astype(np.uint16)))

    # 16-bit: random.
    out.append(("u16_random", rng.integers(0, 4096, size=(30, 40), dtype=np.uint16)))

    return out


def _measure_dict(m) -> dict:
    return dataclasses.asdict(m)


def main() -> int:
    cases = []
    for name, arr in _images():
        mv = image_io.max_value(arr)
        bd = image_io.bit_depth(arr)
        h, w = arr.shape

        hist, _ = np.histogram(arr, bins=256, range=(0, mv + 1))

        auto_me = autothreshold.threshold_maxentropy(arr, mv)
        auto_all = {m: int(autothreshold.auto_threshold(arr, mv, m))
                    for m in autothreshold.METHOD_NAMES}

        # measure() at several thresholds, plus one with exclusions.
        thresholds = sorted({auto_me, mv // 4, mv // 2, (3 * mv) // 4, mv})
        measures = []
        for t in thresholds:
            m = measure.measure(arr, int(t))
            measures.append({"threshold": int(t), "exclusions": [],
                             "result": _measure_dict(m)})
        excl = [[5, 5, 10, 8], [w - 6, 0, 6, h]]
        emask = measure.exclusion_mask(arr.shape, excl)
        m = measure.measure(arr, int(auto_me), exclude_mask=emask)
        measures.append({"threshold": int(auto_me), "exclusions": excl,
                         "result": _measure_dict(m)})

        # auto_stretch + apply_display at a few brightness/contrast settings.
        base = image_io.auto_stretch(arr)
        display = []
        for brightness, contrast in [(0.0, 1.0), (0.2, 1.5), (-0.3, 0.7)]:
            disp = image_io.apply_display(base, brightness, contrast)
            display.append({"brightness": brightness, "contrast": contrast,
                            "base_u8": disp.flatten().astype(int).tolist()})

        cases.append({
            "name": name,
            "bit_depth": int(bd),
            "width": int(w),
            "height": int(h),
            "max_value": int(mv),
            "data": arr.flatten().astype(int).tolist(),
            "histogram256": hist.astype(int).tolist(),
            "auto": auto_all,
            "measure": measures,
            "display": display,
        })

    OUT.write_text(json.dumps({"cases": cases}, indent=1))
    print(f"wrote {OUT}  ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
