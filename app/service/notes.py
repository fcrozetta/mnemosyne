from __future__ import annotations

from dataclasses import dataclass

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


__all__ = ["NotesService"]
