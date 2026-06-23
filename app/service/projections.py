from datetime import UTC, datetime

from app.models.access import AccessContext, Domain, ProjectionName
from app.models.observations import (
    MentionedEntity,
    Observation,
    ObservationRevision,
    content_preview,
)
from app.service.access_policy import PolicyDecision


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _mention_dict(mention: MentionedEntity) -> dict[str, object]:
    return {
        "id": mention.id,
        "type": mention.type.value,
        "label": mention.label,
        "resolution_status": mention.resolution_status.value,
    }


def _base_payload(
    observation: Observation,
    revision: ObservationRevision,
    view: ProjectionName,
) -> dict[str, object]:
    return {
        "id": observation.id,
        "type": observation.type.value,
        "version": revision.version,
        "current_revision": revision.id,
        "view": view.value,
        "domain": revision.domain.value,
        "sensitivity": revision.sensitivity.value,
        "subject": revision.subject,
        "allowed_purposes": [purpose.value for purpose in revision.allowed_purposes],
        "observed_at": _format_datetime(revision.observed_at),
        "created_at": _format_datetime(observation.created_at),
        "updated_at": _format_datetime(observation.updated_at),
    }


def _merchant_labels(revision: ObservationRevision) -> list[str]:
    labels: list[str] = []
    for mention in revision.mentions:
        normalized = mention.label.casefold()
        if (
            "pharmacy" in normalized
            or "farmácia" in normalized
            or "store" in normalized
            or mention.type.value == "location"
        ):
            labels.append(mention.label)
    return labels


def _looks_like_medication_purchase(revision: ObservationRevision) -> bool:
    content = revision.content.casefold()
    return any(
        marker in content
        for marker in (
            "medication",
            "medicine",
            "pharmacy",
            "farmácia",
            "prescription",
            "losartan",
        )
    )


class ProjectionService:
    def project_observation(
        self,
        context: AccessContext,
        observation: Observation,
        decision: PolicyDecision,
    ) -> dict[str, object]:
        latest = observation.latest_revision
        if latest is None:
            msg = f"Observation {observation.id!r} has no revision."
            raise ValueError(msg)

        projection = context.requested_projection
        if projection == ProjectionName.ACCOUNTING_VIEW:
            return self._accounting_view(observation, latest, decision)
        if projection == ProjectionName.HEALTH_CARE_VIEW:
            return self._health_care_view(observation, latest, decision)
        return self._summary_view(observation, latest, decision)

    def _summary_view(
        self,
        observation: Observation,
        revision: ObservationRevision,
        decision: PolicyDecision,
    ) -> dict[str, object]:
        payload = _base_payload(
            observation,
            revision,
            ProjectionName.OBSERVATION_SUMMARY,
        )
        payload.update(
            {
                "content_preview": content_preview(revision.content),
                "mentions": [_mention_dict(mention) for mention in revision.mentions],
                "redactions": ["full_content"]
                if decision.redacted
                or revision.sensitivity.value
                in {"confidential", "restricted", "secret"}
                else [],
            }
        )
        return payload

    def _accounting_view(
        self,
        observation: Observation,
        revision: ObservationRevision,
        decision: PolicyDecision,
    ) -> dict[str, object]:
        payload = _base_payload(observation, revision, ProjectionName.ACCOUNTING_VIEW)
        redactions = ["clinical_health_details"] if decision.redacted else []
        if revision.domain == Domain.HEALTH:
            redactions.append("raw_health_content")
        payload.update(
            {
                "summary": (
                    "Health expense."
                    if revision.domain == Domain.HEALTH
                    else content_preview(revision.content)
                ),
                "merchant_labels": _merchant_labels(revision),
                "item_type": (
                    "Medication"
                    if _looks_like_medication_purchase(revision)
                    else None
                ),
                "redactions": sorted(set(redactions)),
            }
        )
        return payload

    def _health_care_view(
        self,
        observation: Observation,
        revision: ObservationRevision,
        decision: PolicyDecision,
    ) -> dict[str, object]:
        payload = _base_payload(observation, revision, ProjectionName.HEALTH_CARE_VIEW)
        payload.update(
            {
                "content": revision.content,
                "content_format": revision.content_format,
                "mentions": [_mention_dict(mention) for mention in revision.mentions],
                "redactions": ["restricted_details"] if decision.redacted else [],
            }
        )
        return payload


__all__ = ["ProjectionService"]
