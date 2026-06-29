from __future__ import annotations

from typing import Protocol

from app.models.entities import CreateEntityInput, EntityRecord
from app.models.observations import (
    CreateObservationInput,
    Observation,
    ObservationContext,
    ObservationSearchResult,
    PatchObservationInput,
)
from app.storage.bootstrap import StorageBootstrapResult


class ObservationsRepository(Protocol):
    """Persistence boundary for observation storage."""

    def initialize_storage(self) -> StorageBootstrapResult: ...

    def storage_initialized(self) -> bool: ...

    def create_observation(self, observation: CreateObservationInput) -> Observation:
        ...

    def create_entity(self, entity: CreateEntityInput) -> EntityRecord: ...

    def get_entity(self, id: str) -> EntityRecord: ...

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        scope: str | None = None,
        query: str | None = None,
        limit: int = 25,
    ) -> tuple[EntityRecord, ...]: ...

    def get_observation(self, id: str) -> Observation: ...

    def search_observations(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]: ...

    def recent_observations_by_topic(
        self,
        topic: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]: ...

    def patch_observation(
        self,
        id: str,
        patch: PatchObservationInput,
    ) -> Observation: ...

    def get_observation_context(
        self,
        id: str,
        limit: int = 5,
    ) -> ObservationContext: ...


__all__ = ["ObservationsRepository"]
