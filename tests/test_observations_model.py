from __future__ import annotations

from datetime import UTC, datetime

from app.models.observations import (
    EntityMentionInput,
    EntityType,
    Observation,
    ObservationRevision,
    ObservationType,
    create_revision_id,
)


def test_revision_id_is_scoped_to_observation_and_version() -> None:
    assert create_revision_id("obs_01ABC", 2) == "obs_01ABC:v2"


def test_entity_labels_normalize_for_lookup() -> None:
    mention = EntityMentionInput(
        type=EntityType.LOCATION,
        label="  John's   Place ",
    )

    assert mention.normalized_label == "john's place"


def test_observation_latest_revision_returns_highest_version() -> None:
    created_at = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
    observation = Observation(
        id="obs_01ABC",
        type=ObservationType.NOTE,
        created_at=created_at,
        updated_at=created_at,
        revisions=(
            ObservationRevision(
                id="obs_01ABC:v1",
                observation="obs_01ABC",
                version=1,
                content="one",
                content_format="text/plain",
                observed_at=created_at,
                created_at=created_at,
            ),
            ObservationRevision(
                id="obs_01ABC:v2",
                observation="obs_01ABC",
                version=2,
                content="two",
                content_format="text/plain",
                observed_at=created_at,
                created_at=created_at,
            ),
        ),
    )

    assert observation.latest_revision is not None
    assert observation.latest_revision.version == 2
