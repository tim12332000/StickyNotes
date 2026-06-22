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


def get_credentials_path() -> Path:
    """Locate the Google OAuth client file.

    Preference: a copy beside the notes data (works for the packaged exe), then
    the project root (convenient when running from source).
    """
    in_data_dir = get_data_directory() / "credentials.json"
    if in_data_dir.exists():
        return in_data_dir
    in_cwd = Path("credentials.json").resolve()
    if in_cwd.exists():
        return in_cwd
    return in_data_dir


def get_token_path() -> Path:
    return get_data_directory() / "token.json"


def get_sync_state_path() -> Path:
    return get_data_directory() / "sync-state.json"


def get_asset_path(name: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "app" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name
