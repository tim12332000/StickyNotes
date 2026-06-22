from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


DEFAULT_NOTE_COLOR = "#fff59d"


def utc_now_isoformat() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Note:
    content: str = ""
    note_id: UUID = field(default_factory=uuid4)
    color: str = DEFAULT_NOTE_COLOR
    created_at: str = field(default_factory=utc_now_isoformat)
    updated_at: str = field(default_factory=utc_now_isoformat)


@dataclass(slots=True)
class NoteWindowState:
    x: int
    y: int
    width: int
    height: int


@dataclass(slots=True)
class DeletedNote:
    note: Note
    deleted_at: str
