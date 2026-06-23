# Sticky Notes

English · [繁體中文](README.md)

A Windows desktop sticky-notes app in the spirit of Microsoft Sticky Notes. Notes are stored locally as plain-text TXT files (works fully offline) and can optionally sync across machines through the **Google Drive API** — no Google Drive desktop client required.

## Download

No-install single-file executable: **[Download StickyNotes.exe](https://github.com/tim12332000/StickyNotes/releases/download/v0.1.0/StickyNotes.exe)** (or see [Releases](https://github.com/tim12332000/StickyNotes/releases)). Double-click to run — no Python required.

## Features

**The notes**

- Frameless, always-on-top windows; drag the title bar to move, and **resize from any edge or corner like a normal window**.
- Multiple independent notes; one is created automatically when none exist.
- Colored title bar (yellow / pink / blue / green / purple / white), with a **fixed dark body and light text** and a slim dark scrollbar.
- **Selectable font + adjustable size** (A− / A+ or Ctrl+− / Ctrl+=, 8–48pt) — a global setting applied to every note instantly.
- **Collapse** to just the title bar, or **minimize** to the taskbar.
- Auto-saves 500 ms after you stop typing; each note remembers its own position/size (device-local — never overwritten by sync).
- Deletes go to a recycle area first and can be restored from the tray menu (with a confirmation prompt before deleting).
- Lives in the system tray, with optional run-at-startup.
- TXT, metadata and local settings are written via temp file + atomic replace, so a crash never corrupts an already-saved note.

**Cloud sync (Google Drive)**

- Manual sync: the tray "Cloud sync" entry, or **Ctrl+S** on a note.
- Auto sync: once on startup, then ~8 s after an edit/create/delete (only when already authorized — it never pops an auth prompt on its own).
- A title-bar indicator shows status: 🟠 unsynced changes / (spinner) syncing / hidden when in sync.
- Two-way: additions/edits on either side propagate, simultaneous edits keep a **conflict copy** (never a silent overwrite), and deletions propagate both ways.
- Uses the `drive.file` scope (only files the app itself created); each note is a `.txt`, with color/timestamps stored in Drive `appProperties`.

**Control panel**

- The tray "Control panel…" lets you change **where notes are stored**, optionally copying existing notes to the new location, then switches and reloads live.

## Title-bar buttons

Left to right: New note (Ctrl+N), change color, font, decrease font, increase font … sync indicator, delete, collapse, minimize, hide (Ctrl+W).

Tray right-click menu: New note, Show all notes, Cloud sync (Ctrl+S), Control panel…, Restore deleted notes, Run at startup, Quit.

## Development setup

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,drive]"
```

The `drive` extra (the Google API client) is only needed to actually connect to Google Drive; for local notes and tests, `pip install -e ".[dev]"` is enough.

## Run

```powershell
python -m app.main
```

## Google Drive sync setup

Cloud sync needs a Google OAuth client credential, which is **never** committed to Git.

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Google Drive API**.
2. Configure the OAuth consent screen: User type **External**, and add yourself as a **test user** (or publish the app to "Production" to avoid the allowlist).
3. Create an **OAuth client ID** of type **Desktop app** and download the JSON.
4. Rename it to `credentials.json` and place it in the **project root** (when running from source) or the **notes data folder** (for a packaged exe; see below).
5. The first "Cloud sync / Ctrl+S" opens a browser to authorize; a `token.json` is then saved in the data folder for reuse.

> With a non-sensitive scope like `drive.file`, personal use generally needs no Google verification; while unverified, the consent page may show a warning — click "Advanced → Go to …".

## Storage location

By default notes are stored in:

```text
%LOCALAPPDATA%\StickyNotes\data\
```

- `notes\<note-id>.txt` — each note's content
- `metadata.json` — note colors and timestamps
- `local-settings.json` — the global font setting and each note's window position/size (device-local)
- `trash\` — restorable deleted notes
- `sync-state.json`, `token.json` — sync state and the OAuth token (when sync is enabled)

The location can be changed from the tray "Control panel…". Resolution order: the `STICKY_NOTES_DATA_DIR` env var > the control-panel setting > the default location. For development/testing you can override it:

```powershell
$env:STICKY_NOTES_DATA_DIR = "$PWD\data"
python -m app.main
```

## Tests

```powershell
pytest
```

## Windows packaging

```powershell
pyinstaller --noconfirm --clean sticky-notes.spec
```

The result is a no-install executable at `dist\StickyNotes\StickyNotes.exe` (ship the whole folder); Python is not required to run it. The spec also bundles the Google Drive client libraries.

For a **single-file** build instead (one `StickyNotes.exe`, no folder):

```powershell
pyinstaller --noconfirm sticky-notes-onefile.spec --distpath dist/onefile
```
