from __future__ import annotations

from dataclasses import dataclass

from app.models.notes import (
    CreateNoteInput,
    Note,
    NoteContext,
    NoteSearchResult,
    PatchNoteInput,
)
from app.repository.notes import NotesRepository
from app.storage.bootstrap import StorageBootstrapResult


@dataclass(frozen=True, slots=True)
class NotesService:
    """Application boundary for alpha note behavior."""

    repository: NotesRepository

    def initialize_storage(self) -> StorageBootstrapResult:
        return self.repository.initialize_storage()

    def storage_initialized(self) -> bool:
        return self.repository.storage_initialized()

    def create_note(self, note: CreateNoteInput) -> Note:
        return self.repository.create_note(note)

    def get_note(self, note_id: str) -> Note:
        return self.repository.get_note(note_id)

    def search_notes(self, query: str, limit: int = 5) -> tuple[NoteSearchResult, ...]:
        return self.repository.search_notes(query, limit=limit)

    def patch_note(self, note_id: str, patch: PatchNoteInput) -> Note:
        return self.repository.patch_note(note_id, patch)

    def get_note_context(self, note_id: str, limit: int = 5) -> NoteContext:
        return self.repository.get_note_context(note_id, limit=limit)


__all__ = ["NotesService"]
