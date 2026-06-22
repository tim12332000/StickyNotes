from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QSizeGrip,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AUTO_SAVE_DELAY_MILLISECONDS,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
)
from app.models.note import Note, NoteWindowState


NOTE_COLORS = (
    ("Yellow", "#fff59d"),
    ("Pink", "#f8bbd0"),
    ("Blue", "#b3e5fc"),
    ("Green", "#c8e6c9"),
    ("Purple", "#d1c4e9"),
    ("White", "#f5f5f5"),
)


class DragHandle(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class NoteWindow(QMainWindow):
    def __init__(
        self,
        note: Note,
        save_note: Callable[[Note], None],
        create_note: Callable[[], None],
        delete_note: Callable[[UUID], None],
        save_window_state: Callable[[UUID, NoteWindowState], None],
        initial_state: NoteWindowState | None = None,
    ) -> None:
        super().__init__()
        self._note = note
        self._save_note = save_note
        self._create_note = create_note
        self._delete_note = delete_note
        self._save_window_state = save_window_state
        self._ready_to_save_state = False

        self.setWindowTitle("Sticky Notes")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(220, 160)

        self._editor = QPlainTextEdit(note.content)
        self._editor.setPlaceholderText("輸入便箋內容…")
        self._editor.setFrameShape(QFrame.Shape.NoFrame)
        self._editor.textChanged.connect(self._schedule_save)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(AUTO_SAVE_DELAY_MILLISECONDS)
        self._save_timer.timeout.connect(self._save_current_content)

        self._state_timer = QTimer(self)
        self._state_timer.setSingleShot(True)
        self._state_timer.setInterval(300)
        self._state_timer.timeout.connect(self._save_current_window_state)

        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self._create_header())
        layout.addWidget(self._editor, 1)

        resize_row = QHBoxLayout()
        resize_row.setContentsMargins(0, 0, 0, 0)
        resize_row.addStretch(1)
        resize_row.addWidget(QSizeGrip(central_widget))
        layout.addLayout(resize_row)
        self.setCentralWidget(central_widget)

        if initial_state is None:
            self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        else:
            self.setGeometry(
                initial_state.x,
                initial_state.y,
                max(initial_state.width, self.minimumWidth()),
                max(initial_state.height, self.minimumHeight()),
            )
            self._ensure_visible_on_a_screen()
        self._apply_color(note.color)
        self._ready_to_save_state = True

    @property
    def note_id(self) -> UUID:
        return self._note.note_id

    def show_and_activate(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._editor.setFocus()

    def save_before_exit(self) -> None:
        self._flush_pending_save()
        self._save_current_window_state()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.save_before_exit()
        super().closeEvent(event)

    def moveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().moveEvent(event)
        self._schedule_state_save()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._schedule_state_save()

    def _create_header(self) -> DragHandle:
        header = DragHandle(self)
        header.setObjectName("noteHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(5, 3, 3, 3)
        layout.setSpacing(3)

        layout.addWidget(self._button("+", "新增便箋", self._create_note))

        color_button = self._button("Color", "便箋顏色")
        color_menu = QMenu(color_button)
        for label, color in NOTE_COLORS:
            action = QAction(label, color_menu)
            action.setData(color)
            action.triggered.connect(
                lambda checked=False, selected=color: self._set_color(selected)
            )
            color_menu.addAction(action)
        color_button.setMenu(color_menu)
        color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        layout.addWidget(color_button)

        layout.addStretch(1)
        layout.addWidget(self._button("Del", "刪除並移到回收區", self._delete_current_note))
        layout.addWidget(self._button("×", "隱藏便箋", self.close))
        return header

    def _button(
        self,
        text: str,
        tooltip: str,
        callback: Callable[[], None] | None = None,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        if callback is not None:
            button.clicked.connect(callback)
        return button

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _flush_pending_save(self) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_current_content()

    def _save_current_content(self) -> None:
        self._note.content = self._editor.toPlainText()
        self._save_note(self._note)

    def _set_color(self, color: str) -> None:
        self._note.color = color
        self._apply_color(color)
        self._save_current_content()

    def _apply_color(self, color: str) -> None:
        background = QColor(color)
        header = background.darker(106).name()
        border = background.darker(125).name()
        self.centralWidget().setStyleSheet(
            f"QWidget {{ background: {color}; color: #202020; }}"
            f"#noteHeader {{ background: {header}; }}"
            f"QMainWindow {{ border: 1px solid {border}; }}"
            "QPlainTextEdit { padding: 8px; selection-background-color: #607d8b; }"
            "QToolButton { padding: 3px 6px; border-radius: 3px; }"
            "QToolButton:hover { background: rgba(0, 0, 0, 25); }"
        )

    def _delete_current_note(self) -> None:
        self._flush_pending_save()
        self._delete_note(self._note.note_id)

    def _schedule_state_save(self) -> None:
        if self._ready_to_save_state:
            self._state_timer.start()

    def _save_current_window_state(self) -> None:
        if not self._ready_to_save_state:
            return
        geometry = self.geometry()
        self._save_window_state(
            self._note.note_id,
            NoteWindowState(
                x=geometry.x(),
                y=geometry.y(),
                width=geometry.width(),
                height=geometry.height(),
            ),
        )

    def _ensure_visible_on_a_screen(self) -> None:
        if QGuiApplication.screenAt(self.geometry().center()) is not None:
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        geometry = self.geometry()
        geometry.moveLeft(
            min(max(geometry.left(), available.left()), available.right() - 80)
        )
        geometry.moveTop(
            min(max(geometry.top(), available.top()), available.bottom() - 50)
        )
        self.setGeometry(geometry)
