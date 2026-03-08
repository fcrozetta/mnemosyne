from __future__ import annotations

from typing import Protocol

from app.models.notes import NoteRecord, NoteSearchCandidateRecord, NoteWritePayload


class RepositoryVersionConflictError(Exception):
    """Raised when repository-level version checks fail."""

    def __init__(self, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"Expected version {expected_version}, found {current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class NotesRepository(Protocol):
    """Persistence contract for note operations."""

    def create_note(self, payload: NoteWritePayload) -> NoteRecord: ...

    def get_note(self, note_id: str) -> NoteRecord | None: ...

    def create_revision(
        self,
        note_id: str,
        payload: NoteWritePayload,
        expected_version: int | None = None,
    ) -> NoteRecord: ...

    def search_notes(
        self, query: str, limit: int = 5
    ) -> list[NoteSearchCandidateRecord]: ...


__all__ = ["NotesRepository", "RepositoryVersionConflictError"]
