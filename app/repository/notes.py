from __future__ import annotations

from typing import Protocol

from app.models.notes import (
    CreateNoteInput,
    Note,
    NoteContext,
    NoteSearchResult,
    PatchNoteInput,
)
from app.storage.bootstrap import StorageBootstrapResult


class NotesRepository(Protocol):
    """Persistence boundary for alpha note storage."""

    def initialize_storage(self) -> StorageBootstrapResult: ...

    def storage_initialized(self) -> bool: ...

    def create_note(self, note: CreateNoteInput) -> Note: ...

    def get_note(self, note_id: str) -> Note: ...

    def search_notes(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[NoteSearchResult, ...]: ...

    def patch_note(self, note_id: str, patch: PatchNoteInput) -> Note: ...

    def get_note_context(self, note_id: str, limit: int = 5) -> NoteContext: ...


__all__ = ["NotesRepository"]
