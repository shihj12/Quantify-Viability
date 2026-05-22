"""Headless smoke test for the core logic — run directly with the venv python.

    .venv\\Scripts\\python tests\\smoke_core.py [optional_image_path]
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qviability.core import autothreshold, image_io, measure          # noqa: E402
from qviability.core.project import (ImageEntry, Project, load_project,  # noqa: E402
                                     save_project)

DEFAULT_IMAGE = r"C:\Users\shihj\Desktop\4x Tiff Flat\Baf1.1_GFP.tif"


def main() -> int:
    img_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAGE
    if not os.path.isfile(img_path):
        print(f"SKIP: test image not found: {img_path}")
        return 0

    raw = image_io.load_image(img_path)
    print(f"loaded {Path(img_path).name}: shape={raw.shape} dtype={raw.dtype}")
    maxval = image_io.max_value(raw)
    print(f"  bit_depth={image_io.bit_depth(raw)}  max_value={maxval}")

    print("  auto-threshold methods:")
    for method in autothreshold.METHOD_NAMES:
        t = autothreshold.auto_threshold(raw, maxval, method)
        m = measure.measure(raw, t, method)
        print(f"    {method:11s} thr={t:6d}  area%={m.positive_area_pct:8.3f}  "
              f"mean={m.mean_intensity_positive:7.1f}  "
              f"integ={m.integrated_intensity:,.0f}")

    mask = measure.apply_threshold(raw, maxval // 2)
    rgba = measure.overlay_rgba(mask, "Green")
    assert rgba.shape == (raw.shape[0], raw.shape[1], 4)
    assert rgba.dtype.name == "uint8"
    print(f"  overlay rgba: shape={rgba.shape} ok")

    base = image_io.auto_stretch(raw)
    disp = image_io.apply_display(base, 0.0, 1.0)
    assert disp.dtype.name == "uint8" and disp.shape == raw.shape[:2]
    print(f"  display image: dtype={disp.dtype} range=[{disp.min()},{disp.max()}] ok")

    # project save/load round-trip
    proj = Project(green_folder="g", red_folder="r", images=[ImageEntry(
        path=img_path, display_name=Path(img_path).name, channel="Green")])
    proj.images[0].threshold = 120
    proj.images[0].measurement = measure.measure(raw, 120, "Manual")
    tmp = os.path.join(tempfile.gettempdir(), "qv_smoke_session.json")
    save_project(proj, tmp)
    loaded = load_project(tmp)
    assert loaded.images[0].threshold == 120
    assert (loaded.images[0].measurement.positive_pixels
            == proj.images[0].measurement.positive_pixels)
    os.remove(tmp)
    print("  project JSON round-trip ok")

    print("ALL CORE SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
