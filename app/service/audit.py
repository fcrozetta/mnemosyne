from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.access import AccessContext
from app.models.audit import AccessAuditEvent
from app.models.observations import generate_prefixed_ulid, utc_now
from app.service.access_policy import PolicyDecision
from app.storage.arcade import ArcadeStorageBackend


def generate_audit_id() -> str:
    return generate_prefixed_ulid("aud")


def _decision_name(decision: PolicyDecision) -> str:
    if decision.allowed and decision.redacted:
        return "redacted"
    if decision.allowed:
        return "allow"
    return "deny"


def _event_from_decision(
    *,
    audit_id: str,
    context: AccessContext,
    resource_type: str,
    resource_id: str,
    decision: PolicyDecision,
    created_at: datetime,
) -> AccessAuditEvent:
    return AccessAuditEvent(
        id=audit_id,
        created_at=created_at,
        actor_user=context.actor_user,
        client_app=context.client_app,
        service_identity=context.service_identity,
        purpose=context.purpose,
        projection=context.requested_projection,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=_decision_name(decision),
        reason_code=decision.reason_code,
    )


def _datetime_value(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


@dataclass(slots=True)
class InMemoryAccessAuditService:
    audit_id_factory: Callable[[], str] = generate_audit_id
    events: list[AccessAuditEvent] = field(default_factory=list)

    def record(
        self,
        *,
        context: AccessContext,
        resource_type: str,
        resource_id: str,
        decision: PolicyDecision,
    ) -> AccessAuditEvent:
        event = _event_from_decision(
            audit_id=self.audit_id_factory(),
            context=context,
            resource_type=resource_type,
            resource_id=resource_id,
            decision=decision,
            created_at=utc_now(),
        )
        self.events.append(event)
        return event

    def list_events(self) -> tuple[AccessAuditEvent, ...]:
        return tuple(self.events)


@dataclass(slots=True)
class ArcadeAccessAuditService:
    runtime: ArcadeStorageBackend
    audit_id_factory: Callable[[], str] = generate_audit_id

    def record(
        self,
        *,
        context: AccessContext,
        resource_type: str,
        resource_id: str,
        decision: PolicyDecision,
    ) -> AccessAuditEvent:
        event = _event_from_decision(
            audit_id=self.audit_id_factory(),
            context=context,
            resource_type=resource_type,
            resource_id=resource_id,
            decision=decision,
            created_at=utc_now(),
        )
        self.runtime.command(
            "CREATE VERTEX AccessAuditEvent CONTENT :event;",
            language="sqlscript",
            params={
                "event": {
                    "id": event.id,
                    "created_at": _datetime_value(event.created_at),
                    "actor_user": event.actor_user,
                    "client_app": event.client_app,
                    "service_identity": event.service_identity,
                    "purpose": event.purpose.value,
                    "projection": event.projection.value,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "decision": event.decision,
                    "reason_code": event.reason_code,
                }
            },
        )
        return event

    def list_events(self) -> tuple[AccessAuditEvent, ...]:
        return ()


__all__ = [
    "ArcadeAccessAuditService",
    "InMemoryAccessAuditService",
    "generate_audit_id",
]
