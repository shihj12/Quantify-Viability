"""Write small TIFF/PNG fixtures + their Python-decoded arrays for TS decode tests.

Run from the repo root with the project venv:
    ./.venv/Scripts/python.exe web/tests/parity/gen_fixtures.py

Decodes each fixture through the real qviability image_io.load_image (cv2), so
the TS decoder (utif2) can be checked against identical pixel values. This
isolates decode fidelity from compute fidelity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import tifffile

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from qviability.core import image_io  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
OUT = Path(__file__).resolve().parent / "expected_decode.json"


def _arrays() -> list[tuple[str, np.ndarray]]:
    rng = np.random.default_rng(7)
    out: list[tuple[str, np.ndarray]] = []

    h, w = 24, 30
    yy, xx = np.mgrid[0:h, 0:w]
    g8 = (10 + xx / w * 200).astype(np.float32)
    g8[(yy - 12) ** 2 + (xx - 15) ** 2 < 5**2] = 250
    out.append(("u8_gradient", g8.astype(np.uint8)))

    out.append(("u8_random", rng.integers(0, 256, size=(20, 28), dtype=np.uint8)))

    h, w = 26, 34
    yy, xx = np.mgrid[0:h, 0:w]
    g16 = (300 + xx / w * 5000).astype(np.float32)
    g16[(yy - 13) ** 2 + (xx - 17) ** 2 < 6**2] = 60000
    out.append(("u16_gradient", g16.astype(np.uint16)))

    out.append(("u16_random", rng.integers(0, 65536, size=(22, 26), dtype=np.uint16)))

    return out


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    cases = []
    for name, arr in _arrays():
        tif = FIX / f"{name}.tif"
        tifffile.imwrite(tif, arr)
        decoded = image_io.load_image(str(tif))
        assert decoded.shape == arr.shape, (name, decoded.shape, arr.shape)
        cases.append({
            "name": name,
            "file": f"fixtures/{name}.tif",
            "bit_depth": int(image_io.bit_depth(decoded)),
            "width": int(arr.shape[1]),
            "height": int(arr.shape[0]),
            "data": decoded.flatten().astype(int).tolist(),
        })
    OUT.write_text(json.dumps({"cases": cases}, indent=1))
    print(f"wrote {OUT}  ({len(cases)} fixtures in {FIX})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
