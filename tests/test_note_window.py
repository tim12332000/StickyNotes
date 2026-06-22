from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.models.note import Note, NoteWindowState
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
