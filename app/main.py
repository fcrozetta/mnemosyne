from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
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

    _install_openapi_schema(app)
    return app


_OPENAPI_SCHEMA_REF_PREFIX = "#/components/schemas/"


_OPENAPI_COMPONENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "AboutKind": {
        "type": "string",
        "enum": ["person", "location", "item", "topic", "other"],
    },
    "ResolvedAboutInput": {
        "type": "object",
        "required": ["kind", "ref"],
        "additionalProperties": False,
        "properties": {
            "kind": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutKind"},
            "ref": {
                "type": "object",
                "required": ["collection", "key"],
                "additionalProperties": False,
                "properties": {
                    "collection": {"type": "string", "minLength": 1},
                    "key": {"type": "string", "minLength": 1},
                },
            },
        },
    },
    "PendingAboutInput": {
        "type": "object",
        "required": ["kind", "label"],
        "additionalProperties": False,
        "properties": {
            "kind": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutKind"},
            "label": {"type": "string", "minLength": 1},
        },
    },
    "AboutInput": {
        "oneOf": [
            {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}ResolvedAboutInput"},
            {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}PendingAboutInput"},
        ],
    },
    "CreateNoteRequest": {
        "type": "object",
        "required": ["content"],
        "additionalProperties": False,
        "properties": {
            "content": {
                "type": "string",
                "minLength": 1,
                "description": "The full note text to store.",
            },
            "about": {
                "type": "array",
                "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutInput"},
                "default": [],
            },
            "observed_at": {
                "type": "string",
                "format": "date-time",
                "description": (
                    "When the fact was observed. Must include time and timezone."
                ),
            },
            "source_channel": {
                "type": "string",
                "minLength": 1,
                "description": "Optional provenance channel, e.g. chat or email.",
            },
        },
    },
    "PatchNoteRequest": {
        "type": "object",
        "required": ["version"],
        "additionalProperties": False,
        "properties": {
            "version": {
                "type": "integer",
                "minimum": 1,
                "description": "Latest note version observed by the client.",
            },
            "addendum": {
                "type": "string",
                "minLength": 1,
                "description": "Text appended to the existing note content.",
            },
            "add_about": {
                "type": "array",
                "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutInput"},
                "default": [],
            },
            "observed_at": {
                "type": "string",
                "format": "date-time",
                "description": (
                    "Replacement observed timestamp for the new version. "
                    "Must include timezone."
                ),
            },
        },
        "anyOf": [
            {
                "required": ["addendum"],
                "properties": {"addendum": {"type": "string", "minLength": 1}},
            },
            {
                "required": ["add_about"],
                "properties": {
                    "add_about": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutInput"},
                    }
                },
            },
            {"required": ["observed_at"]},
        ],
    },
    "ResolvedAboutView": {
        "type": "object",
        "required": ["kind", "collection", "key"],
        "additionalProperties": False,
        "properties": {
            "kind": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutKind"},
            "collection": {"type": "string"},
            "key": {"type": "string"},
        },
    },
    "PendingAboutView": {
        "type": "object",
        "required": ["kind", "label"],
        "additionalProperties": False,
        "properties": {
            "kind": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}AboutKind"},
            "label": {"type": "string"},
        },
    },
    "NoteView": {
        "type": "object",
        "required": [
            "note_id",
            "version",
            "content",
            "observed_at",
            "created_at",
            "resolved_about",
            "pending_about",
        ],
        "additionalProperties": False,
        "properties": {
            "note_id": {"type": "string", "pattern": "^note_[0-9]+$"},
            "version": {"type": "integer", "minimum": 1},
            "content": {"type": "string"},
            "observed_at": {"type": "string", "format": "date-time"},
            "created_at": {"type": "string", "format": "date-time"},
            "resolved_about": {
                "type": "array",
                "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}ResolvedAboutView"},
            },
            "pending_about": {
                "type": "array",
                "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}PendingAboutView"},
            },
        },
    },
    "NoteSearchResultView": {
        "type": "object",
        "required": ["note_id", "version", "content_preview", "observed_at", "score"],
        "additionalProperties": False,
        "properties": {
            "note_id": {"type": "string", "pattern": "^note_[0-9]+$"},
            "version": {"type": "integer", "minimum": 1},
            "content_preview": {"type": "string"},
            "observed_at": {"type": "string", "format": "date-time"},
            "score": {"type": "number"},
        },
    },
    "NoteContextView": {
        "type": "object",
        "required": ["note", "basis", "related_notes"],
        "additionalProperties": False,
        "properties": {
            "note": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}NoteView"},
            "basis": {
                "type": "object",
                "required": ["resolved_about", "pending_about"],
                "additionalProperties": False,
                "properties": {
                    "resolved_about": {
                        "type": "array",
                        "items": {
                            "$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}ResolvedAboutView"
                        },
                    },
                    "pending_about": {
                        "type": "array",
                        "items": {
                            "$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}PendingAboutView"
                        },
                    },
                },
            },
            "related_notes": {
                "type": "array",
                "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}NoteSearchResultView"},
            },
        },
    },
    "ErrorDetail": {
        "type": "object",
        "required": ["message", "code"],
        "additionalProperties": False,
        "properties": {
            "field": {"type": "string"},
            "message": {"type": "string"},
            "code": {"type": "string"},
            "context": {"type": "object"},
        },
    },
    "ErrorResponse": {
        "type": "object",
        "required": ["error", "details", "request_id"],
        "additionalProperties": False,
        "properties": {
            "error": {
                "type": "string",
                "enum": [
                    "invalid_note_request",
                    "invalid_note_patch",
                    "note_not_found",
                    "version_conflict",
                ],
            },
            "details": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}ErrorDetail"},
            },
            "request_id": {"type": ["string", "null"], "default": None},
        },
    },
}


def _install_openapi_schema(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        component_schemas = schema.setdefault("components", {}).setdefault(
            "schemas",
            {},
        )
        component_schemas.update(_OPENAPI_COMPONENT_SCHEMAS)
        _patch_note_endpoint_openapi(schema)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi


def _patch_note_endpoint_openapi(schema: dict[str, Any]) -> None:
    paths = schema.setdefault("paths", {})
    note_collection = paths.setdefault("/notes", {})
    note_member = paths.setdefault("/notes/{note_id}", {})
    note_context = paths.setdefault("/notes/{note_id}/context", {})

    _set_request_body(note_collection.setdefault("post", {}), "CreateNoteRequest")
    _set_response(note_collection["post"], "201", "Created", "NoteView")
    _set_response(note_collection["post"], "400", "Bad Request", "ErrorResponse")

    _set_response(note_collection.setdefault("get", {}), "200", "OK", None)
    note_collection["get"]["responses"]["200"]["content"] = {
        "application/json": {
            "schema": {
                "type": "array",
                "items": {
                    "$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}NoteSearchResultView"
                },
            }
        }
    }
    _set_response(note_collection["get"], "400", "Bad Request", "ErrorResponse")

    _set_response(note_member.setdefault("get", {}), "200", "OK", "NoteView")
    _set_response(note_member["get"], "404", "Not Found", "ErrorResponse")

    _set_request_body(note_member.setdefault("patch", {}), "PatchNoteRequest")
    _set_response(note_member["patch"], "200", "OK", "NoteView")
    _set_response(note_member["patch"], "400", "Bad Request", "ErrorResponse")
    _set_response(note_member["patch"], "404", "Not Found", "ErrorResponse")
    _set_response(note_member["patch"], "409", "Conflict", "ErrorResponse")

    _set_response(note_context.setdefault("get", {}), "200", "OK", "NoteContextView")
    _set_response(note_context["get"], "404", "Not Found", "ErrorResponse")


def _set_request_body(operation: dict[str, Any], schema_name: str) -> None:
    operation["requestBody"] = {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}{schema_name}"}
            }
        },
    }


def _set_response(
    operation: dict[str, Any],
    status_code: str,
    description: str,
    schema_name: str | None,
) -> None:
    responses = operation.setdefault("responses", {})
    response: dict[str, Any] = {"description": description}
    if schema_name is not None:
        response["content"] = {
            "application/json": {
                "schema": {"$ref": f"{_OPENAPI_SCHEMA_REF_PREFIX}{schema_name}"}
            }
        }
    responses[status_code] = response


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
    if isinstance(addendum, str) and not addendum.strip():
        raise InvalidNoteRequestError(
            error="invalid_note_patch",
            field="addendum",
            message="Addendum must be a non-empty string when provided.",
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
        raise InvalidNoteRequestError(
            error=error,
            field=field,
            message=f"{field} must include a timezone offset.",
        )
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
