from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.observations import (
    CreateObservationInput,
    EntityMentionInput,
    EntityType,
    MentionedEntity,
    Observation,
    ObservationRevision,
    ObservationType,
    PatchObservationInput,
    ResolutionStatus,
    Source,
    SourceInput,
    SourceType,
)
from app.repository.observations_arcade import ArcadeObservationsRepository
from app.storage.arcade import ArcadeRequestError


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
    assert params is None


def test_arcade_search_scores_loaded_current_revisions() -> None:
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
            return {
                "result": [
                    {
                        "observation_id": "obs_001",
                        "observation_type": "note",
                        "version": 1,
                        "content": "Blue shirt is at John's place.",
                        "observed_at": "2026-04-06T17:00:00Z",
                    },
                    {
                        "observation_id": "obs_002",
                        "observation_type": "note",
                        "version": 1,
                        "content": "Blue mug is in the kitchen.",
                        "observed_at": "2026-04-06T18:00:00Z",
                    },
                ]
            }

    backend = _SearchBackend()
    repository = ArcadeObservationsRepository(runtime=backend)

    results = repository.search_observations("shirt blue", limit=5)

    assert [(item.observation_id, item.score) for item in results] == [
        ("obs_001", 1.0),
        ("obs_002", 0.5),
    ]
    query, params = backend.queries[0]
    assert "LIKE" not in query
    assert params is None


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


def test_arcade_repository_create_observation_keeps_source_identity_stable() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(runtime=backend)

    script, _params = repository._create_observation_script(
        observation=CreateObservationInput(
            type=ObservationType.NOTE,
            content="Need to pick up my shirt.",
            source=SourceInput(source_type=SourceType.AGENT),
        ),
        observation_id="obs_001",
        revision_id="obs_001:v1",
        source=SourceInput(source_type=SourceType.AGENT),
        source_id="src_001",
        observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
    )

    assert "source_id = ifnull(source_id, :source_id)" in script
    assert "label <=> :source_label" in script
    assert "source_ref <=> :source_ref" in script


def test_arcade_repository_create_observation_keeps_entity_identity_stable() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(runtime=backend)

    script, _params = repository._create_observation_script(
        observation=CreateObservationInput(
            type=ObservationType.NOTE,
            content="Need to pick up my shirt.",
            mentions=(EntityMentionInput(type=EntityType.ITEM, label="blue shirt"),),
        ),
        observation_id="obs_001",
        revision_id="obs_001:v1",
        source=SourceInput(source_type=SourceType.AGENT),
        source_id="src_001",
        observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
    )

    assert "entity_id = ifnull(entity_id, :entity_id_0)" in script


def test_arcade_repository_patch_observation_increments_version_internally() -> None:
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
            addendum="It is blue.",
            observed_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        ),
    )

    assert observation == updated
    script, language, params = backend.commands[0]
    assert language == "sqlscript"
    assert "LOCK TYPE" not in script
    assert "RETURN AFTER" not in script
    assert "WHERE observation_id = :observation_id" in script
    assert "expected_version" not in script
    assert "CREATE VERTEX Revision CONTENT" in script
    assert "CREATE EDGE PreviousRevision" in script
    assert "DELETE FROM CurrentRevision" in script
    assert (
        "`@out` IN (SELECT FROM Observation WHERE observation_id = :observation_id)"
        in script
    )
    assert "CREATE EDGE CurrentRevision" in script
    assert params is not None
    assert "expected_version" not in params
    assert params["next_version"] == 2
    assert params["revision_id"] == "obs_001:v2"


def test_arcade_repository_patch_retries_when_assigned_version_conflicts() -> None:
    class _ConflictingPatchBackend(_FakeArcadeBackend):
        def command(
            self,
            command: str,
            *,
            language: str = "sql",
            params: dict[str, object] | None = None,
        ) -> object:
            super().command(command, language=language, params=params)
            if len(self.commands) == 1:
                raise ArcadeRequestError("Revision[observation_id,version] duplicate")
            return {"result": "ok"}

    backend = _ConflictingPatchBackend()
    repository = ArcadeObservationsRepository(runtime=backend)
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
    externally_patched = Observation(
        observation_id="obs_001",
        type=ObservationType.NOTE,
        created_at=current.created_at,
        updated_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        revisions=(
            *current.revisions,
            ObservationRevision(
                revision_id="obs_001:v2",
                observation_id="obs_001",
                version=2,
                content="Need to pick up my shirt.\n\nAddendum:\nIt is blue.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
            ),
        ),
    )
    updated = Observation(
        observation_id="obs_001",
        type=ObservationType.NOTE,
        created_at=current.created_at,
        updated_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        revisions=(
            *externally_patched.revisions,
            ObservationRevision(
                revision_id="obs_001:v3",
                observation_id="obs_001",
                version=3,
                content=(
                    "Need to pick up my shirt.\n\n"
                    "Addendum:\n"
                    "It is blue.\n\n"
                    "Addendum:\n"
                    "It is still blue."
                ),
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
            ),
        ),
    )
    observations = [current, externally_patched, updated]
    repository._get_observation = lambda _observation_id: observations.pop(0)  # type: ignore[method-assign]

    observation = repository.patch_observation(
        "obs_001",
        PatchObservationInput(addendum="It is still blue."),
    )

    assert observation == updated
    assert len(backend.commands) == 2
    _first_script, _first_language, first_params = backend.commands[0]
    _second_script, _second_language, second_params = backend.commands[1]
    assert first_params is not None
    assert second_params is not None
    assert first_params["revision_id"] == "obs_001:v2"
    assert second_params["revision_id"] == "obs_001:v3"
    assert second_params["next_version"] == 3
    assert second_params["previous_revision_id"] == "obs_001:v2"
    revision_payload = second_params["revision"]
    assert isinstance(revision_payload, dict)
    assert isinstance(revision_payload["created_at"], str)
    assert revision_payload == {
        "revision_id": "obs_001:v3",
        "observation_id": "obs_001",
        "version": 3,
        "content": (
            "Need to pick up my shirt.\n\n"
            "Addendum:\n"
            "It is blue.\n\n"
            "Addendum:\n"
            "It is still blue."
        ),
        "content_format": "text/plain",
        "observed_at": "2026-04-06T18:00:00Z",
        "created_at": revision_payload["created_at"],
    }


def test_arcade_patch_carries_current_source_and_mentions() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(
        runtime=backend,
        entity_id_factory=lambda: "ent_001",
    )
    source = Source(
        source_id="src_codex",
        source_type=SourceType.AGENT,
        label="codex",
        source_ref=None,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
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
                mentions=(
                    MentionedEntity(
                        entity_id="ent_shirt",
                        type=EntityType.ITEM,
                        label="blue shirt",
                        resolution_status=ResolutionStatus.UNRESOLVED,
                    ),
                ),
                source=source,
            ),
        ),
    )

    script, params = repository._patch_observation_script(
        current=current,
        latest=current.latest_revision,
        patch=PatchObservationInput(
            addendum="It is blue.",
            mentions=(
                EntityMentionInput(type=EntityType.LOCATION, label="John's place"),
            ),
        ),
        revision_id="obs_001:v2",
        next_version=2,
        observed_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        created_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
    )

    assert "CREATE EDGE ObservedFrom" in script
    assert script.count("CREATE EDGE Mentions") == 2
    assert params["source_id"] == "src_codex"
    assert params["entity_id_0"] == "ent_shirt"
    assert params["entity_id_1"] == "ent_001"


def test_arcade_repository_context_uses_related_observation_overlap() -> None:
    class _ContextBackend(_FakeArcadeBackend):
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
            return {
                "result": [
                    {"observation_id": "obs_002"},
                    {"observation_id": "obs_003"},
                ]
            }

    blue_shirt = MentionedEntity(
        entity_id="ent_shirt",
        type=EntityType.ITEM,
        label="blue shirt",
        resolution_status=ResolutionStatus.UNRESOLVED,
    )
    place = MentionedEntity(
        entity_id="ent_place",
        type=EntityType.LOCATION,
        label="John's place",
        resolution_status=ResolutionStatus.UNRESOLVED,
    )
    now = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)
    observations = {
        "obs_001": Observation(
            observation_id="obs_001",
            type=ObservationType.NOTE,
            created_at=now,
            updated_at=now,
            revisions=(
                ObservationRevision(
                    revision_id="obs_001:v1",
                    observation_id="obs_001",
                    version=1,
                    content="Need to pick up my shirt.",
                    content_format="text/plain",
                    observed_at=now,
                    created_at=now,
                    mentions=(blue_shirt, place),
                ),
            ),
        ),
        "obs_002": Observation(
            observation_id="obs_002",
            type=ObservationType.NOTE,
            created_at=now,
            updated_at=now,
            revisions=(
                ObservationRevision(
                    revision_id="obs_002:v1",
                    observation_id="obs_002",
                    version=1,
                    content="Blue shirt is at John's place.",
                    content_format="text/plain",
                    observed_at=now,
                    created_at=now,
                    mentions=(blue_shirt, place),
                ),
            ),
        ),
        "obs_003": Observation(
            observation_id="obs_003",
            type=ObservationType.NOTE,
            created_at=now,
            updated_at=now,
            revisions=(
                ObservationRevision(
                    revision_id="obs_003:v1",
                    observation_id="obs_003",
                    version=1,
                    content="Coffee mug is in the kitchen.",
                    content_format="text/plain",
                    observed_at=now,
                    created_at=now,
                    mentions=(),
                ),
            ),
        ),
    }
    backend = _ContextBackend()
    repository = ArcadeObservationsRepository(runtime=backend)
    repository._get_observation = lambda observation_id: observations[observation_id]  # type: ignore[method-assign]

    context = repository.get_observation_context("obs_001")

    assert [item.observation_id for item in context.related_observations] == [
        "obs_002"
    ]
    assert context.related_observations[0].score == 2.0
    query, params = backend.queries[0]
    assert "observation_id <> :observation_id" in query
    assert params == {"observation_id": "obs_001"}


def test_arcade_repository_storage_initialized_requires_database_and_schema() -> None:
    class _Backend(_FakeArcadeBackend):
        def database_exists(self) -> bool:
            return False

    repository = ArcadeObservationsRepository(runtime=_Backend())

    assert repository.storage_initialized() is False
