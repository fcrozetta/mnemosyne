from fastapi.testclient import TestClient

from app.dependencies import (
    get_access_audit_service,
    reset_access_audit_service_cache,
    reset_observations_repository_cache,
    reset_settings_cache,
)
from app.main import create_app


def _client(monkeypatch, *, flags: bool) -> TestClient:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    if flags:
        monkeypatch.setenv("MNEMOSYNE_DOMAIN_POLICY_ENABLED", "true")
        monkeypatch.setenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED", "true")
        monkeypatch.setenv("MNEMOSYNE_SAFE_PROJECTIONS_ENABLED", "true")
        monkeypatch.setenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED", "true")
    else:
        monkeypatch.delenv("MNEMOSYNE_DOMAIN_POLICY_ENABLED", raising=False)
        monkeypatch.delenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED", raising=False)
        monkeypatch.delenv("MNEMOSYNE_SAFE_PROJECTIONS_ENABLED", raising=False)
        monkeypatch.delenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED", raising=False)
    reset_observations_repository_cache()
    reset_settings_cache()
    reset_access_audit_service_cache()
    return TestClient(create_app())


def _finance_headers(projection: str = "accounting_view") -> dict[str, str]:
    return {
        "X-Mnemosyne-Actor-User": "Fernando",
        "X-Mnemosyne-Client-App": "finance",
        "X-Mnemosyne-Service-Identity": "finance-api",
        "X-Mnemosyne-Purpose": "accounting",
        "X-Mnemosyne-Scopes": "mnemosyne.query finance.read",
        "X-Mnemosyne-Roles": "owner",
        "X-Mnemosyne-Projection": projection,
    }


def _create_health_observation(client: TestClient, content: str):
    response = client.post(
        "/observations",
        json={
            "type": "note",
            "content": content,
            "domain": "health",
            "sensitivity": "confidential",
            "subject": "Fernando",
            "allowed_purposes": ["accounting", "medication_management"],
            "mentions": [
                {"type": "location", "label": "Pharmacy X"},
                {"type": "item", "label": "Losartan"},
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_feature_flags_off_ignore_access_headers_and_keep_raw_api(monkeypatch) -> None:
    client = _client(monkeypatch, flags=False)
    created = _create_health_observation(
        client,
        "Bought Losartan medication at Pharmacy X. Dosage is one tablet daily.",
    )

    response = client.get(
        f"/observations/{created['id']}",
        headers=_finance_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == created["content"]
    assert "domain" not in body
    assert "sensitivity" not in body
    assert "view" not in body


def test_finance_accounting_projection_hides_raw_health_content(monkeypatch) -> None:
    client = _client(monkeypatch, flags=True)
    created = _create_health_observation(
        client,
        "Bought Losartan medication at Pharmacy X. Dosage is one tablet daily.",
    )

    response = client.get(
        f"/observations/{created['id']}",
        headers=_finance_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["view"] == "accounting_view"
    assert body["domain"] == "health"
    assert body["merchant_labels"] == ["Pharmacy X"]
    assert body["item_type"] == "Medication"
    assert "content" not in body
    assert "clinical_health_details" in body["redactions"]
    assert "raw_health_content" in body["redactions"]


def test_finance_accounting_denies_family_medical_history(monkeypatch) -> None:
    client = _client(monkeypatch, flags=True)
    created = _create_health_observation(
        client,
        "Family history of hypertension and genetic risk.",
    )

    response = client.get(
        f"/observations/{created['id']}",
        headers=_finance_headers(),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]["reason_code"]
        == "health_context_denied_for_accounting"
    )
    events = get_access_audit_service().list_events()
    assert len(events) == 1
    assert events[0].decision == "deny"


def test_search_omits_denied_items_when_policy_enabled(monkeypatch) -> None:
    client = _client(monkeypatch, flags=True)
    allowed = _create_health_observation(
        client,
        "Bought Losartan medication at Pharmacy X.",
    )
    denied = _create_health_observation(client, "Family history of hypertension.")

    response = client.get(
        "/observations",
        params={"q": "hypertension Losartan", "limit": 5},
        headers=_finance_headers(),
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert allowed["id"] in ids
    assert denied["id"] not in ids


def test_raw_projection_requires_explicit_raw_scope(monkeypatch) -> None:
    client = _client(monkeypatch, flags=True)
    created = _create_health_observation(
        client,
        "Bought Losartan medication at Pharmacy X.",
    )

    response = client.get(
        f"/observations/{created['id']}",
        headers=_finance_headers(projection="raw_observation"),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason_code"] == "raw_projection_requires_scope"
