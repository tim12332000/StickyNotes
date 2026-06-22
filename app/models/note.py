from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(slots=True)
class Note:
    content: str = ""
    note_id: UUID = field(default_factory=uuid4)
