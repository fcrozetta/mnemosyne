from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.dependencies import get_notes_service
from app.models.notes import (
    AboutKind,
    CreateNoteInput,
    InvalidNotePatchError,
    InvalidNoteRequestError,
    Note,
    NoteContext,
    NoteNotFoundError,
    NoteSearchResult,
    PatchNoteInput,
    PendingAboutRef,
    Provenance,
    ResolvedAboutRef,
    VersionConflictError,
    split_about_refs,
)
from app.service.notes import NotesService


def create_app() -> FastAPI:
    app = FastAPI(title="Mnemosyne", version="0.1.0-alpha")

    @app.exception_handler(NoteNotFoundError)
    def handle_note_not_found(
        _request: object,
        exc: NoteNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_response(
                error="note_not_found",
                field="note_id",
                message="Note was not found.",
                code="note_not_found",
                context={"note_id": exc.note_id},
            ),
        )

    @app.exception_handler(VersionConflictError)
    def handle_version_conflict(
        _request: object,
        exc: VersionConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_response(
                error="version_conflict",
                field="version",
                message="Version does not match latest note version.",
                code="version_conflict",
                context={
                    "note_id": exc.note_id,
                    "current_version": exc.current_version,
                    "requested_version": exc.requested_version,
                },
            ),
        )

    @app.exception_handler(InvalidNotePatchError)
    def handle_invalid_note_patch(
        _request: object,
        exc: InvalidNotePatchError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_response(
                error="invalid_note_patch",
                field=None,
                message=str(exc),
                code="invalid_note_patch",
                context=None,
            ),
        )

    @app.exception_handler(InvalidNoteRequestError)
    def handle_invalid_note_request(
        _request: object,
        exc: InvalidNoteRequestError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_response(
                error=exc.error,
                field=exc.field,
                message=exc.message,
                code=exc.error,
                context=None,
            ),
        )

    @app.exception_handler(RequestValidationError)
    def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        error = "invalid_note_request"
        body_message = "Request body is required."
        if request.method == "PATCH" and request.url.path.startswith("/notes/"):
            error = "invalid_note_patch"
            body_message = "Patch body is required."

        details: list[dict[str, Any]] = []
        for issue in exc.errors():
            field, message = _validation_error_detail(
                issue,
                body_message=body_message,
            )
            details.append(
                {
                    **({"field": field} if field is not None else {}),
                    "message": message,
                    "code": error,
                }
            )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": error,
                "details": details
                or [
                    {
                        "message": "Request validation failed.",
                        "code": error,
                    }
                ],
                "request_id": None,
            },
        )

    @app.get("/healthz")
    def healthz(
        response: Response,
        service: Annotated[NotesService, Depends(get_notes_service)],
    ) -> dict:
        initialized = service.storage_initialized()
        if not initialized:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "ok": initialized,
            "storage_initialized": initialized,
        }

    @app.post("/notes", status_code=status.HTTP_201_CREATED)
    def create_note(
        service: Annotated[NotesService, Depends(get_notes_service)],
        body: Any = Body(...),
    ) -> dict[str, Any]:
        note = service.create_note(_parse_create_note_input(body))
        return _serialize_note(note)

    @app.get("/notes")
    def search_notes(
        service: Annotated[NotesService, Depends(get_notes_service)],
        q: str = "",
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not q.strip():
            raise InvalidNoteRequestError(
                error="invalid_note_request",
                field="q",
                message="Query parameter q must be non-empty.",
            )
        if not 1 <= limit <= 50:
            raise InvalidNoteRequestError(
                error="invalid_note_request",
                field="limit",
                message="Limit must be between 1 and 50.",
            )
        return [
            _serialize_search_result(result)
            for result in service.search_notes(q, limit=limit)
        ]

    @app.get("/notes/{note_id}")
    def get_note(
        note_id: str,
        service: Annotated[NotesService, Depends(get_notes_service)],
    ) -> dict[str, Any]:
        return _serialize_note(service.get_note(note_id))

    @app.patch("/notes/{note_id}")
    def patch_note(
        note_id: str,
        service: Annotated[NotesService, Depends(get_notes_service)],
        body: Any = Body(...),
    ) -> dict[str, Any]:
        patch = _parse_patch_note_input(body)
        return _serialize_note(service.patch_note(note_id, patch))

    @app.get("/notes/{note_id}/context")
    def get_note_context(
        note_id: str,
        service: Annotated[NotesService, Depends(get_notes_service)],
    ) -> dict[str, Any]:
        return _serialize_note_context(service.get_note_context(note_id))

    return app


def _parse_create_note_input(body: Any) -> CreateNoteInput:
    if not isinstance(body, dict):
        raise InvalidNoteRequestError(
            error="invalid_note_request",
            field=None,
            message="Request body must be an object.",
        )
    content = body.get("content")
    if not isinstance(content, str) or not content.strip():
        raise InvalidNoteRequestError(
            error="invalid_note_request",
            field="content",
            message="Content must be a non-empty string.",
        )

    return CreateNoteInput(
        content=content,
        about=_parse_about_refs(body.get("about"), field="about"),
        observed_at=_parse_datetime(body.get("observed_at"), field="observed_at"),
        provenance=Provenance(source_type=_optional_string(body.get("source_channel"))),
    )


def _parse_patch_note_input(body: Any) -> PatchNoteInput:
    if not isinstance(body, dict):
        raise InvalidNoteRequestError(
            error="invalid_note_patch",
            field=None,
            message="Patch body must be an object.",
        )
    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise InvalidNoteRequestError(
            error="invalid_note_patch",
            field="version",
            message="Version must be an integer.",
        )

    addendum = body.get("addendum")
    if addendum is not None and not isinstance(addendum, str):
        raise InvalidNoteRequestError(
            error="invalid_note_patch",
            field="addendum",
            message="Addendum must be a string when provided.",
        )

    return PatchNoteInput(
        version=version,
        addendum=addendum,
        add_about=_parse_about_refs(
            body.get("add_about"),
            field="add_about",
            error="invalid_note_patch",
        ),
        observed_at=_parse_datetime(
            body.get("observed_at"),
            field="observed_at",
            error="invalid_note_patch",
        ),
    )


def _parse_about_refs(
    value: Any,
    *,
    field: str,
    error: str = "invalid_note_request",
) -> tuple[ResolvedAboutRef | PendingAboutRef, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message=f"{field} must be a list.",
        )

    parsed: list[ResolvedAboutRef | PendingAboutRef] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise InvalidNoteRequestError(
                error=error,
                field=f"{field}[{index}]",
                message="About entries must be objects.",
            )

        kind = _parse_about_kind(
            item.get("kind"),
            field=f"{field}[{index}].kind",
            error=error,
        )
        ref = item.get("ref")
        label = item.get("label")

        if ref is not None and label is not None:
            raise InvalidNoteRequestError(
                error=error,
                field=f"{field}[{index}]",
                message="About entries must provide either ref or label, not both.",
            )

        if ref is not None:
            if not isinstance(ref, dict):
                raise InvalidNoteRequestError(
                    error=error,
                    field=f"{field}[{index}].ref",
                    message="Resolved about refs must use an object ref.",
                )
            collection = ref.get("collection")
            key = ref.get("key")
            if not isinstance(collection, str) or not collection.strip():
                raise InvalidNoteRequestError(
                    error=error,
                    field=f"{field}[{index}].ref.collection",
                    message="Resolved about refs require a non-empty collection.",
                )
            if not isinstance(key, str) or not key.strip():
                raise InvalidNoteRequestError(
                    error=error,
                    field=f"{field}[{index}].ref.key",
                    message="Resolved about refs require a non-empty key.",
                )
            parsed.append(
                ResolvedAboutRef(
                    kind=kind,
                    collection=collection,
                    key=key,
                )
            )
            continue

        if not isinstance(label, str) or not label.strip():
            raise InvalidNoteRequestError(
                error=error,
                field=f"{field}[{index}].label",
                message="Pending about refs require a non-empty label.",
            )
        parsed.append(PendingAboutRef(kind=kind, label=label))

    return tuple(parsed)


def _parse_about_kind(
    value: Any,
    *,
    field: str,
    error: str = "invalid_note_request",
) -> AboutKind:
    if not isinstance(value, str):
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message="About kind must be a string.",
        )
    try:
        return AboutKind(value)
    except ValueError as exc:
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message=f"Unsupported about kind: {value!r}.",
        ) from exc


def _parse_datetime(
    value: Any,
    *,
    field: str,
    error: str = "invalid_note_request",
) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message=f"{field} must be an ISO 8601 datetime string.",
        )
    if "T" not in value.upper():
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message=f"{field} must be an ISO 8601 datetime string.",
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message=f"{field} must be an ISO 8601 datetime string.",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _serialize_note(note: Note) -> dict[str, Any]:
    latest = note.latest_revision
    assert latest is not None
    return {
        "note_id": note.note_id,
        "version": latest.version,
        "content": latest.content,
        "observed_at": _iso(latest.observed_at),
        "created_at": _iso(note.created_at),
        "resolved_about": [
            {
                "kind": about_ref.kind,
                "collection": about_ref.collection,
                "key": about_ref.key,
            }
            for about_ref in latest.resolved_about
        ],
        "pending_about": [
            {
                "kind": about_ref.kind,
                "label": about_ref.label,
            }
            for about_ref in latest.pending_about
        ],
    }


def _validation_error_detail(
    issue: dict[str, Any],
    *,
    body_message: str,
) -> tuple[str | None, str]:
    location = issue.get("loc")
    if not isinstance(location, tuple) or not location:
        return None, "Request validation failed."

    scope = location[0]
    if scope == "body":
        if len(location) == 1:
            return None, body_message
        field = ".".join(str(part) for part in location[1:])
        return field, f"{field} is invalid."

    if scope == "query" and len(location) >= 2:
        field = str(location[1])
        return field, f"Invalid value for {field}."

    if scope == "path" and len(location) >= 2:
        field = str(location[1])
        return field, f"Invalid value for {field}."

    return None, "Request validation failed."


def _serialize_search_result(result: NoteSearchResult) -> dict[str, Any]:
    return {
        "note_id": result.note_id,
        "version": result.version,
        "content_preview": result.content_preview,
        "observed_at": _iso(result.observed_at),
        "score": result.score,
    }


def _serialize_note_context(context: NoteContext) -> dict[str, Any]:
    latest = context.note.latest_revision
    assert latest is not None
    resolved_about, pending_about = split_about_refs(
        (*latest.resolved_about, *latest.pending_about)
    )
    return {
        "note": _serialize_note(context.note),
        "basis": {
            "resolved_about": [
                {
                    "kind": about_ref.kind,
                    "collection": about_ref.collection,
                    "key": about_ref.key,
                }
                for about_ref in resolved_about
            ],
            "pending_about": [
                {
                    "kind": about_ref.kind,
                    "label": about_ref.label,
                }
                for about_ref in pending_about
            ],
        },
        "related_notes": [
            _serialize_search_result(result) for result in context.related_notes
        ],
    }


def _error_response(
    *,
    error: str,
    field: str | None,
    message: str,
    code: str,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "message": message,
        "code": code,
    }
    if field is not None:
        detail["field"] = field
    if context is not None:
        detail["context"] = context
    return {
        "error": error,
        "details": [detail],
        "request_id": None,
    }


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


app = create_app()
