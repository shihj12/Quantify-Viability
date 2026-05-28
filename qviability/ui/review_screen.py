"""Review screen — gallery of every tuned image for a final double-check.

Each card shows the annotated thumbnail and key numbers. Click a card to jump
back and re-tune it. "Export" writes the Excel workbook and annotated PNGs.
"""

from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMessageBox, QProgressDialog,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..core import image_io
from ..export import annotate, excel, pdf
from .widgets import numpy_to_qpixmap

THUMB_W = 230
COLUMNS = 4


class ThumbnailCard(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.setFrameShape(QFrame.Shape.Box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.image_lbl = QLabel()
        self.image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_lbl.setMinimumSize(THUMB_W, int(THUMB_W * 0.78))
        self.name_lbl = QLabel()
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.info_lbl = QLabel()
        self.info_lbl.setStyleSheet("font-size: 11px; color: #ccc;")
        layout.addWidget(self.image_lbl)
        layout.addWidget(self.name_lbl)
        layout.addWidget(self.info_lbl)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.index)

    def set_done_style(self, done: bool) -> None:
        self.setStyleSheet(
            "ThumbnailCard { border: 1px solid #555; }" if done else
            "ThumbnailCard { border: 2px solid #d9534f; }")


class ReviewScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.project = None
        # path -> (signature, QPixmap)
        self._thumb_cache: dict[str, tuple] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        title = QLabel("Review — double-check every image")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)
        self.status = QLabel("")
        root.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(10)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, stretch=1)

        buttons = QHBoxLayout()
        back = QPushButton("◀ Back to tuning")
        back.clicked.connect(lambda: self.main.show_threshold())
        buttons.addWidget(back)
        buttons.addStretch(1)
        self.export_btn = QPushButton("Export results  ▶")
        self.export_btn.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.export_btn.clicked.connect(self._on_export)
        buttons.addWidget(self.export_btn)
        root.addLayout(buttons)

    # ------------------------------------------------------------------
    def set_project(self, project) -> None:
        self.project = project

    def refresh(self) -> None:
        """Rebuild the gallery, (re)generating thumbnails as needed."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        images = self.project.images
        not_done = sum(1 for e in images if not e.done)
        self.status.setText(
            f"{len(images)} images   ·   {len(images) - not_done} accepted   ·   "
            + (f"{not_done} still need a threshold (red border)"
               if not_done else "all accepted ✓"))

        progress = QProgressDialog("Preparing thumbnails…", "Cancel",
                                   0, len(images), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        for i, entry in enumerate(images):
            progress.setValue(i)
            if progress.wasCanceled():
                break
            card = ThumbnailCard(i)
            card.clicked.connect(self.main.edit_image)
            card.name_lbl.setText(entry.display_name)
            card.set_done_style(entry.done)
            self._fill_card(card, entry)
            self.grid.addWidget(card, i // COLUMNS, i % COLUMNS)
        progress.setValue(len(images))

    def _fill_card(self, card: ThumbnailCard, entry) -> None:
        m = entry.measurement
        if m:
            card.info_lbl.setText(
                f"{entry.channel}  ·  thr {entry.threshold}\n"
                f"area {m.positive_area_pct:.2f}%  ·  "
                f"int.intensity {round(m.integrated_intensity):,}")
        else:
            card.info_lbl.setText(f"{entry.channel}  ·  not tuned yet")

        signature = (entry.threshold, round(entry.brightness, 3),
                     round(entry.contrast, 3),
                     tuple(tuple(r) for r in entry.exclusions))
        cached = self._thumb_cache.get(entry.path)
        if cached and cached[0] == signature:
            card.image_lbl.setPixmap(cached[1])
            return

        pixmap = self._render_thumb(entry)
        if pixmap is not None:
            self._thumb_cache[entry.path] = (signature, pixmap)
            card.image_lbl.setPixmap(pixmap)
        else:
            card.image_lbl.setText("(could not load)")

    def _render_thumb(self, entry):
        try:
            raw = image_io.get_processed(
                entry.path, self.project.subtract_background,
                self.project.radius_for(entry.channel))
        except Exception:                              # noqa: BLE001
            return None
        threshold = entry.threshold if entry.threshold is not None else 10 ** 9
        rgb = annotate.render_overlay_rgb(
            raw, threshold, entry.channel, entry.brightness, entry.contrast,
            entry.exclusions)
        h, w = rgb.shape[:2]
        new_w = THUMB_W
        new_h = max(1, round(h * new_w / w))
        small = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return numpy_to_qpixmap(small)

    # ------------------------------------------------------------------
    def _on_export(self) -> None:
        images = self.project.images
        not_tuned = [e for e in images if e.threshold is None]
        if not_tuned:
            resp = QMessageBox.question(
                self, "Some images not tuned",
                f"{len(not_tuned)} image(s) have no threshold yet and will be "
                "exported with blank values. Export anyway?")
            if resp != QMessageBox.StandardButton.Yes:
                return

        folder = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not folder:
            return

        try:
            result = self._run_export(folder)
        except Exception as exc:                       # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        if result is None:
            self.main.statusBar().showMessage("Export cancelled.", 5000)
            return

        pdf_note = "viability_QC.pdf, " if result else ""
        QMessageBox.information(
            self, "Export complete",
            f"Wrote viability_results.xlsx, {pdf_note}and annotated images "
            f"to:\n{folder}")

    def _run_export(self, folder: str) -> int | None:
        """Write the spreadsheet, annotated PNGs and QC PDF.

        Returns the number of QC PDF pages written, or None if the user
        cancelled partway through.
        """
        self.project.output_folder = folder
        images = self.project.images
        annotated_dir = Path(folder) / "annotated"
        tuned = [e for e in images if e.threshold is not None]

        total = len(images) + len(tuned) + 1     # PNGs + PDF pages + workbook
        progress = QProgressDialog("Exporting annotated images…", "Cancel",
                                   0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        step = 0

        # 1. Annotated PNGs --------------------------------------------------
        for entry in images:
            progress.setValue(step)
            step += 1
            if progress.wasCanceled():
                return None
            if entry.threshold is None:
                continue
            try:
                raw = image_io.get_processed(
                    entry.path, self.project.subtract_background,
                    self.project.radius_for(entry.channel))
            except Exception:                          # noqa: BLE001
                continue
            m = entry.measurement
            caption = (f"{entry.display_name}  |  {entry.channel}  |  "
                       f"thr {entry.threshold}  |  "
                       f"area {m.positive_area_pct:.2f}%  |  "
                       f"int {round(m.integrated_intensity):,}"
                       if m else f"{entry.display_name}  |  {entry.channel}")
            stem = Path(entry.display_name).stem
            out = annotated_dir / f"{stem}_thr{entry.threshold}.png"
            annotate.save_annotated_png(
                raw, entry.threshold, entry.channel, caption, str(out),
                entry.brightness, entry.contrast, entry.exclusions)

        # 2. QC PDF — one before/after page per tuned image ------------------
        progress.setLabelText("Building QC PDF…")
        pdf_pages = []
        for entry in tuned:
            progress.setValue(step)
            step += 1
            if progress.wasCanceled():
                return None
            page = pdf.render_qc_page(self.project, entry)
            if page is not None:
                pdf_pages.append(page)
        if pdf_pages:
            pdf.save_pdf(pdf_pages, str(Path(folder) / "viability_QC.pdf"))

        # 3. Results spreadsheet --------------------------------------------
        progress.setLabelText("Writing spreadsheet…")
        excel.write_xlsx(self.project,
                         str(Path(folder) / "viability_results.xlsx"))
        progress.setValue(total)
        return len(pdf_pages)
