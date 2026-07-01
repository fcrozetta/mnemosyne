from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.entities import (
    AnimalProfile,
    AnimalProfileInput,
    ContactMethod,
    ContactMethodInput,
    CreateEntityInput,
    EntityNotFoundError,
    EntityRecord,
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
    MentionedEntity,
    Observation,
    ObservationContext,
    ObservationNotFoundError,
    ObservationRevision,
    ObservationSearchResult,
    ObservationType,
    PatchObservationInput,
    ResolutionStatus,
    Source,
    SourceInput,
    append_addendum,
    content_preview,
    create_revision_id,
    generate_entity_id,
    generate_observation_id,
    generate_source_id,
    merge_mentions,
    related_overlap,
    score_content_match,
    topic_matches,
    utc_now,
)
from app.repository.observations import ObservationsRepository
from app.storage.bootstrap import StorageBootstrapResult


@dataclass(slots=True)
class InMemoryObservationsRepository(ObservationsRepository):
    """In-memory observation repository for local tests and no-DB runs."""

    observation_id_factory: Callable[[], str] = generate_observation_id
    entity_id_factory: Callable[[], str] = generate_entity_id
    source_id_factory: Callable[[], str] = generate_source_id
    observations: dict[str, Observation] = field(default_factory=dict)
    entities_by_identity: dict[tuple[str, str], MentionedEntity] = field(
        default_factory=dict
    )
    entity_records_by_id: dict[str, EntityRecord] = field(default_factory=dict)
    entity_records_by_identity: dict[tuple[str, str, str], EntityRecord] = field(
        default_factory=dict
    )
    sources_by_identity: dict[tuple[str, str | None, str | None], Source] = field(
        default_factory=dict
    )
    _initialized: bool = False

    def initialize_storage(self) -> StorageBootstrapResult:
        self._initialized = True
        return StorageBootstrapResult(
            created_tables=(),
            existing_tables=("Observation",),
            created_fields=(),
            existing_fields=(),
            created_views=(),
            existing_views=(),
            created_indexes=(),
            existing_indexes=(),
        )

    def storage_initialized(self) -> bool:
        return self._initialized

    def create_observation(self, observation: CreateObservationInput) -> Observation:
        observed_at = observation.observed_at or utc_now()
        created_at = observed_at
        observation_id = self.observation_id_factory()
        revision = ObservationRevision(
            id=create_revision_id(observation_id, 1),
            observation=observation_id,
            version=1,
            content=observation.content,
            content_format=observation.content_format,
            observed_at=observed_at,
            created_at=created_at,
            mentions=self._resolve_mentions(observation.mentions),
            source=self._resolve_source(observation.source, created_at),
            domain=observation.domain,
            sensitivity=observation.sensitivity,
            subject=observation.subject,
            allowed_purposes=observation.allowed_purposes,
        )
        created = Observation(
            id=observation_id,
            type=observation.type,
            created_at=created_at,
            updated_at=created_at,
            revisions=(revision,),
        )
        self.observations[observation_id] = created
        return created

    def create_entity(self, entity: CreateEntityInput) -> EntityRecord:
        now = utc_now()
        identity = (entity.type.value, entity.normalized_label, entity.scope)
        existing = self.entity_records_by_identity.get(identity)
        entity_id = existing.id if existing is not None else self.entity_id_factory()
        created_at = existing.created_at if existing is not None else now
        record = EntityRecord(
            id=entity_id,
            type=entity.type,
            label=entity.label,
            normalized_label=entity.normalized_label,
            resolution_status=ResolutionStatus.RESOLVED,
            scope=entity.scope,
            sensitivity=entity.sensitivity,
            allowed_purposes=entity.allowed_purposes,
            created_at=created_at,
            updated_at=now,
            person=_person_profile(entity.person),
            location=_location_profile(entity.location),
            store=_store_profile(entity.store),
            item=_item_profile(entity.item),
            animal=_animal_profile(entity.animal),
        )
        self.entity_records_by_id[record.id] = record
        self.entity_records_by_identity[identity] = record
        return record

    def get_entity(self, id: str) -> EntityRecord:
        try:
            return self.entity_records_by_id[id]
        except KeyError as exc:
            raise EntityNotFoundError(id) from exc

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        scope: str | None = None,
        query: str | None = None,
        limit: int = 25,
    ) -> tuple[EntityRecord, ...]:
        normalized_query = query.casefold().strip() if query else None
        matches: list[EntityRecord] = []
        for entity in self.entity_records_by_id.values():
            if entity_type is not None and entity.type.value != entity_type:
                continue
            if scope is not None and entity.scope != scope:
                continue
            if normalized_query and normalized_query not in entity.label.casefold():
                continue
            matches.append(entity)
        return tuple(
            sorted(
                matches,
                key=lambda item: (item.updated_at.timestamp(), item.id),
                reverse=True,
            )[:limit]
        )

    def get_observation(self, id: str) -> Observation:
        try:
            return self.observations[id]
        except KeyError as exc:
            raise ObservationNotFoundError(id) from exc

    def search_observations(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]:
        matches: list[ObservationSearchResult] = []
        for observation in self.observations.values():
            latest = observation.latest_revision
            if latest is None:
                continue
            score = score_content_match(latest.content, query)
            if score <= 0:
                continue
            matches.append(
                ObservationSearchResult(
                    id=observation.id,
                    type=observation.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    updated_at=observation.updated_at,
                    score=score,
                )
            )

        return tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.updated_at.timestamp(),
                    item.id,
                ),
                reverse=True,
            )[:limit]
        )

    def recent_observations_by_topic(
        self,
        topic: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]:
        matches: list[ObservationSearchResult] = []
        for observation in self.observations.values():
            if observation.type != ObservationType.NOTE:
                continue
            latest = observation.latest_revision
            if latest is None or not _revision_mentions_topic(latest, topic):
                continue
            matches.append(
                ObservationSearchResult(
                    id=observation.id,
                    type=observation.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    updated_at=observation.updated_at,
                    score=1.0,
                )
            )

        return tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.updated_at.timestamp(),
                    item.id,
                ),
                reverse=True,
            )[:limit]
        )

    def patch_observation(
        self,
        observation_id: str,
        patch: PatchObservationInput,
    ) -> Observation:
        current = self.get_observation(observation_id)
        latest = current.latest_revision
        if latest is None:
            raise ObservationNotFoundError(observation_id)
        if patch.addendum is None and not patch.mentions and patch.observed_at is None:
            raise InvalidObservationPatchError(
                "Patch request must include at least one change."
            )

        next_version = latest.version + 1
        observed_at = patch.observed_at or latest.observed_at
        created_at = utc_now()
        added_mentions = self._resolve_mentions(patch.mentions)
        revision = ObservationRevision(
            id=create_revision_id(observation_id, next_version),
            observation=observation_id,
            version=next_version,
            content=append_addendum(latest.content, patch.addendum),
            content_format=latest.content_format,
            observed_at=observed_at,
            created_at=created_at,
            mentions=merge_mentions(latest.mentions, added_mentions),
            source=latest.source,
            domain=latest.domain,
            sensitivity=latest.sensitivity,
            subject=latest.subject,
            allowed_purposes=latest.allowed_purposes,
        )
        updated = Observation(
            id=current.id,
            type=current.type,
            created_at=current.created_at,
            updated_at=created_at,
            lifecycle_status=current.lifecycle_status,
            revisions=(*current.revisions, revision),
        )
        self.observations[observation_id] = updated
        return updated

    def get_observation_context(
        self,
        id: str,
        limit: int = 5,
    ) -> ObservationContext:
        anchor = self.get_observation(id)
        related: list[ObservationSearchResult] = []
        for observation in self.observations.values():
            if observation.id == id:
                continue
            latest = observation.latest_revision
            if latest is None:
                continue
            score = float(related_overlap(anchor, observation))
            if score <= 0:
                continue
            related.append(
                ObservationSearchResult(
                    id=observation.id,
                    type=observation.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    updated_at=observation.updated_at,
                    score=score,
                )
            )

        return ObservationContext(
            observation=anchor,
            related_observations=tuple(
                sorted(
                    related,
                    key=lambda item: (
                        item.score,
                        item.updated_at.timestamp(),
                        item.id,
                    ),
                    reverse=True,
                )[:limit]
            ),
        )

    def _resolve_mentions(
        self,
        mentions: tuple[EntityMentionInput, ...],
    ) -> tuple[MentionedEntity, ...]:
        resolved: list[MentionedEntity] = []
        for mention in mentions:
            existing = self.entities_by_identity.get(mention.identity)
            if existing is None:
                existing = MentionedEntity(
                    id=self.entity_id_factory(),
                    type=mention.type,
                    label=mention.label,
                    resolution_status=ResolutionStatus.UNRESOLVED,
                )
                self.entities_by_identity[mention.identity] = existing
            resolved.append(existing)
        return merge_mentions((), resolved)

    def _resolve_source(
        self,
        source: SourceInput | None,
        created_at,
    ) -> Source:
        source_input = source or SourceInput()
        existing = self.sources_by_identity.get(source_input.identity)
        if existing is not None:
            return existing
        created = Source(
            id=self.source_id_factory(),
            source_type=source_input.source_type,
            label=source_input.label,
            source_ref=source_input.source_ref,
            created_at=created_at,
        )
        self.sources_by_identity[source_input.identity] = created
        return created


def _animal_profile(profile: AnimalProfileInput | None) -> AnimalProfile | None:
    if profile is None:
        return None
    return AnimalProfile(
        animal_kind=profile.animal_kind,
        species=profile.species,
        breed=profile.breed,
        sex=profile.sex,
        color=profile.color,
        date_of_birth=profile.date_of_birth,
        microchip_id=profile.microchip_id,
        identifiers=profile.identifiers,
        reference_notes=profile.reference_notes,
    )


def _revision_mentions_topic(revision: ObservationRevision, topic: str) -> bool:
    return any(
        mention.type == EntityType.TOPIC and topic_matches(mention.label, topic)
        for mention in revision.mentions
    )


def _person_profile(value: PersonProfileInput | None) -> PersonProfile | None:
    if value is None:
        return None
    return PersonProfile(
        display_name=value.display_name,
        given_name=value.given_name,
        family_name=value.family_name,
        contact_methods=tuple(
            _contact_method(method) for method in value.contact_methods
        ),
    )


def _contact_method(value: ContactMethodInput) -> ContactMethod:
    return ContactMethod(
        kind=value.kind,
        value=value.value,
        label=value.label,
        sensitivity=value.sensitivity,
    )


def _location_profile(value: LocationProfileInput | None) -> LocationProfile | None:
    if value is None:
        return None
    return LocationProfile(
        location_kind=value.location_kind,
        street_address=value.street_address,
        postal_code=value.postal_code,
        locality=value.locality,
        region=value.region,
        country=value.country,
        latitude=value.latitude,
        longitude=value.longitude,
    )


def _store_profile(value: StoreProfileInput | None) -> StoreProfile | None:
    if value is None:
        return None
    return StoreProfile(
        store_kind=value.store_kind,
        website=value.website,
        categories=value.categories,
        country_scope=value.country_scope,
        physical_store_status=value.physical_store_status,
        source_urls=value.source_urls,
        reference_notes=value.reference_notes,
    )


def _item_profile(value: ItemProfileInput | None) -> ItemProfile | None:
    if value is None:
        return None
    return ItemProfile(
        item_kind=value.item_kind,
        category=value.category,
        subcategory=value.subcategory,
        brand=value.brand,
        model=value.model,
        variant=value.variant,
        color=value.color,
        size=value.size,
        serial_number=value.serial_number,
        identifiers=value.identifiers,
    )


__all__ = ["InMemoryObservationsRepository"]
