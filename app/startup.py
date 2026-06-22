from __future__ import annotations

import sys
from pathlib import Path

from app.config import APPLICATION_NAME


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def startup_command() -> str:
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        executable = pythonw
    return f'"{executable}" -m app.main'


def is_startup_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APPLICATION_NAME)
            return value == startup_command()
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(
                key, APPLICATION_NAME, 0, winreg.REG_SZ, startup_command()
            )
        else:
            try:
                winreg.DeleteValue(key, APPLICATION_NAME)
            except FileNotFoundError:
                pass
