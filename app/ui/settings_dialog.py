from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import asset_icon


class SettingsDialog(QDialog):
    """Control panel for app-wide settings (currently the storage location)."""

    def __init__(self, current_directory: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sticky Notes 控制台")
        self.setWindowIcon(asset_icon("note.svg"))
        self.setMinimumWidth(460)
        self._selected = Path(current_directory)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("便箋存檔位置："))

        path_row = QHBoxLayout()
        self._path_field = QLineEdit(str(self._selected))
        self._path_field.setReadOnly(True)
        path_row.addWidget(self._path_field, 1)
        browse_button = QPushButton("瀏覽…")
        browse_button.clicked.connect(self._browse)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        self._copy_checkbox = QCheckBox("把現有便箋複製到新位置")
        self._copy_checkbox.setChecked(True)
        layout.addWidget(self._copy_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "選擇存檔資料夾", str(self._selected)
        )
        if directory:
            self._selected = Path(directory)
            self._path_field.setText(directory)

    @property
    def selected_directory(self) -> Path:
        return self._selected

    @property
    def copy_existing(self) -> bool:
        return self._copy_checkbox.isChecked()
