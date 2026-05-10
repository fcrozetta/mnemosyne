from __future__ import annotations

import re
from collections.abc import Iterable
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
        return (self.kind.value, normalize_label(self.label))


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


AboutRef = ResolvedAboutRef | PendingAboutRef


@dataclass(frozen=True, slots=True)
class CreateNoteInput:
    content: str
    about: tuple[AboutRef, ...] = ()
    observed_at: datetime | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class PatchNoteInput:
    version: int
    addendum: str | None = None
    add_about: tuple[AboutRef, ...] = ()
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NoteSearchResult:
    note_id: str
    version: int
    content_preview: str
    observed_at: datetime
    score: float


@dataclass(frozen=True, slots=True)
class NoteContext:
    note: Note
    related_notes: tuple[NoteSearchResult, ...]


class NoteNotFoundError(LookupError):
    def __init__(self, note_id: str) -> None:
        super().__init__(f"Note {note_id!r} was not found.")
        self.note_id = note_id


class VersionConflictError(RuntimeError):
    def __init__(
        self,
        note_id: str,
        current_version: int,
        requested_version: int,
    ) -> None:
        super().__init__(f"Version conflict for note {note_id!r}.")
        self.note_id = note_id
        self.current_version = current_version
        self.requested_version = requested_version


class InvalidNotePatchError(ValueError):
    pass


class InvalidNoteRequestError(ValueError):
    def __init__(self, error: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.field = field


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_label(label: str) -> str:
    return " ".join(label.split()).lower()


def split_about_refs(
    about_refs: Iterable[AboutRef],
) -> tuple[tuple[ResolvedAboutRef, ...], tuple[PendingAboutRef, ...]]:
    resolved: list[ResolvedAboutRef] = []
    pending: list[PendingAboutRef] = []

    for about_ref in about_refs:
        if isinstance(about_ref, ResolvedAboutRef):
            resolved.append(about_ref)
        else:
            pending.append(about_ref)

    return tuple(resolved), tuple(pending)


def merge_about_refs(
    existing: Iterable[AboutRef],
    additions: Iterable[AboutRef],
) -> tuple[AboutRef, ...]:
    merged: list[AboutRef] = []
    seen: set[tuple[str, ...]] = set()

    for about_ref in (*tuple(existing), *tuple(additions)):
        identity = about_identity(about_ref)
        if identity in seen:
            continue
        merged.append(about_ref)
        seen.add(identity)

    return tuple(merged)


def about_identity(about_ref: AboutRef) -> tuple[str, ...]:
    if isinstance(about_ref, ResolvedAboutRef):
        return ("resolved", *about_ref.identity)
    return ("pending", *about_ref.identity)


def append_addendum(content: str, addendum: str | None) -> str:
    if addendum is None:
        return content
    return f"{content}\n\nAddendum:\n{addendum}"


def content_preview(content: str, limit: int = 120) -> str:
    preview = content.splitlines()[0].strip()
    if len(preview) <= limit:
        return preview
    return preview[: limit - 1].rstrip() + "…"


def score_content_match(content: str, query: str) -> float:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return 0.0

    normalized_content = content.casefold()
    if normalized_query in normalized_content:
        return 1.0

    query_terms = tuple(term for term in re.split(r"\s+", normalized_query) if term)
    if not query_terms:
        return 0.0

    matches = sum(1 for term in query_terms if term in normalized_content)
    return matches / len(query_terms)


def related_overlap(note: Note, other: Note) -> int:
    note_latest = note.latest_revision
    other_latest = other.latest_revision
    if note_latest is None or other_latest is None:
        return 0

    note_about = {
        about_identity(about_ref)
        for about_ref in (*note_latest.resolved_about, *note_latest.pending_about)
    }
    other_about = {
        about_identity(about_ref)
        for about_ref in (*other_latest.resolved_about, *other_latest.pending_about)
    }
    return len(note_about & other_about)


def next_note_id(existing_note_ids: Iterable[str]) -> str:
    highest = 0
    count = 0

    for note_id in existing_note_ids:
        count += 1
        match = re.fullmatch(r"note_(\d+)", note_id)
        if match is None:
            continue
        highest = max(highest, int(match.group(1)))

    next_number = highest + 1 if highest else count + 1
    return f"note_{next_number:03d}"


__all__ = [
    "AboutRef",
    "AboutKind",
    "CreateNoteInput",
    "InvalidNotePatchError",
    "InvalidNoteRequestError",
    "Note",
    "NoteContext",
    "NoteNotFoundError",
    "NoteRevision",
    "NoteSearchResult",
    "PatchNoteInput",
    "PendingAboutRef",
    "Provenance",
    "ResolvedAboutRef",
    "VersionConflictError",
    "about_identity",
    "append_addendum",
    "content_preview",
    "merge_about_refs",
    "next_note_id",
    "normalize_label",
    "related_overlap",
    "score_content_match",
    "split_about_refs",
    "utc_now",
]
