"""Render the app's screens to PNG files so they can be eyeballed.

Uses the real Windows platform (so fonts render) with WA_DontShowOnScreen so
no window actually pops up.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt                                       # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

from qviability.app import MainWindow                               # noqa: E402
from qviability.core import image_io                                # noqa: E402
from qviability.core.project import (Channel, ImageEntry, Project)  # noqa: E402

FOLDER = r"C:\Users\shihj\Desktop\4x Tiff Flat"
OUT = Path(tempfile.gettempdir()) / "qv_shots"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    files = image_io.scan_folder(FOLDER)
    gfp = [f for f in files if "_GFP" in f.name.upper()][:3]
    rfp = [f for f in files if "_RFP" in f.name.upper()][:2]
    if not gfp:
        print(f"SKIP: no test images in {FOLDER}")
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(1320, 840)
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    app.processEvents()

    win.load_screen.grab().save(str(OUT / "1_load.png"))

    images = [ImageEntry(path=str(p), display_name=p.name,
                         channel=Channel.GREEN) for p in gfp]
    images += [ImageEntry(path=str(p), display_name=p.name,
                          channel=Channel.RED) for p in rfp]
    project = Project(green_folder=tempfile.mkdtemp(), images=images)
    win.start_project(project)
    app.processEvents()
    win.threshold_screen.canvas.fit()
    app.processEvents()
    win.threshold_screen.grab().save(str(OUT / "2_threshold.png"))

    # nudge threshold higher to show a smaller overlay, then re-grab
    ts = win.threshold_screen
    ts._set_threshold(ts.entry.threshold + 40)
    app.processEvents()
    ts.grab().save(str(OUT / "3_threshold_tuned.png"))

    # draw an exclusion box over the bottom-left (where scale bars sit)
    ts.draw_btn.setChecked(True)
    img_h, img_w = ts.raw.shape[:2]
    ts.canvas.region_drawn.emit(0.0, float(img_h - 150), 320.0, 150.0)
    app.processEvents()
    ts.grab().save(str(OUT / "5_exclusion.png"))

    # hold-Space raw preview: overlay off + no display brightness/contrast
    ts._show_raw_preview(True)
    app.processEvents()
    ts.grab().save(str(OUT / "6_raw_preview.png"))
    ts._show_raw_preview(False)

    for entry in project.images:
        entry.done = True
    win.show_review()
    app.processEvents()
    win.review_screen.grab().save(str(OUT / "4_review.png"))

    win.close()
    print(f"screenshots written to {OUT}")
    for f in sorted(OUT.glob("*.png")):
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
