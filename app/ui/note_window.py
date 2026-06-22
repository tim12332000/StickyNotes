from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QPlainTextEdit

from app.config import (
    AUTO_SAVE_DELAY_MILLISECONDS,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from app.models.note import Note


class NoteWindow(QMainWindow):
    def __init__(self, note: Note, save_note: Callable[[Note], None]) -> None:
        super().__init__()
        self._note = note
        self._save_note = save_note

        self._editor = QPlainTextEdit(note.content)
        self._editor.setPlaceholderText("輸入便箋內容…")
        self._editor.textChanged.connect(self._schedule_save)
        self.setCentralWidget(self._editor)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(AUTO_SAVE_DELAY_MILLISECONDS)
        self._save_timer.timeout.connect(self._save_current_content)

        self.setWindowTitle("Sticky Notes")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_current_content()
        super().closeEvent(event)

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _save_current_content(self) -> None:
        self._note.content = self._editor.toPlainText()
        self._save_note(self._note)
