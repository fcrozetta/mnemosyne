from __future__ import annotations

from dataclasses import dataclass

from app.models.entities import CreateEntityInput, EntityRecord
from app.models.observations import (
    CreateObservationInput,
    Observation,
    ObservationContext,
    ObservationSearchResult,
    PatchObservationInput,
)
from app.repository.observations import ObservationsRepository
from app.storage.bootstrap import StorageBootstrapResult


@dataclass(frozen=True, slots=True)
class ObservationsService:
    """Application boundary for observation behavior."""

    repository: ObservationsRepository

    def initialize_storage(self) -> StorageBootstrapResult:
        return self.repository.initialize_storage()

    def storage_initialized(self) -> bool:
        return self.repository.storage_initialized()

    def create_observation(
        self,
        observation: CreateObservationInput,
    ) -> Observation:
        return self.repository.create_observation(observation)

    def create_entity(self, entity: CreateEntityInput) -> EntityRecord:
        return self.repository.create_entity(entity)

    def get_entity(self, id: str) -> EntityRecord:
        return self.repository.get_entity(id)

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        scope: str | None = None,
        query: str | None = None,
        limit: int = 25,
    ) -> tuple[EntityRecord, ...]:
        return self.repository.list_entities(
            entity_type=entity_type,
            scope=scope,
            query=query,
            limit=limit,
        )

    def get_observation(self, id: str) -> Observation:
        return self.repository.get_observation(id)

    def search_observations(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]:
        return self.repository.search_observations(query, limit=limit)

    def recent_observations_by_topic(
        self,
        topic: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]:
        return self.repository.recent_observations_by_topic(topic, limit=limit)

    def patch_observation(
        self,
        id: str,
        patch: PatchObservationInput,
    ) -> Observation:
        return self.repository.patch_observation(id, patch)

    def get_observation_context(
        self,
        id: str,
        limit: int = 5,
    ) -> ObservationContext:
        return self.repository.get_observation_context(id, limit=limit)


__all__ = ["ObservationsService"]
