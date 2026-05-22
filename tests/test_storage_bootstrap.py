from __future__ import annotations

from pathlib import Path

from app.repository.observations_in_memory import InMemoryObservationsRepository
from app.service.observations import ObservationsService

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _compose() -> str:
    return (PROJECT_ROOT / "docker-compose.yml").read_text()


def _compose_dev() -> str:
    return (PROJECT_ROOT / "docker-compose.dev.yml").read_text()


def _makefile() -> str:
    return (PROJECT_ROOT / "Makefile").read_text()


def _env_example() -> str:
    return (PROJECT_ROOT / ".env.example").read_text()


def _dockerfile() -> str:
    return (PROJECT_ROOT / "Dockerfile").read_text()


def test_service_initializes_in_memory_observation_storage() -> None:
    repository = InMemoryObservationsRepository()
    service = ObservationsService(repository=repository)

    result = service.initialize_storage()

    assert result.initialized is True
    assert repository.storage_initialized() is True


def test_compose_base_starts_arcadedb_and_api() -> None:
    compose = _compose()

    assert "arcadedb:" in compose
    assert "arcadedata/arcadedb:" in compose
    assert '"${ARCADE_PORT:-2480}:2480"' in compose
    assert "db-bootstrap:" in compose
    assert "./db:/app/db:ro" in compose
    assert "MNEMOSYNE_STORAGE_BACKEND: arcade" in compose
    assert "ARCADE_URL: http://arcadedb:2480" in compose
    assert "surrealdb:" not in compose
    assert "SURREAL_" not in compose


def test_compose_dev_has_no_surreal_seed_import() -> None:
    compose_dev = _compose_dev()

    assert "surreal" not in compose_dev.lower()
    assert "seed.surql" not in compose_dev


def test_makefile_uses_arcade_defaults() -> None:
    makefile = _makefile()

    assert "ARCADE_PORT ?= 2480" in makefile
    assert "ARCADE_URL ?= http://127.0.0.1:$(ARCADE_PORT)" in makefile
    assert "SURREAL_" not in makefile


def test_env_example_uses_arcade_backend() -> None:
    env = _env_example()

    assert "MNEMOSYNE_STORAGE_BACKEND=arcade" in env
    assert "ARCADE_URL=http://127.0.0.1:2480" in env
    assert "SURREAL_" not in env


def test_dockerfile_copies_arcadedb_schema() -> None:
    dockerfile = _dockerfile()

    assert "COPY db ./db" in dockerfile
