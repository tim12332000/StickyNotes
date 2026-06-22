"""Cloud synchronization boundary.

Provider-agnostic two-way sync. The :class:`SyncEngine` reconciles local notes
with any :class:`SyncBackend`; :class:`InMemoryBackend` is a testable fake and
:class:`GoogleDriveBackend` is the real provider (imported lazily so the core
does not depend on the Google client libraries unless Drive is actually used).
"""

from typing import TYPE_CHECKING

from app.sync.backend import InMemoryBackend, RemoteRecord, SyncBackend
from app.sync.engine import SyncEngine, SyncResult

if TYPE_CHECKING:
    from app.sync.google_drive import GoogleDriveBackend

__all__ = [
    "GoogleDriveBackend",
    "InMemoryBackend",
    "RemoteRecord",
    "SyncBackend",
    "SyncEngine",
    "SyncResult",
]


def __getattr__(name: str):
    if name == "GoogleDriveBackend":
        from app.sync.google_drive import GoogleDriveBackend

        return GoogleDriveBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
