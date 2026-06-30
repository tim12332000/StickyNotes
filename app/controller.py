from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon

from app.config import (
    AUTO_SYNC_DELAY_MILLISECONDS,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    get_bool_flag,
    get_bundled_credentials_path,
    set_bool_flag,
    set_configured_data_directory,
)
from app.icons import asset_icon
from app.models.note import Note, NoteWindowState
from app.startup import is_startup_enabled, set_startup_enabled
from app.storage.note_repository import NoteRepository
from app.sync import SyncEngine, SyncResult
from app.ui.note_window import (
    SYNC_ERROR,
    SYNC_IDLE,
    SYNC_PENDING,
    SYNC_SYNCING,
    NoteWindow,
)
from app.ui.settings_dialog import SettingsDialog


class SyncWorker(QThread):
    """Runs a sync (including the first-time OAuth browser flow) off the UI thread."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: SyncEngine, parent: object | None = None) -> None:
        super().__init__(parent)
        self._engine = engine

    def run(self) -> None:
        try:
            result = self._engine.sync()
        except Exception as exc:  # surface any backend/network/auth error to the UI
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(result)


class StickyNotesController:
    def __init__(self, application: QApplication, repository: NoteRepository) -> None:
        self._application = application
        self._repository = repository
        self._windows: dict[UUID, NoteWindow] = {}
        self._tray_icon: QSystemTrayIcon | None = None
        self._restore_menu: QMenu | None = None
        self._sync_worker: SyncWorker | None = None
        self._sync_state = SYNC_IDLE
        self._sync_detail = ""
        self._state_before_sync = SYNC_IDLE
        self._last_sync_silent = True
        self._auto_sync_timer = QTimer()
        self._auto_sync_timer.setSingleShot(True)
        self._auto_sync_timer.setInterval(AUTO_SYNC_DELAY_MILLISECONDS)
        self._auto_sync_timer.timeout.connect(lambda: self._start_sync(silent=True))
        self._font_family, self._font_size = repository.load_font_settings()
        self._application.aboutToQuit.connect(self._save_all_notes)

    def start(self) -> None:
        self._setup_system_tray()
        notes = self._repository.load_notes()
        if not notes:
            notes.append(self._repository.create_note())
        for note in notes:
            self._open_note(note)
        # Sync once on launch, but only if already authorized (never pops a browser).
        self._start_sync(silent=True)

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
        self._schedule_auto_sync()

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
            save_note=self._save_note,
            create_note=lambda *_, source_id=note.note_id: self.create_note(source_id),
            delete_note=self._delete_note,
            save_window_state=self._repository.save_window_state,
            initial_state=self._repository.load_window_state(note.note_id),
            change_font=self._change_font,
            font_family=self._font_family,
            font_size=self._font_size,
            request_sync=self._sync_now,
            notify_hidden=self._note_hidden,
        )
        self._windows[note.note_id] = window
        window.set_sync_state(self._sync_state, self._sync_detail)
        window.show_and_activate()

    def _save_note(self, note: Note) -> None:
        self._repository.save_note(note)
        self._schedule_auto_sync()

    def _change_font(self, family: str, size: int) -> None:
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        if family == self._font_family and size == self._font_size:
            return
        self._font_family = family
        self._font_size = size
        self._repository.save_font_settings(family, size)
        for window in self._windows.values():
            window.apply_font(family, size)

    def _credentials_path(self) -> Path:
        in_data = self._repository.data_directory / "credentials.json"
        if in_data.exists():
            return in_data
        in_cwd = Path("credentials.json").resolve()
        if in_cwd.exists():
            return in_cwd
        bundled = get_bundled_credentials_path()
        if bundled is not None:
            return bundled
        return in_data

    def _token_path(self) -> Path:
        return self._repository.data_directory / "token.json"

    def _sync_state_path(self) -> Path:
        return self._repository.data_directory / "sync-state.json"

    def _schedule_auto_sync(self) -> None:
        # Only debounce a sync once the user has authorized; otherwise editing
        # would silently do nothing (and must never trigger an OAuth prompt).
        if self._token_path().exists():
            self._apply_sync_state(SYNC_PENDING)
            self._auto_sync_timer.start()

    def _apply_sync_state(self, state: str, detail: str = "") -> None:
        # Remember the detail too, so a note opened later while still in this
        # state (e.g. a new note created during a sync error) shows the reason.
        self._sync_state = state
        self._sync_detail = detail
        for window in self._windows.values():
            window.set_sync_state(state, detail)

    def _sync_now(self) -> None:
        self._start_sync(silent=False)

    def _start_sync(self, *, silent: bool) -> None:
        if self._sync_worker is not None and self._sync_worker.isRunning():
            return
        credentials_path = self._credentials_path()
        if not credentials_path.exists():
            if not silent:
                self._notify(
                    "找不到 credentials.json，請放到：\n" + str(credentials_path.parent)
                )
            return
        # Auto/startup sync must stay silent — never pop an interactive browser.
        if silent and not self._token_path().exists():
            return
        # Make sure debounced edits are on disk so the sync sees the latest text.
        for window in self._windows.values():
            window.flush_pending_content()

        from app.sync import GoogleDriveBackend

        backend = GoogleDriveBackend(
            credentials_path, self._token_path(), allow_interactive=not silent
        )
        engine = SyncEngine(self._repository, backend, self._sync_state_path())
        worker = SyncWorker(engine, self._application)
        worker.finished_ok.connect(self._on_sync_done)
        worker.failed.connect(self._on_sync_error)
        self._sync_worker = worker
        self._last_sync_silent = silent
        self._state_before_sync = self._sync_state
        self._apply_sync_state(SYNC_SYNCING)
        worker.start()

    def _on_sync_done(self, result: SyncResult) -> None:
        # A successful sync gives no toast — the title-bar indicator clearing is
        # enough. Only failures are surfaced (see _on_sync_error).
        self._apply_sync_state(SYNC_IDLE)
        self._refresh_after_sync()
        self._finish_sync()

    def _on_sync_error(self, message: str) -> None:
        # A failed sync must never look like "synced" WHEN there were unsynced
        # changes (or the user asked for it): show a distinct red error state
        # carrying the reason, and notify for a user-initiated sync.
        #
        # But a benign background failure with nothing queued — e.g. simply being
        # offline at launch — should stay quiet: there are no local edits at
        # risk, so reverting to the pre-sync state avoids alarming a red dot on
        # every offline cold start.
        had_unsynced_changes = self._state_before_sync in (SYNC_PENDING, SYNC_ERROR)
        if not self._last_sync_silent or had_unsynced_changes:
            self._apply_sync_state(SYNC_ERROR, detail=message)
            if not self._last_sync_silent:
                self._notify("雲端同步失敗：\n" + message)
        else:
            self._apply_sync_state(self._state_before_sync)
        self._finish_sync()

    def _finish_sync(self) -> None:
        worker = self._sync_worker
        self._sync_worker = None
        if worker is not None:
            worker.deleteLater()

    def _refresh_after_sync(self) -> None:
        notes = {note.note_id: note for note in self._repository.load_notes()}
        for note_id in list(self._windows):
            if note_id not in notes:
                window = self._windows.pop(note_id)
                window.close()
                window.deleteLater()
        for note_id, note in notes.items():
            window = self._windows.get(note_id)
            if window is None:
                self._open_note(note)
            else:
                window.reload(note)

    def _notify(self, message: str) -> None:
        if self._tray_icon is not None:
            self._tray_icon.showMessage(
                "Sticky Notes",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _note_hidden(self) -> None:
        # When a note is hidden (X / Ctrl+W) it goes to the tray, not away.
        # Explain that once, ever, so it never reads as a crash or a lost note.
        if self._tray_icon is None or get_bool_flag("hide_hint_shown"):
            return
        set_bool_flag("hide_hint_shown", True)
        self._notify("便箋已收到系統匣。雙擊系統匣圖示可重新開啟，右鍵有更多選項。")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._repository.data_directory)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_directory = dialog.selected_directory.resolve()
        if new_directory == self._repository.data_directory:
            return
        self._change_data_directory(new_directory, copy_existing=dialog.copy_existing)

    def _change_data_directory(
        self, new_directory: Path, *, copy_existing: bool
    ) -> None:
        old_directory = self._repository.data_directory
        new_directory = Path(new_directory)
        new_directory.mkdir(parents=True, exist_ok=True)
        # Persist the current notes/state to the old location first.
        self._save_all_notes()
        if copy_existing:
            self._copy_data(old_directory, new_directory)
        set_configured_data_directory(new_directory)

        # Switch to the new location and reload everything from it.
        self._repository = NoteRepository(new_directory)
        self._font_family, self._font_size = self._repository.load_font_settings()
        self._apply_sync_state(SYNC_IDLE)
        for window in list(self._windows.values()):
            window.close()
            window.deleteLater()
        self._windows.clear()
        notes = self._repository.load_notes()
        if not notes:
            notes.append(self._repository.create_note())
        for note in notes:
            self._open_note(note)
        self._notify("存檔位置已變更：\n" + str(new_directory))

    @staticmethod
    def _copy_data(old_directory: Path, new_directory: Path) -> None:
        if old_directory == new_directory or not old_directory.exists():
            return
        for sub_directory in ("notes", "trash"):
            source = old_directory / sub_directory
            if source.is_dir():
                target = new_directory / sub_directory
                target.mkdir(parents=True, exist_ok=True)
                for item in source.iterdir():
                    if item.is_file():
                        shutil.copy2(item, target / item.name)
        for name in (
            "metadata.json",
            "local-settings.json",
            "sync-state.json",
            "credentials.json",
            "token.json",
        ):
            source = old_directory / name
            if source.is_file():
                shutil.copy2(source, new_directory / name)

    def _delete_note(self, note_id: UUID) -> None:
        window = self._windows.pop(note_id, None)
        if window is not None:
            window.close()
            window.deleteLater()
        self._repository.delete_note(note_id)
        self._schedule_auto_sync()

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
            self._schedule_auto_sync()

    def _setup_system_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._application.setQuitOnLastWindowClosed(True)
            return

        self._application.setQuitOnLastWindowClosed(False)
        tray_icon = QSystemTrayIcon(asset_icon("note.svg"), self._application)
        menu = QMenu()
        menu.addAction(asset_icon("add.svg"), "新增便箋", lambda: self.create_note())
        menu.addAction(asset_icon("show.svg"), "顯示所有便箋", self.show_all_notes)
        menu.addAction(
            asset_icon("cloud.svg"), "雲端同步 (Ctrl+S)", self._sync_now
        )
        menu.addAction(asset_icon("settings.svg"), "控制台…", self._open_settings)

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
