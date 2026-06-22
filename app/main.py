from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.config import APPLICATION_NAME, get_data_directory
from app.controller import StickyNotesController
from app.icons import asset_icon
from app.single_instance import SingleInstanceServer, notify_running_instance
from app.storage.note_repository import NoteRepository


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(APPLICATION_NAME)
    application.setWindowIcon(asset_icon("note.svg"))
    if notify_running_instance():
        return 0

    repository = NoteRepository(get_data_directory())
    controller = StickyNotesController(application, repository)
    single_instance = SingleInstanceServer(controller.show_all_notes, parent=application)
    if not single_instance.start() and notify_running_instance():
        return 0
    controller.start()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
