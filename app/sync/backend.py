"""Sync backend abstraction.

The engine talks to ``SyncBackend`` and never to a concrete cloud provider, so
the two-way sync logic can be developed and tested against an in-memory fake
before the real Google Drive integration exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RemoteRecord:
    """One note as the backend sees it.

    ``revision`` is an opaque, backend-assigned version token that changes on
    every write. The engine compares it against the last-synced revision to
    detect remote-side edits without trusting clocks. ``content`` is only
    populated by :meth:`SyncBackend.get_content`; listings leave it empty.
    """

    note_id: str
    revision: str
    created_at: str
    updated_at: str
    color: str
    content: str = ""


class SyncBackend(Protocol):
    def list_records(self) -> dict[str, RemoteRecord]:
        """Return ``note_id -> RemoteRecord`` for every remote note (no content)."""
        ...

    def get_content(self, note_id: str) -> RemoteRecord:
        """Return the full record, including content, for one note."""
        ...

    def put(
        self,
        note_id: str,
        content: str,
        color: str,
        created_at: str,
        updated_at: str,
    ) -> RemoteRecord:
        """Create or overwrite a note and return its new record."""
        ...

    def delete(self, note_id: str) -> None:
        """Remove a note from the backend (no error if it is already gone)."""
        ...


class InMemoryBackend:
    """A fake cloud kept entirely in memory — used by tests and local dev.

    Mirrors the contract a real provider must honour: writes bump a global
    revision counter, and listings omit content.
    """

    def __init__(self) -> None:
        self._store: dict[str, RemoteRecord] = {}
        self._revision = 0

    def list_records(self) -> dict[str, RemoteRecord]:
        return {
            note_id: RemoteRecord(
                note_id=record.note_id,
                revision=record.revision,
                created_at=record.created_at,
                updated_at=record.updated_at,
                color=record.color,
                content="",
            )
            for note_id, record in self._store.items()
        }

    def get_content(self, note_id: str) -> RemoteRecord:
        return self._store[note_id]

    def put(
        self,
        note_id: str,
        content: str,
        color: str,
        created_at: str,
        updated_at: str,
    ) -> RemoteRecord:
        self._revision += 1
        record = RemoteRecord(
            note_id=note_id,
            revision=str(self._revision),
            created_at=created_at,
            updated_at=updated_at,
            color=color,
            content=content,
        )
        self._store[note_id] = record
        return record

    def delete(self, note_id: str) -> None:
        self._store.pop(note_id, None)
