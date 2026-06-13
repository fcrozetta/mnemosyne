from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from app.models.observations import (
    CreateObservationInput,
    EntityMentionInput,
    EntityType,
    ObservationType,
    PatchObservationInput,
    SourceInput,
    SourceType,
)
from app.repository.observations_in_memory import InMemoryObservationsRepository


def _ids(*values: str) -> Iterator[str]:
    yield from values


def test_create_patch_search_and_context_flow() -> None:
    observation_ids = _ids("obs_001", "obs_002")
    entity_ids = _ids("ent_shirt", "ent_place")
    source_ids = _ids("src_codex")
    repository = InMemoryObservationsRepository(
        observation_id_factory=lambda: next(observation_ids),
        entity_id_factory=lambda: next(entity_ids),
        source_id_factory=lambda: next(source_ids),
    )
    repository.initialize_storage()

    created = repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="Need to pick up my shirt.",
            mentions=(
                EntityMentionInput(type=EntityType.ITEM, label="blue shirt"),
                EntityMentionInput(type=EntityType.LOCATION, label="John's place"),
            ),
            observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            source=SourceInput(source_type=SourceType.AGENT, label="codex"),
        )
    )

    assert created.id == "obs_001"
    assert created.type == ObservationType.NOTE
    assert created.version == 1
    assert created.latest_revision is not None
    assert created.latest_revision.id == "obs_001:v1"
    assert created.latest_revision.source is not None
    assert created.latest_revision.source.id == "src_codex"
    assert [mention.id for mention in created.latest_revision.mentions] == [
        "ent_shirt",
        "ent_place",
    ]

    second = repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="Blue PME Oxford shirt is at John's place.",
            mentions=(
                EntityMentionInput(type=EntityType.ITEM, label="blue shirt"),
                EntityMentionInput(type=EntityType.LOCATION, label="John's place"),
            ),
            observed_at=datetime(2026, 4, 5, 9, 30, tzinfo=UTC),
            source=SourceInput(source_type=SourceType.AGENT, label="codex"),
        )
    )
    assert second.id == "obs_002"
    assert second.latest_revision is not None
    assert [mention.id for mention in second.latest_revision.mentions] == [
        "ent_shirt",
        "ent_place",
    ]

    patched = repository.patch_observation(
        "obs_001",
        PatchObservationInput(
            addendum="It is the blue one.",
            mentions=(
                EntityMentionInput(type=EntityType.LOCATION, label="John's place"),
            ),
            observed_at=datetime(2026, 4, 6, 18, 5, tzinfo=UTC),
        ),
    )

    assert patched.version == 2
    assert patched.latest_revision is not None
    assert patched.latest_revision.id == "obs_001:v2"
    assert patched.latest_revision.content == (
        "Need to pick up my shirt.\n\nAddendum:\nIt is the blue one."
    )
    assert patched.latest_revision.observed_at == datetime(
        2026,
        4,
        6,
        18,
        5,
        tzinfo=UTC,
    )
    assert [mention.identity for mention in patched.latest_revision.mentions] == [
        ("item", "blue shirt"),
        ("location", "john's place"),
    ]

    search = repository.search_observations("blue", limit=5)
    assert [(item.id, item.version, item.score) for item in search] == [
        ("obs_001", 2, 1.0),
        ("obs_002", 1, 1.0),
    ]

    context = repository.get_observation_context("obs_001")
    assert context.observation.id == "obs_001"
    assert [item.id for item in context.related_observations] == [
        "obs_002"
    ]
    assert context.related_observations[0].score == 2.0


def test_recent_by_topic_matches_partial_topic_and_latest_versions() -> None:
    observation_ids = _ids("obs_001", "obs_002", "obs_003")
    entity_ids = _ids("ent_style", "ent_lint", "ent_schema")
    repository = InMemoryObservationsRepository(
        observation_id_factory=lambda: next(observation_ids),
        entity_id_factory=lambda: next(entity_ids),
        source_id_factory=lambda: "src_unused",
    )
    repository.initialize_storage()

    first = repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="Prefer pathlib for local file handling.",
            mentions=(
                EntityMentionInput(
                    type=EntityType.TOPIC,
                    label="coding:fcrozetta:python:coding-style",
                ),
            ),
            observed_at=datetime(2026, 4, 6, 10, 0, tzinfo=UTC),
        )
    )
    second = repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="Ruff should keep imports sorted.",
            mentions=(
                EntityMentionInput(
                    type=EntityType.TOPIC,
                    label="coding:fcrozetta:python:linting",
                ),
            ),
            observed_at=datetime(2026, 4, 5, 10, 0, tzinfo=UTC),
        )
    )
    repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="ArcadeDB schema changes need smoke tests.",
            mentions=(
                EntityMentionInput(
                    type=EntityType.TOPIC,
                    label="coding:fcrozetta:arcadedb:schema",
                ),
            ),
            observed_at=datetime(2026, 4, 7, 10, 0, tzinfo=UTC),
        )
    )
    repository.patch_observation(
        second.id,
        PatchObservationInput(
            addendum="This is the current version.",
            observed_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
        ),
    )

    recent = repository.recent_observations_by_topic(
        "coding:fcrozetta:python",
        limit=5,
    )

    assert [(item.id, item.version) for item in recent] == [
        (second.id, 2),
        (first.id, 1),
    ]

    partial = repository.recent_observations_by_topic("coding-style", limit=5)

    assert [(item.id, item.version) for item in partial] == [(first.id, 1)]


def test_patch_increments_version_internally() -> None:
    repository = InMemoryObservationsRepository(
        observation_id_factory=lambda: "obs_001",
        entity_id_factory=lambda: "ent_unused",
        source_id_factory=lambda: "src_unused",
    )
    repository.initialize_storage()
    repository.create_observation(
        CreateObservationInput(
            type=ObservationType.NOTE,
            content="Need to pick up my shirt.",
        )
    )
    first_patch = repository.patch_observation(
        "obs_001",
        PatchObservationInput(addendum="It is blue."),
    )
    second_patch = repository.patch_observation(
        "obs_001",
        PatchObservationInput(addendum="It is still blue."),
    )

    assert first_patch.version == 2
    assert second_patch.version == 3
