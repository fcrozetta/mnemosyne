from __future__ import annotations

from typing import Protocol

from app.storage.bootstrap import StorageBootstrapResult


class NotesRepository(Protocol):
    """Persistence boundary for alpha note storage."""

    def initialize_storage(self) -> StorageBootstrapResult: ...

    def storage_initialized(self) -> bool: ...


__all__ = ["NotesRepository"]
