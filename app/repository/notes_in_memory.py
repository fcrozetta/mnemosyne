from __future__ import annotations

from dataclasses import dataclass, field

from app.repository.notes import NotesRepository
from app.storage.bootstrap import (
    ALPHA_STORAGE_LAYOUT,
    StorageBootstrapper,
    StorageBootstrapResult,
    StorageLayout,
)
from app.storage.in_memory import InMemoryStorageBackend


@dataclass(slots=True)
class InMemoryNotesRepository(NotesRepository):
    """Local repository skeleton backed by an in-memory storage catalog."""

    storage: InMemoryStorageBackend = field(default_factory=InMemoryStorageBackend)
    layout: StorageLayout = ALPHA_STORAGE_LAYOUT

    def initialize_storage(self) -> StorageBootstrapResult:
        return StorageBootstrapper(self.storage, self.layout).initialize()

    def storage_initialized(self) -> bool:
        return self.storage.matches(self.layout)


__all__ = ["InMemoryNotesRepository"]
