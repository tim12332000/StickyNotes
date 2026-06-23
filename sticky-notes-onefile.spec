# -*- mode: python ; coding: utf-8 -*-
# Single-file build: produces one StickyNotes.exe (no folder needed).
# Trade-off vs the one-folder build: the exe is larger and the first launch is
# a little slower because it unpacks to a temp dir each run.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas = [("app/assets", "app/assets")]
binaries = []
hiddenimports = []

# Embed the OAuth client so the single exe needs no separate credentials.json.
if Path("credentials.json").exists():
    datas += [("credentials.json", ".")]

for _package in (
    "googleapiclient",
    "google_auth_oauthlib",
    "google.auth",
    "google.oauth2",
    "google_auth_httplib2",
    "httplib2",
    "oauthlib",
    "requests_oauthlib",
    "uritemplate",
):
    _datas, _binaries, _hiddenimports = collect_all(_package)
    datas += _datas
    binaries += _binaries
    hiddenimports += _hiddenimports

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="StickyNotes",
    icon="app/assets/note.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
