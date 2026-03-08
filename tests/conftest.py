import pytest

from app.dependencies import get_arango_database
from app.repository.notes_arango import ArangoNotesRepository
from app.repository.notes_in_memory import InMemoryNotesRepository
from app.service.notes import NotesService


@pytest.fixture
def notes_service() -> NotesService:
    """Fresh notes service per test with isolated in-memory persistence."""

    return NotesService(InMemoryNotesRepository())


@pytest.fixture
def arango_notes_repository() -> ArangoNotesRepository:
    """Repository backed by the local Arango database."""

    return ArangoNotesRepository(get_arango_database())
