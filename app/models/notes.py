from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import ArangoDocument, ArangoEdge, ModelBase
from app.schemas.common import EntityKind


class PendingAboutRecord(ModelBase):
    """Unresolved note-local context stored inline on a note revision."""

    kind: EntityKind
    label: str = Field(min_length=1)


class ResolvedAboutRecord(ModelBase):
    """Resolved context associated with a note revision."""

    kind: EntityKind
    collection: str
    key: str


class NoteDocument(ArangoDocument):
    """Stable note anchor document."""

    note_id: str
    current_content: str = ""
    pending_about_labels: list[str] = Field(default_factory=list)
    resolved_about_labels: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    observed_at: datetime | None = None


class NoteRevisionDocument(ArangoDocument):
    """Immutable note revision document."""

    note_id: str
    revision: int
    content: str = Field(min_length=1)
    observed_at: datetime
    pending_about: list[PendingAboutRecord] = Field(default_factory=list)


class EventDocument(ArangoDocument):
    """Provenance event created for note writes."""

    event_kind: Literal["manual_note", "manual_edit", "manual_patch"]
    source_system: str
    source_channel: str


class BelongsToEdge(ArangoEdge):
    """Connects a note revision to its stable note anchor."""


class LatestRevisionEdge(ArangoEdge):
    """Points from the note anchor to the current latest revision."""


class SupersedesEdge(ArangoEdge):
    """Connects a new revision to the revision it supersedes."""


class OriginatesFromEdge(ArangoEdge):
    """Connects a revision to the event that produced it."""


class AboutEdge(ArangoEdge):
    """Connects a revision to a resolved context entity."""

    kind: EntityKind


class NoteWritePayload(ModelBase):
    """Normalized note write input used between service and repository."""

    content: str = Field(min_length=1)
    observed_at: datetime
    resolved_about: list[ResolvedAboutRecord] = Field(default_factory=list)
    pending_about: list[PendingAboutRecord] = Field(default_factory=list)
    source_channel: str = "chat"
    created_by: str = "system"
    event_kind: Literal["manual_note", "manual_edit", "manual_patch"]


class NoteRecord(ModelBase):
    """Internal aggregate for the latest visible note state."""

    note: NoteDocument
    latest_revision: NoteRevisionDocument
    resolved_about: list[ResolvedAboutRecord] = Field(default_factory=list)

    @property
    def note_id(self) -> str:
        return self.note.note_id

    @property
    def version(self) -> int:
        return self.latest_revision.revision


class NoteSearchCandidateRecord(ModelBase):
    """Internal note search candidate."""

    note_id: str
    version: int
    latest_content: str
    score: float
    updated_at: datetime
    observed_at: datetime


__all__ = [
    "AboutEdge",
    "BelongsToEdge",
    "EventDocument",
    "LatestRevisionEdge",
    "NoteDocument",
    "NoteRecord",
    "NoteRevisionDocument",
    "NoteSearchCandidateRecord",
    "NoteWritePayload",
    "OriginatesFromEdge",
    "PendingAboutRecord",
    "ResolvedAboutRecord",
    "SupersedesEdge",
]
