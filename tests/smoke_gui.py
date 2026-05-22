"""Headless GUI integration test — drives the whole workflow offscreen.

    .venv\\Scripts\\python tests\\smoke_gui.py

Builds a project from a few real images, simulates threshold tuning with key
events, accepts every image, opens the review gallery and exports — verifying
the xlsx, annotated PNGs and the autosaved session.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np                                                  # noqa: E402
from PySide6.QtCore import Qt                                       # noqa: E402
from PySide6.QtTest import QTest                                    # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

from qviability.app import MainWindow                               # noqa: E402
from qviability.core import image_io                                # noqa: E402
from qviability.core.project import (Channel, ImageEntry, Project,  # noqa: E402
                                     default_session_path, load_project)

FOLDER = r"C:\Users\shihj\Desktop\4x Tiff Flat"


def _check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        raise AssertionError(label)


def main() -> int:
    files = image_io.scan_folder(FOLDER)
    gfp = [f for f in files if "_GFP" in f.name.upper()][:2]
    rfp = [f for f in files if "_RFP" in f.name.upper()][:1]
    if len(gfp) < 1 or len(rfp) < 1:
        print(f"SKIP: not enough test images in {FOLDER}")
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()

    images = [ImageEntry(path=str(p), display_name=p.name,
                         channel=Channel.GREEN) for p in gfp]
    images += [ImageEntry(path=str(p), display_name=p.name,
                          channel=Channel.RED) for p in rfp]
    n = len(images)
    print(f"testing with {n} images")

    session_dir = tempfile.mkdtemp(prefix="qv_green_")
    project = Project(green_folder=session_dir, red_folder=None, images=images)
    win.start_project(project)

    ts = win.threshold_screen
    _check("threshold screen shows image 0", win.stack.currentWidget() is ts)
    _check("auto threshold seeded", ts.entry.threshold is not None)
    t0 = ts.entry.threshold
    print(f"    auto threshold = {t0}")

    for _ in range(5):
        QTest.keyClick(ts, Qt.Key.Key_Up)
    _check("5x Up raised threshold by 5", ts.entry.threshold == t0 + 5)

    QTest.keyClick(ts, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    _check("Shift+Down applied coarse step",
           ts.entry.threshold == t0 + 5 - ts._coarse)

    QTest.keyClick(ts, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    _check("Ctrl+Z undo restored previous threshold",
           ts.entry.threshold == t0 + 5)

    _check("measurement computed", ts.entry.measurement is not None)
    before = ts.entry.measurement.positive_pixels
    ts.brightness.setValue(60)
    ts.contrast.setValue(220)
    _check("brightness/contrast did NOT change measurement",
           ts.entry.measurement.positive_pixels == before)

    QTest.keyPress(ts, Qt.Key.Key_Space)
    _check("holding Space hides the quantification overlay",
           not ts.canvas.overlay_item.isVisible())
    _check("holding Space shows the raw, unprocessed image",
           np.array_equal(ts.canvas.base_item.image, ts._raw_display))
    QTest.keyRelease(ts, Qt.Key.Key_Space)
    _check("releasing Space restores the overlay",
           ts.canvas.overlay_item.isVisible())
    _check("releasing Space restores the processed display view",
           not np.array_equal(ts.canvas.base_item.image, ts._raw_display))

    overlay_before = ts.canvas.overlay_item.image
    QTest.keyClick(ts, Qt.Key.Key_O)
    _check("O enables the highlight-marks aid",
           ts._outline and ts.outline_chk.isChecked())
    _check("highlight-marks aid changed the displayed overlay",
           not np.array_equal(ts.canvas.overlay_item.image, overlay_before))
    QTest.keyClick(ts, Qt.Key.Key_O)
    _check("O again disables the highlight-marks aid",
           not ts._outline and not ts.outline_chk.isChecked())
    _check("highlight-marks aid did NOT change the measurement",
           ts.entry.measurement.positive_pixels == before)

    for _ in range(n):
        QTest.keyClick(ts, Qt.Key.Key_Return)
    _check("accepting all images opened the review screen",
           win.stack.currentWidget() is win.review_screen)
    _check("every image marked done", project.all_done())
    _check("review gallery built one card per image",
           win.review_screen.grid.count() == n)

    out_dir = tempfile.mkdtemp(prefix="qv_out_")
    pdf_pages = win.review_screen._run_export(out_dir)
    xlsx = Path(out_dir) / "viability_results.xlsx"
    pdf_file = Path(out_dir) / "viability_QC.pdf"
    pngs = list((Path(out_dir) / "annotated").glob("*.png"))
    _check("viability_results.xlsx written", xlsx.is_file())
    _check(f"annotated PNG per image ({len(pngs)}/{n})", len(pngs) == n)
    _check("viability_QC.pdf written", pdf_file.is_file())
    _check(f"QC PDF has one page per tuned image ({pdf_pages}/{n})",
           pdf_pages == n)

    session = default_session_path(project)
    _check("session autosaved", bool(session) and os.path.isfile(session))
    reloaded = load_project(session)
    _check("session reloads with all images done", reloaded.all_done())
    _check("reloaded measurement preserved",
           reloaded.images[0].measurement is not None)

    win.close()
    print("ALL GUI SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
