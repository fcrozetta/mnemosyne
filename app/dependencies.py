from __future__ import annotations

import os
from functools import lru_cache

from app.repository.notes import NotesRepository
from app.repository.notes_in_memory import InMemoryNotesRepository
from app.repository.notes_surreal import SurrealNotesRepository
from app.service.notes import NotesService
from app.storage.surreal import SurrealStorageBackend


def build_notes_repository() -> NotesRepository:
    backend = os.getenv("MNEMOSYNE_STORAGE_BACKEND", "surreal").strip().lower()
    if backend == "in-memory":
        repository = InMemoryNotesRepository()
        repository.initialize_storage()
        return repository
    if backend != "surreal":
        msg = f"Unsupported storage backend: {backend!r}."
        raise ValueError(msg)

    base_url = os.getenv("SURREAL_URL", "http://127.0.0.1:8001")
    namespace = os.getenv("SURREAL_NAMESPACE", "mnemosyne")
    database = os.getenv("SURREAL_DATABASE", "mnemosyne")
    timeout_seconds = float(os.getenv("SURREAL_TIMEOUT_SECONDS", "5"))

    runtime = SurrealStorageBackend(
        base_url=base_url,
        namespace=namespace,
        database=database,
        username=os.getenv("SURREAL_USERNAME", "mnemosyne"),
        password=os.getenv("SURREAL_PASSWORD", "mnemosyne"),
        timeout_seconds=timeout_seconds,
    )
    bootstrap = SurrealStorageBackend(
        base_url=base_url,
        namespace=namespace,
        database=database,
        username=os.getenv("SURREAL_ROOT_USERNAME", "root"),
        password=os.getenv("SURREAL_ROOT_PASSWORD", "root"),
        timeout_seconds=timeout_seconds,
    )
    return SurrealNotesRepository(runtime=runtime, bootstrap=bootstrap)


@lru_cache
def get_notes_repository() -> NotesRepository:
    return build_notes_repository()


def reset_notes_repository_cache() -> None:
    get_notes_repository.cache_clear()


def get_notes_service() -> NotesService:
    return NotesService(repository=get_notes_repository())
