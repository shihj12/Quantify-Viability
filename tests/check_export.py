"""Export a couple of images and print the resulting workbook for inspection."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd                                                  # noqa: E402

from qviability.core import autothreshold, image_io, measure         # noqa: E402
from qviability.core.project import (Channel, ImageEntry, Project)   # noqa: E402
from qviability.export import annotate, excel                        # noqa: E402

FOLDER = r"C:\Users\shihj\Desktop\4x Tiff Flat"
OUT = Path(tempfile.gettempdir()) / "qv_export_check"


def main() -> int:
    files = image_io.scan_folder(FOLDER)
    gfp = [f for f in files if "_GFP" in f.name.upper()][:2]
    rfp = [f for f in files if "_RFP" in f.name.upper()][:1]
    if not gfp or not rfp:
        print("SKIP: no test images")
        return 0

    OUT.mkdir(exist_ok=True)
    images = []
    for p, ch in [(gfp[0], Channel.GREEN), (gfp[1], Channel.GREEN),
                  (rfp[0], Channel.RED)]:
        raw = image_io.get_image(str(p))
        e = ImageEntry(path=str(p), display_name=p.name, channel=ch)
        e.bit_depth = image_io.bit_depth(raw)
        e.max_value = image_io.max_value(raw)
        e.height, e.width = raw.shape[:2]
        e.threshold = autothreshold.auto_threshold(raw, e.max_value, "MaxEntropy")
        e.auto_method = "MaxEntropy"
        e.measurement = measure.measure(raw, e.threshold, "MaxEntropy")
        e.done = True
        images.append(e)
        annotate.save_annotated_png(
            raw, e.threshold, e.channel,
            f"{e.display_name} | {e.channel} | thr {e.threshold}",
            str(OUT / "annotated" / f"{p.stem}_thr{e.threshold}.png"))

    project = Project(green_folder=str(gfp[0].parent), images=images)
    xlsx = OUT / "viability_results.xlsx"
    excel.write_xlsx(project, str(xlsx))

    df = pd.read_excel(xlsx)
    print("viability_results.xlsx columns:")
    print("  " + ", ".join(df.columns))
    print(df.to_string(index=False))
    print(f"\nannotated PNGs: {sorted((OUT / 'annotated').glob('*.png'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
