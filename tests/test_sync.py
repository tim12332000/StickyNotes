from __future__ import annotations

from pathlib import Path

from app.config import get_bundled_credentials_path, get_data_directory
from app.storage.note_repository import NoteRepository
from app.sync import InMemoryBackend, SyncEngine, SyncResult

LATER = "2030-01-01T00:00:00+00:00"
LATEST = "2030-06-01T00:00:00+00:00"


def _build(tmp_path: Path) -> tuple[NoteRepository, InMemoryBackend, SyncEngine]:
    repository = NoteRepository(tmp_path)
    backend = InMemoryBackend()
    engine = SyncEngine(repository, backend, tmp_path / "sync-state.json")
    return repository, backend, engine


def _notes_by_id(repository: NoteRepository) -> dict[str, object]:
    return {str(note.note_id): note for note in repository.load_notes()}


def test_bundled_credentials_absent_when_running_from_source() -> None:
    # No PyInstaller bundle when running tests, so there is nothing embedded.
    assert get_bundled_credentials_path() is None


def test_env_var_overrides_data_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STICKY_NOTES_DATA_DIR", str(tmp_path))
    assert get_data_directory() == tmp_path.resolve()


def test_new_local_note_is_uploaded(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    note.content = "hello"
    repository.save_note(note)

    result = engine.sync()

    note_id = str(note.note_id)
    assert note_id in result.uploaded
    assert backend.get_content(note_id).content == "hello"


def test_new_remote_note_is_downloaded(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note_id = "11111111-1111-1111-1111-111111111111"
    backend.put(note_id, "from cloud", "#b3e5fc", LATER, LATEST)

    result = engine.sync()

    assert note_id in result.downloaded
    notes = _notes_by_id(repository)
    assert notes[note_id].content == "from cloud"
    assert notes[note_id].color == "#b3e5fc"


def test_local_edit_is_uploaded(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    engine.sync()

    note.content = "edited"
    note.updated_at = LATER
    repository.save_note(note, touch=False)
    result = engine.sync()

    note_id = str(note.note_id)
    assert note_id in result.uploaded
    assert backend.get_content(note_id).content == "edited"


def test_remote_edit_is_downloaded(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    engine.sync()
    note_id = str(note.note_id)

    backend.put(note_id, "remote edit", note.color, note.created_at, LATER)
    result = engine.sync()

    assert note_id in result.downloaded
    assert _notes_by_id(repository)[note_id].content == "remote edit"


def test_local_deletion_propagates_to_remote(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    engine.sync()
    note_id = str(note.note_id)

    repository.delete_note(note.note_id)
    result = engine.sync()

    assert note_id in result.deleted_remote
    assert note_id not in backend.list_records()


def test_remote_deletion_propagates_to_local(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    engine.sync()
    note_id = str(note.note_id)

    backend.delete(note_id)
    result = engine.sync()

    assert note_id in result.deleted_local
    assert note_id not in _notes_by_id(repository)


def test_conflicting_edits_keep_both_versions(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    engine.sync()
    note_id = str(note.note_id)

    note.content = "local edit"
    note.updated_at = LATER
    repository.save_note(note, touch=False)
    backend.put(note_id, "remote edit", note.color, note.created_at, LATEST)

    result = engine.sync()

    assert note_id in result.conflicts
    notes = _notes_by_id(repository)
    # Remote wins the original id; the local edit survives as a separate note.
    assert notes[note_id].content == "remote edit"
    conflict_copies = [
        n for nid, n in notes.items() if nid != note_id and n.content == "local edit"
    ]
    assert len(conflict_copies) == 1
    # Both versions exist on the remote too.
    assert backend.get_content(str(conflict_copies[0].note_id)).content == "local edit"


def test_identical_change_on_both_sides_is_not_a_conflict(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    note = repository.create_note()
    engine.sync()
    note_id = str(note.note_id)

    # Both sides independently end up with the exact same content.
    note.content = "same text"
    note.updated_at = LATER
    repository.save_note(note, touch=False)
    backend.put(note_id, "same text", note.color, note.created_at, LATEST)

    result = engine.sync()

    assert result.conflicts == []
    notes = _notes_by_id(repository)
    assert len(notes) == 1
    assert notes[note_id].content == "same text"


def test_repeated_sync_is_a_noop(tmp_path: Path) -> None:
    repository, backend, engine = _build(tmp_path)
    repository.create_note()
    engine.sync()

    assert engine.sync() == SyncResult()
