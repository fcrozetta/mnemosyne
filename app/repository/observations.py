from __future__ import annotations

from typing import Protocol

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

    def get_observation(self, observation_id: str) -> Observation: ...

    def search_observations(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]: ...

    def patch_observation(
        self,
        observation_id: str,
        patch: PatchObservationInput,
    ) -> Observation: ...

    def get_observation_context(
        self,
        observation_id: str,
        limit: int = 5,
    ) -> ObservationContext: ...


__all__ = ["ObservationsRepository"]
