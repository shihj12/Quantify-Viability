"""Load screen — pick a green folder and a red folder, then Start.

Each slot has an optional "filename contains" filter so a folder that mixes
GFP / RFP / Overlay files (as the CELENA-S exports do) can be narrowed to one
channel without sorting files by hand. The channel is set purely by which slot
a folder is in — there is no automatic channel detection.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import image_io
from ..core.project import (DEFAULT_GREEN_BG_RADIUS, DEFAULT_RED_BG_RADIUS,
                            Channel, ImageEntry, Project,
                            find_session, load_project)


class LoadScreen(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.green_folder: str | None = None
        self.red_folder: str | None = None
        self.session_path: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("ViabilityQuantifier")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)
        root.addWidget(QLabel(
            "Choose the folder of green (live / GFP) images and the folder of "
            "red (dead / RFP) images, then press Start."))

        self.green_box, self.green_path_lbl, self.green_filter = \
            self._make_folder_box("Green / Live (GFP) folder", Channel.GREEN)
        self.red_box, self.red_path_lbl, self.red_filter = \
            self._make_folder_box("Red / Dead (RFP) folder", Channel.RED)
        root.addWidget(self.green_box)
        root.addWidget(self.red_box)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Include", "Filename", "Channel"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.table, stretch=1)

        self.status = QLabel("No images loaded.")
        root.addWidget(self.status)

        self.bg_check = QCheckBox(
            "Subtract background (rolling ball) — corrects uneven illumination "
            "before thresholding")
        self.bg_check.toggled.connect(self._on_bg_toggled)
        root.addWidget(self.bg_check)

        # Per-channel rolling-ball radius. The radius should be at least the
        # size of the largest object to keep, so the green/GFP and red/RFP
        # channels typically need different values.
        self.radius_row = QHBoxLayout()
        self.radius_row.setContentsMargins(24, 0, 0, 0)
        self.radius_row.addWidget(QLabel("Rolling-ball radius (px) —  Green:"))
        self.green_radius = QSpinBox()
        self.green_radius.setRange(1, 500)
        self.green_radius.setValue(DEFAULT_GREEN_BG_RADIUS)
        self.radius_row.addWidget(self.green_radius)
        self.radius_row.addSpacing(16)
        self.radius_row.addWidget(QLabel("Red:"))
        self.red_radius = QSpinBox()
        self.red_radius.setRange(1, 500)
        self.red_radius.setValue(DEFAULT_RED_BG_RADIUS)
        self.radius_row.addWidget(self.red_radius)
        self.radius_row.addStretch(1)
        root.addLayout(self.radius_row)
        self._on_bg_toggled(False)

        buttons = QHBoxLayout()
        self.resume_btn = QPushButton("Resume previous session")
        self.resume_btn.clicked.connect(self._on_resume)
        self.resume_btn.setVisible(False)
        buttons.addWidget(self.resume_btn)
        buttons.addStretch(1)
        self.start_btn = QPushButton("Start  ▶")
        self.start_btn.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start)
        buttons.addWidget(self.start_btn)
        root.addLayout(buttons)

    # ------------------------------------------------------------------
    def _make_folder_box(self, label: str, channel: str):
        box = QGroupBox(label)
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        browse = QPushButton("Choose folder…")
        browse.clicked.connect(lambda: self._browse(channel))
        path_lbl = QLabel("(none)")
        path_lbl.setStyleSheet("color: #888;")
        row.addWidget(browse)
        row.addWidget(path_lbl, stretch=1)
        layout.addLayout(row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filename contains:"))
        filt = QLineEdit()
        filt.setPlaceholderText("e.g. GFP  —  leave blank to include every image")
        filt.textChanged.connect(self._rescan)
        filter_row.addWidget(filt, stretch=1)
        layout.addLayout(filter_row)
        return box, path_lbl, filt

    def _browse(self, channel: str) -> None:
        folder = QFileDialog.getExistingDirectory(self, f"Choose {channel} folder")
        if not folder:
            return
        if channel == Channel.GREEN:
            self.green_folder = folder
            self.green_path_lbl.setText(folder)
            self.green_path_lbl.setStyleSheet("color: #ddd;")
        else:
            self.red_folder = folder
            self.red_path_lbl.setText(folder)
            self.red_path_lbl.setStyleSheet("color: #ddd;")
        self._check_for_session(folder)
        self._rescan()

    def _check_for_session(self, folder: str) -> None:
        session = find_session(folder)
        if session:
            self.session_path = session
            self.resume_btn.setVisible(True)
            self.resume_btn.setText(
                f"Resume previous session ({Path(session).name})")

    # ------------------------------------------------------------------
    def _collect(self, folder: str | None, text_filter: str) -> list[Path]:
        if not folder:
            return []
        files = image_io.scan_folder(folder)
        needle = text_filter.strip().lower()
        if needle:
            files = [f for f in files if needle in f.name.lower()]
        return files

    def _rescan(self) -> None:
        green = self._collect(self.green_folder, self.green_filter.text())
        red = self._collect(self.red_folder, self.red_filter.text())

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self._rows: list[tuple[str, str]] = []   # (path, channel)
        for files, channel in ((green, Channel.GREEN), (red, Channel.RED)):
            for f in files:
                self._add_row(f, channel)
        self.table.blockSignals(False)

        n = len(self._rows)
        self.status.setText(
            f"{len(green)} green + {len(red)} red = {n} image(s) listed."
            if n else "No images match — choose a folder or adjust the filter.")
        self._update_start_enabled()

    def _add_row(self, path: Path, channel: str) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self._rows.append((str(path), channel))

        check = QTableWidgetItem()
        check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        check.setCheckState(Qt.CheckState.Checked)
        self.table.setItem(r, 0, check)

        name_item = QTableWidgetItem(path.name)
        name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.table.setItem(r, 1, name_item)

        chan_item = QTableWidgetItem(channel)
        chan_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        chan_item.setForeground(QColor(
            "#5fd16a" if channel == Channel.GREEN else "#ff6fae"))
        self.table.setItem(r, 2, chan_item)

    def _on_bg_toggled(self, checked: bool) -> None:
        self.green_radius.setEnabled(checked)
        self.red_radius.setEnabled(checked)

    def _on_item_changed(self, _item) -> None:
        self._update_start_enabled()

    def _checked_count(self) -> int:
        return sum(1 for r in range(self.table.rowCount())
                   if self.table.item(r, 0).checkState() == Qt.CheckState.Checked)

    def _update_start_enabled(self) -> None:
        self.start_btn.setEnabled(self._checked_count() > 0)

    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        images: list[ImageEntry] = []
        for r, (path, channel) in enumerate(self._rows):
            if self.table.item(r, 0).checkState() != Qt.CheckState.Checked:
                continue
            images.append(ImageEntry(
                path=path, display_name=Path(path).name, channel=channel))
        if not images:
            return
        project = Project(green_folder=self.green_folder,
                           red_folder=self.red_folder, images=images,
                           subtract_background=self.bg_check.isChecked(),
                           green_bg_radius=self.green_radius.value(),
                           red_bg_radius=self.red_radius.value())
        self.main.start_project(project)

    def _on_resume(self) -> None:
        if not self.session_path:
            return
        try:
            project = load_project(self.session_path)
        except Exception as exc:                       # noqa: BLE001
            self.status.setText(f"Could not read session: {exc}")
            return
        self.main.resume_project(project, self.session_path)
