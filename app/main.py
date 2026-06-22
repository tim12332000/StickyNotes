from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.config import APPLICATION_NAME, get_data_directory
from app.storage.note_repository import NoteRepository
from app.ui.note_window import NoteWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(APPLICATION_NAME)

    repository = NoteRepository(get_data_directory())
    notes = repository.load_notes()
    if not notes:
        notes.append(repository.create_note())

    windows = [NoteWindow(note, repository.save_note) for note in notes]
    for window in windows:
        window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
