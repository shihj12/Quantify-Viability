"""Threshold screen — the core interactive per-image tuning view.

Left: the image with a translucent overlay on the pixels currently counted as
positive. Right: threshold readout, live measurements, histogram, and
display-only brightness/contrast. Arrow keys nudge the threshold; Enter
accepts and advances.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox,
                               QProgressDialog, QPushButton, QScrollArea,
                               QSlider, QVBoxLayout, QWidget)

from ..core import autothreshold, image_io, measure
from .widgets import HistogramWidget, ImageCanvas


def _fmt_int(n: int) -> str:
    return f"{n:,}"


class ThresholdScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.project = None
        self.entry = None
        self.raw = None                       # literal raw file pixels
        self.proc = None                      # working image (raw or bg-subtracted)
        self.base = None                      # auto-stretched float32 base
        self.return_to_review = False
        self._undo_stack: list[int] = []
        self._exclude_mask = None
        self._raw_display = None              # raw pixels mapped to uint8
        self._space_held = False
        self._outline = False                 # highlight-marks display aid
        self._fine = 1
        self._coarse = 10

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.canvas = ImageCanvas()
        self.canvas.region_drawn.connect(self._on_region_drawn)
        root.addWidget(self.canvas, stretch=3)

        panel = self._build_panel()
        root.addWidget(panel, stretch=0)

    # ------------------------------------------------------------------
    # Panel construction
    # ------------------------------------------------------------------
    def _build_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(360)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(14, 14, 14, 14)
        col.setSpacing(12)

        self.file_lbl = QLabel("—")
        self.file_lbl.setWordWrap(True)
        self.file_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.channel_lbl = QLabel("")
        self.bg_lbl = QLabel("")
        self.bg_lbl.setStyleSheet("color: #6cae6c; font-size: 11px;")
        col.addWidget(self.file_lbl)
        col.addWidget(self.channel_lbl)
        col.addWidget(self.bg_lbl)

        self.threshold_lbl = QLabel("Threshold: —")
        self.threshold_lbl.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #ff7777;")
        col.addWidget(self.threshold_lbl)

        # Reset to the MaxEntropy auto-threshold -----------------------------
        reset_auto_btn = QPushButton("Reset to auto-threshold")
        reset_auto_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reset_auto_btn.clicked.connect(self._reset_auto)
        col.addWidget(reset_auto_btn)

        # Measurements --------------------------------------------------------
        meas_box = QGroupBox("Measurements")
        grid = QGridLayout(meas_box)
        grid.setVerticalSpacing(4)
        self.m_pixels = QLabel("—")
        self.m_area = QLabel("—")
        self.m_mean = QLabel("—")
        self.m_integ = QLabel("—")
        self.m_integ.setStyleSheet("font-weight: bold; color: #ffd966;")
        for r, (name, widget) in enumerate((
                ("Positive pixels", self.m_pixels),
                ("Positive area %", self.m_area),
                ("Mean intensity", self.m_mean),
                ("Integrated intensity", self.m_integ))):
            grid.addWidget(QLabel(name + ":"), r, 0)
            widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(widget, r, 1)
        col.addWidget(meas_box)

        # Histogram -----------------------------------------------------------
        hist_box = QGroupBox("Histogram (drag the red line)")
        hlay = QVBoxLayout(hist_box)
        self.histogram = HistogramWidget()
        self.histogram.threshold_changed.connect(self._on_histogram_drag)
        hlay.addWidget(self.histogram)
        col.addWidget(hist_box)

        # Display brightness / contrast --------------------------------------
        disp_box = QGroupBox("Display  (does not affect measurement)")
        dlay = QGridLayout(disp_box)
        dlay.addWidget(QLabel("Brightness"), 0, 0)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(-100, 100)
        self.brightness.setValue(0)
        self.brightness.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.brightness.valueChanged.connect(self._on_display_changed)
        dlay.addWidget(self.brightness, 0, 1)
        dlay.addWidget(QLabel("Contrast"), 1, 0)
        self.contrast = QSlider(Qt.Orientation.Horizontal)
        self.contrast.setRange(10, 400)
        self.contrast.setValue(100)
        self.contrast.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.contrast.valueChanged.connect(self._on_display_changed)
        dlay.addWidget(self.contrast, 1, 1)
        reset_disp = QPushButton("Reset display")
        reset_disp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reset_disp.clicked.connect(self._reset_display)
        dlay.addWidget(reset_disp, 2, 0, 1, 2)
        self.outline_chk = QCheckBox("Highlight marked regions  (O)")
        self.outline_chk.setToolTip(
            "Draw a bright outline around the marked pixels so small blobs "
            "are easy to see. Display only — does not change the exported "
            "images or any measurement.")
        self.outline_chk.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.outline_chk.toggled.connect(self._on_outline_toggled)
        dlay.addWidget(self.outline_chk, 3, 0, 1, 2)
        col.addWidget(disp_box)

        # Exclusion boxes -----------------------------------------------------
        excl_box = QGroupBox("Exclude regions  (e.g. scale bars)")
        elay = QVBoxLayout(excl_box)
        self.draw_btn = QPushButton("Draw exclusion box")
        self.draw_btn.setCheckable(True)
        self.draw_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.draw_btn.toggled.connect(self._toggle_draw_mode)
        elay.addWidget(self.draw_btn)
        excl_btns = QHBoxLayout()
        for text, slot in (("Undo box", self._undo_exclusion),
                           ("Clear boxes", self._clear_exclusions)):
            btn = QPushButton(text)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(slot)
            excl_btns.addWidget(btn)
        elay.addLayout(excl_btns)
        self.apply_all_btn = QPushButton("Apply boxes to all images")
        self.apply_all_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_btn.clicked.connect(self._apply_exclusions_to_all)
        elay.addWidget(self.apply_all_btn)
        self.excl_lbl = QLabel("No exclusion boxes")
        self.excl_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        elay.addWidget(self.excl_lbl)
        col.addWidget(excl_box)

        col.addStretch(1)

        # Progress + navigation ----------------------------------------------
        self.progress_lbl = QLabel("")
        self.progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.progress_lbl)

        nav = QHBoxLayout()
        for text, slot in (("◀ Prev", self._prev), ("Next ▶", self._next)):
            btn = QPushButton(text)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(slot)
            nav.addWidget(btn)
        col.addLayout(nav)

        self.accept_btn = QPushButton("Accept  (Enter)")
        self.accept_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        self.accept_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.accept_btn.clicked.connect(self._accept)
        col.addWidget(self.accept_btn)

        bottom = QHBoxLayout()
        for text, slot in (("Save", self._save),
                           ("Go to Review", self._go_review)):
            btn = QPushButton(text)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(slot)
            bottom.addWidget(btn)
        col.addLayout(bottom)

        help_lbl = QLabel("↑/↓ tune  ·  Shift or PageUp/Dn = coarse  ·  "
                          "Enter = accept  ·  ←/→ navigate  ·  "
                          "R = reset auto  ·  O = highlight marks  ·  "
                          "Ctrl+Z = undo  ·  hold Space = original image")
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet("color: #888; font-size: 11px;")
        col.addWidget(help_lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        col.addWidget(line)

        scroll.setWidget(inner)
        return scroll

    # ------------------------------------------------------------------
    # Loading an image
    # ------------------------------------------------------------------
    def open_project(self, project, index: int, return_to_review: bool = False):
        """Show *project* starting at image *index*."""
        self.project = project
        self.return_to_review = return_to_review
        self.load_index(index)

    def load_index(self, index: int) -> None:
        if not self.project or not self.project.images:
            return
        index = max(0, min(index, len(self.project.images) - 1))
        self.project.current_index = index
        self.entry = self.project.images[index]
        self._undo_stack.clear()
        self._load_current()

    def _load_current(self) -> None:
        entry = self.entry
        self.file_lbl.setText(entry.display_name)
        self.channel_lbl.setText(f"Channel: {entry.channel}")

        try:
            self.raw = image_io.get_image(entry.path)
            self.proc = image_io.get_processed(
                entry.path, self.project.subtract_background,
                self.project.radius_for(entry.channel))
        except Exception as exc:                       # noqa: BLE001
            entry.missing = True
            self.raw = None
            self.proc = None
            self.threshold_lbl.setText("Could not load image")
            self.channel_lbl.setText(f"{entry.channel}  —  {exc}")
            self._update_progress()
            self.setFocus()
            return

        entry.missing = False
        entry.bit_depth = image_io.bit_depth(self.proc)
        entry.max_value = image_io.max_value(self.proc)
        entry.height, entry.width = self.raw.shape[:2]
        self._fine = max(1, round(entry.max_value / 255))
        self._coarse = self._fine * 10

        self.base = image_io.auto_stretch(self.proc)
        self._raw_display = image_io.raw_display(
            self.raw, image_io.max_value(self.raw))
        self.histogram.set_histogram(self.proc, entry.max_value)
        self._exclude_mask = measure.exclusion_mask(
            self.proc.shape, entry.exclusions)
        self._update_exclusion_label()
        self.bg_lbl.setText("✓ background subtracted (rolling ball)"
                            if self.project.subtract_background else "")
        self.canvas.set_draw_mode(self.draw_btn.isChecked())
        self._space_held = False
        self.canvas.set_overlay_visible(True)

        # restore display sliders for this image
        for slider, value in ((self.brightness, int(entry.brightness * 100)),
                               (self.contrast, int(entry.contrast * 100))):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)

        if entry.threshold is None:
            entry.auto_method = "MaxEntropy"
            entry.threshold = autothreshold.auto_threshold(
                self.proc, entry.max_value, "MaxEntropy")
            method = "MaxEntropy"
        else:
            method = entry.measurement.method if entry.measurement else "Manual"

        self._render_base()
        self.canvas.fit()
        self._set_threshold(entry.threshold, push_undo=False, method=method)
        self._update_progress()
        self.setFocus()

    # ------------------------------------------------------------------
    # Threshold + rendering
    # ------------------------------------------------------------------
    def _set_threshold(self, value: int, push_undo: bool = True,
                       method: str = "Manual") -> None:
        if self.proc is None or self.entry is None:
            return
        value = max(0, min(int(value), self.entry.max_value))
        if push_undo and self.entry.threshold is not None:
            self._undo_stack.append(self.entry.threshold)
            del self._undo_stack[:-200]

        self.entry.threshold = value
        self.entry.measurement = measure.measure(
            self.proc, value, method, self._exclude_mask)

        positive = self.proc >= value
        self.canvas.set_overlay(measure.overlay_rgba(
            positive, self.entry.channel, self._exclude_mask, self._outline))
        self.histogram.set_threshold(value)
        self._update_readouts()

    def _refresh_overlay(self) -> None:
        """Redraw just the overlay (e.g. after toggling the highlight aid)."""
        if self.proc is None or self.entry is None \
                or self.entry.threshold is None:
            return
        positive = self.proc >= self.entry.threshold
        self.canvas.set_overlay(measure.overlay_rgba(
            positive, self.entry.channel, self._exclude_mask, self._outline))

    def _render_base(self) -> None:
        if self.base is None:
            return
        disp = image_io.apply_display(
            self.base, self.entry.brightness, self.entry.contrast)
        self.canvas.set_base(disp)

    def _update_readouts(self) -> None:
        entry = self.entry
        self.threshold_lbl.setText(
            f"Threshold: {entry.threshold} / {entry.max_value}")
        m = entry.measurement
        if m:
            self.m_pixels.setText(_fmt_int(m.positive_pixels))
            self.m_area.setText(f"{m.positive_area_pct:.2f} %")
            self.m_mean.setText(f"{m.mean_intensity_positive:.1f}")
            self.m_integ.setText(_fmt_int(round(m.integrated_intensity)))

    def _update_progress(self) -> None:
        p = self.project
        idx = p.current_index + 1
        self.progress_lbl.setText(
            f"Image {idx} / {len(p.images)}   ·   {p.done_count()} accepted")
        done = self.entry.done if self.entry else False
        self.accept_btn.setText("Accepted ✓ — Enter for next"
                                if done else "Accept  (Enter)")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_histogram_drag(self, value: int) -> None:
        self._set_threshold(value)

    def _reapply_auto(self) -> None:
        if self.proc is None:
            return
        self.entry.auto_method = "MaxEntropy"
        value = autothreshold.auto_threshold(
            self.proc, self.entry.max_value, "MaxEntropy")
        self._set_threshold(value, method="MaxEntropy")

    def _reset_auto(self) -> None:
        self._reapply_auto()

    def _on_display_changed(self) -> None:
        if self.entry is None:
            return
        self.entry.brightness = self.brightness.value() / 100.0
        self.entry.contrast = self.contrast.value() / 100.0
        if not self._space_held:        # raw preview ignores brightness/contrast
            self._render_base()

    def _reset_display(self) -> None:
        self.brightness.setValue(0)
        self.contrast.setValue(100)

    def _on_outline_toggled(self, checked: bool) -> None:
        self._outline = checked
        if not self._space_held:
            self._refresh_overlay()
        self.setFocus()

    def _undo(self) -> None:
        if self._undo_stack:
            self._set_threshold(self._undo_stack.pop(), push_undo=False)

    # --- exclusion boxes ----------------------------------------------
    def _on_region_drawn(self, x: float, y: float,
                         w: float, h: float) -> None:
        if self.raw is None or self.entry is None:
            return
        img_h, img_w = self.raw.shape[:2]
        x0 = max(0, min(round(x), img_w))
        y0 = max(0, min(round(y), img_h))
        x1 = max(0, min(round(x + w), img_w))
        y1 = max(0, min(round(y + h), img_h))
        box_w, box_h = x1 - x0, y1 - y0
        if box_w < 3 or box_h < 3:        # ignore stray clicks
            return
        self.entry.exclusions.append([x0, y0, box_w, box_h])
        self._refresh_exclusions()

    def _toggle_draw_mode(self, checked: bool) -> None:
        self.canvas.set_draw_mode(checked)
        self.setFocus()

    def _undo_exclusion(self) -> None:
        if self.entry and self.entry.exclusions:
            self.entry.exclusions.pop()
            self._refresh_exclusions()

    def _clear_exclusions(self) -> None:
        if self.entry and self.entry.exclusions:
            self.entry.exclusions.clear()
            self._refresh_exclusions()

    def _refresh_exclusions(self) -> None:
        self._exclude_mask = measure.exclusion_mask(
            self.raw.shape, self.entry.exclusions)
        self._update_exclusion_label()
        method = (self.entry.measurement.method
                  if self.entry.measurement else "Manual")
        self._set_threshold(self.entry.threshold, push_undo=False,
                            method=method)

    def _update_exclusion_label(self) -> None:
        n = len(self.entry.exclusions) if self.entry else 0
        if n:
            self.excl_lbl.setText(
                f"{n} exclusion box{'es' if n != 1 else ''} — not counted")
        else:
            self.excl_lbl.setText("No exclusion boxes")

    def _apply_exclusions_to_all(self) -> None:
        """Copy this image's exclusion boxes onto every other image."""
        if not self.project or self.entry is None:
            return
        boxes = [list(b) for b in self.entry.exclusions]
        others = [e for e in self.project.images if e is not self.entry]
        if not others:
            return

        if boxes:
            count = f"{len(boxes)} box{'es' if len(boxes) != 1 else ''}"
            question = (f"Apply the current {count} to all "
                        f"{len(self.project.images)} images?\n\n"
                        "This replaces any exclusion boxes already drawn on "
                        "the other images.")
        else:
            question = ("The current image has no exclusion boxes.\n\n"
                        f"Remove exclusion boxes from all other "
                        f"{len(others)} images?")
        if QMessageBox.question(self, "Apply boxes to all images",
                                question) != QMessageBox.StandardButton.Yes:
            return

        for entry in others:
            entry.exclusions = [list(b) for b in boxes]

        # Re-measure images already tuned, so their numbers stay correct.
        to_recompute = [e for e in others if e.threshold is not None]
        progress = None
        if to_recompute:
            progress = QProgressDialog("Updating measurements…", "Cancel",
                                       0, len(to_recompute), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(400)
        for i, entry in enumerate(to_recompute):
            if progress is not None:
                progress.setValue(i)
                if progress.wasCanceled():
                    break
            try:
                img = image_io.get_processed(
                    entry.path, self.project.subtract_background,
                    self.project.radius_for(entry.channel))
            except Exception:                          # noqa: BLE001
                continue
            excl = measure.exclusion_mask(img.shape, entry.exclusions)
            method = entry.measurement.method if entry.measurement else "Manual"
            entry.measurement = measure.measure(
                img, entry.threshold, method, excl)
        if progress is not None:
            progress.setValue(len(to_recompute))

        self.main.autosave()
        verb = "Applied boxes to" if boxes else "Cleared boxes from"
        self.main.statusBar().showMessage(
            f"{verb} {len(others)} other image(s).", 5000)

    def _accept(self) -> None:
        if self.entry is None or self.raw is None:
            self._next()
            return
        self.entry.done = True
        self.main.autosave()
        if self.return_to_review:
            self._go_review()
            return
        nxt = self._next_unfinished()
        if nxt is None:
            self._go_review()
        else:
            self.load_index(nxt)

    def _next_unfinished(self) -> int | None:
        imgs = self.project.images
        cur = self.project.current_index
        for i in range(cur + 1, len(imgs)):
            if not imgs[i].done:
                return i
        for i in range(0, cur):
            if not imgs[i].done:
                return i
        return None

    def _next(self) -> None:
        if self.project.current_index < len(self.project.images) - 1:
            self.load_index(self.project.current_index + 1)

    def _prev(self) -> None:
        if self.project.current_index > 0:
            self.load_index(self.project.current_index - 1)

    def _save(self) -> None:
        self.main.autosave(notify=True)

    def _go_review(self) -> None:
        self.main.show_review()

    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        coarse = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if self.raw is not None and key == Qt.Key.Key_Up:
            self._set_threshold(self.entry.threshold +
                                (self._coarse if coarse else self._fine))
        elif self.raw is not None and key == Qt.Key.Key_Down:
            self._set_threshold(self.entry.threshold -
                                (self._coarse if coarse else self._fine))
        elif self.raw is not None and key == Qt.Key.Key_PageUp:
            self._set_threshold(self.entry.threshold + self._coarse)
        elif self.raw is not None and key == Qt.Key.Key_PageDown:
            self._set_threshold(self.entry.threshold - self._coarse)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept()
        elif key == Qt.Key.Key_Left:
            self._prev()
        elif key == Qt.Key.Key_Right:
            self._next()
        elif key == Qt.Key.Key_Z and (mods & Qt.KeyboardModifier.ControlModifier):
            self._undo()
        elif key == Qt.Key.Key_R and self.raw is not None:
            self._reset_auto()
        elif key == Qt.Key.Key_O:
            self.outline_chk.toggle()
        elif key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._show_raw_preview(True)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._show_raw_preview(False)
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        # Never leave the raw preview stuck on if focus is lost mid-hold.
        if self._space_held:
            self._show_raw_preview(False)
        super().focusOutEvent(event)

    def _show_raw_preview(self, on: bool) -> None:
        """Hold-Space preview: show the raw image with no overlay and no
        display brightness/contrast — exactly the data being quantified."""
        if self.raw is None:
            return
        self._space_held = on
        if on:
            self.canvas.set_base(self._raw_display)
            self.canvas.set_overlay_visible(False)
        else:
            self._render_base()
            self._refresh_overlay()   # in case the highlight aid was toggled
            self.canvas.set_overlay_visible(True)
