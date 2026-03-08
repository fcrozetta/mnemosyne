from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from app.schemas.common import EntityKind, EntityRef, SchemaModel


class ResolvedAboutInput(SchemaModel):
    """Context target already resolved to a canonical entity."""

    kind: EntityKind
    ref: EntityRef


class UnresolvedAboutInput(SchemaModel):
    """Context target captured as note-local pending context."""

    kind: EntityKind
    label: str = Field(min_length=1)


NoteAboutInput: TypeAlias = ResolvedAboutInput | UnresolvedAboutInput


class CreateNoteRequest(SchemaModel):
    """Request payload for creating a new note anchor and first revision."""

    content: str = Field(min_length=1)
    about: list[NoteAboutInput] = Field(default_factory=list)
    observed_at: datetime | None = None
    source_channel: Literal["chat", "manual"] = "chat"


class PutNoteRequest(SchemaModel):
    """Request payload for creating a fully specified new note revision."""

    content: str = Field(min_length=1)
    about: list[NoteAboutInput] = Field(default_factory=list)
    observed_at: datetime | None = None
    version: int | None = None


class PatchNoteRequest(SchemaModel):
    """Request payload for deriving a new note revision from the latest one."""

    addendum: str | None = Field(default=None, min_length=1)
    add_about: list[NoteAboutInput] = Field(default_factory=list)
    observed_at: datetime | None = None
    version: int | None = None

    @model_validator(mode="after")
    def validate_patch_operation(self) -> "PatchNoteRequest":
        if self.addendum is None and not self.add_about and self.observed_at is None:
            raise ValueError(
                "Patch requests must include addendum, add_about, or observed_at."
            )
        return self


class ResolvedAboutView(SchemaModel):
    """Resolved context returned with the latest note view."""

    kind: EntityKind
    collection: str
    key: str


class PendingAboutView(SchemaModel):
    """Unresolved context returned with the latest note view."""

    kind: EntityKind
    label: str


class NoteView(SchemaModel):
    """Latest note view exposed by the public API."""

    note_id: str
    version: int
    content: str
    observed_at: datetime
    created_at: datetime
    resolved_about: list[ResolvedAboutView] = Field(default_factory=list)
    pending_about: list[PendingAboutView] = Field(default_factory=list)


class NoteSearchResultView(SchemaModel):
    """Ranked note returned by the search endpoint."""

    note_id: str
    version: int
    content_preview: str
    observed_at: datetime
    score: float


__all__ = [
    "CreateNoteRequest",
    "NoteAboutInput",
    "NoteSearchResultView",
    "NoteView",
    "PatchNoteRequest",
    "PendingAboutView",
    "PutNoteRequest",
    "ResolvedAboutInput",
    "ResolvedAboutView",
    "UnresolvedAboutInput",
]
