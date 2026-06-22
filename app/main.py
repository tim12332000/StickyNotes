from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.config import APPLICATION_NAME, get_data_directory
from app.controller import StickyNotesController
from app.storage.note_repository import NoteRepository


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(APPLICATION_NAME)

    repository = NoteRepository(get_data_directory())
    controller = StickyNotesController(application, repository)
    controller.start()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
