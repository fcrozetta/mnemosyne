from __future__ import annotations

from functools import lru_cache

from app.repository.notes import NotesRepository
from app.repository.notes_in_memory import InMemoryNotesRepository
from app.service.notes import NotesService


@lru_cache
def get_notes_repository() -> NotesRepository:
    repository = InMemoryNotesRepository()
    repository.initialize_storage()
    return repository


def get_notes_service() -> NotesService:
    return NotesService(repository=get_notes_repository())
