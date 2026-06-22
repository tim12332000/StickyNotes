"""Sync backend abstraction.

The engine talks to ``SyncBackend`` and never to a concrete cloud provider, so
the two-way sync logic can be developed and tested against an in-memory fake
before the real Google Drive integration exists.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


def content_revision(content: str, color: str) -> str:
    """A stable fingerprint of a note's synced data (text + color).

    Used as the change token so a remote note only counts as "changed" when its
    content or color actually differs — never because the storage provider bumps
    its own internal version number.
    """
    digest = hashlib.sha1()
    digest.update(content.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(color.encode("utf-8"))
    return digest.hexdigest()


@dataclass(frozen=True)
class RemoteRecord:
    """One note as the backend sees it.

    ``revision`` is a fingerprint of the note's content+color (see
    :func:`content_revision`); the engine compares it against the last-synced
    revision to detect real remote edits. ``content`` is only populated by
    :meth:`SyncBackend.get_content`; listings leave it empty.
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

    Mirrors the contract a real provider must honour: each write fingerprints
    the content+color as its revision, and listings omit content.
    """

    def __init__(self) -> None:
        self._store: dict[str, RemoteRecord] = {}

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
        record = RemoteRecord(
            note_id=note_id,
            revision=content_revision(content, color),
            created_at=created_at,
            updated_at=updated_at,
            color=color,
            content=content,
        )
        self._store[note_id] = record
        return record

    def delete(self, note_id: str) -> None:
        self._store.pop(note_id, None)
