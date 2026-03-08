from functools import lru_cache

from arango import ArangoClient

from app.handler.notes import NotesHandler
from app.repository.notes import NotesRepository
from app.repository.notes_arango import ArangoNotesRepository
from app.service.notes import NotesService
from app.settings import Settings


@lru_cache
def get_settings() -> Settings:
    """Load runtime settings once per process."""

    return Settings()


@lru_cache
def get_arango_database():
    """Create the shared Arango database handle for the API runtime."""

    settings = get_settings()
    client = ArangoClient(hosts=settings.arango_hosts)
    return client.db(
        settings.arango_db,
        username=settings.arango_username,
        password=settings.arango_password,
    )


@lru_cache
def get_notes_repository() -> NotesRepository:
    """Build the notes repository backed by Arango."""

    return ArangoNotesRepository(get_arango_database())


@lru_cache
def get_notes_service() -> NotesService:
    """Build the notes service for dependency injection."""

    return NotesService(get_notes_repository())


@lru_cache
def get_notes_handler() -> NotesHandler:
    """Build the notes handler for dependency injection."""

    return NotesHandler(get_notes_service())


__all__ = [
    "get_arango_database",
    "get_notes_handler",
    "get_notes_repository",
    "get_notes_service",
    "get_settings",
]
