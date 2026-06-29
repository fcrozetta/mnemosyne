from dataclasses import dataclass, field
from enum import StrEnum


class Domain(StrEnum):
    GENERAL = "general"
    HEALTH = "health"
    FINANCE = "finance"
    DOCUMENTS = "documents"
    IDENTITY = "identity"
    HOUSEHOLD = "household"
    SHOPPING = "shopping"
    SYSTEM = "system"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    PERSONAL = "personal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


class Purpose(StrEnum):
    RECALL = "recall"
    ACCOUNTING = "accounting"
    MEDICATION_MANAGEMENT = "medication_management"
    REIMBURSEMENT = "reimbursement"
    REMINDER = "reminder"
    CARE_COORDINATION = "care_coordination"
    IMPORT = "import"
    ADMINISTRATION = "administration"


class RequesterKind(StrEnum):
    USER = "user"
    SERVICE_ACCOUNT = "service_account"
    APP = "app"
    AGENT = "agent"
    BACKGROUND_JOB = "background_job"


class ProjectionName(StrEnum):
    RAW_OBSERVATION = "raw_observation"
    OBSERVATION_SUMMARY = "observation_summary"
    ACCOUNTING_VIEW = "accounting_view"
    HEALTH_CARE_VIEW = "health_care_view"


@dataclass(frozen=True, slots=True)
class AccessContext:
    actor_user: str | None = None
    client_app: str = "unknown"
    service_identity: str = "unknown"
    requester_kind: RequesterKind = RequesterKind.APP
    purpose: Purpose = Purpose.RECALL
    scopes: frozenset[str] = field(default_factory=frozenset)
    roles: frozenset[str] = field(default_factory=frozenset)
    requested_projection: ProjectionName = ProjectionName.OBSERVATION_SUMMARY


__all__ = [
    "AccessContext",
    "Domain",
    "ProjectionName",
    "Purpose",
    "RequesterKind",
    "Sensitivity",
]
