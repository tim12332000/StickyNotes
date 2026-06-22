from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QEvent, QPoint, QSize, QTimer, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QKeySequence,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    AUTO_SAVE_DELAY_MILLISECONDS,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    FONT_FAMILY_CHOICES,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
)
from app.icons import asset_icon, color_swatch_icon
from app.models.note import Note, NoteWindowState


NOTE_COLORS = (
    ("黃色", "#fff59d"),
    ("粉紅", "#f8bbd0"),
    ("藍色", "#b3e5fc"),
    ("綠色", "#c8e6c9"),
    ("紫色", "#d1c4e9"),
    ("白色", "#f5f5f5"),
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
    RESIZE_MARGIN = 6

    def __init__(
        self,
        note: Note,
        save_note: Callable[[Note], None],
        create_note: Callable[[], None],
        delete_note: Callable[[UUID], None],
        save_window_state: Callable[[UUID, NoteWindowState], None],
        initial_state: NoteWindowState | None = None,
        change_font: Callable[[str, int], None] | None = None,
        font_family: str = "",
        font_size: int = 11,
    ) -> None:
        super().__init__()
        self._note = note
        self._save_note = save_note
        self._create_note = create_note
        self._delete_note = delete_note
        self._save_window_state = save_window_state
        self._change_font = change_font or (lambda family, size: None)
        self._font_family = font_family
        self._font_size = font_size
        self._font_actions: dict[str, QAction] = {}
        self._ready_to_save_state = False
        self._collapsed = False
        self._expanded_height = DEFAULT_WINDOW_HEIGHT
        self._expanded_min_height = 0

        self.setWindowTitle("Sticky Notes")
        self.setWindowIcon(asset_icon("note.svg"))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(300, 160)

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
        central_widget.setObjectName("noteBody")
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self._header = self._create_header()
        layout.addWidget(self._header)
        layout.addWidget(self._editor, 1)
        self.setCentralWidget(central_widget)

        self._enable_edge_resizing(central_widget)

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
        self.apply_font(self._font_family, self._font_size)
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
        layout.setContentsMargins(5, 4, 4, 4)
        layout.setSpacing(2)

        layout.addWidget(
            self._button(
                "add.svg",
                "新增便箋 (Ctrl+N)",
                self._create_note,
                QKeySequence.StandardKey.New,
            )
        )

        color_button = self._button("palette.svg", "變更便箋顏色")
        color_menu = QMenu(color_button)
        for label, color in NOTE_COLORS:
            action = QAction(color_swatch_icon(color), label, color_menu)
            action.setData(color)
            action.triggered.connect(
                lambda checked=False, selected=color: self._set_color(selected)
            )
            color_menu.addAction(action)
        color_button.setMenu(color_menu)
        color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        layout.addWidget(color_button)

        layout.addWidget(self._create_font_button())
        layout.addWidget(
            self._button(
                "font-decrease.svg",
                "縮小字體 (Ctrl+-)",
                self._decrease_font_size,
                QKeySequence.StandardKey.ZoomOut,
            )
        )
        layout.addWidget(
            self._button(
                "font-increase.svg",
                "放大字體 (Ctrl++)",
                self._increase_font_size,
                QKeySequence.StandardKey.ZoomIn,
            )
        )

        layout.addStretch(1)
        layout.addWidget(
            self._button(
                "trash.svg", "刪除並移到回收區", self._delete_current_note
            )
        )
        self._collapse_button = self._button(
            "collapse.svg", "收合", self._toggle_collapsed
        )
        layout.addWidget(self._collapse_button)
        layout.addWidget(
            self._button("minimize.svg", "最小化", self.showMinimized)
        )
        layout.addWidget(
            self._button(
                "close.svg",
                "隱藏便箋 (Ctrl+W)",
                self.close,
                QKeySequence.StandardKey.Close,
                "closeButton",
            )
        )
        return header

    def _button(
        self,
        icon_name: str,
        tooltip: str,
        callback: Callable[[], None] | None = None,
        shortcut: QKeySequence.StandardKey | None = None,
        object_name: str = "headerButton",
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setIcon(asset_icon(icon_name))
        button.setIconSize(QSize(17, 17))
        button.setFixedSize(28, 26)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip.split(" (")[0])
        button.setAutoRaise(True)
        if shortcut is not None:
            button.setShortcut(QKeySequence(shortcut))
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
        # The chosen color paints only the title bar; the body stays a fixed
        # dark surface with light text regardless of the selected color.
        border = QColor(color).darker(130).name()
        self.centralWidget().setStyleSheet(
            f"#noteBody {{ background: #333333; border: 1px solid {border}; }}"
            f"#noteHeader {{ background: {color}; }}"
            "QPlainTextEdit { background: #333333; color: #f5f5f5; border: 0;"
            " padding: 8px; selection-background-color: #2f6fb0;"
            " selection-color: #ffffff; }"
            "QToolButton { background: transparent; border: 0; border-radius: 5px; }"
            "QToolButton:hover { background: rgba(0, 0, 0, 40); }"
            "QToolButton:pressed { background: rgba(0, 0, 0, 70); }"
            "#closeButton:hover { background: rgba(190, 45, 45, 160); }"
            "QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }"
            "QScrollBar::handle:vertical { background: rgba(255, 255, 255, 55);"
            " border-radius: 4px; min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 110); }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical"
            " { background: transparent; }"
            "QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }"
            "QScrollBar::handle:horizontal { background: rgba(255, 255, 255, 55);"
            " border-radius: 4px; min-width: 30px; }"
            "QScrollBar::handle:horizontal:hover { background: rgba(255, 255, 255, 110); }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal"
            " { background: transparent; }"
        )

    def _create_font_button(self) -> QToolButton:
        button = self._button("font.svg", "字型")
        menu = QMenu(button)
        installed = set(QFontDatabase.families())
        families = list(FONT_FAMILY_CHOICES)
        if self._font_family and self._font_family not in families:
            families.insert(0, self._font_family)
        for family in families:
            if family not in installed and family != self._font_family:
                continue
            action = QAction(family, menu)
            action.setData(family)
            action.setCheckable(True)
            action.setChecked(family == self._font_family)
            action.triggered.connect(
                lambda checked=False, selected=family: self._change_font(
                    selected, self._font_size
                )
            )
            menu.addAction(action)
            self._font_actions[family] = action
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return button

    def _increase_font_size(self) -> None:
        self._change_font(self._font_family, self._font_size + 1)

    def _decrease_font_size(self) -> None:
        self._change_font(self._font_family, self._font_size - 1)

    def apply_font(self, family: str, size: int) -> None:
        self._font_family = family
        self._font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        self._editor.setFont(QFont(family, self._font_size))
        for action_family, action in self._font_actions.items():
            action.setChecked(action_family == family)

    def _delete_current_note(self) -> None:
        self._flush_pending_save()
        self._delete_note(self._note.note_id)

    def _toggle_collapsed(self) -> None:
        # Roll the note up to just its title bar, or unroll it again. The window
        # stays on screen; only the body is hidden.
        maximum_height = 16777215  # QWIDGETSIZE_MAX
        if self._collapsed:
            self._editor.show()
            self.setMaximumHeight(maximum_height)
            self.setMinimumHeight(self._expanded_min_height)
            self.resize(self.width(), self._expanded_height)
            self._collapsed = False
            self._collapse_button.setIcon(asset_icon("collapse.svg"))
            self._collapse_button.setToolTip("收合")
        else:
            self._expanded_height = self.height()
            self._expanded_min_height = self.minimumHeight()
            collapsed_height = self.height() - self._editor.height()
            self._editor.hide()
            self.setMinimumHeight(0)
            self.setFixedHeight(collapsed_height)
            self._collapsed = True
            self._collapse_button.setIcon(asset_icon("expand.svg"))
            self._collapse_button.setToolTip("展開")

    def _schedule_state_save(self) -> None:
        if self._ready_to_save_state:
            self._state_timer.start()

    def _save_current_window_state(self) -> None:
        if not self._ready_to_save_state:
            return
        geometry = self.geometry()
        # While collapsed the window is only as tall as the title bar; persist the
        # expanded height so the note reopens at a usable size.
        height = self._expanded_height if self._collapsed else geometry.height()
        self._save_window_state(
            self._note.note_id,
            NoteWindowState(
                x=geometry.x(),
                y=geometry.y(),
                width=geometry.width(),
                height=height,
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

    def _enable_edge_resizing(self, central_widget: QWidget) -> None:
        # Frameless windows have no native resize border. Watch the widgets that
        # reach the window edge and hand drags near an edge to the OS, so resizing
        # feels exactly like an ordinary window (live resize, cursors, snapping).
        self._resize_targets = [
            central_widget,
            self._header,
            self._editor,
            self._editor.viewport(),
        ]
        self._default_cursors = {}
        for widget in self._resize_targets:
            self._default_cursors[widget] = widget.cursor()
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        self.setMouseTracking(True)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[no-untyped-def]
        event_type = event.type()
        if (
            event_type == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            edges = self._resize_edges_at(event.globalPosition().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None and handle.startSystemResize(edges):
                    return True
        elif event_type == QEvent.Type.MouseMove and not (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._update_resize_cursor(
                watched, self._resize_edges_at(event.globalPosition().toPoint())
            )
        return super().eventFilter(watched, event)

    def _resize_edges_at(self, global_point: QPoint) -> Qt.Edge:
        point = self.mapFromGlobal(global_point)
        margin = self.RESIZE_MARGIN
        edges = Qt.Edge(0)
        if point.x() <= margin:
            edges |= Qt.Edge.LeftEdge
        elif point.x() >= self.width() - margin:
            edges |= Qt.Edge.RightEdge
        if point.y() <= margin:
            edges |= Qt.Edge.TopEdge
        elif point.y() >= self.height() - margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _update_resize_cursor(self, widget: QWidget, edges: Qt.Edge) -> None:
        cursor = self._resize_cursor(edges)
        if cursor is None:
            widget.setCursor(
                self._default_cursors.get(widget, Qt.CursorShape.ArrowCursor)
            )
        else:
            widget.setCursor(cursor)

    @staticmethod
    def _resize_cursor(edges: Qt.Edge) -> Qt.CursorShape | None:
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return None
