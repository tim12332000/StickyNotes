from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import UUID

from app.models.note import Note


NOTE_FILE_SUFFIX = ".txt"
TEXT_ENCODING = "utf-8"


class NoteRepository:
    def __init__(self, data_directory: Path) -> None:
        self._notes_directory = data_directory / "notes"
        self._notes_directory.mkdir(parents=True, exist_ok=True)

    def create_note(self) -> Note:
        note = Note()
        self.save_note(note)
        return note

    def load_notes(self) -> list[Note]:
        notes: list[Note] = []
        for note_path in sorted(self._notes_directory.glob(f"*{NOTE_FILE_SUFFIX}")):
            try:
                note_id = UUID(note_path.stem)
            except ValueError:
                continue

            notes.append(
                Note(
                    note_id=note_id,
                    content=note_path.read_text(encoding=TEXT_ENCODING),
                )
            )

        return notes

    def save_note(self, note: Note) -> None:
        destination = self._get_note_path(note.note_id)
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=TEXT_ENCODING,
                newline="",
                dir=self._notes_directory,
                prefix=f".{note.note_id}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(note.content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)

            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _get_note_path(self, note_id: UUID) -> Path:
        return self._notes_directory / f"{note_id}{NOTE_FILE_SUFFIX}"
