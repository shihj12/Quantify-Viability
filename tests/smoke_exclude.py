"""Verify the exclusion-box feature: masking, measurement, persistence."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np                                                  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox              # noqa: E402

from qviability.app import MainWindow                               # noqa: E402
from qviability.core import image_io, measure                       # noqa: E402
from qviability.core.project import (Channel, ImageEntry, Project,  # noqa: E402
                                     default_session_path, load_project)

FOLDER = os.environ.get("QV_TEST_IMAGES", "")   # set to a folder of test images


def _check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        raise AssertionError(label)


def test_core() -> None:
    print("core:")
    raw = np.zeros((100, 200), dtype=np.uint8)
    raw[10:20, 10:30] = 200          # block A: 10x20 = 200 bright px
    raw[50:60, 100:120] = 200        # block B: 10x20 = 200 bright px

    _check("no exclusions -> None", measure.exclusion_mask(raw.shape, []) is None)

    m = measure.measure(raw, 100)
    _check("plain measure counts both blocks", m.positive_pixels == 400)
    _check("plain total is whole image", m.total_pixels == 100 * 200)

    excl = measure.exclusion_mask(raw.shape, [[100, 50, 20, 10]])
    _check("exclusion mask covers 200 px", int(excl.sum()) == 200)

    m2 = measure.measure(raw, 100, exclude_mask=excl)
    _check("excluded block B no longer counted", m2.positive_pixels == 200)
    _check("excluded pixels removed from total",
           m2.total_pixels == 100 * 200 - 200)

    rgba = measure.overlay_rgba(raw >= 100, "Green", excl)
    _check("excluded region drawn gray, not green",
           tuple(rgba[55, 110]) == measure.EXCLUDE_RGBA)
    _check("counted region drawn green", rgba[15, 20, 3] == measure.OVERLAY_ALPHA)


def test_gui() -> None:
    print("gui:")
    files = image_io.scan_folder(FOLDER)
    gfp = [f for f in files if "_GFP" in f.name.upper()][:1]
    if not gfp:
        print("  SKIP: no test image")
        return

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    entry = ImageEntry(path=str(gfp[0]), display_name=gfp[0].name,
                       channel=Channel.GREEN)
    project = Project(green_folder=tempfile.mkdtemp(prefix="qv_excl_"),
                      images=[entry])
    win.start_project(project)

    ts = win.threshold_screen
    raw = ts.raw
    img_h, img_w = raw.shape[:2]
    _check("starts with whole image as total",
           ts.entry.measurement.total_pixels == raw.size)

    ts.draw_btn.setChecked(True)
    _check("draw toggle enables canvas draw mode", ts.canvas.view.draw_mode)

    # simulate the user dragging a box over a bottom-left scale bar
    ts.canvas.region_drawn.emit(0.0, float(img_h - 100), 200.0, 100.0)
    _check("drawn box recorded", len(ts.entry.exclusions) == 1)
    _check("box removed from total",
           ts.entry.measurement.total_pixels == raw.size - 200 * 100)

    # a stray tiny click is ignored
    ts.canvas.region_drawn.emit(5.0, 5.0, 1.0, 1.0)
    _check("tiny stray click ignored", len(ts.entry.exclusions) == 1)

    ts._undo_exclusion()
    _check("undo removes the box", len(ts.entry.exclusions) == 0)
    _check("total restored after undo",
           ts.entry.measurement.total_pixels == raw.size)

    ts.canvas.region_drawn.emit(0.0, 0.0, 60.0, 60.0)
    ts.canvas.region_drawn.emit(100.0, 100.0, 80.0, 80.0)
    _check("two boxes recorded", len(ts.entry.exclusions) == 2)
    ts._clear_exclusions()
    _check("clear removes all boxes", len(ts.entry.exclusions) == 0)

    # persistence
    ts.canvas.region_drawn.emit(0.0, float(img_h - 80), 150.0, 80.0)
    win.autosave()
    reloaded = load_project(default_session_path(project))
    _check("exclusions persisted to session",
           reloaded.images[0].exclusions == [[0, img_h - 80, 150, 80]])

    win.close()


def test_apply_all() -> None:
    print("apply-to-all:")
    files = image_io.scan_folder(FOLDER)
    gfp = [f for f in files if "_GFP" in f.name.upper()][:2]
    rfp = [f for f in files if "_RFP" in f.name.upper()][:1]
    if len(gfp) < 2 or not rfp:
        print("  SKIP: not enough test images")
        return

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    images = [ImageEntry(path=str(p), display_name=p.name,
                         channel=Channel.GREEN) for p in gfp]
    images.append(ImageEntry(path=str(rfp[0]), display_name=rfp[0].name,
                             channel=Channel.RED))
    project = Project(green_folder=tempfile.mkdtemp(prefix="qv_all_"),
                      images=images)
    win.start_project(project)
    ts = win.threshold_screen

    ts._accept()           # tune+accept image 0, advance to 1
    ts._accept()           # tune+accept image 1, advance to 2
    total_before = project.images[0].measurement.total_pixels
    _check("other images measured at full size before apply",
           total_before == project.images[0].measurement.total_pixels)

    img_h, img_w = ts.raw.shape[:2]
    ts.canvas.region_drawn.emit(0.0, float(img_h - 100), 200.0, 100.0)
    _check("box drawn on current image",
           len(project.images[2].exclusions) == 1)

    # auto-confirm the modal dialog
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes)
    ts._apply_exclusions_to_all()

    box = project.images[2].exclusions
    _check("box copied to image 0", project.images[0].exclusions == box)
    _check("box copied to image 1", project.images[1].exclusions == box)
    _check("already-tuned image 0 was re-measured",
           project.images[0].measurement.total_pixels
           == img_h * img_w - 200 * 100)

    win.close()


def main() -> int:
    test_core()
    test_gui()
    test_apply_all()
    print("EXCLUSION SMOKE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
