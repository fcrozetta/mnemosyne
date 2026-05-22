from __future__ import annotations

import os
from functools import lru_cache

from app.repository.observations import ObservationsRepository
from app.repository.observations_arcade import ArcadeObservationsRepository
from app.repository.observations_in_memory import InMemoryObservationsRepository
from app.service.observations import ObservationsService
from app.storage.arcade import ArcadeStorageBackend


def build_observations_repository() -> ObservationsRepository:
    backend = os.getenv("MNEMOSYNE_STORAGE_BACKEND", "arcade").strip().lower()
    if backend == "in-memory":
        repository = InMemoryObservationsRepository()
        repository.initialize_storage()
        return repository
    if backend == "arcade":
        runtime = ArcadeStorageBackend(
            base_url=os.getenv("ARCADE_URL", "http://127.0.0.1:2480"),
            database=os.getenv("ARCADE_DATABASE", "mnemosyne"),
            username=os.getenv("ARCADE_USERNAME", "root"),
            password=os.getenv("ARCADE_PASSWORD", "mnemosyne-root"),
            timeout_seconds=float(os.getenv("ARCADE_TIMEOUT_SECONDS", "5")),
        )
        return ArcadeObservationsRepository(runtime=runtime)
    msg = f"Unsupported storage backend: {backend!r}."
    raise ValueError(msg)


@lru_cache
def get_observations_repository() -> ObservationsRepository:
    return build_observations_repository()


def reset_observations_repository_cache() -> None:
    get_observations_repository.cache_clear()


def get_observations_service() -> ObservationsService:
    return ObservationsService(repository=get_observations_repository())


__all__ = [
    "build_observations_repository",
    "get_observations_repository",
    "get_observations_service",
    "reset_observations_repository_cache",
]
