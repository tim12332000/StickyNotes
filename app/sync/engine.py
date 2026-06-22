"""Two-way note synchronization.

The engine reconciles the local notes (via :class:`NoteRepository`) with a
:class:`SyncBackend` using a three-way merge against the last-synced state:

- new on one side  -> copy to the other
- changed on one side only -> propagate that change
- changed on both sides -> keep the remote copy and preserve the local edit as
  a new conflict note (never a silent overwrite)
- removed on one side (after having been synced) -> propagate the deletion

Window positions live in ``local-settings.json`` and are intentionally never
touched here — they are device-local.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from app.models.note import Note
from app.storage.note_repository import NoteRepository
from app.sync.backend import RemoteRecord, SyncBackend, content_revision

STATE_FORMAT_VERSION = 1


@dataclass
class SyncResult:
    uploaded: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    deleted_local: list[str] = field(default_factory=list)
    deleted_remote: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


class SyncEngine:
    def __init__(
        self,
        repository: NoteRepository,
        backend: SyncBackend,
        state_path: Path,
    ) -> None:
        self._repository = repository
        self._backend = backend
        self._state_path = Path(state_path)

    def sync(self) -> SyncResult:
        result = SyncResult()
        state = self._load_state()
        local = {str(note.note_id): note for note in self._repository.load_notes()}
        remote = self._backend.list_records()

        for note_id in set(local) | set(remote) | set(state):
            self._reconcile(
                note_id, local.get(note_id), remote.get(note_id), state, result
            )

        self._save_state(state)
        return result

    def _reconcile(
        self,
        note_id: str,
        local: Note | None,
        remote: RemoteRecord | None,
        state: dict[str, dict[str, str]],
        result: SyncResult,
    ) -> None:
        base = state.get(note_id)
        base_revision = base.get("revision") if base else None
        local_revision = (
            content_revision(local.content, local.color) if local is not None else None
        )
        remote_revision = remote.revision if remote is not None else None

        if local is not None and remote is not None:
            local_changed = local_revision != base_revision
            remote_changed = remote_revision != base_revision
            if not local_changed and not remote_changed:
                return
            if local_changed and not remote_changed:
                self._push(note_id, local, state)
                result.uploaded.append(note_id)
            elif remote_changed and not local_changed:
                self._pull(note_id, remote, state)
                result.downloaded.append(note_id)
            elif local_revision == remote_revision:
                # Both sides reached the same content — just record the baseline,
                # no transfer and no conflict (also how legacy state migrates).
                state[note_id] = {"revision": remote_revision}
            else:
                self._resolve_conflict(note_id, local, remote, state, result)
        elif local is not None:
            if base is None:
                self._push(note_id, local, state)
                result.uploaded.append(note_id)
            else:
                # Synced before, now gone from the remote -> deleted elsewhere.
                self._repository.delete_note(UUID(note_id))
                state.pop(note_id, None)
                result.deleted_local.append(note_id)
        elif remote is not None:
            if base is None:
                self._pull(note_id, remote, state)
                result.downloaded.append(note_id)
            else:
                # Synced before, now gone locally -> deleted here.
                self._backend.delete(note_id)
                state.pop(note_id, None)
                result.deleted_remote.append(note_id)
        else:
            state.pop(note_id, None)

    def _push(
        self, note_id: str, note: Note, state: dict[str, dict[str, str]]
    ) -> None:
        record = self._backend.put(
            note_id, note.content, note.color, note.created_at, note.updated_at
        )
        state[note_id] = {"revision": record.revision}

    def _pull(
        self, note_id: str, remote: RemoteRecord, state: dict[str, dict[str, str]]
    ) -> None:
        full = self._backend.get_content(note_id)
        self._repository.save_note(
            Note(
                note_id=UUID(note_id),
                content=full.content,
                color=full.color,
                created_at=full.created_at,
                updated_at=full.updated_at,
            ),
            touch=False,
        )
        state[note_id] = {"revision": remote.revision}

    def _resolve_conflict(
        self,
        note_id: str,
        local: Note,
        remote: RemoteRecord,
        state: dict[str, dict[str, str]],
        result: SyncResult,
    ) -> None:
        # Remote wins the original id; the local edit survives as a fresh note so
        # neither version is lost. The conflict copy is pushed immediately.
        self._pull(note_id, remote, state)
        conflict = Note(content=local.content, color=local.color)
        self._repository.save_note(conflict)
        self._push(str(conflict.note_id), conflict, state)
        result.conflicts.append(note_id)
        result.uploaded.append(str(conflict.note_id))

    def _load_state(self) -> dict[str, dict[str, str]]:
        if not self._state_path.exists():
            return {}
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        notes = data.get("notes") if isinstance(data, dict) else None
        return notes if isinstance(notes, dict) else {}

    def _save_state(self, state: dict[str, dict[str, str]]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(
                {"version": STATE_FORMAT_VERSION, "notes": state},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
