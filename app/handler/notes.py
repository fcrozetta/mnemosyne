from collections.abc import Callable

from fastapi import status
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorResponse
from app.schemas.notes import (
    CreateNoteRequest,
    NoteSearchResultView,
    NoteView,
    PatchNoteRequest,
    PutNoteRequest,
)
from app.service.notes import NotesService, ServiceError


class NotesHandler:
    """Thin HTTP-facing adapter over the note service."""

    def __init__(self, service: NotesService) -> None:
        self.service = service

    def create_note(self, payload: CreateNoteRequest) -> NoteView | JSONResponse:
        return self._invoke(lambda: self.service.create_note(payload))

    def get_note(self, note_id: str) -> NoteView | JSONResponse:
        return self._invoke(lambda: self.service.get_note(note_id))

    def search_notes(self, query: str, limit: int) -> list[NoteSearchResultView]:
        return self.service.search_notes(query, limit=limit)

    def put_note(
        self, note_id: str, payload: PutNoteRequest
    ) -> NoteView | JSONResponse:
        return self._invoke(lambda: self.service.put_note(note_id, payload))

    def patch_note(
        self, note_id: str, payload: PatchNoteRequest
    ) -> NoteView | JSONResponse:
        return self._invoke(lambda: self.service.patch_note(note_id, payload))

    def _invoke(
        self, operation: Callable[[], NoteView]
    ) -> NoteView | JSONResponse:
        try:
            return operation()
        except ServiceError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(
                    error=exc.error, details=exc.details
                ).model_dump(mode="json"),
            )


def notes_responses() -> dict[int | str, dict[str, object]]:
    """Shared OpenAPI response mapping for note endpoints."""

    return {
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "The request is syntactically valid but semantically invalid."
            ),
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "The requested note does not exist.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The supplied version does not match the latest note version."
            ),
        },
    }


__all__ = ["NotesHandler", "notes_responses"]
