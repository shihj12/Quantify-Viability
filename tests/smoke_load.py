"""Verify the load screen: folder scanning, the filename filter, and Start."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt                                       # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

from qviability.app import MainWindow                               # noqa: E402
from qviability.core.project import Channel                         # noqa: E402

FOLDER = r"C:\Users\shihj\Desktop\4x Tiff Flat"


def _check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        raise AssertionError(label)


def main() -> int:
    if not os.path.isdir(FOLDER):
        print(f"SKIP: {FOLDER} not found")
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    ls = win.load_screen

    # Point both slots at the same mixed folder, filtered by channel token.
    ls.green_folder = FOLDER
    ls.red_folder = FOLDER
    ls.green_filter.setText("GFP")
    ls.red_filter.setText("RFP")          # triggers _rescan

    rows = ls._rows
    _check("rescan produced rows", len(rows) > 0)
    green = [r for r in rows if r[1] == Channel.GREEN]
    red = [r for r in rows if r[1] == Channel.RED]
    _check("green rows are all _GFP files",
           all("gfp" in Path(p).name.lower() for p, _ in green))
    _check("red rows are all _RFP files",
           all("rfp" in Path(p).name.lower() for p, _ in red))
    _check("filter excluded Overlay/Trans files",
           not any("overlay" in Path(p).name.lower()
                   or "trans" in Path(p).name.lower() for p, _ in rows))
    print(f"    {len(green)} green + {len(red)} red rows")

    _check("table row count matches", ls.table.rowCount() == len(rows))
    _check("Start enabled when images present", ls.start_btn.isEnabled())

    # Uncheck the first row → still enabled, count drops by one.
    full = ls._checked_count()
    ls.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    _check("unchecking a row updates the count",
           ls._checked_count() == full - 1)

    # Narrow the filter to nothing → Start disables.
    ls.green_filter.setText("zzz_no_match")
    ls.red_filter.setText("zzz_no_match")
    _check("Start disabled when no images match", not ls.start_btn.isEnabled())

    # Restore and Start.
    ls.green_filter.setText("GFP")
    ls.red_filter.setText("RFP")
    ls._on_start()
    _check("Start built a project and switched screens",
           win.stack.currentWidget() is win.threshold_screen)
    _check("project has the expected image count",
           len(win.project.images) == len(ls._rows))

    win.close()
    print("LOAD SCREEN SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
