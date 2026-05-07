from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class AboutKind(StrEnum):
    PERSON = "person"
    LOCATION = "location"
    ITEM = "item"
    TOPIC = "topic"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ResolvedAboutRef:
    kind: AboutKind
    collection: str
    key: str

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.kind.value, self.collection, self.key)


@dataclass(frozen=True, slots=True)
class PendingAboutRef:
    kind: AboutKind
    label: str

    @property
    def identity(self) -> tuple[str, str]:
        return (self.kind.value, " ".join(self.label.split()).lower())


@dataclass(frozen=True, slots=True)
class Provenance:
    writer: str | None = None
    session_id: str | None = None
    source_type: str | None = None
    source_ref: str | None = None


@dataclass(frozen=True, slots=True)
class NoteRevision:
    version: int
    content: str
    observed_at: datetime
    created_at: datetime
    resolved_about: tuple[ResolvedAboutRef, ...] = ()
    pending_about: tuple[PendingAboutRef, ...] = ()
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class Note:
    note_id: str
    created_at: datetime
    revisions: tuple[NoteRevision, ...] = ()

    @property
    def latest_revision(self) -> NoteRevision | None:
        if not self.revisions:
            return None
        return self.revisions[-1]

    @property
    def version(self) -> int:
        latest = self.latest_revision
        return latest.version if latest is not None else 0


def utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "AboutKind",
    "Note",
    "NoteRevision",
    "PendingAboutRef",
    "Provenance",
    "ResolvedAboutRef",
    "utc_now",
]
