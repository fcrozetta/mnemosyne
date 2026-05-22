from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.observations import (
    CreateObservationInput,
    EntityMentionInput,
    EntityType,
    Observation,
    ObservationRevision,
    ObservationType,
    PatchObservationInput,
    SourceInput,
    SourceType,
)
from app.repository.observations_arcade import ArcadeObservationsRepository


@dataclass
class _FakeArcadeBackend:
    commands: list[tuple[str, str, dict[str, object] | None]] = field(
        default_factory=list
    )

    def ensure_database(self) -> bool:
        return False

    def apply_default_schema(self) -> None:
        return None

    def ready(self) -> bool:
        return True

    def command(
        self,
        command: str,
        *,
        language: str = "sql",
        params: dict[str, object] | None = None,
    ) -> object:
        self.commands.append((command, language, params))
        return {"result": "ok"}

    def query(
        self,
        query: str,
        *,
        language: str = "sql",
        params: dict[str, object] | None = None,
    ) -> object:
        return {"result": []}


def test_arcade_repository_search_uses_current_revision_and_observation_type() -> None:
    class _SearchBackend(_FakeArcadeBackend):
        def __init__(self) -> None:
            super().__init__()
            self.queries: list[tuple[str, dict[str, object] | None]] = []

        def query(
            self,
            query: str,
            *,
            language: str = "sql",
            params: dict[str, object] | None = None,
        ) -> object:
            del language
            self.queries.append((query, params))
            if "FROM Observation" in query and "CurrentRevision" in query:
                return {
                    "result": [
                        {
                            "observation_id": "obs_001",
                            "observation_type": "document",
                            "version": 2,
                            "content": "The blue shirt is at John's place.",
                            "observed_at": "2026-04-06T18:05:00Z",
                        }
                    ]
                }
            return {
                "result": [
                    {
                        "observation_id": "obs_001",
                        "version": 1,
                        "content": "The blue shirt is missing.",
                        "observed_at": "2026-04-06T17:00:00Z",
                    },
                    {
                        "observation_id": "obs_001",
                        "version": 2,
                        "content": "The blue shirt is at John's place.",
                        "observed_at": "2026-04-06T18:05:00Z",
                    },
                ]
            }

    backend = _SearchBackend()
    repository = ArcadeObservationsRepository(runtime=backend)

    results = repository.search_observations("shirt", limit=5)

    assert [(item.observation_id, item.type, item.version) for item in results] == [
        ("obs_001", ObservationType.DOCUMENT, 2)
    ]
    query, params = backend.queries[0]
    assert "FROM Observation" in query
    assert "CurrentRevision" in query
    assert "FROM Revision" not in query
    assert params == {"query": "%shirt%", "limit": 5}


def test_arcade_repository_create_observation_writes_truth_graph() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(
        runtime=backend,
        observation_id_factory=lambda: "obs_001",
        entity_id_factory=lambda: "ent_001",
        source_id_factory=lambda: "src_001",
    )
    expected = Observation(
        observation_id="obs_001",
        type=ObservationType.NOTE,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            ObservationRevision(
                revision_id="obs_001:v1",
                observation_id="obs_001",
                version=1,
                content="Need to pick up my shirt.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    repository._get_observation = lambda _observation_id: expected  # type: ignore[method-assign]

    observation = repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="Need to pick up my shirt.",
            mentions=(EntityMentionInput(type=EntityType.ITEM, label="blue shirt"),),
            observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            source=SourceInput(source_type=SourceType.AGENT, label="codex"),
        )
    )

    assert observation == expected
    script, language, params = backend.commands[0]
    assert language == "sqlscript"
    assert "CREATE VERTEX Note CONTENT" in script
    assert "CREATE VERTEX Revision CONTENT" in script
    assert "UPDATE Source SET" in script
    assert "UPSERT WHERE source_type = :source_type" in script
    assert "UPDATE Item SET" in script
    assert "UPSERT WHERE entity_type = :entity_type_0" in script
    assert "CREATE EDGE HasRevision" in script
    assert "CREATE EDGE CurrentRevision" in script
    assert "CREATE EDGE ObservedFrom" in script
    assert "CREATE EDGE Mentions" in script
    assert params is not None
    assert params["observation_id"] == "obs_001"
    assert params["revision_id"] == "obs_001:v1"
    assert params["source_id"] == "src_001"
    assert params["entity_id_0"] == "ent_001"


def test_arcade_repository_patch_observation_uses_version_guard() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(
        runtime=backend,
        entity_id_factory=lambda: "ent_001",
    )
    current = Observation(
        observation_id="obs_001",
        type=ObservationType.NOTE,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            ObservationRevision(
                revision_id="obs_001:v1",
                observation_id="obs_001",
                version=1,
                content="Need to pick up my shirt.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    updated = Observation(
        observation_id="obs_001",
        type=ObservationType.NOTE,
        created_at=current.created_at,
        updated_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        revisions=(
            *current.revisions,
            ObservationRevision(
                revision_id="obs_001:v2",
                observation_id="obs_001",
                version=2,
                content="Need to pick up my shirt.\n\nAddendum:\nIt is blue.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
            ),
        ),
    )
    observations = [current, updated]
    repository._get_observation = lambda _observation_id: observations.pop(0)  # type: ignore[method-assign]

    observation = repository.patch_observation(
        "obs_001",
        PatchObservationInput(
            version=1,
            addendum="It is blue.",
            observed_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        ),
    )

    assert observation == updated
    script, language, params = backend.commands[0]
    assert language == "sqlscript"
    assert "LOCK TYPE" not in script
    assert "WHERE observation_id = :observation_id" in script
    assert "current_version = :expected_version" in script
    assert "CREATE VERTEX Revision CONTENT" in script
    assert "CREATE EDGE PreviousRevision" in script
    assert "DELETE FROM CurrentRevision" in script
    assert (
        "`@out` IN (SELECT FROM Observation WHERE observation_id = :observation_id)"
        in script
    )
    assert "CREATE EDGE CurrentRevision" in script
    assert params is not None
    assert params["expected_version"] == 1
    assert params["next_version"] == 2
    assert params["revision_id"] == "obs_001:v2"
