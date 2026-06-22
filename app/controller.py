from __future__ import annotations

from uuid import UUID

from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app.models.note import Note
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

    def create_note(self) -> None:
        self._open_note(self._repository.create_note())

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
            create_note=self.create_note,
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
        tray_icon = QSystemTrayIcon(self._create_icon(), self._application)
        menu = QMenu()
        menu.addAction("新增便箋", self.create_note)
        menu.addAction("顯示所有便箋", self.show_all_notes)

        restore_menu = menu.addMenu("復原已刪除便箋")
        restore_menu.aboutToShow.connect(self._populate_restore_menu)
        self._restore_menu = restore_menu

        startup_action = QAction("開機時自動啟動", menu)
        startup_action.setCheckable(True)
        startup_action.setChecked(is_startup_enabled())
        startup_action.toggled.connect(set_startup_enabled)
        menu.addAction(startup_action)

        menu.addSeparator()
        menu.addAction("結束", self._quit)
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
            action = self._restore_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, note_id=deleted_note.note.note_id: self._restore_note(
                    note_id
                )
            )

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_all_notes()

    def _create_icon(self) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#fff176"))
        return QIcon(pixmap)

    def _save_all_notes(self) -> None:
        for window in self._windows.values():
            window.save_before_exit()

    def _quit(self) -> None:
        self._save_all_notes()
        self._application.quit()
