from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings


APPLICATION_NAME = "StickyNotes"
SETTINGS_ORGANIZATION = "StickyNotes"
SETTINGS_APPLICATION = "StickyNotes"
DATA_DIRECTORY_SETTING_KEY = "data_directory"
DATA_DIRECTORY_ENVIRONMENT_VARIABLE = "STICKY_NOTES_DATA_DIR"
AUTO_SAVE_DELAY_MILLISECONDS = 500
# How long to wait after the last edit before auto-syncing to the cloud.
AUTO_SYNC_DELAY_MILLISECONDS = 8000
DEFAULT_WINDOW_WIDTH = 320
DEFAULT_WINDOW_HEIGHT = 320

DEFAULT_FONT_FAMILY = "Microsoft JhengHei"
DEFAULT_FONT_SIZE = 11
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 48
# Curated families offered in the font menu; only the ones actually installed
# are shown. The note's current family is always included as a fallback.
FONT_FAMILY_CHOICES = (
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "PMingLiU",
    "DFKai-SB",
    "Segoe UI",
    "Arial",
    "Times New Roman",
    "Consolas",
    "Courier New",
)


def _settings() -> QSettings:
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def get_configured_data_directory() -> str | None:
    """The data directory the user picked in the control panel, if any."""
    value = _settings().value(DATA_DIRECTORY_SETTING_KEY)
    return value if isinstance(value, str) and value.strip() else None


def set_configured_data_directory(path: Path | str) -> None:
    _settings().setValue(DATA_DIRECTORY_SETTING_KEY, str(path))


def default_data_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APPLICATION_NAME / "data"
    return Path.home() / f".{APPLICATION_NAME.lower()}" / "data"


def get_data_directory() -> Path:
    # Precedence: env var (dev/test override) > user setting > default location.
    configured_directory = os.environ.get(DATA_DIRECTORY_ENVIRONMENT_VARIABLE)
    if configured_directory:
        return Path(configured_directory).expanduser().resolve()

    user_choice = get_configured_data_directory()
    if user_choice:
        return Path(user_choice).expanduser().resolve()

    return default_data_directory()


def get_asset_path(name: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "app" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name


def get_bundled_credentials_path() -> Path | None:
    """Credentials embedded in the packaged exe, if present.

    Lets a single self-contained exe sync without the user placing a separate
    credentials.json. Returns None when running from source / not bundled.
    """
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidate = Path(bundle_root) / "credentials.json"
        if candidate.exists():
            return candidate
    return None
