from __future__ import annotations

import sys
from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QSize,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSystemTrayIcon,
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


SYNC_IDLE = "idle"
SYNC_PENDING = "pending"
SYNC_SYNCING = "syncing"
SYNC_ERROR = "error"


def system_animations_enabled() -> bool:
    """Honor the OS "show animations"/"reduce motion" preference.

    On Windows this reads SPI_GETCLIENTAREAANIMATION; anywhere else (or on any
    failure) we assume animations are wanted. Lets users who disable motion
    system-wide get instant transitions instead of forced fades/roll-ups.
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        enabled = ctypes.c_int(1)
        SPI_GETCLIENTAREAANIMATION = 0x1042
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0
        )
        return bool(enabled.value) if ok else True
    except Exception:
        return True


class SyncIndicator(QWidget):
    """Title-bar sync status: hidden when synced, an orange dot for unsynced
    changes, a rotating arc while syncing, and a red dot if the last sync
    failed (with the reason in its tooltip)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = SYNC_IDLE
        self._angle = 0
        self.setFixedSize(20, 20)
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._advance)
        self.hide()

    @property
    def is_spinning(self) -> bool:
        return self._timer.isActive()

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str, detail: str = "") -> None:
        self._state = state
        if state == SYNC_SYNCING:
            self.setToolTip("雲端同步中…")
            if not self._timer.isActive():
                self._timer.start()
            self.show()
        elif state == SYNC_PENDING:
            self.setToolTip("有未同步的變更")
            self._timer.stop()
            self.show()
        elif state == SYNC_ERROR:
            self.setToolTip("雲端同步失敗：\n" + detail if detail else "雲端同步失敗")
            self._timer.stop()
            self.show()
        else:
            self._timer.stop()
            self.hide()
        self.update()

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        if self._state == SYNC_SYNCING:
            pen = QPen(QColor(41, 41, 36, 210))
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            # A 280° arc whose start angle advances each tick reads as a spinner.
            painter.drawArc(rect, self._angle * 16, 280 * 16)
        elif self._state == SYNC_PENDING:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(230, 150, 40)))
            painter.drawEllipse(self.rect().center(), 4, 4)
        elif self._state == SYNC_ERROR:
            # A red dot, distinct from the orange "pending" dot, so a failed sync
            # never looks the same as "changes not yet sent".
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(200, 55, 45)))
            painter.drawEllipse(self.rect().center(), 4, 4)


class NoteWindow(QMainWindow):
    RESIZE_MARGIN = 6
    # Roll-up/roll-down and fade-in timings. Short enough to feel instant,
    # long enough to read as motion rather than a snap.
    COLLAPSE_DURATION_MS = 160
    APPEAR_DURATION_MS = 140

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
        request_sync: Callable[[], None] | None = None,
        notify_hidden: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._note = note
        self._save_note = save_note
        self._create_note = create_note
        self._delete_note = delete_note
        self._save_window_state = save_window_state
        self._change_font = change_font or (lambda family, size: None)
        self._request_sync = request_sync or (lambda: None)
        self._notify_hidden = notify_hidden or (lambda: None)
        self._font_family = font_family
        self._font_size = font_size
        self._font_actions: dict[str, QAction] = {}
        self._ready_to_save_state = False
        self._collapsed = False
        self._expanded_height = DEFAULT_WINDOW_HEIGHT
        self._expanded_min_height = 0
        self._collapse_animation: QParallelAnimationGroup | None = None
        self._has_appeared = False

        self.setWindowTitle("Sticky Notes")
        self.setWindowIcon(asset_icon("note.svg"))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(300, 160)

        self._editor = QPlainTextEdit(note.content)
        self._editor.setPlaceholderText("輸入便箋內容…")
        self._editor.setFrameShape(QFrame.Shape.NoFrame)
        # Let the editor shrink to nothing so the body can roll up smoothly during
        # a collapse; the window's own minimum height governs the expanded floor.
        self._editor.setMinimumHeight(0)
        # Tab moves focus to the header buttons (and Shift+Tab back) instead of
        # inserting a tab character, so the toolbar is reachable by keyboard.
        self._editor.setTabChangesFocus(True)
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

        # Ctrl+S forces an immediate sync from any focused note.
        sync_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Save), self)
        sync_shortcut.activated.connect(self._request_sync)

        self._ready_to_save_state = True

    @property
    def note_id(self) -> UUID:
        return self._note.note_id

    def show_and_activate(self) -> None:
        # Fade in the first time a note appears; later shows (e.g. "show all
        # notes") just raise it instantly so repeated clicks don't flicker.
        first_show = not self._has_appeared
        self._has_appeared = True
        self.setWindowOpacity(0.0 if first_show else 1.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._editor.setFocus()
        if first_show:
            self._fade_in()

    def _fade_in(self) -> None:
        if not system_animations_enabled():
            self.setWindowOpacity(1.0)
            return
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(self.APPEAR_DURATION_MS)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._appear_animation = animation
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def save_before_exit(self) -> None:
        self._flush_pending_save()
        self._save_current_window_state()

    def flush_pending_content(self) -> None:
        """Write any debounced edit to disk now (used before a sync run)."""
        self._flush_pending_save()

    def set_sync_state(self, state: str, detail: str = "") -> None:
        self._sync_indicator.set_state(state, detail)

    def reload(self, note: Note) -> None:
        """Refresh the editor/color from a note pulled by sync.

        Only touches the editor when the text actually changed, and never while
        an edit is still pending — otherwise a routine sync would reset the
        scroll position to the top or clobber what is being typed. When it does
        update, the scroll position and cursor are preserved.
        """
        color_changed = note.color != self._note.color
        content_changed = (
            not self._save_timer.isActive()
            and note.content != self._editor.toPlainText()
        )
        self._note = note
        if content_changed:
            scrollbar = self._editor.verticalScrollBar()
            scroll = scrollbar.value()
            cursor_position = self._editor.textCursor().position()
            self._editor.blockSignals(True)
            self._editor.setPlainText(note.content)
            self._editor.blockSignals(False)
            cursor = self._editor.textCursor()
            cursor.setPosition(min(cursor_position, len(note.content)))
            self._editor.setTextCursor(cursor)
            scrollbar.setValue(min(scroll, scrollbar.maximum()))
        if color_changed:
            self._apply_color(note.color)

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
        self._sync_indicator = SyncIndicator(header)
        layout.addWidget(self._sync_indicator)
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
                self._user_hide,
                QKeySequence.StandardKey.Close,
                "closeButton",
            )
        )
        return header

    def _user_hide(self) -> None:
        # The X / Ctrl+W hides the note to the tray rather than closing the app.
        # Let the controller explain where it went (once), so it doesn't read as
        # a crash or a lost note.
        self._notify_hidden()
        self.close()

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
        # Reachable by keyboard: Tab lands on it, Space/Enter activates (and opens
        # the color/font menus). Without this the whole header is mouse-only.
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
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
        # Only promise tray-based restore when a tray actually exists, so the
        # dialog never points the user at a menu that isn't there.
        if QSystemTrayIcon.isSystemTrayAvailable():
            detail = "\n(會移到回收區,可從系統匣選單復原)"
        else:
            detail = "\n(會移到回收區)"
        confirmed = QMessageBox.question(
            self,
            "刪除便箋",
            "確定要刪除這張便箋嗎？" + detail,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._flush_pending_save()
        self._delete_note(self._note.note_id)

    def _toggle_collapsed(self) -> None:
        # Roll the note up to just its title bar, or unroll it again. The window
        # stays on screen and anchored at its top-left; only the body height
        # animates. The body is hidden once fully rolled up.
        animating = self._collapse_running()
        self._stop_collapse_animation()
        start_height = self.height()
        if self._collapsed:
            # ---- expand ----
            self._editor.show()
            self._collapsed = False
            self._collapse_button.setIcon(asset_icon("collapse.svg"))
            self._collapse_button.setToolTip("收合")
            self._animate_height(
                start_height, self._expanded_height, self._finish_expand
            )
        else:
            # ---- collapse ----  (don't recapture the expanded size mid-flight)
            if not animating:
                self._expanded_height = start_height
                self._expanded_min_height = self.minimumHeight()
            self._collapsed = True
            self._collapse_button.setIcon(asset_icon("expand.svg"))
            self._collapse_button.setToolTip("展開")
            # Let the window shrink below its normal minimum while collapsed.
            self.setMinimumHeight(0)
            self._animate_height(
                start_height, self._collapsed_height(), self._editor.hide
            )

    def _collapsed_height(self) -> int:
        layout = self.centralWidget().layout()
        margins = layout.contentsMargins()
        return self._header.sizeHint().height() + margins.top() + margins.bottom()

    def _animate_height(
        self, start: int, end: int, on_finish: Callable[[], None]
    ) -> None:
        if not system_animations_enabled():
            # Reduced-motion: jump straight to the end state, no animation.
            self.setMinimumHeight(end)
            self.setMaximumHeight(end)
            on_finish()
            return
        # Driving both the min and max height in lockstep forces the frameless
        # window to actually resize (it has no native frame to drag), giving a
        # live roll-up/roll-down anchored at the top-left.
        group = QParallelAnimationGroup(self)
        for property_name in (b"minimumHeight", b"maximumHeight"):
            animation = QPropertyAnimation(self, property_name, group)
            animation.setDuration(self.COLLAPSE_DURATION_MS)
            animation.setStartValue(start)
            animation.setEndValue(end)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(animation)
        group.finished.connect(on_finish)
        self._collapse_animation = group
        group.start()

    def _finish_expand(self) -> None:
        # Hand resizing back to the user once fully unrolled.
        self.setMinimumHeight(self._expanded_min_height)
        self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX

    def _collapse_running(self) -> bool:
        animation = self._collapse_animation
        return (
            animation is not None
            and animation.state() == QAbstractAnimation.State.Running
        )

    def _stop_collapse_animation(self) -> None:
        animation = self._collapse_animation
        self._collapse_animation = None
        if animation is not None:
            try:
                animation.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            animation.stop()
            animation.deleteLater()

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
