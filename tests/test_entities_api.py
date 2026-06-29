from fastapi.testclient import TestClient

from app.dependencies import (
    get_access_audit_service,
    reset_access_audit_service_cache,
    reset_observations_repository_cache,
    reset_settings_cache,
)
from app.main import create_app


def _client(monkeypatch, *, flags: bool = False) -> TestClient:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    if flags:
        monkeypatch.setenv("MNEMOSYNE_ACCESS_POLICY_ENABLED", "true")
        monkeypatch.setenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED", "true")
        monkeypatch.setenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED", "true")
    else:
        monkeypatch.delenv("MNEMOSYNE_ACCESS_POLICY_ENABLED", raising=False)
        monkeypatch.delenv("MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED", raising=False)
        monkeypatch.delenv("MNEMOSYNE_ACCESS_AUDIT_ENABLED", raising=False)
    reset_observations_repository_cache()
    reset_settings_cache()
    reset_access_audit_service_cache()
    return TestClient(create_app())


def _owner_headers(*, extra_scopes: tuple[str, ...] = ()) -> dict[str, str]:
    scopes = " ".join(("mnemosyne.query", *extra_scopes))
    return {
        "X-Mnemosyne-Actor-User": "Sample User",
        "X-Mnemosyne-Client-App": "contacts",
        "X-Mnemosyne-Service-Identity": "contacts-api",
        "X-Mnemosyne-Purpose": "recall",
        "X-Mnemosyne-Scopes": scopes,
        "X-Mnemosyne-Roles": "owner",
        "X-Mnemosyne-Projection": "observation_summary",
    }


def test_create_get_and_list_person_contact_entity(monkeypatch) -> None:
    client = _client(monkeypatch)

    created = client.post(
        "/entities",
        json={
            "type": "person",
            "label": "Mario Rossi",
            "scope": "contacts",
            "sensitivity": "confidential",
            "allowed_purposes": ["recall", "reminder"],
            "person": {
                "display_name": "Mario",
                "given_name": "Mario",
                "family_name": "Rossi",
                "contact_methods": [
                    {
                        "kind": "phone",
                        "label": "mobile",
                        "value": "+55 11 99999-0000",
                        "sensitivity": "restricted",
                    },
                    {
                        "kind": "email",
                        "value": "mario@example.com",
                    },
                ],
            },
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["type"] == "person"
    assert body["label"] == "Mario Rossi"
    assert body["scope"] == "contacts"
    assert body["sensitivity"] == "confidential"
    assert body["allowed_purposes"] == ["recall", "reminder"]
    assert body["person"]["display_name"] == "Mario"
    assert body["person"]["contact_methods"][0] == {
        "kind": "phone",
        "label": "mobile",
        "value": "+55 11 99999-0000",
        "sensitivity": "restricted",
    }

    fetched = client.get(f"/entities/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    listed = client.get(
        "/entities",
        params={"type": "person", "scope": "contacts", "q": "mario"},
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]


def test_create_location_entity_with_address_and_geolocation(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/entities",
        json={
            "type": "location",
            "label": "Mario's house",
            "scope": "places",
            "sensitivity": "restricted",
            "location": {
                "location_kind": "home",
                "street_address": "Rua Exemplo, 123",
                "postal_code": "00000-000",
                "locality": "São Paulo",
                "region": "SP",
                "country": "BR",
                "latitude": -23.5505,
                "longitude": -46.6333,
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "location"
    assert body["scope"] == "places"
    assert body["location"] == {
        "location_kind": "home",
        "street_address": "Rua Exemplo, 123",
        "postal_code": "00000-000",
        "locality": "São Paulo",
        "region": "SP",
        "country": "BR",
        "latitude": -23.5505,
        "longitude": -46.6333,
    }


def test_create_store_vendor_merchant_entity(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/entities",
        json={
            "type": "store",
            "label": "Penworld",
            "scope": "vendors",
            "sensitivity": "personal",
            "store": {
                "store_kind": "merchant",
                "website": "https://www.penworld.eu",
                "categories": ["pens", "stationery"],
                "country_scope": "EU",
                "physical_store_status": "online_only",
                "source_urls": ["https://www.penworld.eu"],
                "reference_notes": "Preferred fountain pen vendor candidate.",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "store"
    assert body["scope"] == "vendors"
    assert body["store"] == {
        "store_kind": "merchant",
        "website": "https://www.penworld.eu",
        "categories": ["pens", "stationery"],
        "country_scope": "EU",
        "physical_store_status": "online_only",
        "source_urls": ["https://www.penworld.eu"],
        "reference_notes": "Preferred fountain pen vendor candidate.",
    }
    listed = client.get("/entities", params={"type": "store", "q": "pen"})
    assert [item["id"] for item in listed.json()] == [body["id"]]


def test_create_classified_item_entities(monkeypatch) -> None:
    client = _client(monkeypatch)

    pen = client.post(
        "/entities",
        json={
            "type": "item",
            "label": "Pilot Custom 823 Amber",
            "scope": "possessions/pens",
            "sensitivity": "personal",
            "item": {
                "item_kind": "pen",
                "category": "writing_instrument",
                "subcategory": "fountain_pen",
                "brand": "Pilot",
                "model": "Custom 823",
                "variant": "Amber",
                "color": "amber",
                "identifiers": ["pilot-custom-823-amber"],
            },
        },
    )
    laptop = client.post(
        "/entities",
        json={
            "type": "item",
            "label": "Framework Laptop",
            "scope": "possessions/electronics",
            "item": {
                "item_kind": "electronics",
                "category": "computer",
                "subcategory": "laptop",
                "brand": "Framework",
                "serial_number": "FW-REDACT-ME",
            },
        },
    )

    assert pen.status_code == 201
    assert laptop.status_code == 201
    assert pen.json()["item"]["subcategory"] == "fountain_pen"
    assert laptop.json()["item"]["category"] == "computer"
    assert {
        item["scope"]
        for item in client.get("/entities", params={"type": "item"}).json()
    } == {"possessions/pens", "possessions/electronics"}


def test_entity_scope_allows_same_label_in_different_scopes(monkeypatch) -> None:
    client = _client(monkeypatch)

    personal = client.post(
        "/entities",
        json={"type": "person", "label": "Alex", "scope": "personal"},
    )
    work = client.post(
        "/entities",
        json={"type": "person", "label": "Alex", "scope": "work"},
    )

    assert personal.status_code == 201
    assert work.status_code == 201
    assert personal.json()["id"] != work.json()["id"]
    assert {
        item["scope"] for item in client.get("/entities", params={"q": "alex"}).json()
    } == {
        "personal",
        "work",
    }


def test_entity_endpoint_rejects_invalid_type_and_profile_mismatch(monkeypatch) -> None:
    client = _client(monkeypatch)

    invalid_type = client.post("/entities", json={"type": "topic", "label": "shirt"})
    assert invalid_type.status_code == 400
    assert invalid_type.json()["details"][0]["field"] == "type"

    mismatch = client.post(
        "/entities",
        json={
            "type": "person",
            "label": "Mario",
            "location": {"locality": "São Paulo"},
        },
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["details"][0]["field"] == "location"


def test_entity_policy_redacts_confidential_contact_and_location_details(
    monkeypatch,
) -> None:
    client = _client(monkeypatch, flags=True)
    person = client.post(
        "/entities",
        json={
            "type": "person",
            "label": "Mario Rossi",
            "scope": "contacts",
            "sensitivity": "confidential",
            "person": {
                "contact_methods": [{"kind": "phone", "value": "+55 11 99999-0000"}],
            },
        },
    ).json()
    location = client.post(
        "/entities",
        json={
            "type": "location",
            "label": "Mario's house",
            "scope": "places",
            "sensitivity": "confidential",
            "location": {
                "street_address": "Rua Exemplo, 123",
                "locality": "São Paulo",
                "latitude": -23.5505,
                "longitude": -46.6333,
            },
        },
    ).json()

    person_response = client.get(f"/entities/{person['id']}", headers=_owner_headers())
    location_response = client.get(
        f"/entities/{location['id']}", headers=_owner_headers()
    )

    assert person_response.status_code == 200
    assert person_response.json()["person"]["contact_methods"][0]["value"] is None
    assert "contact_methods.value" in person_response.json()["redactions"]
    assert location_response.status_code == 200
    assert location_response.json()["location"]["street_address"] is None
    assert location_response.json()["location"]["latitude"] is None
    assert "location.precise_address" in location_response.json()["redactions"]
    assert len(get_access_audit_service().list_events()) == 2


def test_entity_raw_scope_discloses_confidential_details(monkeypatch) -> None:
    client = _client(monkeypatch, flags=True)
    person = client.post(
        "/entities",
        json={
            "type": "person",
            "label": "Mario Rossi",
            "scope": "contacts",
            "sensitivity": "confidential",
            "person": {
                "contact_methods": [{"kind": "phone", "value": "+55 11 99999-0000"}],
            },
        },
    ).json()

    response = client.get(
        f"/entities/{person['id']}",
        headers=_owner_headers(extra_scopes=("mnemosyne.raw",)),
    )

    assert response.status_code == 200
    assert (
        response.json()["person"]["contact_methods"][0]["value"] == "+55 11 99999-0000"
    )
    assert response.json()["redactions"] == []


def test_entity_policy_redacts_restricted_contact_on_personal_entity(
    monkeypatch,
) -> None:
    client = _client(monkeypatch, flags=True)
    person = client.post(
        "/entities",
        json={
            "type": "person",
            "label": "Mario Rossi",
            "scope": "contacts",
            "sensitivity": "personal",
            "person": {
                "contact_methods": [
                    {
                        "kind": "phone",
                        "value": "+55 11 99999-0000",
                        "sensitivity": "restricted",
                    }
                ],
            },
        },
    ).json()

    response = client.get(f"/entities/{person['id']}", headers=_owner_headers())

    assert response.status_code == 200
    assert response.json()["person"]["contact_methods"][0]["value"] is None
    assert "contact_methods.value" in response.json()["redactions"]


def test_entity_policy_denies_secret_entity_without_admin(monkeypatch) -> None:
    client = _client(monkeypatch, flags=True)
    created = client.post(
        "/entities",
        json={"type": "location", "label": "Safe house", "sensitivity": "secret"},
    ).json()

    response = client.get(f"/entities/{created['id']}", headers=_owner_headers())

    assert response.status_code == 403
    assert response.json()["detail"]["reason_code"] == "sensitivity_denied"
