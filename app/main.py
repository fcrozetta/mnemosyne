from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.dependencies import (
    get_access_audit_service,
    get_observations_service,
    get_settings,
)
from app.models.access import (
    AccessContext,
    Domain,
    ProjectionName,
    Purpose,
    Sensitivity,
)
from app.models.observations import (
    CreateObservationInput,
    EntityMentionInput,
    EntityType,
    InvalidObservationPatchError,
    InvalidObservationRequestError,
    MentionedEntity,
    Observation,
    ObservationContext,
    ObservationNotFoundError,
    ObservationSearchResult,
    ObservationType,
    PatchObservationInput,
    Source,
    SourceInput,
    SourceType,
)
from app.service.access_policy import AccessPolicy, PolicyDecision
from app.service.observations import ObservationsService
from app.service.projections import ProjectionService
from app.settings import MnemosyneSettings


def create_app() -> FastAPI:
    app = FastAPI(title="Mnemosyne", version="0.1.0-alpha")

    @app.exception_handler(ObservationNotFoundError)
    def handle_observation_not_found(
        _request: object,
        exc: ObservationNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_response(
                error="observation_not_found",
                field="id",
                message="Observation was not found.",
                code="observation_not_found",
                context={"id": exc.id},
            ),
        )

    @app.exception_handler(InvalidObservationPatchError)
    def handle_invalid_observation_patch(
        _request: object,
        exc: InvalidObservationPatchError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_response(
                error="invalid_observation_patch",
                field=None,
                message=str(exc),
                code="invalid_observation_patch",
                context=None,
            ),
        )

    @app.exception_handler(InvalidObservationRequestError)
    def handle_invalid_observation_request(
        _request: object,
        exc: InvalidObservationRequestError,
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
        error = "invalid_observation_request"
        body_message = "Request body is required."
        if (
            request.method == "PATCH"
            and request.url.path.startswith("/observations/")
        ):
            error = "invalid_observation_patch"
            body_message = "Patch body is required."

        details = [
            {
                "message": _validation_error_message(issue, body_message),
                "code": error,
            }
            for issue in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": error,
                "details": details,
                "request_id": None,
            },
        )

    @app.get("/healthz")
    def healthz(
        response: Response,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
    ) -> dict[str, bool]:
        initialized = service.storage_initialized()
        if not initialized:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "ok": initialized,
            "storage_initialized": initialized,
        }

    @app.post("/observations", status_code=status.HTTP_201_CREATED)
    def create_observation(
        request: Request,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        body: Any = Body(...),
    ) -> dict[str, Any]:
        observation = service.create_observation(_parse_create_observation_input(body))
        return _serialize_observation(
            observation,
            include_classification=_metadata_response_enabled(request),
        )

    @app.get("/observations")
    def search_observations(
        request: Request,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        q: str = "",
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search current observation revisions with lexical scoring.

        `q` is stripped and casefolded, then matched against the casefolded
        latest revision content. A full-query substring match scores `1.0`;
        otherwise the query is split on whitespace and the score is the
        fraction of query terms present in the content. Results with score
        `0` are omitted and matches sort by `updated_at` descending. Scores are
        query-relative, not globally calibrated.
        """
        if not q.strip():
            raise InvalidObservationRequestError(
                error="invalid_observation_request",
                field="q",
                message="Query parameter q must be non-empty.",
            )
        if not 1 <= limit <= 50:
            raise InvalidObservationRequestError(
                error="invalid_observation_request",
                field="limit",
                message="Limit must be between 1 and 50.",
            )
        return _serialize_search_response(
            request,
            service,
            service.search_observations(q, limit=limit),
        )

    @app.get("/topics/{topic}/observations")
    def recent_observations_by_topic(
        request: Request,
        topic: str,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not topic.strip():
            raise InvalidObservationRequestError(
                error="invalid_observation_request",
                field="topic",
                message="Topic path parameter must be non-empty.",
            )
        if not 1 <= limit <= 50:
            raise InvalidObservationRequestError(
                error="invalid_observation_request",
                field="limit",
                message="Limit must be between 1 and 50.",
            )
        return _serialize_search_response(
            request,
            service,
            service.recent_observations_by_topic(topic, limit=limit),
        )

    @app.get("/observations/{id}")
    def get_observation(
        request: Request,
        id: str,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
    ) -> dict[str, Any]:
        return _observation_response(request, service.get_observation(id))

    @app.patch("/observations/{id}")
    def patch_observation(
        id: str,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        body: Any = Body(...),
    ) -> dict[str, Any]:
        return _serialize_observation(
            service.patch_observation(
                id,
                _parse_patch_observation_input(body),
            )
        )

    @app.get("/observations/{id}/context")
    def get_observation_context(
        request: Request,
        id: str,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
    ) -> dict[str, Any]:
        return _serialize_observation_context(
            request,
            service,
            service.get_observation_context(id),
        )

    return app


def _parse_create_observation_input(body: Any) -> CreateObservationInput:
    data = _object_body(body, error="invalid_observation_request")
    content = _required_non_empty_string(
        data,
        "content",
        error="invalid_observation_request",
    )
    observation_type = _parse_observation_type(
        data.get("type", ObservationType.NOTE.value),
        error="invalid_observation_request",
        field="type",
    )
    return CreateObservationInput(
        type=observation_type,
        content=content,
        mentions=(
            *_parse_mentions(
                data.get("mentions", ()),
                error="invalid_observation_request",
                field="mentions",
            ),
            *_parse_topics(
                data.get("topics", ()),
                error="invalid_observation_request",
                field="topics",
            ),
        ),
        observed_at=_parse_optional_datetime(
            data.get("observed_at"),
            error="invalid_observation_request",
            field="observed_at",
        ),
        source=_parse_optional_source(
            data.get("source"),
            error="invalid_observation_request",
            field="source",
        ),
        domain=_parse_domain(
            data.get("domain", Domain.GENERAL.value),
            error="invalid_observation_request",
            field="domain",
        ),
        sensitivity=_parse_sensitivity(
            data.get("sensitivity", Sensitivity.PERSONAL.value),
            error="invalid_observation_request",
            field="sensitivity",
        ),
        subject=_optional_string(
            data.get("subject"),
            field="subject",
            error="invalid_observation_request",
        ),
        allowed_purposes=_parse_purposes(
            data.get("allowed_purposes", ()),
            error="invalid_observation_request",
            field="allowed_purposes",
        ),
    )


def _parse_patch_observation_input(body: Any) -> PatchObservationInput:
    data = _object_body(body, error="invalid_observation_patch")
    if "version" in data:
        raise InvalidObservationRequestError(
            error="invalid_observation_patch",
            field="version",
            message="version is assigned internally and must not be provided.",
        )
    addendum = data.get("addendum")
    if addendum is not None:
        if not isinstance(addendum, str):
            raise InvalidObservationRequestError(
                error="invalid_observation_patch",
                field="addendum",
                message="addendum must be a string.",
            )
        addendum = addendum.strip()
        if not addendum:
            raise InvalidObservationRequestError(
                error="invalid_observation_patch",
                field="addendum",
                message="addendum must be non-empty.",
            )
    mentions = (
        *_parse_mentions(
            data.get("mentions", ()),
            error="invalid_observation_patch",
            field="mentions",
        ),
        *_parse_topics(
            data.get("topics", ()),
            error="invalid_observation_patch",
            field="topics",
        ),
    )
    observed_at = _parse_optional_datetime(
        data.get("observed_at"),
        error="invalid_observation_patch",
        field="observed_at",
    )
    if addendum is None and not mentions and observed_at is None:
        raise InvalidObservationPatchError(
            "Patch request must include at least one change."
        )
    return PatchObservationInput(
        addendum=addendum,
        mentions=mentions,
        observed_at=observed_at,
    )


def _object_body(body: Any, *, error: str) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise InvalidObservationRequestError(
            error=error,
            field=None,
            message="Request body must be an object.",
        )
    return body


def _required_non_empty_string(
    data: dict[str, Any],
    field: str,
    *,
    error: str,
) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be a non-empty string.",
        )
    return value


def _parse_observation_type(
    value: Any,
    *,
    error: str,
    field: str,
) -> ObservationType:
    try:
        return ObservationType(str(value))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="type must be one of: note, document, message.",
        ) from exc


def _parse_domain(value: Any, *, error: str, field: str) -> Domain:
    try:
        return Domain(str(value))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="domain must be a supported domain value.",
        ) from exc


def _parse_sensitivity(value: Any, *, error: str, field: str) -> Sensitivity:
    try:
        return Sensitivity(str(value))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="sensitivity must be a supported sensitivity value.",
        ) from exc


def _parse_purpose(value: Any, *, error: str, field: str) -> Purpose:
    try:
        return Purpose(str(value))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="purpose must be a supported purpose value.",
        ) from exc


def _parse_projection(value: Any, *, error: str, field: str) -> ProjectionName:
    try:
        return ProjectionName(str(value))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="projection must be a supported projection value.",
        ) from exc


def _parse_purposes(value: Any, *, error: str, field: str) -> tuple[Purpose, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be a list.",
        )
    return tuple(_parse_purpose(item, error=error, field=field) for item in value)


def _parse_mentions(
    value: Any,
    *,
    error: str,
    field: str,
) -> tuple[EntityMentionInput, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be a list.",
        )
    return tuple(_parse_mention(item, error=error, field=field) for item in value)


def _parse_topics(
    value: Any,
    *,
    error: str,
    field: str,
) -> tuple[EntityMentionInput, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be a list.",
        )

    topics: list[EntityMentionInput] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InvalidObservationRequestError(
                error=error,
                field=field,
                message="Each topic must be a non-empty string.",
            )
        topics.append(EntityMentionInput(type=EntityType.TOPIC, label=item.strip()))
    return tuple(topics)


def _parse_mention(
    item: Any,
    *,
    error: str,
    field: str,
) -> EntityMentionInput:
    if not isinstance(item, dict):
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="Each mention must be an object.",
        )
    label = _required_non_empty_string(item, "label", error=error)
    try:
        entity_type = EntityType(str(item.get("type")))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=f"{field}.type",
            message=(
                "mention type must be one of: person, location, item, topic, "
                "other."
            ),
        ) from exc
    return EntityMentionInput(type=entity_type, label=label)


def _parse_optional_source(
    value: Any,
    *,
    error: str,
    field: str,
) -> SourceInput | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message="source must be an object.",
        )
    try:
        source_type = SourceType(str(value.get("source_type", SourceType.AGENT.value)))
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=f"{field}.source_type",
            message=(
                "source_type must be one of: user, agent, import, integration, system."
            ),
        ) from exc
    return SourceInput(
        source_type=source_type,
        label=_optional_string(value.get("label"), field=f"{field}.label", error=error),
        source_ref=_optional_string(
            value.get("source_ref"),
            field=f"{field}.source_ref",
            error=error,
        ),
        writer=_optional_string(
            value.get("writer"),
            field=f"{field}.writer",
            error=error,
        ),
        session_id=_optional_string(
            value.get("session_id"),
            field=f"{field}.session_id",
            error=error,
        ),
        observed_channel=_optional_string(
            value.get("observed_channel"),
            field=f"{field}.observed_channel",
            error=error,
        ),
    )


def _optional_string(value: Any, *, field: str, error: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be a non-empty string when provided.",
        )
    return value


def _parse_optional_datetime(
    value: Any,
    *,
    error: str,
    field: str,
) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be an ISO 8601 datetime string.",
        )
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must be an ISO 8601 datetime string.",
        ) from exc
    if parsed.tzinfo is None:
        raise InvalidObservationRequestError(
            error=error,
            field=field,
            message=f"{field} must include timezone.",
        )
    return parsed


def _observation_response(request: Request, observation: Observation) -> dict[str, Any]:
    settings = get_settings()
    if not _use_access_pipeline(settings, request):
        return _serialize_observation(observation)

    context = _access_context_from_request(request, settings)
    decision = _authorize_observation(context, observation)
    _audit_decision(settings, context, "observation", observation.id, decision)
    if not decision.allowed:
        _raise_access_denied(decision)
    if settings.safe_projections_enabled:
        return ProjectionService().project_observation(context, observation, decision)
    return _serialize_observation(observation, include_classification=True)


def _serialize_search_response(
    request: Request,
    service: ObservationsService,
    results: tuple[ObservationSearchResult, ...],
) -> list[dict[str, Any]]:
    settings = get_settings()
    if not _use_access_pipeline(settings, request):
        return [_serialize_search_result(result) for result in results]

    context = _access_context_from_request(request, settings)
    _require_query_allowed(context)
    items: list[dict[str, Any]] = []
    for result in results:
        observation = service.get_observation(result.id)
        decision = AccessPolicy().can_disclose_revision(
            context,
            _latest_revision(observation),
        )
        _audit_decision(settings, context, "observation", observation.id, decision)
        if not decision.allowed:
            continue
        if settings.safe_projections_enabled:
            items.append(
                ProjectionService().project_observation(
                    context, observation, decision
                )
            )
        else:
            items.append(_serialize_search_result(result))
    return items


def _use_access_pipeline(settings: MnemosyneSettings, request: Request) -> bool:
    if not (settings.domain_policy_enabled or settings.safe_projections_enabled):
        return False
    if not settings.access_context_headers_enabled:
        return False
    return any(key.lower().startswith("x-mnemosyne-") for key in request.headers)


def _metadata_response_enabled(request: Request) -> bool:
    settings = get_settings()
    return settings.domain_policy_enabled and _use_access_pipeline(settings, request)


def _access_context_from_request(
    request: Request,
    settings: MnemosyneSettings,
) -> AccessContext:
    if not settings.access_context_headers_enabled:
        return AccessContext()
    return AccessContext(
        actor_user=_optional_header(request, "x-mnemosyne-actor-user"),
        client_app=_header_or_default(request, "x-mnemosyne-client-app", "unknown"),
        service_identity=_header_or_default(
            request,
            "x-mnemosyne-service-identity",
            "unknown",
        ),
        purpose=_parse_purpose(
            request.headers.get("x-mnemosyne-purpose", Purpose.RECALL.value),
            error="invalid_access_context",
            field="x-mnemosyne-purpose",
        ),
        scopes=frozenset(_split_header_values(request.headers.get("x-mnemosyne-scopes"))),
        roles=frozenset(_split_header_values(request.headers.get("x-mnemosyne-roles"))),
        requested_projection=_parse_projection(
            request.headers.get(
                "x-mnemosyne-projection",
                ProjectionName.OBSERVATION_SUMMARY.value,
            ),
            error="invalid_access_context",
            field="x-mnemosyne-projection",
        ),
    )


def _optional_header(request: Request, name: str) -> str | None:
    value = request.headers.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _header_or_default(request: Request, name: str, default: str) -> str:
    return _optional_header(request, name) or default


def _split_header_values(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item for item in value.replace(",", " ").split() if item)


def _authorize_observation(
    context: AccessContext,
    observation: Observation,
) -> PolicyDecision:
    _require_query_allowed(context)
    return AccessPolicy().can_disclose_revision(context, _latest_revision(observation))


def _require_query_allowed(context: AccessContext) -> None:
    decision = AccessPolicy().can_query_mnemosyne(context)
    if not decision.allowed:
        _raise_access_denied(decision)


def _latest_revision(observation: Observation):
    latest = observation.latest_revision
    if latest is None:
        raise ObservationNotFoundError(observation.id)
    return latest


def _audit_decision(
    settings: MnemosyneSettings,
    context: AccessContext,
    resource_type: str,
    resource_id: str,
    decision: PolicyDecision,
) -> None:
    if not settings.access_audit_enabled:
        return
    audit = get_access_audit_service()
    audit.record(
        context=context,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=decision,
    )


def _raise_access_denied(decision: PolicyDecision) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "access_denied", "reason_code": decision.reason_code},
    )


def _serialize_observation(
    observation: Observation,
    *,
    include_classification: bool = False,
) -> dict[str, Any]:
    latest = observation.latest_revision
    if latest is None:
        raise ObservationNotFoundError(observation.id)
    payload = {
        "id": observation.id,
        "type": observation.type.value,
        "version": latest.version,
        "current_revision": latest.id,
        "content": latest.content,
        "content_format": latest.content_format,
        "observed_at": _format_datetime(latest.observed_at),
        "created_at": _format_datetime(observation.created_at),
        "updated_at": _format_datetime(observation.updated_at),
        "mentions": [_serialize_mention(mention) for mention in latest.mentions],
        "source": _serialize_source(latest.source),
    }
    if include_classification:
        payload.update(
            {
                "domain": latest.domain.value,
                "sensitivity": latest.sensitivity.value,
                "subject": latest.subject,
                "allowed_purposes": [
                    purpose.value for purpose in latest.allowed_purposes
                ],
            }
        )
    return payload


def _serialize_mention(mention: MentionedEntity) -> dict[str, Any]:
    return {
        "id": mention.id,
        "type": mention.type.value,
        "label": mention.label,
        "resolution_status": mention.resolution_status.value,
    }


def _serialize_source(source: Source | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "id": source.id,
        "source_type": source.source_type.value,
        "label": source.label,
        "source_ref": source.source_ref,
    }


def _serialize_search_result(result: ObservationSearchResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "type": result.type.value,
        "version": result.version,
        "content_preview": result.content_preview,
        "observed_at": _format_datetime(result.observed_at),
        "updated_at": _format_datetime(result.updated_at),
        "score": result.score,
    }


def _serialize_observation_context(
    request: Request,
    service: ObservationsService,
    context: ObservationContext,
) -> dict[str, Any]:
    settings = get_settings()
    if not _use_access_pipeline(settings, request):
        return {
            "observation": _serialize_observation(context.observation),
            "related_observations": [
                _serialize_search_result(result)
                for result in context.related_observations
            ],
        }

    anchor = _observation_response(request, context.observation)
    return {
        "observation": anchor,
        "related_observations": _serialize_search_response(
            request,
            service,
            context.related_observations,
        ),
    }


def _format_datetime(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _validation_error_message(issue: dict[str, Any], body_message: str) -> str:
    location = issue.get("loc", ())
    if tuple(location) == ("body",):
        return body_message
    return str(issue.get("msg", "Request validation failed."))


def _error_response(
    *,
    error: str,
    field: str | None,
    message: str,
    code: str,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        **({"field": field} if field is not None else {}),
        "message": message,
        "code": code,
        **({"context": context} if context is not None else {}),
    }
    return {
        "error": error,
        "details": [detail],
        "request_id": None,
    }


app = create_app()


__all__ = ["app", "create_app"]
