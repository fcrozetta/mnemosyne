from __future__ import annotations

import re
import secrets
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class ObservationType(StrEnum):
    NOTE = "note"
    DOCUMENT = "document"
    MESSAGE = "message"


class EntityType(StrEnum):
    PERSON = "person"
    LOCATION = "location"
    ITEM = "item"
    TOPIC = "topic"
    OTHER = "other"


class ResolutionStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    MERGED = "merged"
    ARCHIVED = "archived"


class SourceType(StrEnum):
    USER = "user"
    AGENT = "agent"
    IMPORT = "import"
    INTEGRATION = "integration"
    SYSTEM = "system"


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ClaimStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class EntityMentionInput:
    type: EntityType
    label: str
    origin: str = "user_supplied"
    confidence: float | None = None

    @property
    def normalized_label(self) -> str:
        return normalize_label(self.label)

    @property
    def identity(self) -> tuple[str, str]:
        return (self.type.value, self.normalized_label)


@dataclass(frozen=True, slots=True)
class MentionedEntity:
    id: str
    type: EntityType
    label: str
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED

    @property
    def normalized_label(self) -> str:
        return normalize_label(self.label)

    @property
    def identity(self) -> tuple[str, str]:
        return (self.type.value, self.normalized_label)


@dataclass(frozen=True, slots=True)
class SourceInput:
    source_type: SourceType = SourceType.AGENT
    label: str | None = None
    source_ref: str | None = None
    writer: str | None = None
    session_id: str | None = None
    observed_channel: str | None = None

    @property
    def identity(self) -> tuple[str, str | None, str | None]:
        return (self.source_type.value, self.label, self.source_ref)


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    source_type: SourceType
    label: str | None
    source_ref: str | None
    created_at: datetime

    @property
    def identity(self) -> tuple[str, str | None, str | None]:
        return (self.source_type.value, self.label, self.source_ref)


@dataclass(frozen=True, slots=True)
class ObservationRevision:
    id: str
    observation: str
    version: int
    content: str
    content_format: str
    observed_at: datetime
    created_at: datetime
    mentions: tuple[MentionedEntity, ...] = ()
    source: Source | None = None


@dataclass(frozen=True, slots=True)
class Observation:
    id: str
    type: ObservationType
    created_at: datetime
    updated_at: datetime
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    revisions: tuple[ObservationRevision, ...] = ()

    @property
    def latest_revision(self) -> ObservationRevision | None:
        if not self.revisions:
            return None
        return max(self.revisions, key=lambda revision: revision.version)

    @property
    def version(self) -> int:
        latest = self.latest_revision
        return latest.version if latest is not None else 0


@dataclass(frozen=True, slots=True)
class CreateObservationInput:
    type: ObservationType
    content: str
    mentions: tuple[EntityMentionInput, ...] = ()
    observed_at: datetime | None = None
    source: SourceInput | None = None
    content_format: str = "text/plain"


@dataclass(frozen=True, slots=True)
class PatchObservationInput:
    addendum: str | None = None
    mentions: tuple[EntityMentionInput, ...] = ()
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ObservationSearchResult:
    id: str
    type: ObservationType
    version: int
    content_preview: str
    observed_at: datetime
    updated_at: datetime
    score: float


@dataclass(frozen=True, slots=True)
class ObservationContext:
    observation: Observation
    related_observations: tuple[ObservationSearchResult, ...]


class ObservationNotFoundError(LookupError):
    def __init__(self, id: str) -> None:
        super().__init__(f"Observation {id!r} was not found.")
        self.id = id


class InvalidObservationPatchError(ValueError):
    pass


class InvalidObservationRequestError(ValueError):
    def __init__(self, error: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.field = field


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_label(label: str) -> str:
    return " ".join(label.split()).lower()


def create_revision_id(observation_id: str, version: int) -> str:
    return f"{observation_id}:v{version}"


def generate_observation_id() -> str:
    return generate_prefixed_ulid("obs")


def generate_entity_id() -> str:
    return generate_prefixed_ulid("ent")


def generate_claim_id() -> str:
    return generate_prefixed_ulid("clm")


def generate_source_id() -> str:
    return generate_prefixed_ulid("src")


def generate_prefixed_ulid(prefix: str) -> str:
    timestamp_ms = int(time.time() * 1000)
    value = (timestamp_ms << 80) | secrets.randbits(80)
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD_ALPHABET[value & 0x1F])
        value >>= 5
    return f"{prefix}_{''.join(reversed(chars))}"


def append_addendum(content: str, addendum: str | None) -> str:
    if addendum is None:
        return content
    return f"{content}\n\nAddendum:\n{addendum}"


def content_preview(content: str, limit: int = 120) -> str:
    preview = content.splitlines()[0].strip()
    if len(preview) <= limit:
        return preview
    return preview[: limit - 1].rstrip() + "..."


def score_content_match(content: str, query: str) -> float:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return 0.0

    normalized_content = content.casefold()
    if normalized_query in normalized_content:
        return 1.0

    query_terms = tuple(term for term in re.split(r"\s+", normalized_query) if term)
    if not query_terms:
        return 0.0

    matches = sum(1 for term in query_terms if term in normalized_content)
    return matches / len(query_terms)


def topic_matches(label: str, query: str) -> bool:
    normalized_query = normalize_label(query)
    if not normalized_query:
        return False
    return normalized_query in normalize_label(label)


def merge_mentions(
    existing: Iterable[MentionedEntity],
    additions: Iterable[MentionedEntity],
) -> tuple[MentionedEntity, ...]:
    merged: list[MentionedEntity] = []
    seen: set[tuple[str, str]] = set()

    for mention in (*tuple(existing), *tuple(additions)):
        if mention.identity in seen:
            continue
        merged.append(mention)
        seen.add(mention.identity)

    return tuple(merged)


def related_overlap(observation: Observation, other: Observation) -> int:
    latest = observation.latest_revision
    other_latest = other.latest_revision
    if latest is None or other_latest is None:
        return 0

    mentions = {mention.identity for mention in latest.mentions}
    other_mentions = {mention.identity for mention in other_latest.mentions}
    return len(mentions & other_mentions)


__all__ = [
    "ClaimStatus",
    "CreateObservationInput",
    "EntityMentionInput",
    "EntityType",
    "InvalidObservationPatchError",
    "InvalidObservationRequestError",
    "LifecycleStatus",
    "MentionedEntity",
    "Observation",
    "ObservationContext",
    "ObservationNotFoundError",
    "ObservationRevision",
    "ObservationSearchResult",
    "ObservationType",
    "PatchObservationInput",
    "ResolutionStatus",
    "Source",
    "SourceInput",
    "SourceType",
    "append_addendum",
    "content_preview",
    "create_revision_id",
    "generate_claim_id",
    "generate_entity_id",
    "generate_observation_id",
    "generate_prefixed_ulid",
    "generate_source_id",
    "merge_mentions",
    "normalize_label",
    "related_overlap",
    "score_content_match",
    "topic_matches",
    "utc_now",
]
