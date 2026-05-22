"""Shared Qt widgets: the image canvas, the histogram, and small helpers."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget

pg.setConfigOptions(imageAxisOrder="row-major", antialias=False)


def numpy_to_qpixmap(rgb: np.ndarray) -> QPixmap:
    """Convert a contiguous HxWx3 uint8 RGB array to a QPixmap."""
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _ExclusionViewBox(pg.ViewBox):
    """ViewBox that, in draw mode, lets the user click-drag an exclusion box.

    Emits ``region_drawn(x, y, w, h)`` in image-pixel coordinates on release.
    Outside draw mode it behaves like a normal ViewBox (pan / zoom).
    """

    region_drawn = Signal(float, float, float, float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.draw_mode = False

    def mouseDragEvent(self, ev, axis=None):
        if self.draw_mode and ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
            if ev.isFinish():
                self.rbScaleBox.hide()
                rect = QRectF(pg.Point(ev.buttonDownPos()), pg.Point(ev.pos()))
                rect = self.childGroup.mapRectFromParent(rect).normalized()
                self.region_drawn.emit(rect.x(), rect.y(),
                                       rect.width(), rect.height())
            else:
                self.updateScaleBox(ev.buttonDownPos(), ev.pos())
        else:
            super().mouseDragEvent(ev, axis)


class ImageCanvas(QWidget):
    """pyqtgraph view with a base grayscale image and a translucent overlay.

    Focus policy is NoFocus so arrow keys always reach the threshold screen.
    """

    region_drawn = Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground("#1a1a1a")
        self.glw.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.glw)

        self.view = _ExclusionViewBox()
        self.view.setAspectLocked(True)
        self.view.invertY(True)
        self.view.setMenuEnabled(False)
        self.glw.addItem(self.view)
        self.view.region_drawn.connect(self.region_drawn)

        self.base_item = pg.ImageItem()
        self.overlay_item = pg.ImageItem()
        self.overlay_item.setZValue(10)
        self.view.addItem(self.base_item)
        self.view.addItem(self.overlay_item)

    def set_base(self, disp_u8: np.ndarray) -> None:
        """Set the grayscale display image (uint8 HxW)."""
        self.base_item.setImage(disp_u8, autoLevels=False, levels=(0, 255))

    def set_overlay(self, rgba: np.ndarray) -> None:
        """Set the RGBA overlay (uint8 HxWx4)."""
        self.overlay_item.setImage(rgba, autoLevels=False)

    def fit(self) -> None:
        """Zoom to fit the current image."""
        self.view.autoRange(padding=0.02)

    def set_draw_mode(self, on: bool) -> None:
        """Enable click-drag drawing of exclusion boxes."""
        self.view.draw_mode = on
        self.glw.setCursor(Qt.CursorShape.CrossCursor if on
                           else Qt.CursorShape.ArrowCursor)

    def set_overlay_visible(self, visible: bool) -> None:
        """Show/hide the quantification overlay (original-image preview)."""
        self.overlay_item.setVisible(visible)


class HistogramWidget(QWidget):
    """Pixel-value histogram with a draggable threshold line.

    Emits ``threshold_changed`` when the user drags the line.
    """

    threshold_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#262626")
        self.plot.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot.setMaximumHeight(150)
        self.plot.setMinimumHeight(110)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideAxis("left")
        self.plot.hideButtons()
        self.plot.getAxis("bottom").setPen("#888888")
        self.plot.getAxis("bottom").setTextPen("#bbbbbb")

        self.curve = pg.PlotCurveItem(
            fillLevel=0, brush=(120, 130, 175, 160),
            pen=pg.mkPen((170, 180, 220)))
        self.plot.addItem(self.curve)

        self.line = pg.InfiniteLine(
            angle=90, movable=True,
            pen=pg.mkPen("#ff5555", width=2),
            hoverPen=pg.mkPen("#ff9999", width=3))
        self.plot.addItem(self.line)
        self.line.sigPositionChanged.connect(self._on_line_moved)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

    def set_histogram(self, raw: np.ndarray, maxval: int) -> None:
        """Compute and display the 256-bin histogram of *raw*."""
        hist, edges = np.histogram(raw, bins=256, range=(0, maxval + 1))
        # sqrt compresses the huge dark-background peak so signal stays visible.
        self.curve.setData(edges, np.sqrt(hist.astype(np.float64)),
                           stepMode="center")
        self.plot.setXRange(0, maxval, padding=0.02)
        self.line.setBounds((0, maxval))

    def set_threshold(self, value: int) -> None:
        """Move the line without emitting (call when threshold changes elsewhere)."""
        self._updating = True
        self.line.setValue(value)
        self._updating = False

    def _on_line_moved(self) -> None:
        if self._updating:
            return
        self.threshold_changed.emit(int(round(self.line.value())))
