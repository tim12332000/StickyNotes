from pathlib import Path

from app.models.note import Note, NoteWindowState
from app.storage.note_repository import NoteRepository


def test_create_note_saves_plain_text_file(tmp_path: Path) -> None:
    repository = NoteRepository(tmp_path)

    note = repository.create_note()

    note_path = tmp_path / "notes" / f"{note.note_id}.txt"
    assert note_path.exists()
    assert note_path.read_text(encoding="utf-8") == ""


def test_save_and_load_note_preserves_unicode_content(tmp_path: Path) -> None:
    repository = NoteRepository(tmp_path)
    expected_note = Note(content="第一張便箋\nGoogle Drive 稍後同步")

    repository.save_note(expected_note)
    loaded_notes = repository.load_notes()

    assert loaded_notes == [expected_note]


def test_load_notes_ignores_unrelated_text_files(tmp_path: Path) -> None:
    notes_directory = tmp_path / "notes"
    notes_directory.mkdir(parents=True)
    (notes_directory / "not-a-note.txt").write_text("ignore", encoding="utf-8")
    repository = NoteRepository(tmp_path)

    assert repository.load_notes() == []


def test_note_metadata_and_window_state_survive_reload(tmp_path: Path) -> None:
    repository = NoteRepository(tmp_path)
    note = Note(content="藍色便箋", color="#b3e5fc")
    state = NoteWindowState(x=120, y=80, width=450, height=260)

    repository.save_note(note)
    repository.save_window_state(note.note_id, state)

    reloaded_repository = NoteRepository(tmp_path)
    loaded_note = reloaded_repository.load_notes()[0]
    assert loaded_note.note_id == note.note_id
    assert loaded_note.content == note.content
    assert loaded_note.color == note.color
    assert loaded_note.created_at == note.created_at
    assert reloaded_repository.load_window_state(note.note_id) == state


def test_delete_and_restore_preserves_note_without_leaving_active_state(
    tmp_path: Path,
) -> None:
    repository = NoteRepository(tmp_path)
    note = Note(content="可以復原", color="#f8bbd0")
    repository.save_note(note)
    repository.save_window_state(
        note.note_id, NoteWindowState(x=1, y=2, width=300, height=200)
    )

    repository.delete_note(note.note_id)

    assert repository.load_notes() == []
    assert repository.load_window_state(note.note_id) is None
    deleted_notes = repository.load_deleted_notes()
    assert len(deleted_notes) == 1
    assert deleted_notes[0].note.content == "可以復原"
    assert deleted_notes[0].note.color == "#f8bbd0"
    assert deleted_notes[0].deleted_at

    restored_note = repository.restore_note(note.note_id)

    assert restored_note is not None
    assert restored_note.content == note.content
    assert restored_note.color == note.color
    assert repository.load_deleted_notes() == []
    assert repository.load_notes()[0].note_id == note.note_id


def test_invalid_json_does_not_prevent_loading_plain_text_notes(tmp_path: Path) -> None:
    repository = NoteRepository(tmp_path)
    note = repository.create_note()
    (tmp_path / "metadata.json").write_text("not json", encoding="utf-8")

    loaded_notes = NoteRepository(tmp_path).load_notes()

    assert len(loaded_notes) == 1
    assert loaded_notes[0].note_id == note.note_id
