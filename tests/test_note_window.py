from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.controller import StickyNotesController
from app.models.note import Note, NoteWindowState
from app.storage.note_repository import NoteRepository
from app.ui.note_window import NoteWindow


@pytest.fixture(scope="module")
def application() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app


def test_close_flushes_pending_content_and_window_state(
    application: QApplication,
) -> None:
    note = Note(content="before")
    saved_notes: list[Note] = []
    saved_states: list[NoteWindowState] = []
    window = NoteWindow(
        note=note,
        save_note=lambda saved_note: saved_notes.append(saved_note),
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: saved_states.append(state),
    )
    window.show()
    window._editor.setPlainText("after")

    window.close()

    assert saved_notes[-1].content == "after"
    assert saved_states
    assert saved_states[-1].width >= 220
    assert saved_states[-1].height >= 160


def test_color_change_is_saved(application: QApplication) -> None:
    note = Note()
    saved_colors: list[str] = []
    window = NoteWindow(
        note=note,
        save_note=lambda saved_note: saved_colors.append(saved_note.color),
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )

    window._set_color("#c8e6c9")
    window.close()

    assert note.color == "#c8e6c9"
    assert saved_colors[-1] == "#c8e6c9"


def test_new_note_is_offset_from_source_window(
    application: QApplication, tmp_path: Path
) -> None:
    repository = NoteRepository(tmp_path)
    source_note = repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()
    source_window = controller._windows[source_note.note_id]
    source_window.setGeometry(50, 60, 300, 220)

    controller.create_note(source_note.note_id)

    new_note_id = next(
        note_id for note_id in controller._windows if note_id != source_note.note_id
    )
    new_geometry = controller._windows[new_note_id].geometry()
    assert new_geometry.x() == 80
    assert new_geometry.y() == 90
    assert new_geometry.size() == source_window.geometry().size()
    for window in controller._windows.values():
        window.hide()
