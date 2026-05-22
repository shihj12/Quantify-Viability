"""Verify optional rolling-ball background subtraction."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2                                                           # noqa: E402
import numpy as np                                                  # noqa: E402
from PySide6.QtWidgets import QApplication                           # noqa: E402

from qviability.app import MainWindow                                # noqa: E402
from qviability.core import image_io                                 # noqa: E402
from qviability.core.project import Channel, ImageEntry, Project     # noqa: E402

FOLDER = os.environ.get("QV_TEST_IMAGES", "")   # set to a folder of test images


def _check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        raise AssertionError(label)


def test_core() -> None:
    print("core:")
    # synthetic image: a sloped background gradient + one bright blob
    h, w = 400, 500
    yy, xx = np.mgrid[0:h, 0:w]
    img = (30 + xx / w * 60).astype(np.float32)        # background 30..90
    blob = (yy - 200) ** 2 + (xx - 250) ** 2 < 40 ** 2
    img[blob] = 230
    img = img.astype(np.uint8)

    sub = image_io.subtract_background(img)
    _check("output keeps shape and dtype",
           sub.shape == img.shape and sub.dtype == np.uint8)
    orig_bg = img[40:110, 40:110].mean()
    sub_bg = sub[40:110, 40:110].mean()
    _check(f"background reduced ({orig_bg:.0f} -> {sub_bg:.0f})",
           sub_bg < orig_bg - 10 and sub_bg < 20)
    _check("bright blob survives subtraction",
           sub[185:215, 235:265].mean() > 60)

    path = os.path.join(tempfile.gettempdir(), "qv_bg_test.tif")
    cv2.imwrite(path, img)
    image_io.clear_cache()
    _check("get_processed(subtract=False) returns the raw image",
           np.array_equal(image_io.get_processed(path, False), img))
    proc = image_io.get_processed(path, True)
    _check("get_processed(subtract=True) returns a subtracted image",
           not np.array_equal(proc, img))
    _check("processed result is cached", image_io.get_processed(path, True) is proc)
    os.remove(path)


def test_gui() -> None:
    print("gui:")
    files = image_io.scan_folder(FOLDER)
    gfp = [f for f in files if "_GFP" in f.name.upper()][:1]
    if not gfp:
        print("  SKIP: no test image")
        return
    app = QApplication.instance() or QApplication(sys.argv)

    # --- without background subtraction -------------------------------------
    win = MainWindow()
    win.show()
    entry = ImageEntry(path=str(gfp[0]), display_name=gfp[0].name,
                       channel=Channel.GREEN)
    proj = Project(green_folder=tempfile.mkdtemp(prefix="qv_nobg_"),
                   images=[entry], subtract_background=False)
    win.start_project(proj)
    ts = win.threshold_screen
    _check("subtraction off: working image is the raw image",
           ts.proc is ts.raw)
    _check("subtraction off: no background indicator", ts.bg_lbl.text() == "")
    win.close()

    # --- with background subtraction ---------------------------------------
    win2 = MainWindow()
    win2.show()
    entry2 = ImageEntry(path=str(gfp[0]), display_name=gfp[0].name,
                        channel=Channel.GREEN)
    proj2 = Project(green_folder=tempfile.mkdtemp(prefix="qv_bg_"),
                    images=[entry2], subtract_background=True)
    win2.start_project(proj2)
    ts2 = win2.threshold_screen
    _check("subtraction on: working image differs from raw",
           ts2.proc is not ts2.raw)
    _check("subtraction on: raw preview is still the untouched raw image",
           np.array_equal(ts2._raw_display, ts2.raw))
    _check("subtraction on: background indicator shown",
           "background subtracted" in ts2.bg_lbl.text())
    _check("measurement computed on the subtracted image",
           ts2.entry.measurement is not None)
    win2.close()


def test_load_screen() -> None:
    print("load screen:")
    if not os.path.isdir(FOLDER):
        print("  SKIP")
        return
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    ls = win.load_screen
    ls.green_folder = FOLDER
    ls.green_filter.setText("GFP")
    ls.bg_check.setChecked(True)
    ls._on_start()
    _check("load-screen checkbox sets project.subtract_background",
           win.project.subtract_background is True)
    win.close()


def main() -> int:
    test_core()
    test_gui()
    test_load_screen()
    print("BACKGROUND-SUBTRACTION SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
