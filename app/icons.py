from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from app.config import get_asset_path


def asset_icon(name: str) -> QIcon:
    return QIcon(str(get_asset_path(name)))


def color_swatch_icon(color: str) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#555555"), 1))
    painter.setBrush(QColor(color))
    painter.drawEllipse(2, 2, 13, 13)
    painter.end()
    return QIcon(pixmap)
