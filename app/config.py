from __future__ import annotations

import os
import sys
from pathlib import Path


APPLICATION_NAME = "StickyNotes"
DATA_DIRECTORY_ENVIRONMENT_VARIABLE = "STICKY_NOTES_DATA_DIR"
AUTO_SAVE_DELAY_MILLISECONDS = 500
DEFAULT_WINDOW_WIDTH = 320
DEFAULT_WINDOW_HEIGHT = 320


def get_data_directory() -> Path:
    configured_directory = os.environ.get(DATA_DIRECTORY_ENVIRONMENT_VARIABLE)
    if configured_directory:
        return Path(configured_directory).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APPLICATION_NAME / "data"

    return Path.home() / f".{APPLICATION_NAME.lower()}" / "data"


def get_asset_path(name: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "app" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name
