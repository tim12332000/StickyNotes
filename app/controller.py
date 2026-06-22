from __future__ import annotations

from uuid import UUID

from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app.icons import asset_icon
from app.models.note import Note, NoteWindowState
from app.startup import is_startup_enabled, set_startup_enabled
from app.storage.note_repository import NoteRepository
from app.ui.note_window import NoteWindow


class StickyNotesController:
    def __init__(self, application: QApplication, repository: NoteRepository) -> None:
        self._application = application
        self._repository = repository
        self._windows: dict[UUID, NoteWindow] = {}
        self._tray_icon: QSystemTrayIcon | None = None
        self._restore_menu: QMenu | None = None
        self._application.aboutToQuit.connect(self._save_all_notes)

    def start(self) -> None:
        self._setup_system_tray()
        notes = self._repository.load_notes()
        if not notes:
            notes.append(self._repository.create_note())
        for note in notes:
            self._open_note(note)

    def create_note(self, source_note_id: UUID | None = None) -> None:
        note = self._repository.create_note()
        source_window = self._windows.get(source_note_id) if source_note_id else None
        if source_window is not None:
            source_geometry = source_window.geometry()
            screen = QGuiApplication.screenAt(source_geometry.center())
            if screen is not None:
                available = screen.availableGeometry()
                x = source_geometry.x() + 30
                y = source_geometry.y() + 30
                if x + source_geometry.width() > available.right() + 1:
                    x = available.left() + 30
                if y + source_geometry.height() > available.bottom() + 1:
                    y = available.top() + 30
                self._repository.save_window_state(
                    note.note_id,
                    NoteWindowState(
                        x=x,
                        y=y,
                        width=source_geometry.width(),
                        height=source_geometry.height(),
                    ),
                )
        self._open_note(note)

    def show_all_notes(self) -> None:
        for window in self._windows.values():
            window.show_and_activate()

    def _open_note(self, note: Note) -> None:
        existing_window = self._windows.get(note.note_id)
        if existing_window is not None:
            existing_window.show_and_activate()
            return

        window = NoteWindow(
            note=note,
            save_note=self._repository.save_note,
            create_note=lambda source_id=note.note_id: self.create_note(source_id),
            delete_note=self._delete_note,
            save_window_state=self._repository.save_window_state,
            initial_state=self._repository.load_window_state(note.note_id),
        )
        self._windows[note.note_id] = window
        window.show_and_activate()

    def _delete_note(self, note_id: UUID) -> None:
        window = self._windows.pop(note_id, None)
        if window is not None:
            window.close()
            window.deleteLater()
        self._repository.delete_note(note_id)

        if self._tray_icon is not None:
            self._tray_icon.showMessage(
                "Sticky Notes",
                "便箋已移到回收區，可從系統匣選單復原。",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        elif not self._windows:
            self.create_note()

    def _restore_note(self, note_id: UUID) -> None:
        note = self._repository.restore_note(note_id)
        if note is not None:
            self._open_note(note)

    def _setup_system_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._application.setQuitOnLastWindowClosed(True)
            return

        self._application.setQuitOnLastWindowClosed(False)
        tray_icon = QSystemTrayIcon(asset_icon("note.svg"), self._application)
        menu = QMenu()
        menu.addAction(asset_icon("add.svg"), "新增便箋", lambda: self.create_note())
        menu.addAction(asset_icon("show.svg"), "顯示所有便箋", self.show_all_notes)

        restore_menu = menu.addMenu(asset_icon("restore.svg"), "復原已刪除便箋")
        restore_menu.aboutToShow.connect(self._populate_restore_menu)
        self._restore_menu = restore_menu

        startup_action = QAction("開機時自動啟動", menu)
        startup_action.setIcon(asset_icon("startup.svg"))
        startup_action.setCheckable(True)
        startup_action.setChecked(is_startup_enabled())
        startup_action.toggled.connect(set_startup_enabled)
        menu.addAction(startup_action)

        menu.addSeparator()
        menu.addAction(asset_icon("quit.svg"), "結束", self._quit)
        tray_icon.setContextMenu(menu)
        tray_icon.activated.connect(self._tray_activated)
        tray_icon.show()
        self._tray_icon = tray_icon

    def _populate_restore_menu(self) -> None:
        if self._restore_menu is None:
            return
        self._restore_menu.clear()
        deleted_notes = self._repository.load_deleted_notes()
        if not deleted_notes:
            empty_action = self._restore_menu.addAction("沒有可復原的便箋")
            empty_action.setEnabled(False)
            return

        for deleted_note in reversed(deleted_notes):
            first_line = deleted_note.note.content.strip().splitlines()
            label = first_line[0][:35] if first_line else "空白便箋"
            action = self._restore_menu.addAction(asset_icon("restore.svg"), label)
            action.triggered.connect(
                lambda checked=False, note_id=deleted_note.note.note_id: self._restore_note(
                    note_id
                )
            )

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_all_notes()

    def _save_all_notes(self) -> None:
        for window in self._windows.values():
            window.save_before_exit()

    def _quit(self) -> None:
        self._save_all_notes()
        self._application.quit()
