from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
    SourceType,
    append_addendum,
    content_preview,
    create_revision_id,
    generate_entity_id,
    generate_observation_id,
    generate_source_id,
    merge_mentions,
    normalize_label,
    related_overlap,
    score_content_match,
    topic_matches,
    utc_now,
)
from app.repository.observations import ObservationsRepository
from app.storage.arcade import ArcadeRequestError, ArcadeStorageBackend
from app.storage.bootstrap import StorageBootstrapResult

_PATCH_RETRY_ATTEMPTS = 8


@dataclass(slots=True)
class ArcadeObservationsRepository(ObservationsRepository):
    """ArcadeDB-backed observation repository."""

    runtime: ArcadeStorageBackend
    observation_id_factory: Callable[[], str] = generate_observation_id
    entity_id_factory: Callable[[], str] = generate_entity_id
    source_id_factory: Callable[[], str] = generate_source_id

    def initialize_storage(self) -> StorageBootstrapResult:
        self.runtime.ensure_database()
        self.runtime.apply_default_schema()
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
        try:
            if not self.runtime.ready() or not self.runtime.database_exists():
                return False
            self.runtime.query("SELECT FROM Observation LIMIT 1")
            self.runtime.query("SELECT FROM Revision LIMIT 1")
        except ArcadeRequestError:
            return False
        return True

    def create_observation(self, observation: CreateObservationInput) -> Observation:
        observed_at = observation.observed_at or utc_now()
        created_at = observed_at
        observation_id = self.observation_id_factory()
        revision_id = create_revision_id(observation_id, 1)
        source = observation.source or SourceInput()
        source_id = self.source_id_factory()
        script, params = self._create_observation_script(
            observation=observation,
            observation_id=observation_id,
            revision_id=revision_id,
            source=source,
            source_id=source_id,
            observed_at=observed_at,
            created_at=created_at,
        )
        self.runtime.command(script, language="sqlscript", params=params)
        return self._get_observation(observation_id)

    def get_observation(self, observation_id: str) -> Observation:
        return self._get_observation(observation_id)

    def search_observations(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[ObservationSearchResult, ...]:
        result = self.runtime.query(
            "SELECT id, observation_type, "
            "updated_at, "
            "out('CurrentRevision')[0].version AS version, "
            "out('CurrentRevision')[0].content AS content, "
            "out('CurrentRevision')[0].observed_at AS observed_at "
            "FROM Observation WHERE id IS NOT NULL "
            "AND out('CurrentRevision')[0] IS NOT NULL"
        )
        matches: list[ObservationSearchResult] = []
        for row in _records(result):
            content = str(row.get("content", ""))
            score = score_content_match(content, query)
            if score <= 0:
                continue
            matches.append(
                ObservationSearchResult(
                    id=str(row["id"]),
                    type=ObservationType(str(row.get("observation_type", "note"))),
                    version=int(row["version"]),
                    content_preview=content_preview(content),
                    observed_at=_datetime(row["observed_at"]),
                    updated_at=_datetime(row["updated_at"]),
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
        normalized_topic = normalize_label(topic)
        if not normalized_topic:
            return ()

        topic_rows = _records(
            self.runtime.query(
                (
                    "SELECT id, normalized_label FROM Topic "
                    "WHERE normalized_label LIKE :topic_pattern"
                ),
                params={"topic_pattern": f"%{normalized_topic}%"},
            )
        )
        matches: dict[str, ObservationSearchResult] = {}
        for topic_row in topic_rows:
            topic_id = _optional_str(topic_row.get("id"))
            if topic_id is None:
                continue
            revision_rows = _records(
                self.runtime.query(
                    "SELECT expand(in('Mentions')) FROM Topic WHERE id = :topic_id",
                    params={"topic_id": topic_id},
                )
            )
            for revision_row in revision_rows:
                observation_id = _optional_str(revision_row.get("observation"))
                if observation_id is None or observation_id in matches:
                    continue
                observation = self._get_observation(observation_id)
                if observation.type != ObservationType.NOTE:
                    continue
                latest = observation.latest_revision
                if latest is None or not _revision_mentions_topic(latest, topic):
                    continue
                matches[observation.id] = ObservationSearchResult(
                    id=observation.id,
                    type=observation.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    updated_at=observation.updated_at,
                    score=1.0,
                )

        return tuple(
            sorted(
                matches.values(),
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
        current = self._get_observation(observation_id)
        last_error: ArcadeRequestError | None = None

        for _attempt in range(_PATCH_RETRY_ATTEMPTS):
            latest = current.latest_revision
            if latest is None:
                raise ObservationNotFoundError(observation_id)
            if (
                patch.addendum is None
                and not patch.mentions
                and patch.observed_at is None
            ):
                raise InvalidObservationPatchError(
                    "Patch request must include at least one change."
                )

            next_version = latest.version + 1
            observed_at = patch.observed_at or latest.observed_at
            created_at = utc_now()
            revision_id = create_revision_id(observation_id, next_version)
            script, params = self._patch_observation_script(
                current=current,
                latest=latest,
                patch=patch,
                revision_id=revision_id,
                next_version=next_version,
                observed_at=observed_at,
                created_at=created_at,
            )
            try:
                self.runtime.command(script, language="sqlscript", params=params)
            except ArcadeRequestError as exc:
                last_error = exc
                refreshed = self._get_observation(observation_id)
                if refreshed.version > latest.version:
                    current = refreshed
                    continue
                raise
            return self._get_observation(observation_id)

        if last_error is not None:
            raise last_error
        raise ObservationNotFoundError(observation_id)

    def get_observation_context(
        self,
        observation_id: str,
        limit: int = 5,
    ) -> ObservationContext:
        observation = self._get_observation(observation_id)
        rows = _records(
            self.runtime.query(
                (
                    "SELECT id FROM Observation "
                    "WHERE id IS NOT NULL AND id <> :observation_id"
                ),
                params={"observation_id": observation_id},
            )
        )
        related: list[ObservationSearchResult] = []
        for row in rows:
            candidate_id = str(row["id"])
            candidate = self._get_observation(candidate_id)
            latest = candidate.latest_revision
            if latest is None:
                continue
            score = float(related_overlap(observation, candidate))
            if score <= 0:
                continue
            related.append(
                ObservationSearchResult(
                    id=candidate.id,
                    type=candidate.type,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    updated_at=candidate.updated_at,
                    score=score,
                )
            )
        return ObservationContext(
            observation=observation,
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

    def _get_observation(self, observation_id: str) -> Observation:
        observation_rows = _records(
            self.runtime.query(
                "SELECT FROM Observation WHERE id = :observation_id",
                params={"observation_id": observation_id},
            )
        )
        if not observation_rows:
            raise ObservationNotFoundError(observation_id)

        row = observation_rows[0]
        revision_rows = _records(
            self.runtime.query(
                (
                    "SELECT FROM Revision WHERE observation = :observation_id "
                    "ORDER BY version ASC"
                ),
                params={"observation_id": observation_id},
            )
        )
        revisions = tuple(
            self._revision_from_row(revision_row) for revision_row in revision_rows
        )
        return Observation(
            id=str(row["id"]),
            type=ObservationType(str(row.get("observation_type", "note"))),
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            revisions=revisions,
        )

    def _revision_from_row(self, row: dict[str, Any]) -> ObservationRevision:
        revision_id = str(row["id"])
        mentions = tuple(
            self._entity_from_row(entity)
            for entity in _records(
                self.runtime.query(
                    (
                        "SELECT expand(out('Mentions')) FROM Revision "
                        "WHERE id = :revision_id"
                    ),
                    params={"revision_id": revision_id},
                )
            )
        )
        sources = _records(
            self.runtime.query(
                (
                    "SELECT expand(out('ObservedFrom')) FROM Revision "
                    "WHERE id = :revision_id"
                ),
                params={"revision_id": revision_id},
            )
        )
        source = self._source_from_row(sources[0]) if sources else None
        return ObservationRevision(
            id=revision_id,
            observation=str(row["observation"]),
            version=int(row["version"]),
            content=str(row["content"]),
            content_format=str(row.get("content_format", "text/plain")),
            observed_at=_datetime(row["observed_at"]),
            created_at=_datetime(row["created_at"]),
            mentions=mentions,
            source=source,
        )

    def _entity_from_row(self, row: dict[str, Any]) -> MentionedEntity:
        return MentionedEntity(
            id=str(row["id"]),
            type=EntityType(str(row["entity_type"])),
            label=str(row["label"]),
            resolution_status=ResolutionStatus(
                str(row.get("resolution_status", ResolutionStatus.UNRESOLVED.value))
            ),
        )

    def _source_from_row(self, row: dict[str, Any]) -> Source:
        return Source(
            id=str(row["id"]),
            source_type=SourceType(str(row["source_type"])),
            label=_optional_str(row.get("label")),
            source_ref=_optional_str(row.get("source_ref")),
            created_at=_datetime(row["created_at"]),
        )

    def _create_observation_script(
        self,
        *,
        observation: CreateObservationInput,
        observation_id: str,
        revision_id: str,
        source: SourceInput,
        source_id: str,
        observed_at: datetime,
        created_at: datetime,
    ) -> tuple[str, dict[str, object]]:
        lines = [
            "BEGIN;",
            (
                f"CREATE VERTEX {_observation_type(observation.type)} "
                "CONTENT :observation;"
            ),
            "CREATE VERTEX Revision CONTENT :revision;",
            (
                "UPDATE Source SET id = ifnull(id, :source_id), "
                "source_type = :source_type, label = :source_label, "
                "source_ref = :source_ref, "
                "created_at = ifnull(created_at, :created_at) "
                "UPSERT WHERE source_type = :source_type "
                "AND label <=> :source_label AND source_ref <=> :source_ref;"
            ),
        ]
        params: dict[str, object] = {
            "observation_id": observation_id,
            "revision_id": revision_id,
            "source_id": source_id,
            "source_type": source.source_type.value,
            "source_label": source.label,
            "source_ref": source.source_ref,
            "created_at": _datetime_value(created_at),
            "observation": {
                "id": observation_id,
                "observation_type": observation.type.value,
                "current_version": 1,
                "created_at": _datetime_value(created_at),
                "updated_at": _datetime_value(created_at),
                "lifecycle_status": "active",
            },
            "revision": {
                "id": revision_id,
                "observation": observation_id,
                "version": 1,
                "content": observation.content,
                "content_format": observation.content_format,
                "observed_at": _datetime_value(observed_at),
                "created_at": _datetime_value(created_at),
            },
        }
        lines.extend(_observation_revision_edges())
        lines.append(
            "CREATE EDGE ObservedFrom FROM "
            "(SELECT FROM Revision WHERE id = :revision_id) TO "
            "(SELECT FROM Source WHERE source_type = :source_type "
            "AND label <=> :source_label AND source_ref <=> :source_ref) "
            "IF NOT EXISTS CONTENT :observed_from;"
        )
        params["observed_from"] = {
            "writer": source.writer,
            "session_id": source.session_id,
            "observed_channel": source.observed_channel,
            "created_at": _datetime_value(created_at),
        }
        for index, mention in enumerate(observation.mentions):
            lines.extend(
                self._mention_sql(
                    mention,
                    index=index,
                    created_at=created_at,
                )
            )
            params.update(
                self._mention_params(
                    mention,
                    index=index,
                    created_at=created_at,
                )
            )
        lines.append("COMMIT RETRY 10;")
        return "\n".join(lines), params

    def _patch_observation_script(
        self,
        *,
        current: Observation,
        latest: ObservationRevision,
        patch: PatchObservationInput,
        revision_id: str,
        next_version: int,
        observed_at: datetime,
        created_at: datetime,
    ) -> tuple[str, dict[str, object]]:
        lines = [
            "BEGIN;",
            (
                "UPDATE Observation SET current_version = :next_version, "
                "updated_at = :updated_at WHERE id = :observation_id "
                ";"
            ),
            "CREATE VERTEX Revision CONTENT :revision;",
            _edge_has_revision(),
            (
                "CREATE EDGE PreviousRevision FROM "
                "(SELECT FROM Revision WHERE id = :revision_id) TO "
                "(SELECT FROM Revision WHERE id = :previous_revision_id) "
                "IF NOT EXISTS;"
            ),
            (
                "DELETE FROM CurrentRevision WHERE "
                "`@out` IN (SELECT FROM Observation "
                "WHERE id = :observation_id);"
            ),
            _edge_current_revision(),
        ]
        params: dict[str, object] = {
            "observation_id": current.id,
            "next_version": next_version,
            "updated_at": _datetime_value(created_at),
            "revision_id": revision_id,
            "previous_revision_id": latest.id,
            "revision": {
                "id": revision_id,
                "observation": current.id,
                "version": next_version,
                "content": append_addendum(latest.content, patch.addendum),
                "content_format": latest.content_format,
                "observed_at": _datetime_value(observed_at),
                "created_at": _datetime_value(created_at),
            },
        }
        if latest.source is not None:
            params.update(
                {
                    "source_id": latest.source.id,
                    "observed_from": {
                        "writer": None,
                        "session_id": None,
                        "observed_channel": None,
                        "created_at": _datetime_value(created_at),
                    },
                }
            )
            lines.append(
                "CREATE EDGE ObservedFrom FROM "
                "(SELECT FROM Revision WHERE id = :revision_id) TO "
                "(SELECT FROM Source WHERE id = :source_id) "
                "IF NOT EXISTS CONTENT :observed_from;"
            )

        merged_mentions = merge_mentions(
            latest.mentions,
            (
                MentionedEntity(
                    id=self.entity_id_factory(),
                    type=mention.type,
                    label=mention.label,
                    resolution_status=ResolutionStatus.UNRESOLVED,
                )
                for mention in patch.mentions
            ),
        )
        for index, mention in enumerate(merged_mentions):
            lines.extend(
                self._mentioned_entity_sql(
                    mention,
                    index=index,
                    created_at=created_at,
                )
            )
            params.update(
                self._mentioned_entity_params(
                    mention,
                    index=index,
                    created_at=created_at,
                )
            )
        lines.append("COMMIT RETRY 10;")
        return "\n".join(lines), params

    def _mention_sql(
        self,
        mention: EntityMentionInput,
        *,
        index: int,
        created_at: datetime,
    ) -> tuple[str, str]:
        del created_at
        return (
            (
                f"UPDATE {_entity_type(mention.type)} SET "
                f"id = ifnull(id, :entity_id_{index}), "
                f"entity_type = :entity_type_{index}, "
                f"label = :entity_label_{index}, "
                f"normalized_label = :normalized_label_{index}, "
                f"resolution_status = 'unresolved', "
                f"created_at = ifnull(created_at, :created_at), "
                f"updated_at = :created_at UPSERT WHERE "
                f"entity_type = :entity_type_{index} "
                f"AND normalized_label = :normalized_label_{index};"
            ),
            (
                "CREATE EDGE Mentions FROM "
                "(SELECT FROM Revision WHERE id = :revision_id) TO "
                f"(SELECT FROM Entity WHERE entity_type = :entity_type_{index} "
                f"AND normalized_label = :normalized_label_{index}) "
                f"IF NOT EXISTS CONTENT :mention_edge_{index};"
            ),
        )

    def _mention_params(
        self,
        mention: EntityMentionInput,
        *,
        index: int,
        created_at: datetime,
    ) -> dict[str, object]:
        return {
            f"entity_id_{index}": self.entity_id_factory(),
            f"entity_type_{index}": mention.type.value,
            f"entity_label_{index}": mention.label,
            f"normalized_label_{index}": mention.normalized_label,
            f"mention_edge_{index}": {
                "origin": mention.origin,
                "confidence": mention.confidence,
                "created_at": _datetime_value(created_at),
            },
        }

    def _mentioned_entity_sql(
        self,
        mention: MentionedEntity,
        *,
        index: int,
        created_at: datetime,
    ) -> tuple[str, str]:
        del created_at
        return (
            (
                f"UPDATE {_entity_type(mention.type)} SET "
                f"id = ifnull(id, :entity_id_{index}), "
                f"entity_type = :entity_type_{index}, "
                f"label = :entity_label_{index}, "
                f"normalized_label = :normalized_label_{index}, "
                f"resolution_status = :resolution_status_{index}, "
                f"created_at = ifnull(created_at, :created_at), "
                f"updated_at = :created_at UPSERT WHERE "
                f"entity_type = :entity_type_{index} "
                f"AND normalized_label = :normalized_label_{index};"
            ),
            (
                "CREATE EDGE Mentions FROM "
                "(SELECT FROM Revision WHERE id = :revision_id) TO "
                f"(SELECT FROM Entity WHERE entity_type = :entity_type_{index} "
                f"AND normalized_label = :normalized_label_{index}) "
                f"IF NOT EXISTS CONTENT :mention_edge_{index};"
            ),
        )

    def _mentioned_entity_params(
        self,
        mention: MentionedEntity,
        *,
        index: int,
        created_at: datetime,
    ) -> dict[str, object]:
        return {
            f"entity_id_{index}": mention.id,
            f"entity_type_{index}": mention.type.value,
            f"entity_label_{index}": mention.label,
            f"normalized_label_{index}": mention.normalized_label,
            f"resolution_status_{index}": mention.resolution_status.value,
            f"mention_edge_{index}": {
                "origin": "carried_forward",
                "confidence": None,
                "created_at": _datetime_value(created_at),
            },
        }


def _observation_revision_edges() -> tuple[str, str]:
    return (_edge_has_revision(), _edge_current_revision())


def _edge_has_revision() -> str:
    return (
        "CREATE EDGE HasRevision FROM "
        "(SELECT FROM Observation WHERE id = :observation_id) TO "
        "(SELECT FROM Revision WHERE id = :revision_id) IF NOT EXISTS;"
    )


def _edge_current_revision() -> str:
    return (
        "CREATE EDGE CurrentRevision FROM "
        "(SELECT FROM Observation WHERE id = :observation_id) TO "
        "(SELECT FROM Revision WHERE id = :revision_id) IF NOT EXISTS;"
    )


def _observation_type(observation_type: ObservationType) -> str:
    return {
        ObservationType.NOTE: "Note",
        ObservationType.DOCUMENT: "DocumentObservation",
        ObservationType.MESSAGE: "MessageObservation",
    }[observation_type]


def _entity_type(entity_type: EntityType) -> str:
    return {
        EntityType.PERSON: "Person",
        EntityType.LOCATION: "Location",
        EntityType.ITEM: "Item",
        EntityType.TOPIC: "Topic",
        EntityType.OTHER: "UnknownEntity",
    }[entity_type]


def _records(result: object) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        value = result.get("result", [])
    else:
        value = result
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _datetime_value(value: datetime) -> str:
    # ArcadeDB DATETIME columns silently drop SET assignments when given an
    # ISO 8601 string with a `T` separator or `Z` suffix. The accepted wire
    # format is `yyyy-MM-dd HH:mm:ss` (always UTC, since this layer normalizes
    # via .astimezone(UTC) first).
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _revision_mentions_topic(revision: ObservationRevision, topic: str) -> bool:
    return any(
        mention.type == EntityType.TOPIC and topic_matches(mention.label, topic)
        for mention in revision.mentions
    )


__all__ = ["ArcadeObservationsRepository"]
