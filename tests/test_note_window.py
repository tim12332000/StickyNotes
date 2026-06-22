from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QToolButton

from app.config import MAX_FONT_SIZE, MIN_FONT_SIZE
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


def test_header_uses_accessible_icon_buttons(application: QApplication) -> None:
    window = NoteWindow(
        note=Note(),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )

    buttons = window.findChildren(QToolButton)

    assert len(buttons) == 9
    assert all(button.text() == "" for button in buttons)
    assert all(not button.icon().isNull() for button in buttons)
    assert all(button.accessibleName() for button in buttons)
    window.close()


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


def test_add_button_offsets_from_source_window(
    application: QApplication, tmp_path: Path
) -> None:
    repository = NoteRepository(tmp_path)
    source_note = repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()
    source_window = controller._windows[source_note.note_id]
    source_window.setGeometry(50, 60, 300, 220)

    add_button = next(
        button
        for button in source_window.findChildren(QToolButton)
        if button.accessibleName() == "新增便箋"
    )
    add_button.click()

    new_note_id = next(
        note_id for note_id in controller._windows if note_id != source_note.note_id
    )
    new_geometry = controller._windows[new_note_id].geometry()
    assert new_geometry.x() == 80
    assert new_geometry.y() == 90
    for window in controller._windows.values():
        window.hide()


def test_refresh_after_sync_reconciles_windows(
    application: QApplication, tmp_path: Path
) -> None:
    repository = NoteRepository(tmp_path)
    repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()

    # A note that sync downloaded (written straight into the repository).
    downloaded = Note(content="from cloud")
    repository.save_note(downloaded)
    controller._refresh_after_sync()
    assert downloaded.note_id in controller._windows
    window = controller._windows[downloaded.note_id]
    assert window._editor.toPlainText() == "from cloud"

    # A remote edit to an already-open note is reloaded into its window.
    downloaded.content = "edited in cloud"
    repository.save_note(downloaded)
    controller._refresh_after_sync()
    assert window._editor.toPlainText() == "edited in cloud"

    # A remote deletion closes the window.
    repository.delete_note(downloaded.note_id)
    controller._refresh_after_sync()
    assert downloaded.note_id not in controller._windows
    for open_window in controller._windows.values():
        open_window.hide()


def test_startup_sync_is_skipped_without_a_token(
    application: QApplication, tmp_path: Path
) -> None:
    repository = NoteRepository(tmp_path)
    repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()
    # No token means not authorized, so startup must not launch a sync worker.
    assert controller._sync_worker is None
    for window in controller._windows.values():
        window.hide()


def test_editing_arms_auto_sync_only_when_connected(
    application: QApplication, tmp_path: Path
) -> None:
    repository = NoteRepository(tmp_path)
    note = repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()

    # Not connected yet: saving does not arm the debounce timer.
    controller._save_note(note)
    assert not controller._auto_sync_timer.isActive()

    # After authorization (token present): saving arms a debounced sync.
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")
    controller._save_note(note)
    assert controller._auto_sync_timer.isActive()

    controller._auto_sync_timer.stop()
    for window in controller._windows.values():
        window.hide()


def test_reload_keeps_view_when_content_is_unchanged(
    application: QApplication,
) -> None:
    window = NoteWindow(
        note=Note(content="line1\nline2\nline3"),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )
    cursor = window._editor.textCursor()
    cursor.setPosition(5)
    window._editor.setTextCursor(cursor)

    # Same content: the editor (and cursor) must be left untouched, not reset.
    window.reload(Note(content="line1\nline2\nline3"))
    assert window._editor.textCursor().position() == 5
    assert window._editor.toPlainText() == "line1\nline2\nline3"

    # Different content: the editor updates.
    window.reload(Note(content="changed"))
    assert window._editor.toPlainText() == "changed"
    window.close()


def test_sync_indicator_starts_and_stops(application: QApplication) -> None:
    window = NoteWindow(
        note=Note(),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )
    assert not window._spinner.is_spinning
    window.start_sync_indicator()
    assert window._spinner.is_spinning
    window.stop_sync_indicator()
    assert not window._spinner.is_spinning
    window.close()


def test_color_is_applied_only_to_the_header(application: QApplication) -> None:
    window = NoteWindow(
        note=Note(color="#b3e5fc"),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )

    style = window.centralWidget().styleSheet()

    # The chosen color paints the title bar only; the body stays a fixed dark
    # surface and the editor keeps light text — independent of the color.
    assert "#noteHeader { background: #b3e5fc; }" in style
    assert "#noteBody { background: #333333;" in style
    assert "QPlainTextEdit { background: #333333; color: #f5f5f5;" in style
    # The scrollbar is restyled to match the dark body instead of the chunky
    # native one.
    assert "QScrollBar::handle:vertical" in style
    window.close()


def test_collapse_rolls_up_to_the_title_bar_and_back(
    application: QApplication,
) -> None:
    window = NoteWindow(
        note=Note(),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )
    window.resize(300, 260)
    window.show()
    application.processEvents()
    expanded_height = window.height()
    assert window._editor.isVisible()

    window._toggle_collapsed()
    application.processEvents()
    assert not window._editor.isVisible()
    assert window.height() < expanded_height

    window._toggle_collapsed()
    application.processEvents()
    assert window._editor.isVisible()
    assert window.height() == expanded_height
    window.close()


def test_collapsed_window_persists_expanded_height(
    application: QApplication,
) -> None:
    saved_states: list[NoteWindowState] = []
    window = NoteWindow(
        note=Note(),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: saved_states.append(state),
    )
    window.resize(300, 260)
    window.show()
    application.processEvents()
    expanded_height = window.height()

    window._toggle_collapsed()
    window.save_before_exit()

    assert saved_states[-1].height == expanded_height
    window.close()


def test_apply_font_updates_editor_and_menu_check(application: QApplication) -> None:
    window = NoteWindow(
        note=Note(),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
        font_family="Arial",
        font_size=11,
    )

    # The current family is always offered in the menu and starts checked.
    assert window._font_actions["Arial"].isChecked()

    window.apply_font("Arial", 18)
    assert window._editor.font().family() == "Arial"
    assert window._editor.font().pointSize() == 18

    # Switching family drives the editor font and clears the old menu check.
    window.apply_font("Times New Roman", 14)
    assert window._editor.font().family() == "Times New Roman"
    assert window._editor.font().pointSize() == 14
    assert not window._font_actions["Arial"].isChecked()
    window.close()


def test_font_change_applies_to_all_notes_and_persists(
    application: QApplication, tmp_path: Path
) -> None:
    repository = NoteRepository(tmp_path)
    repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()
    controller.create_note()  # a second note picks up the current global font

    controller._change_font("Consolas", 20)

    for window in controller._windows.values():
        assert window._editor.font().family() == "Consolas"
        assert window._editor.font().pointSize() == 20
    assert repository.load_font_settings() == ("Consolas", 20)
    for window in controller._windows.values():
        window.hide()


def test_font_size_is_clamped(application: QApplication, tmp_path: Path) -> None:
    repository = NoteRepository(tmp_path)
    repository.create_note()
    controller = StickyNotesController(application, repository)
    controller.start()

    controller._change_font("Arial", 9999)
    assert repository.load_font_settings()[1] == MAX_FONT_SIZE

    controller._change_font("Arial", 1)
    assert repository.load_font_settings()[1] == MIN_FONT_SIZE
    for window in controller._windows.values():
        window.hide()


def test_resize_cursor_matches_edges() -> None:
    assert NoteWindow._resize_cursor(Qt.Edge(0)) is None
    assert NoteWindow._resize_cursor(Qt.Edge.LeftEdge) == Qt.CursorShape.SizeHorCursor
    assert NoteWindow._resize_cursor(Qt.Edge.BottomEdge) == Qt.CursorShape.SizeVerCursor
    assert (
        NoteWindow._resize_cursor(Qt.Edge.TopEdge | Qt.Edge.LeftEdge)
        == Qt.CursorShape.SizeFDiagCursor
    )
    assert (
        NoteWindow._resize_cursor(Qt.Edge.BottomEdge | Qt.Edge.LeftEdge)
        == Qt.CursorShape.SizeBDiagCursor
    )


def test_window_borders_are_detected_as_resize_edges(
    application: QApplication,
) -> None:
    window = NoteWindow(
        note=Note(),
        save_note=lambda saved_note: None,
        create_note=lambda: None,
        delete_note=lambda note_id: None,
        save_window_state=lambda note_id, state: None,
    )
    window.setGeometry(120, 140, 300, 220)
    window.show()

    bottom_right = window.mapToGlobal(
        QPoint(window.width() - 1, window.height() - 1)
    )
    edges = window._resize_edges_at(bottom_right)
    assert edges & Qt.Edge.RightEdge
    assert edges & Qt.Edge.BottomEdge

    center = window.mapToGlobal(QPoint(window.width() // 2, window.height() // 2))
    assert window._resize_edges_at(center) == Qt.Edge(0)
    window.close()
