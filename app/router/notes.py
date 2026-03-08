from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_notes_handler
from app.handler.notes import NotesHandler, notes_responses
from app.schemas.notes import (
    CreateNoteRequest,
    NoteSearchResultView,
    NoteView,
    PatchNoteRequest,
    PutNoteRequest,
)

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post(
    "",
    response_model=NoteView,
    responses=notes_responses(),
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    payload: CreateNoteRequest,
    handler: NotesHandler = Depends(get_notes_handler),
) -> NoteView:
    return handler.create_note(payload)


@router.get(
    "",
    response_model=list[NoteSearchResultView],
)
def search_notes(
    q: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=50),
    handler: NotesHandler = Depends(get_notes_handler),
) -> list[NoteSearchResultView]:
    return handler.search_notes(q, limit)


@router.get(
    "/{note_id}",
    response_model=NoteView,
    responses=notes_responses(),
)
def get_note(
    note_id: str,
    handler: NotesHandler = Depends(get_notes_handler),
) -> NoteView:
    return handler.get_note(note_id)


@router.put(
    "/{note_id}",
    response_model=NoteView,
    responses=notes_responses(),
)
def put_note(
    note_id: str,
    payload: PutNoteRequest,
    handler: NotesHandler = Depends(get_notes_handler),
) -> NoteView:
    return handler.put_note(note_id, payload)


@router.patch(
    "/{note_id}",
    response_model=NoteView,
    responses=notes_responses(),
)
def patch_note(
    note_id: str,
    payload: PatchNoteRequest,
    handler: NotesHandler = Depends(get_notes_handler),
) -> NoteView:
    return handler.patch_note(note_id, payload)


__all__ = ["router"]
