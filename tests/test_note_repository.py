from pathlib import Path

from app.models.note import Note
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
