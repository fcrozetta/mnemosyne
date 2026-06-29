from dataclasses import dataclass

from app.models.access import (
    AccessContext,
    Domain,
    ProjectionName,
    Purpose,
    Sensitivity,
)
from app.models.entities import CreateEntityInput, EntityRecord
from app.models.observations import ObservationRevision

_SENSITIVE_HEALTH_DENY_MARKERS = (
    "family history",
    "genetic risk",
    "diagnosis",
    "doctor note",
    "clinical note",
    "inferred condition",
)

_CLINICAL_REDACTION_MARKERS = (
    "dosage",
    "dose",
    "frequency",
    "prescription",
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    redacted: bool = False


class AccessPolicy:
    def can_query_mnemosyne(self, context: AccessContext) -> PolicyDecision:
        if "mnemosyne.query" not in context.scopes and "admin" not in context.roles:
            return PolicyDecision(False, "missing_mnemosyne_query_scope")
        return PolicyDecision(True, "query_scope_allowed")

    def can_mutate_observation(
        self,
        context: AccessContext,
        revision: ObservationRevision,
    ) -> PolicyDecision:
        del revision
        query_decision = self.can_query_mnemosyne(context)
        if not query_decision.allowed:
            return query_decision
        if "mnemosyne.write" not in context.scopes and "admin" not in context.roles:
            return PolicyDecision(False, "missing_mnemosyne_write_scope")
        return PolicyDecision(True, "write_scope_allowed")

    def can_mutate_entity(
        self,
        context: AccessContext,
        entity: CreateEntityInput,
    ) -> PolicyDecision:
        del entity
        query_decision = self.can_query_mnemosyne(context)
        if not query_decision.allowed:
            return query_decision
        if "mnemosyne.write" not in context.scopes and "admin" not in context.roles:
            return PolicyDecision(False, "missing_mnemosyne_write_scope")
        return PolicyDecision(True, "write_scope_allowed")

    def can_disclose_entity(
        self,
        context: AccessContext,
        entity: EntityRecord,
    ) -> PolicyDecision:
        if (
            "admin" not in context.roles
            and entity.allowed_purposes
            and context.purpose not in entity.allowed_purposes
        ):
            return PolicyDecision(False, "purpose_not_allowed")
        if entity.sensitivity in {Sensitivity.SECRET, Sensitivity.RESTRICTED}:
            if "admin" in context.roles:
                return PolicyDecision(True, "admin_sensitive_allowed")
            return PolicyDecision(False, "sensitivity_denied")
        if entity.sensitivity == Sensitivity.CONFIDENTIAL and (
            "mnemosyne.raw" not in context.scopes and "admin" not in context.roles
        ):
            return PolicyDecision(
                True, "confidential_entity_summary_allowed", redacted=True
            )
        return PolicyDecision(True, "entity_projection_allowed")

    def can_disclose_revision(
        self,
        context: AccessContext,
        revision: ObservationRevision,
    ) -> PolicyDecision:
        if (
            "admin" not in context.roles
            and revision.allowed_purposes
            and context.purpose not in revision.allowed_purposes
        ):
            return PolicyDecision(False, "purpose_not_allowed")

        if context.requested_projection == ProjectionName.RAW_OBSERVATION:
            if "mnemosyne.raw" in context.scopes or "admin" in context.roles:
                return PolicyDecision(True, "raw_scope_allowed")
            return PolicyDecision(False, "raw_projection_requires_scope")

        if (
            context.client_app == "finance"
            and context.purpose == Purpose.ACCOUNTING
            and revision.domain == Domain.HEALTH
        ):
            return self._finance_health_accounting_decision(revision)

        if revision.sensitivity in {Sensitivity.SECRET, Sensitivity.RESTRICTED}:
            if "admin" in context.roles:
                return PolicyDecision(True, "admin_sensitive_allowed")
            return PolicyDecision(False, "sensitivity_denied")

        return PolicyDecision(True, "projection_allowed")

    def _finance_health_accounting_decision(
        self,
        revision: ObservationRevision,
    ) -> PolicyDecision:
        content = revision.content.casefold()
        if revision.sensitivity in {Sensitivity.SECRET, Sensitivity.RESTRICTED}:
            return PolicyDecision(False, "health_sensitivity_denied_for_accounting")
        if any(marker in content for marker in _SENSITIVE_HEALTH_DENY_MARKERS):
            return PolicyDecision(False, "health_context_denied_for_accounting")
        redacted = any(marker in content for marker in _CLINICAL_REDACTION_MARKERS)
        return PolicyDecision(
            True,
            "health_accounting_projection_allowed",
            redacted=redacted,
        )


__all__ = ["AccessPolicy", "PolicyDecision"]
