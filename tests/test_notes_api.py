from __future__ import annotations

from fastapi.testclient import TestClient

from app.dependencies import get_notes_service
from app.main import create_app
from app.repository.notes_in_memory import InMemoryNotesRepository
from app.service.notes import NotesService


def _client() -> TestClient:
    repository = InMemoryNotesRepository()
    repository.initialize_storage()
    app = create_app()
    app.dependency_overrides[get_notes_service] = lambda: NotesService(
        repository=repository
    )
    return TestClient(app)


def test_notes_create_get_patch_search_and_context_flow() -> None:
    client = _client()

    created = client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "about": [
                {
                    "kind": "item",
                    "ref": {"collection": "item", "key": "item_shirt_001"},
                },
                {"kind": "location", "label": "John's place"},
            ],
            "observed_at": "2026-04-06T17:00:00Z",
            "source_channel": "chat",
        },
    )

    assert created.status_code == 201
    assert created.json() == {
        "note_id": "note_001",
        "version": 1,
        "content": "Need to pick up my shirt.",
        "observed_at": "2026-04-06T17:00:00Z",
        "created_at": "2026-04-06T17:00:00Z",
        "resolved_about": [
            {
                "kind": "item",
                "collection": "item",
                "key": "item_shirt_001",
            }
        ],
        "pending_about": [{"kind": "location", "label": "John's place"}],
    }

    fetched = client.get("/notes/note_001")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()

    second = client.post(
        "/notes",
        json={
            "content": "Blue PME Oxford shirt is at John's place.",
            "about": [
                {
                    "kind": "item",
                    "ref": {"collection": "item", "key": "item_shirt_001"},
                },
                {"kind": "location", "label": "John's place"},
            ],
            "observed_at": "2026-04-05T09:30:00Z",
        },
    )
    assert second.status_code == 201

    patched = client.patch(
        "/notes/note_001",
        json={
            "version": 1,
            "addendum": "It is the blue one.",
            "add_about": [{"kind": "location", "label": "John's place"}],
            "observed_at": "2026-04-06T18:05:00Z",
        },
    )

    assert patched.status_code == 200
    assert patched.json() == {
        "note_id": "note_001",
        "version": 2,
        "content": "Need to pick up my shirt.\n\nAddendum:\nIt is the blue one.",
        "observed_at": "2026-04-06T18:05:00Z",
        "created_at": "2026-04-06T17:00:00Z",
        "resolved_about": [
            {
                "kind": "item",
                "collection": "item",
                "key": "item_shirt_001",
            }
        ],
        "pending_about": [{"kind": "location", "label": "John's place"}],
    }

    search = client.get("/notes", params={"q": "blue", "limit": 5})
    assert search.status_code == 200
    assert search.json() == [
        {
            "note_id": "note_001",
            "version": 2,
            "content_preview": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T18:05:00Z",
            "score": 1.0,
        },
        {
            "note_id": "note_002",
            "version": 1,
            "content_preview": "Blue PME Oxford shirt is at John's place.",
            "observed_at": "2026-04-05T09:30:00Z",
            "score": 1.0,
        },
    ]

    context = client.get("/notes/note_001/context")
    assert context.status_code == 200
    assert context.json() == {
        "note": patched.json(),
        "basis": {
            "resolved_about": [
                {
                    "kind": "item",
                    "collection": "item",
                    "key": "item_shirt_001",
                }
            ],
            "pending_about": [{"kind": "location", "label": "John's place"}],
        },
        "related_notes": [
            {
                "note_id": "note_002",
                "version": 1,
                "content_preview": "Blue PME Oxford shirt is at John's place.",
                "observed_at": "2026-04-05T09:30:00Z",
                "score": 2.0,
            }
        ],
    }


def test_patch_returns_version_conflict_shape() -> None:
    client = _client()
    client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T17:00:00Z",
        },
    )
    client.patch(
        "/notes/note_001",
        json={"version": 1, "addendum": "It is the blue one."},
    )

    response = client.patch(
        "/notes/note_001",
        json={"version": 1, "addendum": "Still the blue one."},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": "version_conflict",
        "details": [
            {
                "field": "version",
                "message": "Version does not match latest note version.",
                "code": "version_conflict",
                "context": {
                    "note_id": "note_001",
                    "current_version": 2,
                    "requested_version": 1,
                },
            }
        ],
        "request_id": None,
    }


def test_patch_without_operations_returns_invalid_note_patch() -> None:
    client = _client()
    client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T17:00:00Z",
        },
    )

    response = client.patch("/notes/note_001", json={"version": 1})

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_patch",
        "details": [
            {
                "message": "Patch request must include at least one change.",
                "code": "invalid_note_patch",
            }
        ],
        "request_id": None,
    }


def test_patch_with_malformed_add_about_returns_invalid_note_patch() -> None:
    client = _client()
    client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T17:00:00Z",
        },
    )

    response = client.patch(
        "/notes/note_001",
        json={"version": 1, "add_about": {"kind": "location", "label": "x"}},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_patch",
        "details": [
            {
                "field": "add_about",
                "message": "add_about must be a list.",
                "code": "invalid_note_patch",
            }
        ],
        "request_id": None,
    }


def test_patch_with_invalid_observed_at_returns_invalid_note_patch() -> None:
    client = _client()
    client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T17:00:00Z",
        },
    )

    response = client.patch(
        "/notes/note_001",
        json={"version": 1, "observed_at": "not-a-datetime"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_patch",
        "details": [
            {
                "field": "observed_at",
                "message": "observed_at must be an ISO 8601 datetime string.",
                "code": "invalid_note_patch",
            }
        ],
        "request_id": None,
    }


def test_patch_with_non_object_body_returns_invalid_note_patch() -> None:
    client = _client()
    client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T17:00:00Z",
        },
    )

    response = client.patch(
        "/notes/note_001",
        json=[],
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_patch",
        "details": [
            {
                "message": "Patch body must be an object.",
                "code": "invalid_note_patch",
            }
        ],
        "request_id": None,
    }


def test_create_with_non_object_body_returns_invalid_note_request() -> None:
    client = _client()

    response = client.post(
        "/notes",
        json=[],
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_request",
        "details": [
            {
                "message": "Request body must be an object.",
                "code": "invalid_note_request",
            }
        ],
        "request_id": None,
    }


def test_create_without_body_returns_invalid_note_request() -> None:
    client = _client()

    response = client.post("/notes")

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_request",
        "details": [
            {
                "message": "Request body is required.",
                "code": "invalid_note_request",
            }
        ],
        "request_id": None,
    }


def test_patch_without_body_returns_invalid_note_patch() -> None:
    client = _client()
    client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06T17:00:00Z",
        },
    )

    response = client.patch("/notes/note_001")

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_patch",
        "details": [
            {
                "message": "Patch body is required.",
                "code": "invalid_note_patch",
            }
        ],
        "request_id": None,
    }


def test_search_with_invalid_limit_type_returns_invalid_note_request() -> None:
    client = _client()

    response = client.get("/notes", params={"q": "shirt", "limit": "abc"})

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_request",
        "details": [
            {
                "field": "limit",
                "message": "Invalid value for limit.",
                "code": "invalid_note_request",
            }
        ],
        "request_id": None,
    }


def test_create_with_date_only_observed_at_returns_invalid_note_request() -> None:
    client = _client()

    response = client.post(
        "/notes",
        json={
            "content": "Need to pick up my shirt.",
            "observed_at": "2026-04-06",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_note_request",
        "details": [
            {
                "field": "observed_at",
                "message": "observed_at must be an ISO 8601 datetime string.",
                "code": "invalid_note_request",
            }
        ],
        "request_id": None,
    }


def test_missing_note_returns_not_found_shape() -> None:
    client = _client()

    response = client.get("/notes/note_999")

    assert response.status_code == 404
    assert response.json() == {
        "error": "note_not_found",
        "details": [
            {
                "field": "note_id",
                "message": "Note was not found.",
                "code": "note_not_found",
                "context": {"note_id": "note_999"},
            }
        ],
        "request_id": None,
    }
