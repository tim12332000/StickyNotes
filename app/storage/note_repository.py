from __future__ import annotations

import os
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
)
from app.models.note import (
    DEFAULT_NOTE_COLOR,
    DeletedNote,
    Note,
    NoteWindowState,
    utc_now_isoformat,
)


NOTE_FILE_SUFFIX = ".txt"
TEXT_ENCODING = "utf-8"
DATA_FORMAT_VERSION = 1


class NoteRepository:
    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
        self._notes_directory = data_directory / "notes"
        self._trash_directory = data_directory / "trash"
        self._metadata_path = data_directory / "metadata.json"
        self._local_settings_path = data_directory / "local-settings.json"
        self._notes_directory.mkdir(parents=True, exist_ok=True)
        self._trash_directory.mkdir(parents=True, exist_ok=True)

    @property
    def data_directory(self) -> Path:
        return self._data_directory

    def create_note(self) -> Note:
        note = Note()
        self.save_note(note)
        return note

    def load_notes(self) -> list[Note]:
        metadata = self._mapping_value(self._load_json(self._metadata_path), "notes")
        notes: list[Note] = []
        for note_path in sorted(self._notes_directory.glob(f"*{NOTE_FILE_SUFFIX}")):
            try:
                note_id = UUID(note_path.stem)
            except ValueError:
                continue

            note_metadata = self._mapping_value(metadata, str(note_id))
            notes.append(self._note_from_data(note_id, note_path, note_metadata))

        return notes

    def save_note(self, note: Note, *, touch: bool = True) -> None:
        # touch=False preserves note.updated_at, which sync needs when writing a
        # note pulled from the cloud so its timestamp is not bumped to "now".
        destination = self._get_note_path(note.note_id)
        if touch:
            note.updated_at = utc_now_isoformat()
        self._atomic_write_text(destination, note.content)

        metadata = self._load_json(self._metadata_path)
        self._ensure_mapping(metadata, "notes")[str(note.note_id)] = {
            "color": note.color,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        self._save_json(self._metadata_path, metadata)

    def delete_note(self, note_id: UUID) -> None:
        source = self._get_note_path(note_id)
        if not source.exists():
            return

        metadata = self._load_json(self._metadata_path)
        note_metadata = self._ensure_mapping(metadata, "notes").pop(str(note_id), {})
        if not isinstance(note_metadata, dict):
            note_metadata = {}
        deleted_metadata = self._load_json(self._trash_directory / "metadata.json")
        self._ensure_mapping(deleted_metadata, "notes")[str(note_id)] = {
            **note_metadata,
            "deleted_at": utc_now_isoformat(),
        }

        os.replace(source, self._trash_directory / source.name)
        self._save_json(self._metadata_path, metadata)
        self._save_json(self._trash_directory / "metadata.json", deleted_metadata)

        local_settings = self._load_json(self._local_settings_path)
        self._ensure_mapping(local_settings, "windows").pop(str(note_id), None)
        self._save_json(self._local_settings_path, local_settings)

    def load_deleted_notes(self) -> list[DeletedNote]:
        deleted_metadata = self._mapping_value(
            self._load_json(self._trash_directory / "metadata.json"), "notes"
        )
        deleted_notes: list[DeletedNote] = []
        for note_path in sorted(self._trash_directory.glob(f"*{NOTE_FILE_SUFFIX}")):
            try:
                note_id = UUID(note_path.stem)
            except ValueError:
                continue
            note_metadata = self._mapping_value(deleted_metadata, str(note_id))
            deleted_notes.append(
                DeletedNote(
                    note=self._note_from_data(note_id, note_path, note_metadata),
                    deleted_at=note_metadata.get("deleted_at", ""),
                )
            )
        return sorted(deleted_notes, key=lambda item: item.deleted_at)

    def restore_note(self, note_id: UUID) -> Note | None:
        source = self._trash_directory / f"{note_id}{NOTE_FILE_SUFFIX}"
        if not source.exists():
            return None

        deleted_metadata = self._load_json(self._trash_directory / "metadata.json")
        note_metadata = self._ensure_mapping(deleted_metadata, "notes").pop(
            str(note_id), {}
        )
        if not isinstance(note_metadata, dict):
            note_metadata = {}
        destination = self._get_note_path(note_id)
        os.replace(source, destination)

        metadata = self._load_json(self._metadata_path)
        self._ensure_mapping(metadata, "notes")[str(note_id)] = {
            key: value
            for key, value in note_metadata.items()
            if key in {"color", "created_at", "updated_at"}
        }
        self._save_json(self._metadata_path, metadata)
        self._save_json(self._trash_directory / "metadata.json", deleted_metadata)
        return self._note_from_data(note_id, destination, note_metadata)

    def load_window_state(self, note_id: UUID) -> NoteWindowState | None:
        windows = self._mapping_value(
            self._load_json(self._local_settings_path), "windows"
        )
        data = self._mapping_value(windows, str(note_id))
        if not data:
            return None
        try:
            return NoteWindowState(
                x=int(data["x"]),
                y=int(data["y"]),
                width=int(data["width"]),
                height=int(data["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def save_window_state(self, note_id: UUID, state: NoteWindowState) -> None:
        local_settings = self._load_json(self._local_settings_path)
        self._ensure_mapping(local_settings, "windows")[str(note_id)] = asdict(state)
        self._save_json(self._local_settings_path, local_settings)

    def load_font_settings(self) -> tuple[str, int]:
        data = self._mapping_value(
            self._load_json(self._local_settings_path), "font"
        )
        family = data.get("family")
        if not isinstance(family, str) or not family:
            family = DEFAULT_FONT_FAMILY
        try:
            size = int(data["size"])
        except (KeyError, TypeError, ValueError):
            size = DEFAULT_FONT_SIZE
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        return family, size

    def save_font_settings(self, family: str, size: int) -> None:
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(size)))
        local_settings = self._load_json(self._local_settings_path)
        local_settings["font"] = {"family": family, "size": size}
        self._save_json(self._local_settings_path, local_settings)

    def _get_note_path(self, note_id: UUID) -> Path:
        return self._notes_directory / f"{note_id}{NOTE_FILE_SUFFIX}"

    def _note_from_data(
        self, note_id: UUID, note_path: Path, metadata: dict[str, Any]
    ) -> Note:
        return Note(
            note_id=note_id,
            content=note_path.read_text(encoding=TEXT_ENCODING),
            color=str(metadata.get("color", DEFAULT_NOTE_COLOR)),
            created_at=str(metadata.get("created_at", utc_now_isoformat())),
            updated_at=str(metadata.get("updated_at", utc_now_isoformat())),
        )

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"version": DATA_FORMAT_VERSION}
        try:
            value = json.loads(path.read_text(encoding=TEXT_ENCODING))
        except (OSError, json.JSONDecodeError):
            return {"version": DATA_FORMAT_VERSION}
        return value if isinstance(value, dict) else {"version": DATA_FORMAT_VERSION}

    def _mapping_value(
        self, value: dict[str, Any], key: str
    ) -> dict[str, Any]:
        nested = value.get(key, {})
        return nested if isinstance(nested, dict) else {}

    def _ensure_mapping(
        self, value: dict[str, Any], key: str
    ) -> dict[str, Any]:
        nested = value.get(key)
        if not isinstance(nested, dict):
            nested = {}
            value[key] = nested
        return nested

    def _save_json(self, path: Path, value: dict[str, Any]) -> None:
        value["version"] = DATA_FORMAT_VERSION
        self._atomic_write_text(
            path,
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def _atomic_write_text(self, destination: Path, content: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=TEXT_ENCODING,
                newline="",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
