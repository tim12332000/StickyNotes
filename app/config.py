from __future__ import annotations

import os
import sys
from pathlib import Path


APPLICATION_NAME = "StickyNotes"
DATA_DIRECTORY_ENVIRONMENT_VARIABLE = "STICKY_NOTES_DATA_DIR"
AUTO_SAVE_DELAY_MILLISECONDS = 500
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
