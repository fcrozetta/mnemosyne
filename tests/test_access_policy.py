from datetime import UTC, datetime

from app.models.access import (
    AccessContext,
    Domain,
    ProjectionName,
    Purpose,
    Sensitivity,
)
from app.models.observations import ObservationRevision
from app.service.access_policy import AccessPolicy


def _revision(content: str, sensitivity: Sensitivity = Sensitivity.CONFIDENTIAL):
    now = datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
    return ObservationRevision(
        id="obs_1:v1",
        observation="obs_1",
        version=1,
        content=content,
        content_format="text/plain",
        observed_at=now,
        created_at=now,
        domain=Domain.HEALTH,
        sensitivity=sensitivity,
        subject="Fernando",
        allowed_purposes=(Purpose.ACCOUNTING, Purpose.MEDICATION_MANAGEMENT),
    )


def test_access_context_defaults_are_conservative() -> None:
    context = AccessContext()

    assert context.actor_user is None
    assert context.client_app == "unknown"
    assert context.service_identity == "unknown"
    assert context.purpose == Purpose.RECALL
    assert context.scopes == frozenset()
    assert context.roles == frozenset()
    assert context.requested_projection == ProjectionName.OBSERVATION_SUMMARY


def test_domain_and_sensitivity_values_are_stable() -> None:
    assert Domain.HEALTH.value == "health"
    assert Domain.FINANCE.value == "finance"
    assert Sensitivity.CONFIDENTIAL.value == "confidential"
    assert Sensitivity.RESTRICTED.value == "restricted"


def test_finance_accounting_can_receive_safe_health_purchase_projection() -> None:
    context = AccessContext(
        client_app="finance",
        service_identity="finance-api",
        purpose=Purpose.ACCOUNTING,
        scopes=frozenset({"mnemosyne.query", "finance.read"}),
        requested_projection=ProjectionName.ACCOUNTING_VIEW,
    )

    decision = AccessPolicy().can_disclose_revision(
        context,
        _revision("Bought Losartan medication at Pharmacy X."),
    )

    assert decision.allowed is True
    assert decision.reason_code == "health_accounting_projection_allowed"


def test_finance_accounting_cannot_receive_family_medical_history() -> None:
    context = AccessContext(
        client_app="finance",
        service_identity="finance-api",
        purpose=Purpose.ACCOUNTING,
        scopes=frozenset({"mnemosyne.query", "finance.read"}),
        requested_projection=ProjectionName.ACCOUNTING_VIEW,
    )

    decision = AccessPolicy().can_disclose_revision(
        context,
        _revision("Family history of hypertension."),
    )

    assert decision.allowed is False
    assert decision.reason_code == "health_context_denied_for_accounting"


def test_raw_projection_requires_raw_scope_or_admin() -> None:
    context = AccessContext(
        client_app="finance",
        service_identity="finance-api",
        purpose=Purpose.ACCOUNTING,
        scopes=frozenset({"mnemosyne.query"}),
        requested_projection=ProjectionName.RAW_OBSERVATION,
    )

    decision = AccessPolicy().can_disclose_revision(
        context,
        _revision("Bought medicine."),
    )

    assert decision.allowed is False
    assert decision.reason_code == "raw_projection_requires_scope"
