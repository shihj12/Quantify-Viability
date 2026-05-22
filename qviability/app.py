"""Main window — owns the project and switches between the three screens."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QMainWindow, QStackedWidget

from .core.project import Project, default_session_path, save_project
from .ui.load_screen import LoadScreen
from .ui.review_screen import ReviewScreen
from .ui.threshold_screen import ThresholdScreen


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ViabilityQuantifier")
        self.resize(1320, 840)

        self.project: Project | None = None
        self.session_path: str | None = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.load_screen = LoadScreen(self)
        self.threshold_screen = ThresholdScreen(self)
        self.review_screen = ReviewScreen(self)
        for widget in (self.load_screen, self.threshold_screen,
                       self.review_screen):
            self.stack.addWidget(widget)

        self.stack.setCurrentWidget(self.load_screen)
        self.statusBar().showMessage("Choose a green folder and a red folder to begin.")

    # ------------------------------------------------------------------
    def start_project(self, project: Project) -> None:
        self.project = project
        self.session_path = default_session_path(project)
        self.review_screen.set_project(project)
        self.threshold_screen.open_project(project, 0, return_to_review=False)
        self.stack.setCurrentWidget(self.threshold_screen)
        self.autosave()

    def resume_project(self, project: Project, session_path: str) -> None:
        for entry in project.images:
            entry.missing = not os.path.isfile(entry.path)
        self.project = project
        self.session_path = session_path
        self.review_screen.set_project(project)
        self.threshold_screen.open_project(
            project, project.first_unfinished(), return_to_review=False)
        self.stack.setCurrentWidget(self.threshold_screen)
        self.statusBar().showMessage(
            f"Resumed — {project.done_count()} of {len(project.images)} done.",
            5000)

    def edit_image(self, index: int) -> None:
        """Jump from the review gallery to re-tune one image."""
        self.threshold_screen.open_project(
            self.project, index, return_to_review=True)
        self.stack.setCurrentWidget(self.threshold_screen)

    def show_threshold(self) -> None:
        self.threshold_screen.return_to_review = False
        self.stack.setCurrentWidget(self.threshold_screen)
        self.threshold_screen.setFocus()

    def show_review(self) -> None:
        self.review_screen.set_project(self.project)
        self.review_screen.refresh()
        self.stack.setCurrentWidget(self.review_screen)

    # ------------------------------------------------------------------
    def autosave(self, notify: bool = False) -> None:
        if not self.project or not self.session_path:
            return
        try:
            save_project(self.project, self.session_path)
            if notify:
                self.statusBar().showMessage(f"Saved → {self.session_path}", 4000)
        except Exception as exc:                       # noqa: BLE001
            self.statusBar().showMessage(f"Could not save session: {exc}", 6000)

    def closeEvent(self, event) -> None:
        self.autosave()
        super().closeEvent(event)
