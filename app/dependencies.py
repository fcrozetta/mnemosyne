from __future__ import annotations

import os
from functools import lru_cache

from app.repository.observations import ObservationsRepository
from app.repository.observations_arcade import ArcadeObservationsRepository
from app.repository.observations_in_memory import InMemoryObservationsRepository
from app.service.audit import ArcadeAccessAuditService, InMemoryAccessAuditService
from app.service.observations import ObservationsService
from app.settings import MnemosyneSettings
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


@lru_cache
def get_settings() -> MnemosyneSettings:
    return MnemosyneSettings.from_env()


@lru_cache
def get_access_audit_service() -> InMemoryAccessAuditService | ArcadeAccessAuditService:
    backend = os.getenv("MNEMOSYNE_STORAGE_BACKEND", "arcade").strip().lower()
    if backend == "in-memory":
        return InMemoryAccessAuditService()
    runtime = ArcadeStorageBackend(
        base_url=os.getenv("ARCADE_URL", "http://127.0.0.1:2480"),
        database=os.getenv("ARCADE_DATABASE", "mnemosyne"),
        username=os.getenv("ARCADE_USERNAME", "root"),
        password=os.getenv("ARCADE_PASSWORD", "mnemosyne-root"),
        timeout_seconds=float(os.getenv("ARCADE_TIMEOUT_SECONDS", "5")),
    )
    return ArcadeAccessAuditService(runtime=runtime)


def reset_observations_repository_cache() -> None:
    get_observations_repository.cache_clear()


def reset_settings_cache() -> None:
    get_settings.cache_clear()


def reset_access_audit_service_cache() -> None:
    get_access_audit_service.cache_clear()


def get_observations_service() -> ObservationsService:
    return ObservationsService(repository=get_observations_repository())


__all__ = [
    "build_observations_repository",
    "get_access_audit_service",
    "get_observations_repository",
    "get_observations_service",
    "get_settings",
    "reset_access_audit_service_cache",
    "reset_observations_repository_cache",
    "reset_settings_cache",
]
