from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.observations import (
    CreateObservationInput,
    EntityMentionInput,
    InvalidObservationPatchError,
    MentionedEntity,
    Observation,
    ObservationContext,
    ObservationNotFoundError,
    ObservationRevision,
    ObservationSearchResult,
    PatchObservationInput,
    ResolutionStatus,
    Source,
    SourceInput,
    VersionConflictError,
    append_addendum,
    content_preview,
    create_revision_id,
    generate_entity_id,
    generate_observation_id,
    generate_source_id,
    merge_mentions,
    related_overlap,
    score_content_match,
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
            revision_id=create_revision_id(observation_id, 1),
            observation_id=observation_id,
            version=1,
            content=observation.content,
            content_format=observation.content_format,
            observed_at=observed_at,
            created_at=created_at,
            mentions=self._resolve_mentions(observation.mentions),
            source=self._resolve_source(observation.source, created_at),
        )
        created = Observation(
            observation_id=observation_id,
            type=observation.type,
            created_at=created_at,
            updated_at=created_at,
            revisions=(revision,),
        )
        self.observations[observation_id] = created
        return created

    def get_observation(self, observation_id: str) -> Observation:
        try:
            return self.observations[observation_id]
        except KeyError as exc:
            raise ObservationNotFoundError(observation_id) from exc

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
                    observation_id=observation.observation_id,
                    type=observation.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    score=score,
                )
            )

        return tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.score,
                    item.observed_at.timestamp(),
                    item.observation_id,
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
        if patch.version != latest.version:
            raise VersionConflictError(
                observation_id=observation_id,
                current_version=latest.version,
                requested_version=patch.version,
            )
        if patch.addendum is None and not patch.mentions and patch.observed_at is None:
            raise InvalidObservationPatchError(
                "Patch request must include at least one change."
            )

        next_version = latest.version + 1
        observed_at = patch.observed_at or latest.observed_at
        created_at = utc_now()
        added_mentions = self._resolve_mentions(patch.mentions)
        revision = ObservationRevision(
            revision_id=create_revision_id(observation_id, next_version),
            observation_id=observation_id,
            version=next_version,
            content=append_addendum(latest.content, patch.addendum),
            content_format=latest.content_format,
            observed_at=observed_at,
            created_at=created_at,
            mentions=merge_mentions(latest.mentions, added_mentions),
            source=latest.source,
        )
        updated = Observation(
            observation_id=current.observation_id,
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
        observation_id: str,
        limit: int = 5,
    ) -> ObservationContext:
        anchor = self.get_observation(observation_id)
        related: list[ObservationSearchResult] = []
        for observation in self.observations.values():
            if observation.observation_id == observation_id:
                continue
            latest = observation.latest_revision
            if latest is None:
                continue
            score = float(related_overlap(anchor, observation))
            if score <= 0:
                continue
            related.append(
                ObservationSearchResult(
                    observation_id=observation.observation_id,
                    type=observation.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
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
                        item.observed_at.timestamp(),
                        item.observation_id,
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
                    entity_id=self.entity_id_factory(),
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
            source_id=self.source_id_factory(),
            source_type=source_input.source_type,
            label=source_input.label,
            source_ref=source_input.source_ref,
            created_at=created_at,
        )
        self.sources_by_identity[source_input.identity] = created
        return created


__all__ = ["InMemoryObservationsRepository"]
