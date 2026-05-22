from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_observations_create_get_patch_search_and_context_flow(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()

    created = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "Need to pick up my shirt.",
            "mentions": [
                {"type": "item", "label": "blue shirt"},
                {"type": "location", "label": "John's place"},
            ],
            "observed_at": "2026-04-06T17:00:00Z",
            "source": {"source_type": "agent", "label": "codex"},
        },
    )

    assert created.status_code == 201
    created_body = created.json()
    assert re.fullmatch(r"obs_[0-9A-Z]{26}", created_body["observation_id"])
    assert created_body["type"] == "note"
    assert created_body["version"] == 1
    assert created_body["current_revision_id"] == (
        f"{created_body['observation_id']}:v1"
    )
    assert created_body["content"] == "Need to pick up my shirt."
    assert created_body["observed_at"] == "2026-04-06T17:00:00Z"
    assert created_body["mentions"] == [
        {
            "entity_id": created_body["mentions"][0]["entity_id"],
            "type": "item",
            "label": "blue shirt",
            "resolution_status": "unresolved",
        },
        {
            "entity_id": created_body["mentions"][1]["entity_id"],
            "type": "location",
            "label": "John's place",
            "resolution_status": "unresolved",
        },
    ]
    assert created_body["source"]["source_type"] == "agent"
    assert created_body["source"]["label"] == "codex"

    fetched = client.get(f"/observations/{created_body['observation_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created_body

    second = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "Blue PME Oxford shirt is at John's place.",
            "mentions": [
                {"type": "item", "label": "blue shirt"},
                {"type": "location", "label": "John's place"},
            ],
            "observed_at": "2026-04-05T09:30:00Z",
            "source": {"source_type": "agent", "label": "codex"},
        },
    )
    assert second.status_code == 201

    patched = client.patch(
        f"/observations/{created_body['observation_id']}",
        json={
            "addendum": "It is the blue one.",
            "mentions": [{"type": "location", "label": "John's place"}],
            "observed_at": "2026-04-06T18:05:00Z",
        },
    )

    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["version"] == 2
    assert patched_body["content"] == (
        "Need to pick up my shirt.\n\nAddendum:\nIt is the blue one."
    )
    assert patched_body["observed_at"] == "2026-04-06T18:05:00Z"
    assert patched_body["current_revision_id"] == (
        f"{created_body['observation_id']}:v2"
    )
    assert [(item["type"], item["label"]) for item in patched_body["mentions"]] == [
        ("item", "blue shirt"),
        ("location", "John's place"),
    ]

    search = client.get("/observations", params={"q": "blue", "limit": 5})
    assert search.status_code == 200
    assert [(item["observation_id"], item["version"]) for item in search.json()] == [
        (created_body["observation_id"], 2),
        (second.json()["observation_id"], 1),
    ]

    context = client.get(f"/observations/{created_body['observation_id']}/context")
    assert context.status_code == 200
    assert context.json()["observation"]["observation_id"] == (
        created_body["observation_id"]
    )
    related_ids = [
        item["observation_id"]
        for item in context.json()["related_observations"]
    ]
    assert related_ids == [second.json()["observation_id"]]


def test_observation_patch_rejects_empty_change(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()
    created = client.post(
        "/observations",
        json={"type": "note", "content": "Need to pick up my shirt."},
    ).json()

    response = client.patch(
        f"/observations/{created['observation_id']}",
        json={},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_observation_patch",
        "details": [
            {
                "message": "Patch request must include at least one change.",
                "code": "invalid_observation_patch",
            }
        ],
        "request_id": None,
    }


def test_observation_patch_rejects_client_version(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()
    created = client.post(
        "/observations",
        json={"type": "note", "content": "Need to pick up my shirt."},
    ).json()

    response = client.patch(
        f"/observations/{created['observation_id']}",
        json={"version": 1, "addendum": "It is blue."},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_observation_patch",
        "details": [
            {
                "field": "version",
                "message": "version is assigned internally and must not be provided.",
                "code": "invalid_observation_patch",
            }
        ],
        "request_id": None,
    }


def test_observation_patch_missing_body_uses_patch_error(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()

    response = client.patch("/observations/obs_missing")

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_observation_patch",
        "details": [
            {
                "message": "Patch body is required.",
                "code": "invalid_observation_patch",
            }
        ],
        "request_id": None,
    }


def test_notes_endpoint_is_not_part_of_the_alpha_observation_api(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()

    response = client.post("/notes", json={"content": "legacy"})

    assert response.status_code == 404
