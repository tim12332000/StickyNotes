"""Google Drive backend for note synchronization.

Each note is a ``.txt`` file inside a dedicated app folder; the note id, color
and timestamps live in the file's ``appProperties``. Uses the ``drive.file``
scope, so the app only ever sees files it created itself. Requires
``credentials.json`` (a Desktop OAuth client) and writes ``token.json`` after
the first browser authorization.
"""

from __future__ import annotations

import io
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaInMemoryUpload

from app.models.note import DEFAULT_NOTE_COLOR
from app.sync.backend import RemoteRecord, content_revision

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_MIME = "application/vnd.google-apps.folder"
TEXT_MIME = "text/plain"
DEFAULT_FOLDER_NAME = "StickyNotes"
# Stop waiting for the browser redirect after this long so a denied or abandoned
# authorization surfaces as an error instead of hanging the sync forever.
OAUTH_TIMEOUT_SECONDS = 180


class GoogleDriveBackend:
    def __init__(
        self,
        credentials_path: Path | str,
        token_path: Path | str,
        folder_name: str = DEFAULT_FOLDER_NAME,
        *,
        allow_interactive: bool = True,
    ) -> None:
        self._credentials_path = Path(credentials_path)
        self._token_path = Path(token_path)
        self._folder_name = folder_name
        # A background sync must never pop a browser; only a user-initiated sync
        # may re-run the consent flow when the saved token is no longer usable.
        self._allow_interactive = allow_interactive
        self._service = None
        self._folder_id: str | None = None

    # -- authentication / service ------------------------------------------------

    def _credentials(self) -> Credentials:
        creds: Credentials | None = None
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self._token_path), SCOPES
            )
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._token_path.write_text(creds.to_json(), encoding="utf-8")
                return creds
            except RefreshError:
                # The refresh token was revoked or expired (e.g. an app still in
                # Google's "Testing" mode expires it after 7 days). The saved
                # token is dead — discard it and fall through to re-authorize.
                self._discard_token()
                creds = None
        if not self._allow_interactive:
            raise PermissionError(
                "雲端授權已失效，請點選「雲端同步」重新登入 Google。"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self._credentials_path), SCOPES
        )
        creds = flow.run_local_server(port=0, timeout_seconds=OAUTH_TIMEOUT_SECONDS)
        self._token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _discard_token(self) -> None:
        try:
            self._token_path.unlink()
        except OSError:
            pass

    def _drive(self):
        if self._service is None:
            self._service = build(
                "drive", "v3", credentials=self._credentials(), cache_discovery=False
            )
        return self._service

    def _folder(self) -> str:
        if self._folder_id is not None:
            return self._folder_id
        drive = self._drive()
        query = (
            f"mimeType='{FOLDER_MIME}' and name='{self._folder_name}'"
            " and trashed=false"
        )
        found = (
            drive.files()
            .list(q=query, spaces="drive", fields="files(id)")
            .execute()
            .get("files", [])
        )
        if found:
            self._folder_id = found[0]["id"]
        else:
            created = (
                drive.files()
                .create(
                    body={"name": self._folder_name, "mimeType": FOLDER_MIME},
                    fields="id",
                )
                .execute()
            )
            self._folder_id = created["id"]
        return self._folder_id

    def _file_id(self, note_id: str) -> str | None:
        query = (
            f"'{self._folder()}' in parents and trashed=false"
            f" and appProperties has {{ key='noteId' and value='{note_id}' }}"
        )
        found = (
            self._drive()
            .files()
            .list(q=query, spaces="drive", fields="files(id)")
            .execute()
            .get("files", [])
        )
        return found[0]["id"] if found else None

    @staticmethod
    def _record(file: dict, content: str = "") -> RemoteRecord:
        props = file.get("appProperties") or {}
        color = props.get("color", DEFAULT_NOTE_COLOR)
        return RemoteRecord(
            note_id=props.get("noteId", ""),
            # Files we wrote carry the fingerprint in "rev"; legacy ones are
            # fingerprinted from their (downloaded) content instead.
            revision=props.get("rev") or content_revision(content, color),
            created_at=props.get("createdAt", ""),
            updated_at=props.get("updatedAt", ""),
            color=color,
            content=content,
        )

    def _download_text(self, file_id: str) -> str:
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            buffer, self._drive().files().get_media(fileId=file_id)
        )
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue().decode("utf-8")

    # -- SyncBackend protocol ----------------------------------------------------

    def list_records(self) -> dict[str, RemoteRecord]:
        drive = self._drive()
        records: dict[str, RemoteRecord] = {}
        page_token = None
        while True:
            response = (
                drive.files()
                .list(
                    q=f"'{self._folder()}' in parents and trashed=false",
                    spaces="drive",
                    fields="nextPageToken, files(id,name,appProperties)",
                    pageToken=page_token,
                )
                .execute()
            )
            for file in response.get("files", []):
                props = file.get("appProperties") or {}
                if not props.get("noteId"):
                    continue
                if props.get("rev"):
                    record = self._record(file)
                else:
                    # Legacy file with no fingerprint — derive one from content.
                    record = self._record(file, content=self._download_text(file["id"]))
                records[record.note_id] = record
            page_token = response.get("nextPageToken")
            if not page_token:
                return records

    def get_content(self, note_id: str) -> RemoteRecord:
        file_id = self._file_id(note_id)
        if file_id is None:
            raise KeyError(note_id)
        meta = (
            self._drive()
            .files()
            .get(fileId=file_id, fields="id,name,appProperties")
            .execute()
        )
        return self._record(meta, content=self._download_text(file_id))

    def put(
        self,
        note_id: str,
        content: str,
        color: str,
        created_at: str,
        updated_at: str,
    ) -> RemoteRecord:
        drive = self._drive()
        app_properties = {
            "noteId": note_id,
            "color": color,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "rev": content_revision(content, color),
        }
        media = MediaInMemoryUpload(
            content.encode("utf-8"), mimetype=TEXT_MIME, resumable=False
        )
        fields = "id,name,appProperties"
        file_id = self._file_id(note_id)
        if file_id is None:
            file = (
                drive.files()
                .create(
                    body={
                        "name": f"{note_id}.txt",
                        "parents": [self._folder()],
                        "appProperties": app_properties,
                    },
                    media_body=media,
                    fields=fields,
                )
                .execute()
            )
        else:
            file = (
                drive.files()
                .update(
                    fileId=file_id,
                    body={"appProperties": app_properties},
                    media_body=media,
                    fields=fields,
                )
                .execute()
            )
        return self._record(file, content=content)

    def delete(self, note_id: str) -> None:
        file_id = self._file_id(note_id)
        if file_id is not None:
            self._drive().files().delete(fileId=file_id).execute()


def _smoke_test() -> None:
    """Authorize and round-trip a throwaway note: create, list, read, delete.

    Run with: ``.venv\\Scripts\\python.exe -m app.sync.google_drive``
    Opens a browser for consent the first time, then saves token.json.
    """
    backend = GoogleDriveBackend("credentials.json", "token.json")
    note_id = "00000000-0000-0000-0000-000000000000"
    print("Uploading a test note…")
    backend.put(note_id, "drive smoke test", "#fff59d", "2026-01-01", "2026-01-01")
    listing = backend.list_records()
    print("Remote notes:", list(listing))
    print("Read back:", repr(backend.get_content(note_id).content))
    backend.delete(note_id)
    print("Deleted test note. OK ✓")


if __name__ == "__main__":
    _smoke_test()
