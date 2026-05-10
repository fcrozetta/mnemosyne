from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    build_notes_repository,
    get_notes_service,
    reset_notes_repository_cache,
)
from app.main import create_app
from app.repository.notes_in_memory import InMemoryNotesRepository
from app.repository.notes_surreal import SurrealNotesRepository
from app.service.notes import NotesService


class _StubRepository:
    def __init__(self, *, initialized: bool) -> None:
        self._initialized = initialized

    def initialize_storage(self) -> None:
        return None

    def storage_initialized(self) -> bool:
        return self._initialized


@pytest.fixture(autouse=True)
def clear_repository_cache() -> None:
    reset_notes_repository_cache()
    yield
    reset_notes_repository_cache()


def test_health_reports_initialized_storage_for_in_memory_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")

    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "storage_initialized": True}


def test_health_returns_503_when_storage_is_not_initialized() -> None:
    app = create_app()
    app.dependency_overrides[get_notes_service] = lambda: NotesService(
        repository=_StubRepository(initialized=False)
    )
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"ok": False, "storage_initialized": False}


def test_build_notes_repository_defaults_to_surreal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MNEMOSYNE_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("SURREAL_URL", raising=False)

    repository = build_notes_repository()

    assert isinstance(repository, SurrealNotesRepository)
    assert repository.runtime.base_url == "http://127.0.0.1:8001"


def test_build_notes_repository_supports_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")

    repository = build_notes_repository()

    assert isinstance(repository, InMemoryNotesRepository)
