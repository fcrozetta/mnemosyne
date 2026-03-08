from fastapi.testclient import TestClient

from app.dependencies import get_notes_handler
from app.handler.notes import NotesHandler
from app.main import app
from app.repository.notes_in_memory import InMemoryNotesRepository
from app.service.notes import NotesService


def test_create_note_endpoint_returns_note_view() -> None:
    service = NotesService(InMemoryNotesRepository())
    app.dependency_overrides[get_notes_handler] = lambda: NotesHandler(service)

    with TestClient(app) as client:
        response = client.post(
            "/notes",
            json={
                "content": "Need to pick up my shirt.",
                "about": [
                    {
                        "kind": "item",
                        "ref": {"collection": "item", "key": "item_shirt_001"},
                    },
                    {"kind": "place", "label": "John's place"},
                ],
            },
        )

    app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 201
    assert payload["note_id"] == "note_001"
    assert payload["version"] == 1
    assert payload["content"] == "Need to pick up my shirt."
    assert payload["resolved_about"] == [
        {"kind": "item", "collection": "item", "key": "item_shirt_001"}
    ]
    assert payload["pending_about"] == [{"kind": "place", "label": "John's place"}]


def test_put_note_endpoint_returns_conflict_in_shared_error_shape() -> None:
    service = NotesService(InMemoryNotesRepository())
    app.dependency_overrides[get_notes_handler] = lambda: NotesHandler(service)

    with TestClient(app) as client:
        created = client.post("/notes", json={"content": "Need to pick up my shirt."})
        note_id = created.json()["note_id"]
        client.patch(
            f"/notes/{note_id}",
            json={"addendum": "It is the blue one.", "version": 1},
        )
        response = client.put(
            f"/notes/{note_id}",
            json={"content": "Need to pick it up tomorrow.", "version": 1},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "error": "version_conflict",
        "details": [
            {
                "field": "version",
                "message": "Version does not match latest note version.",
                "code": "version_conflict",
                "context": {
                    "note_id": note_id,
                    "current_version": 2,
                    "requested_version": 1,
                },
            }
        ],
        "request_id": None,
    }


def test_get_missing_note_endpoint_returns_not_found_error_shape() -> None:
    service = NotesService(InMemoryNotesRepository())
    app.dependency_overrides[get_notes_handler] = lambda: NotesHandler(service)

    with TestClient(app) as client:
        response = client.get("/notes/note_missing")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "error": "note_not_found",
        "details": [
            {
                "field": "note_id",
                "message": "No note exists for the provided note_id.",
                "code": "note_not_found",
                "context": {"note_id": "note_missing"},
            }
        ],
        "request_id": None,
    }


def test_search_notes_endpoint_returns_ranked_candidates() -> None:
    service = NotesService(InMemoryNotesRepository())
    app.dependency_overrides[get_notes_handler] = lambda: NotesHandler(service)

    with TestClient(app) as client:
        created = client.post(
            "/notes", json={"content": "Need to pick up my blue PME Oxford shirt."}
        )
        client.post("/notes", json={"content": "Buy more blue ink."})
        note_id = created.json()["note_id"]
        response = client.get("/notes", params={"q": "shirt note"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["note_id"] == note_id
    assert response.json()[0]["content_preview"] == (
        "Need to pick up my blue PME Oxford shirt."
    )


def test_patch_note_endpoint_returns_latest_note_view() -> None:
    service = NotesService(InMemoryNotesRepository())
    app.dependency_overrides[get_notes_handler] = lambda: NotesHandler(service)

    with TestClient(app) as client:
        created = client.post("/notes", json={"content": "Need to pick up my shirt."})
        note_id = created.json()["note_id"]
        response = client.patch(
            f"/notes/{note_id}",
            json={"addendum": "It is the blue one.", "version": 1},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["content"] == (
        "Need to pick up my shirt.\n\nAddendum:\nIt is the blue one."
    )


def test_search_notes_endpoint_can_match_pending_about_labels() -> None:
    service = NotesService(InMemoryNotesRepository())
    app.dependency_overrides[get_notes_handler] = lambda: NotesHandler(service)

    with TestClient(app) as client:
        created = client.post(
            "/notes",
            json={
                "content": "Need to pick up my notebook.",
                "about": [{"kind": "place", "label": "Utrecht Central"}],
            },
        )
        note_id = created.json()["note_id"]
        response = client.get("/notes", params={"q": "utrecht"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["note_id"] == note_id
