from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.dependencies import reset_settings_cache
from app.main import create_app


def _client() -> TestClient:
    reset_settings_cache()
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
    assert re.fullmatch(r"obs_[0-9A-Z]{26}", created_body["id"])
    assert created_body["type"] == "note"
    assert created_body["version"] == 1
    assert created_body["current_revision"] == (
        f"{created_body['id']}:v1"
    )
    assert created_body["content"] == "Need to pick up my shirt."
    assert created_body["observed_at"] == "2026-04-06T17:00:00Z"
    assert created_body["mentions"] == [
        {
            "id": created_body["mentions"][0]["id"],
            "type": "item",
            "label": "blue shirt",
            "resolution_status": "unresolved",
        },
        {
            "id": created_body["mentions"][1]["id"],
            "type": "location",
            "label": "John's place",
            "resolution_status": "unresolved",
        },
    ]
    assert created_body["source"]["source_type"] == "agent"
    assert created_body["source"]["label"] == "codex"

    fetched = client.get(f"/observations/{created_body['id']}")
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
        f"/observations/{created_body['id']}",
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
    assert patched_body["current_revision"] == (
        f"{created_body['id']}:v2"
    )
    assert [(item["type"], item["label"]) for item in patched_body["mentions"]] == [
        ("item", "blue shirt"),
        ("location", "John's place"),
    ]

    search = client.get("/observations", params={"q": "blue", "limit": 5})
    assert search.status_code == 200
    assert [(item["id"], item["version"]) for item in search.json()] == [
        (created_body["id"], 2),
        (second.json()["id"], 1),
    ]

    context = client.get(f"/observations/{created_body['id']}/context")
    assert context.status_code == 200
    assert context.json()["observation"]["id"] == (
        created_body["id"]
    )
    related_ids = [
        item["id"]
        for item in context.json()["related_observations"]
    ]
    assert related_ids == [second.json()["id"]]


def test_observations_support_topic_strings_and_recent_topic_lookup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()

    first = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "Prefer pathlib for local file handling.",
            "topics": ["coding:fcrozetta:python:coding-style"],
            "observed_at": "2026-04-06T10:00:00Z",
        },
    )
    second = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "Ruff should keep imports sorted.",
            "topics": ["coding:fcrozetta:python:linting"],
            "observed_at": "2026-04-05T10:00:00Z",
        },
    )
    unrelated = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "ArcadeDB schema changes need smoke tests.",
            "topics": ["coding:fcrozetta:arcadedb:schema"],
            "observed_at": "2026-04-07T10:00:00Z",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert unrelated.status_code == 201
    assert [(item["type"], item["label"]) for item in first.json()["mentions"]] == [
        ("topic", "coding:fcrozetta:python:coding-style")
    ]

    patched = client.patch(
        f"/observations/{second.json()['id']}",
        json={
            "addendum": "This is the current version.",
            "observed_at": "2026-04-04T10:00:00Z",
        },
    )
    assert patched.status_code == 200

    recent = client.get(
        "/topics/coding:fcrozetta:python/observations",
        params={"limit": 5},
    )

    assert recent.status_code == 200
    assert [(item["id"], item["version"]) for item in recent.json()] == [
        (second.json()["id"], 2),
        (first.json()["id"], 1),
    ]
    assert [item["updated_at"] for item in recent.json()] == sorted(
        [item["updated_at"] for item in recent.json()],
        reverse=True,
    )

    partial = client.get("/topics/coding-style/observations")

    assert partial.status_code == 200
    assert [(item["id"], item["version"]) for item in partial.json()] == [
        (first.json()["id"], 1)
    ]


def test_observations_search_orders_by_updated_at_desc(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()

    older_higher_score = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "Cerulean saxifrage marker is stored in the closet.",
            "observed_at": "2026-04-10T10:00:00Z",
        },
    )
    newer_lower_score = client.post(
        "/observations",
        json={
            "type": "note",
            "content": "Cerulean marker is in the laundry basket.",
            "observed_at": "2026-04-05T10:00:00Z",
        },
    )
    patched = client.patch(
        f"/observations/{newer_lower_score.json()['id']}",
        json={
            "addendum": "Still cerulean.",
            "observed_at": "2026-04-04T10:00:00Z",
        },
    )

    assert older_higher_score.status_code == 201
    assert newer_lower_score.status_code == 201
    assert patched.status_code == 200

    response = client.get(
        "/observations",
        params={"q": "cerulean saxifrage", "limit": 5},
    )

    assert response.status_code == 200
    results = response.json()
    assert [(item["id"], item["version"], item["score"]) for item in results] == [
        (newer_lower_score.json()["id"], 2, 0.5),
        (older_higher_score.json()["id"], 1, 1.0),
    ]
    assert [item["updated_at"] for item in results] == sorted(
        [item["updated_at"] for item in results],
        reverse=True,
    )


def test_observation_patch_rejects_empty_change(monkeypatch) -> None:
    monkeypatch.setenv("MNEMOSYNE_STORAGE_BACKEND", "in-memory")
    client = _client()
    created = client.post(
        "/observations",
        json={"type": "note", "content": "Need to pick up my shirt."},
    ).json()

    response = client.patch(
        f"/observations/{created['id']}",
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
        f"/observations/{created['id']}",
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


def test_observations_search_openapi_documents_scoring_semantics() -> None:
    client = _client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    description = response.json()["paths"]["/observations"]["get"][
        "description"
    ]
    assert "lexical scoring" in description
    assert "full-query substring match scores `1.0`" in description
    assert "matches sort by `updated_at` descending" in description
    assert "query-relative" in description
