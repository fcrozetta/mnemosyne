from app.models.access import AccessContext, ProjectionName, Purpose
from app.service.access_policy import PolicyDecision
from app.service.audit import ArcadeAccessAuditService, InMemoryAccessAuditService
from app.storage.arcade import ArcadeStorageBackend


def _context() -> AccessContext:
    return AccessContext(
        actor_user="Sample User",
        client_app="finance",
        service_identity="finance-api",
        purpose=Purpose.ACCOUNTING,
        scopes=frozenset({"mnemosyne.query"}),
        requested_projection=ProjectionName.ACCOUNTING_VIEW,
    )


def test_in_memory_audit_records_redacted_decision() -> None:
    service = InMemoryAccessAuditService(audit_id_factory=lambda: "aud_1")

    event = service.record(
        context=_context(),
        resource_type="observation",
        resource_id="obs_1",
        decision=PolicyDecision(
            allowed=True,
            redacted=True,
            reason_code="health_accounting_projection_allowed",
        ),
    )

    assert event.id == "aud_1"
    assert event.decision == "redacted"
    assert event.reason_code == "health_accounting_projection_allowed"
    assert service.list_events() == (event,)


def test_arcade_audit_writes_access_audit_event_vertex() -> None:
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    class _FakeBackend(ArcadeStorageBackend):
        def command(
            self,
            command: str,
            *,
            language: str = "sql",
            params: dict[str, object] | None = None,
        ) -> object:
            calls.append((command, language, params))
            return {"result": "ok"}

    service = ArcadeAccessAuditService(
        runtime=_FakeBackend(
            base_url="http://127.0.0.1:2480",
            database="mnemosyne",
            username="root",
            password="mnemosyne-root",
        ),
        audit_id_factory=lambda: "aud_1",
    )

    event = service.record(
        context=_context(),
        resource_type="observation",
        resource_id="obs_1",
        decision=PolicyDecision(
            allowed=False,
            reason_code="health_context_denied_for_accounting",
        ),
    )

    assert event.decision == "deny"
    assert calls[0][0] == "CREATE VERTEX AccessAuditEvent CONTENT :event;"
    assert calls[0][1] == "sqlscript"
    assert calls[0][2] is not None
    payload = calls[0][2]["event"]
    assert isinstance(payload, dict)
    assert payload["id"] == "aud_1"
    assert payload["client_app"] == "finance"
    assert payload["projection"] == "accounting_view"
    assert payload["decision"] == "deny"
