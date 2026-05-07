from __future__ import annotations

from dataclasses import dataclass

from app.repository.notes import NotesRepository
from app.storage.bootstrap import (
    ALPHA_STORAGE_LAYOUT,
    StorageBootstrapper,
    StorageBootstrapResult,
    StorageLayout,
    StorageLayoutConflict,
)
from app.storage.surreal import SurrealRequestError, SurrealStorageBackend


@dataclass(slots=True)
class SurrealNotesRepository(NotesRepository):
    """Repository skeleton backed by SurrealDB bootstrap and layout checks."""

    runtime: SurrealStorageBackend
    bootstrap: SurrealStorageBackend | None = None
    layout: StorageLayout = ALPHA_STORAGE_LAYOUT

    def initialize_storage(self) -> StorageBootstrapResult:
        backend = self.bootstrap if self.bootstrap is not None else self.runtime
        backend.wait_until_ready(timeout_seconds=backend.timeout_seconds)
        backend.ensure_namespace_database()
        result = StorageBootstrapper(backend, self.layout).initialize()
        if self.bootstrap is not None:
            self.bootstrap.ensure_database_user(
                self.runtime.username,
                self.runtime.password,
            )
        return result

    def storage_initialized(self) -> bool:
        try:
            self.runtime.wait_until_ready(timeout_seconds=self.runtime.timeout_seconds)
            return self.runtime.sign_in().matches_layout(self.layout)
        except (StorageLayoutConflict, SurrealRequestError, TimeoutError):
            return False


__all__ = ["SurrealNotesRepository"]
