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
                            "id": "obs_001",
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
                        "id": "obs_001",
                        "version": 1,
                        "content": "The blue shirt is missing.",
                        "observed_at": "2026-04-06T17:00:00Z",
                    },
                    {
                        "id": "obs_001",
                        "version": 2,
                        "content": "The blue shirt is at John's place.",
                        "observed_at": "2026-04-06T18:05:00Z",
                    },
                ]
            }

    backend = _SearchBackend()
    repository = ArcadeObservationsRepository(runtime=backend)

    results = repository.search_observations("shirt", limit=5)

    assert [(item.id, item.type, item.version) for item in results] == [
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
                        "id": "obs_001",
                        "observation_type": "note",
                        "version": 1,
                        "content": "Blue shirt is at John's place.",
                        "observed_at": "2026-04-06T17:00:00Z",
                    },
                    {
                        "id": "obs_002",
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

    assert [(item.id, item.score) for item in results] == [
        ("obs_001", 1.0),
        ("obs_002", 0.5),
    ]
    query, params = backend.queries[0]
    assert "LIKE" not in query
    assert params is None


def test_arcade_recent_by_topic_uses_index_and_latest_notes() -> None:
    class _TopicBackend(_FakeArcadeBackend):
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
            if "FROM Topic" in query and "normalized_label LIKE" in query:
                return {
                    "result": [
                        {
                            "id": "ent_style",
                            "normalized_label": "coding:fcrozetta:python:coding-style",
                        },
                        {
                            "id": "ent_lint",
                            "normalized_label": "coding:fcrozetta:python:linting",
                        },
                    ]
                }
            if "expand(in('Mentions'))" in query:
                if params == {"topic_id": "ent_style"}:
                    return {"result": [{"id": "obs_001:v1", "observation": "obs_001"}]}
                if params == {"topic_id": "ent_lint"}:
                    return {"result": [{"id": "obs_002:v2", "observation": "obs_002"}]}
            return {"result": []}

    style_topic = MentionedEntity(
        id="ent_style",
        type=EntityType.TOPIC,
        label="coding:fcrozetta:python:coding-style",
        resolution_status=ResolutionStatus.UNRESOLVED,
    )
    lint_topic = MentionedEntity(
        id="ent_lint",
        type=EntityType.TOPIC,
        label="coding:fcrozetta:python:linting",
        resolution_status=ResolutionStatus.UNRESOLVED,
    )
    observations = {
        "obs_001": Observation(
            id="obs_001",
            type=ObservationType.NOTE,
            created_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
            revisions=(
                ObservationRevision(
                    id="obs_001:v1",
                    observation="obs_001",
                    version=1,
                    content="Prefer pathlib for local file handling.",
                    content_format="text/plain",
                    observed_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
                    created_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
                    mentions=(style_topic,),
                ),
            ),
        ),
        "obs_002": Observation(
            id="obs_002",
            type=ObservationType.NOTE,
            created_at=datetime(2026, 4, 5, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
            revisions=(
                ObservationRevision(
                    id="obs_002:v1",
                    observation="obs_002",
                    version=1,
                    content="Ruff should keep imports sorted.",
                    content_format="text/plain",
                    observed_at=datetime(2026, 4, 5, 10, 0, tzinfo=UTC),
                    created_at=datetime(2026, 4, 5, 10, 0, tzinfo=UTC),
                    mentions=(lint_topic,),
                ),
                ObservationRevision(
                    id="obs_002:v2",
                    observation="obs_002",
                    version=2,
                    content=(
                        "Ruff should keep imports sorted.\n\n"
                        "Addendum:\nThis is the current version."
                    ),
                    content_format="text/plain",
                    observed_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    created_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
                    mentions=(lint_topic,),
                ),
            ),
        ),
    }
    backend = _TopicBackend()
    repository = ArcadeObservationsRepository(runtime=backend)
    repository._get_observation = lambda observation_id: observations[observation_id]  # type: ignore[method-assign]

    recent = repository.recent_observations_by_topic(
        "coding:fcrozetta:python",
        limit=5,
    )

    assert [(item.id, item.version) for item in recent] == [
        ("obs_002", 2),
        ("obs_001", 1),
    ]
    topic_query, topic_params = backend.queries[0]
    assert "FROM Topic" in topic_query
    assert "normalized_label LIKE :topic_pattern" in topic_query
    assert topic_params == {"topic_pattern": "%coding:fcrozetta:python%"}


def test_arcade_repository_create_observation_writes_truth_graph() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(
        runtime=backend,
        observation_id_factory=lambda: "obs_001",
        entity_id_factory=lambda: "ent_001",
        source_id_factory=lambda: "src_001",
    )
    expected = Observation(
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            ObservationRevision(
                id="obs_001:v1",
                observation="obs_001",
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

    assert "id = ifnull(id, :source_id)" in script
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

    assert "id = ifnull(id, :entity_id_0)" in script


def test_arcade_repository_serializes_datetime_in_arcadedb_format() -> None:
    # Regression: ArcadeDB DATETIME columns silently drop SET assignments when
    # given an ISO 8601 string with the `T` separator or `Z` suffix. Every
    # write path through this repository must emit `yyyy-MM-dd HH:mm:ss`
    # (always UTC) so Source/Revision/Entity rows actually persist their
    # timestamps. Failure mode: created_at ends up null on every UPSERT and
    # the response projection raises ValueError on read.
    from app.repository.observations_arcade import _datetime_value

    encoded = _datetime_value(datetime(2026, 4, 6, 17, 0, tzinfo=UTC))
    assert encoded == "2026-04-06 17:00:00"
    assert "T" not in encoded
    assert "Z" not in encoded


def test_arcade_repository_patch_observation_increments_version_internally() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(
        runtime=backend,
        entity_id_factory=lambda: "ent_001",
    )
    current = Observation(
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            ObservationRevision(
                id="obs_001:v1",
                observation="obs_001",
                version=1,
                content="Need to pick up my shirt.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    updated = Observation(
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=current.created_at,
        updated_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        revisions=(
            *current.revisions,
            ObservationRevision(
                id="obs_001:v2",
                observation="obs_001",
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
    assert "WHERE id = :observation_id" in script
    assert "expected_version" not in script
    assert "CREATE VERTEX Revision CONTENT" in script
    assert "CREATE EDGE PreviousRevision" in script
    assert "DELETE FROM CurrentRevision" in script
    assert (
        "`@out` IN (SELECT FROM Observation WHERE id = :observation_id)"
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
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            ObservationRevision(
                id="obs_001:v1",
                observation="obs_001",
                version=1,
                content="Need to pick up my shirt.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    externally_patched = Observation(
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=current.created_at,
        updated_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
        revisions=(
            *current.revisions,
            ObservationRevision(
                id="obs_001:v2",
                observation="obs_001",
                version=2,
                content="Need to pick up my shirt.\n\nAddendum:\nIt is blue.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 18, 0, tzinfo=UTC),
            ),
        ),
    )
    updated = Observation(
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=current.created_at,
        updated_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        revisions=(
            *externally_patched.revisions,
            ObservationRevision(
                id="obs_001:v3",
                observation="obs_001",
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
        "id": "obs_001:v3",
        "observation": "obs_001",
        "version": 3,
        "content": (
            "Need to pick up my shirt.\n\n"
            "Addendum:\n"
            "It is blue.\n\n"
            "Addendum:\n"
            "It is still blue."
        ),
        "content_format": "text/plain",
        "observed_at": "2026-04-06 18:00:00",
        "created_at": revision_payload["created_at"],
    }


def test_arcade_patch_carries_current_source_and_mentions() -> None:
    backend = _FakeArcadeBackend()
    repository = ArcadeObservationsRepository(
        runtime=backend,
        entity_id_factory=lambda: "ent_001",
    )
    source = Source(
        id="src_codex",
        source_type=SourceType.AGENT,
        label="codex",
        source_ref=None,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
    )
    current = Observation(
        id="obs_001",
        type=ObservationType.NOTE,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            ObservationRevision(
                id="obs_001:v1",
                observation="obs_001",
                version=1,
                content="Need to pick up my shirt.",
                content_format="text/plain",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                mentions=(
                    MentionedEntity(
                        id="ent_shirt",
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
                    {"id": "obs_002"},
                    {"id": "obs_003"},
                ]
            }

    blue_shirt = MentionedEntity(
        id="ent_shirt",
        type=EntityType.ITEM,
        label="blue shirt",
        resolution_status=ResolutionStatus.UNRESOLVED,
    )
    place = MentionedEntity(
        id="ent_place",
        type=EntityType.LOCATION,
        label="John's place",
        resolution_status=ResolutionStatus.UNRESOLVED,
    )
    now = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)
    observations = {
        "obs_001": Observation(
            id="obs_001",
            type=ObservationType.NOTE,
            created_at=now,
            updated_at=now,
            revisions=(
                ObservationRevision(
                    id="obs_001:v1",
                    observation="obs_001",
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
            id="obs_002",
            type=ObservationType.NOTE,
            created_at=now,
            updated_at=now,
            revisions=(
                ObservationRevision(
                    id="obs_002:v1",
                    observation="obs_002",
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
            id="obs_003",
            type=ObservationType.NOTE,
            created_at=now,
            updated_at=now,
            revisions=(
                ObservationRevision(
                    id="obs_003:v1",
                    observation="obs_003",
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

    assert [item.id for item in context.related_observations] == ["obs_002"]
    assert context.related_observations[0].score == 2.0
    query, params = backend.queries[0]
    assert "id <> :observation_id" in query
    assert params == {"observation_id": "obs_001"}


def test_arcade_repository_storage_initialized_requires_database_and_schema() -> None:
    class _Backend(_FakeArcadeBackend):
        def database_exists(self) -> bool:
            return False

    repository = ArcadeObservationsRepository(runtime=_Backend())

    assert repository.storage_initialized() is False
