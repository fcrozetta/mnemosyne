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
from app.models.entities import (
    AnimalProfile,
    AnimalProfileInput,
    ContactMethod,
    ContactMethodInput,
    ContactMethodKind,
    CreateEntityInput,
    EntityNotFoundError,
    EntityRecord,
    InvalidEntityRequestError,
    ItemProfile,
    ItemProfileInput,
    LocationProfile,
    LocationProfileInput,
    PersonProfile,
    PersonProfileInput,
    StoreProfile,
    StoreProfileInput,
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

    @app.exception_handler(EntityNotFoundError)
    def handle_entity_not_found(
        _request: object,
        exc: EntityNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_response(
                error="entity_not_found",
                field="id",
                message="Entity was not found.",
                code="entity_not_found",
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

    @app.exception_handler(InvalidEntityRequestError)
    def handle_invalid_entity_request(
        _request: object,
        exc: InvalidEntityRequestError,
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
        if request.method == "PATCH" and request.url.path.startswith("/observations/"):
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

    @app.post("/entities", status_code=status.HTTP_201_CREATED)
    def create_entity(
        request: Request,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        body: Any = Body(...),
    ) -> dict[str, Any]:
        entity_input = _parse_create_entity_input(body)
        settings = get_settings()
        if _use_access_pipeline(settings, request):
            context = _access_context_from_request(request, settings)
            mutation_decision = AccessPolicy().can_mutate_entity(context, entity_input)
            if not mutation_decision.allowed:
                _audit_decision(
                    settings,
                    context,
                    "entity_mutation",
                    entity_input.normalized_label,
                    mutation_decision,
                )
                _raise_access_denied(mutation_decision)
            decision = AccessPolicy().can_disclose_new_entity(context, entity_input)
            if not decision.allowed:
                _audit_decision(
                    settings,
                    context,
                    "entity",
                    entity_input.normalized_label,
                    decision,
                )
                _raise_access_denied(decision)
            entity = service.create_entity(entity_input)
            _audit_decision(
                settings,
                context,
                "entity_mutation",
                entity.id,
                mutation_decision,
            )
            _audit_decision(settings, context, "entity", entity.id, decision)
            if not decision.allowed:
                _raise_access_denied(decision)
            return _serialize_entity(
                entity,
                redacted=decision.redacted,
                expose_restricted_fields=_can_read_restricted_fields(context),
            )
        entity = service.create_entity(entity_input)
        return _serialize_entity(entity)

    @app.get("/entities")
    def list_entities(
        request: Request,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        type: str | None = None,
        scope: str | None = None,
        q: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise InvalidEntityRequestError(
                error="invalid_entity_request",
                field="limit",
                message="Limit must be between 1 and 100.",
            )
        entity_type = _parse_optional_entity_filter(type)
        return _serialize_entity_list_response(
            request,
            service.list_entities(
                entity_type=entity_type,
                scope=scope.strip() if scope and scope.strip() else None,
                query=q,
                limit=limit,
            ),
        )

    @app.get("/entities/{id}")
    def get_entity(
        request: Request,
        id: str,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
    ) -> dict[str, Any]:
        return _entity_response(request, service.get_entity(id))

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
        request: Request,
        id: str,
        service: Annotated[
            ObservationsService,
            Depends(get_observations_service),
        ],
        body: Any = Body(...),
    ) -> dict[str, Any]:
        patch_input = _parse_patch_observation_input(body)
        settings = get_settings()
        if not _use_access_pipeline(settings, request):
            return _serialize_observation(service.patch_observation(id, patch_input))

        context = _access_context_from_request(request, settings)
        current = service.get_observation(id)
        mutation_decision = AccessPolicy().can_mutate_observation(
            context,
            _latest_revision(current),
        )
        _audit_decision(
            settings,
            context,
            "observation_mutation",
            id,
            mutation_decision,
        )
        if not mutation_decision.allowed:
            _raise_access_denied(mutation_decision)

        disclosure_decision = _authorize_observation(context, current)
        _audit_decision(settings, context, "observation", id, disclosure_decision)
        if not disclosure_decision.allowed:
            _raise_access_denied(disclosure_decision)

        updated = service.patch_observation(id, patch_input)
        updated_decision = _authorize_observation(context, updated)
        _audit_decision(settings, context, "observation", id, updated_decision)
        if not updated_decision.allowed:
            _raise_access_denied(updated_decision)
        return _serialize_authorized_observation(
            settings,
            context,
            updated,
            updated_decision,
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


def _parse_create_entity_input(body: Any) -> CreateEntityInput:
    data = _entity_object_body(body)
    label = _required_entity_string(data, "label")
    entity_type = _parse_entity_type_for_registry(data.get("type"))
    scope = _optional_entity_string(data.get("scope"), "scope") or "personal"
    person = _parse_person_profile(data.get("person"), entity_type)
    location = _parse_location_profile(data.get("location"), entity_type)
    store = _parse_store_profile(data.get("store"), entity_type)
    item = _parse_item_profile(data.get("item"), entity_type)
    animal = _parse_animal_profile(data.get("animal"), entity_type)
    return CreateEntityInput(
        type=entity_type,
        label=label,
        scope=scope,
        sensitivity=_parse_entity_sensitivity(
            data.get("sensitivity", data.get("secrecy", Sensitivity.PERSONAL.value)),
            "sensitivity",
        ),
        allowed_purposes=_parse_entity_purposes(data.get("allowed_purposes", ())),
        person=person,
        location=location,
        store=store,
        item=item,
        animal=animal,
    )


def _parse_optional_entity_filter(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _parse_entity_type_for_registry(value).value


def _entity_object_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field=None,
            message="Request body must be an object.",
        )
    return body


def _required_entity_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field=field,
            message=f"{field} must be a non-empty string.",
        )
    return value.strip()


def _optional_entity_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field=field,
            message=f"{field} must be a non-empty string when provided.",
        )
    return value.strip()


def _parse_entity_type_for_registry(value: Any) -> EntityType:
    supported = {
        EntityType.PERSON,
        EntityType.LOCATION,
        EntityType.STORE,
        EntityType.ITEM,
        EntityType.ANIMAL,
    }
    try:
        entity_type = EntityType(str(value))
    except ValueError as exc:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="type",
            message="type must be one of: person, location, store, item, animal.",
        ) from exc
    if entity_type not in supported:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="type",
            message="type must be one of: person, location, store, item, animal.",
        )
    return entity_type


def _parse_entity_sensitivity(value: Any, field: str) -> Sensitivity:
    try:
        return Sensitivity(str(value))
    except ValueError as exc:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field=field,
            message="sensitivity must be a supported sensitivity value.",
        ) from exc


def _parse_entity_purpose(value: Any) -> Purpose:
    try:
        return Purpose(str(value))
    except ValueError as exc:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="allowed_purposes",
            message="allowed_purposes must contain supported purpose values.",
        ) from exc


def _parse_entity_purposes(value: Any) -> tuple[Purpose, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="allowed_purposes",
            message="allowed_purposes must be a list.",
        )
    return tuple(_parse_entity_purpose(item) for item in value)


def _parse_person_profile(
    value: Any, entity_type: EntityType
) -> PersonProfileInput | None:
    if value is None:
        if entity_type == EntityType.PERSON:
            return PersonProfileInput()
        return None
    if entity_type != EntityType.PERSON:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="person",
            message="person profile is only valid for person entities.",
        )
    if not isinstance(value, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="person",
            message="person must be an object.",
        )
    return PersonProfileInput(
        display_name=_optional_entity_string(
            value.get("display_name"), "person.display_name"
        ),
        given_name=_optional_entity_string(
            value.get("given_name"), "person.given_name"
        ),
        family_name=_optional_entity_string(
            value.get("family_name"), "person.family_name"
        ),
        contact_methods=_parse_contact_methods(value.get("contact_methods", ())),
    )


def _parse_contact_methods(value: Any) -> tuple[ContactMethodInput, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="person.contact_methods",
            message="person.contact_methods must be a list.",
        )
    return tuple(_parse_contact_method(item) for item in value)


def _parse_contact_method(item: Any) -> ContactMethodInput:
    if not isinstance(item, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="person.contact_methods",
            message="Each contact method must be an object.",
        )
    try:
        kind = ContactMethodKind(str(item.get("kind")))
    except ValueError as exc:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="person.contact_methods.kind",
            message=(
                "contact method kind must be one of: phone, email, url, handle, other."
            ),
        ) from exc
    return ContactMethodInput(
        kind=kind,
        value=_required_entity_string(item, "value"),
        label=_optional_entity_string(
            item.get("label"), "person.contact_methods.label"
        ),
        sensitivity=_parse_entity_sensitivity(
            item.get("sensitivity", Sensitivity.PERSONAL.value),
            "person.contact_methods.sensitivity",
        ),
    )


def _parse_location_profile(
    value: Any,
    entity_type: EntityType,
) -> LocationProfileInput | None:
    if value is None:
        if entity_type == EntityType.LOCATION:
            return LocationProfileInput()
        return None
    if entity_type != EntityType.LOCATION:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="location",
            message="location profile is only valid for location entities.",
        )
    if not isinstance(value, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="location",
            message="location must be an object.",
        )
    return LocationProfileInput(
        location_kind=_optional_entity_string(
            value.get("location_kind"), "location.location_kind"
        ),
        street_address=_optional_entity_string(
            value.get("street_address"), "location.street_address"
        ),
        postal_code=_optional_entity_string(
            value.get("postal_code"), "location.postal_code"
        ),
        locality=_optional_entity_string(value.get("locality"), "location.locality"),
        region=_optional_entity_string(value.get("region"), "location.region"),
        country=_optional_entity_string(value.get("country"), "location.country"),
        latitude=_optional_float(value.get("latitude"), "location.latitude"),
        longitude=_optional_float(value.get("longitude"), "location.longitude"),
    )


def _parse_store_profile(
    value: Any, entity_type: EntityType
) -> StoreProfileInput | None:
    if value is None:
        if entity_type == EntityType.STORE:
            return StoreProfileInput()
        return None
    if entity_type != EntityType.STORE:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="store",
            message="store profile is only valid for store entities.",
        )
    if not isinstance(value, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="store",
            message="store must be an object.",
        )
    return StoreProfileInput(
        store_kind=_optional_entity_string(value.get("store_kind"), "store.store_kind"),
        website=_optional_entity_string(value.get("website"), "store.website"),
        categories=_parse_string_list(value.get("categories", ()), "store.categories"),
        country_scope=_optional_entity_string(
            value.get("country_scope"), "store.country_scope"
        ),
        physical_store_status=_optional_entity_string(
            value.get("physical_store_status"), "store.physical_store_status"
        ),
        source_urls=_parse_string_list(
            value.get("source_urls", ()), "store.source_urls"
        ),
        reference_notes=_optional_entity_string(
            value.get("reference_notes"), "store.reference_notes"
        ),
    )


def _parse_item_profile(value: Any, entity_type: EntityType) -> ItemProfileInput | None:
    if value is None:
        if entity_type == EntityType.ITEM:
            return ItemProfileInput()
        return None
    if entity_type != EntityType.ITEM:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="item",
            message="item profile is only valid for item entities.",
        )
    if not isinstance(value, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="item",
            message="item must be an object.",
        )
    return ItemProfileInput(
        item_kind=_optional_entity_string(value.get("item_kind"), "item.item_kind"),
        category=_optional_entity_string(value.get("category"), "item.category"),
        subcategory=_optional_entity_string(
            value.get("subcategory"), "item.subcategory"
        ),
        brand=_optional_entity_string(value.get("brand"), "item.brand"),
        model=_optional_entity_string(value.get("model"), "item.model"),
        variant=_optional_entity_string(value.get("variant"), "item.variant"),
        color=_optional_entity_string(value.get("color"), "item.color"),
        size=_optional_entity_string(value.get("size"), "item.size"),
        serial_number=_optional_entity_string(
            value.get("serial_number"), "item.serial_number"
        ),
        identifiers=_parse_string_list(
            value.get("identifiers", ()), "item.identifiers"
        ),
    )


def _parse_animal_profile(
    value: Any,
    entity_type: EntityType,
) -> AnimalProfileInput | None:
    if value is None:
        if entity_type == EntityType.ANIMAL:
            return AnimalProfileInput()
        return None
    if entity_type != EntityType.ANIMAL:
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="animal",
            message="animal profile is only valid for animal entities.",
        )
    if not isinstance(value, dict):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field="animal",
            message="animal must be an object.",
        )
    return AnimalProfileInput(
        animal_kind=_optional_entity_string(
            value.get("animal_kind"), "animal.animal_kind"
        ),
        species=_optional_entity_string(value.get("species"), "animal.species"),
        breed=_optional_entity_string(value.get("breed"), "animal.breed"),
        sex=_optional_entity_string(value.get("sex"), "animal.sex"),
        color=_optional_entity_string(value.get("color"), "animal.color"),
        date_of_birth=_optional_entity_string(
            value.get("date_of_birth"), "animal.date_of_birth"
        ),
        microchip_id=_optional_entity_string(
            value.get("microchip_id"), "animal.microchip_id"
        ),
        identifiers=_parse_string_list(
            value.get("identifiers", ()), "animal.identifiers"
        ),
        reference_notes=_optional_entity_string(
            value.get("reference_notes"), "animal.reference_notes"
        ),
    )


def _parse_string_list(value: Any, field: str) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field=field,
            message=f"{field} must be a list.",
        )
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InvalidEntityRequestError(
                error="invalid_entity_request",
                field=field,
                message=f"{field} must contain non-empty strings.",
            )
        items.append(item.strip())
    return tuple(items)


def _optional_float(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidEntityRequestError(
            error="invalid_entity_request",
            field=field,
            message=f"{field} must be a number when provided.",
        )
    return float(value)


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
                "mention type must be one of: person, location, item, topic, other."
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
    return _serialize_authorized_observation(settings, context, observation, decision)


def _serialize_authorized_observation(
    settings: MnemosyneSettings,
    context: AccessContext,
    observation: Observation,
    decision: PolicyDecision,
) -> dict[str, Any]:
    if (
        settings.safe_projections_enabled
        or decision.redacted
        or context.requested_projection != ProjectionName.RAW_OBSERVATION
    ):
        return ProjectionService().project_observation(context, observation, decision)
    return _serialize_observation(observation, include_classification=True)


def _entity_response(request: Request, entity: EntityRecord) -> dict[str, Any]:
    settings = get_settings()
    if not _use_access_pipeline(settings, request):
        return _serialize_entity(entity)
    context = _access_context_from_request(request, settings)
    query_decision = AccessPolicy().can_query_mnemosyne(context)
    if not query_decision.allowed:
        _audit_decision(settings, context, "entity", entity.id, query_decision)
        _raise_access_denied(query_decision)
    decision = AccessPolicy().can_disclose_entity(context, entity)
    _audit_decision(settings, context, "entity", entity.id, decision)
    if not decision.allowed:
        _raise_access_denied(decision)
    return _serialize_entity(
        entity,
        redacted=decision.redacted,
        expose_restricted_fields=_can_read_restricted_fields(context),
    )


def _serialize_entity_list_response(
    request: Request,
    entities: tuple[EntityRecord, ...],
) -> list[dict[str, Any]]:
    settings = get_settings()
    if not _use_access_pipeline(settings, request):
        return [_serialize_entity(entity) for entity in entities]
    context = _access_context_from_request(request, settings)
    query_decision = AccessPolicy().can_query_mnemosyne(context)
    if not query_decision.allowed:
        _raise_access_denied(query_decision)
    items: list[dict[str, Any]] = []
    for entity in entities:
        decision = AccessPolicy().can_disclose_entity(context, entity)
        _audit_decision(settings, context, "entity", entity.id, decision)
        if not decision.allowed:
            continue
        items.append(
            _serialize_entity(
                entity,
                redacted=decision.redacted,
                expose_restricted_fields=_can_read_restricted_fields(context),
            )
        )
    return items


def _serialize_entity(
    entity: EntityRecord,
    *,
    redacted: bool = False,
    expose_restricted_fields: bool = True,
) -> dict[str, Any]:
    return {
        "id": entity.id,
        "type": entity.type.value,
        "label": entity.label,
        "normalized_label": entity.normalized_label,
        "resolution_status": entity.resolution_status.value,
        "scope": entity.scope,
        "sensitivity": entity.sensitivity.value,
        "allowed_purposes": [purpose.value for purpose in entity.allowed_purposes],
        "created_at": _format_datetime(entity.created_at),
        "updated_at": _format_datetime(entity.updated_at),
        "person": _serialize_person_profile(
            entity.person,
            redacted=redacted,
            expose_restricted_fields=expose_restricted_fields,
        ),
        "location": _serialize_location_profile(entity.location, redacted=redacted),
        "store": _serialize_store_profile(entity.store, redacted=redacted),
        "item": _serialize_item_profile(entity.item, redacted=redacted),
        "animal": _serialize_animal_profile(entity.animal, redacted=redacted),
        "redactions": _entity_redactions(
            entity,
            redacted=redacted,
            expose_restricted_fields=expose_restricted_fields,
        ),
    }


def _serialize_person_profile(
    profile: PersonProfile | None,
    *,
    redacted: bool,
    expose_restricted_fields: bool,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "display_name": profile.display_name,
        "given_name": profile.given_name,
        "family_name": profile.family_name,
        "contact_methods": [
            _serialize_contact_method(
                method,
                redacted=redacted,
                expose_restricted_fields=expose_restricted_fields,
            )
            for method in profile.contact_methods
        ],
    }


def _serialize_contact_method(
    method: ContactMethod,
    *,
    redacted: bool,
    expose_restricted_fields: bool,
) -> dict[str, Any]:
    redact_value = redacted or (
        not expose_restricted_fields
        and method.sensitivity in {Sensitivity.RESTRICTED, Sensitivity.SECRET}
    )
    return {
        "kind": method.kind.value,
        "label": method.label,
        "value": None if redact_value else method.value,
        "sensitivity": method.sensitivity.value,
    }


def _serialize_location_profile(
    profile: LocationProfile | None,
    *,
    redacted: bool,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "location_kind": profile.location_kind,
        "street_address": None if redacted else profile.street_address,
        "postal_code": None if redacted else profile.postal_code,
        "locality": profile.locality,
        "region": profile.region,
        "country": profile.country,
        "latitude": None if redacted else profile.latitude,
        "longitude": None if redacted else profile.longitude,
    }


def _serialize_store_profile(
    profile: StoreProfile | None,
    *,
    redacted: bool,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "store_kind": profile.store_kind,
        "website": profile.website,
        "categories": list(profile.categories),
        "country_scope": profile.country_scope,
        "physical_store_status": profile.physical_store_status,
        "source_urls": list(profile.source_urls),
        "reference_notes": None if redacted else profile.reference_notes,
    }


def _serialize_item_profile(
    profile: ItemProfile | None,
    *,
    redacted: bool,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "item_kind": profile.item_kind,
        "category": profile.category,
        "subcategory": profile.subcategory,
        "brand": profile.brand,
        "model": profile.model,
        "variant": profile.variant,
        "color": profile.color,
        "size": profile.size,
        "serial_number": None if redacted else profile.serial_number,
        "identifiers": [] if redacted else list(profile.identifiers),
    }


def _serialize_animal_profile(
    profile: AnimalProfile | None,
    *,
    redacted: bool,
) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "animal_kind": profile.animal_kind,
        "species": profile.species,
        "breed": profile.breed,
        "sex": profile.sex,
        "color": profile.color,
        "date_of_birth": profile.date_of_birth,
        "microchip_id": None if redacted else profile.microchip_id,
        "identifiers": [] if redacted else list(profile.identifiers),
        "reference_notes": None if redacted else profile.reference_notes,
    }


def _entity_redactions(
    entity: EntityRecord,
    *,
    redacted: bool,
    expose_restricted_fields: bool,
) -> list[str]:
    redactions: list[str] = []
    if entity.person is not None and (
        redacted
        or (
            not expose_restricted_fields
            and any(
                method.sensitivity in {Sensitivity.RESTRICTED, Sensitivity.SECRET}
                for method in entity.person.contact_methods
            )
        )
    ):
        redactions.append("contact_methods.value")
    if not redacted:
        return redactions
    if entity.location is not None:
        if entity.location.street_address or entity.location.postal_code:
            redactions.append("location.precise_address")
        if (
            entity.location.latitude is not None
            or entity.location.longitude is not None
        ):
            redactions.append("location.geolocation")
    if entity.store is not None and entity.store.reference_notes:
        redactions.append("store.reference_notes")
    if entity.item is not None:
        if entity.item.serial_number:
            redactions.append("item.serial_number")
        if entity.item.identifiers:
            redactions.append("item.identifiers")
    if entity.animal is not None:
        if entity.animal.microchip_id:
            redactions.append("animal.microchip_id")
        if entity.animal.identifiers:
            redactions.append("animal.identifiers")
        if entity.animal.reference_notes:
            redactions.append("animal.reference_notes")
    return redactions


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
        if (
            settings.safe_projections_enabled
            or decision.redacted
            or context.requested_projection != ProjectionName.RAW_OBSERVATION
        ):
            items.append(
                ProjectionService().project_observation(context, observation, decision)
            )
        else:
            items.append(_serialize_search_result(result))
    return items


def _use_access_pipeline(settings: MnemosyneSettings, request: Request) -> bool:
    del request
    if not (settings.domain_policy_enabled or settings.safe_projections_enabled):
        return False
    if not settings.access_context_headers_enabled:
        return False
    return True


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
        scopes=frozenset(
            _split_header_values(request.headers.get("x-mnemosyne-scopes"))
        ),
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


def _can_read_restricted_fields(context: AccessContext) -> bool:
    return "mnemosyne.raw" in context.scopes or "admin" in context.roles


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
    query_decision = AccessPolicy().can_query_mnemosyne(context)
    if not query_decision.allowed:
        return query_decision
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
