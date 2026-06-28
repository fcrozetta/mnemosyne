from dataclasses import dataclass
from datetime import datetime

from app.models.access import ProjectionName, Purpose


@dataclass(frozen=True, slots=True)
class AccessAuditEvent:
    id: str
    created_at: datetime
    actor_user: str | None
    client_app: str
    service_identity: str
    purpose: Purpose
    projection: ProjectionName
    resource_type: str
    resource_id: str
    decision: str
    reason_code: str


__all__ = ["AccessAuditEvent"]
