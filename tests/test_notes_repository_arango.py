from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app.models.notes import NoteWritePayload, PendingAboutRecord
from app.repository.notes import RepositoryVersionConflictError
from app.repository.notes_arango import ArangoNotesRepository


def wait_for_search(
    repository: ArangoNotesRepository,
    query: str,
    *,
    expected_note_id: str,
    timeout_seconds: float = 3.0,
) -> list[str]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        results = repository.search_notes(query, limit=10)
        note_ids = [item.note_id for item in results]
        if expected_note_id in note_ids:
            return note_ids
        time.sleep(0.2)
    pytest.fail(
        f"Timed out waiting for {expected_note_id} to appear in search for {query!r}."
    )


def search_note_ids(
    repository: ArangoNotesRepository,
    query: str,
    *,
    timeout_seconds: float = 3.0,
) -> list[str]:
    deadline = time.monotonic() + timeout_seconds
    latest: list[str] = []
    while time.monotonic() < deadline:
        latest = [item.note_id for item in repository.search_notes(query, limit=10)]
        if latest:
            return latest
        time.sleep(0.2)
    return latest


def test_create_note_updates_note_anchor_search_fields(
    arango_notes_repository: ArangoNotesRepository,
) -> None:
    token = f"notebook-{uuid4().hex[:10]}"
    payload = NoteWritePayload(
        content=f"Need to pick up my {token} tomorrow.",
        observed_at=time_to_utc_iso_free(),
        pending_about=[PendingAboutRecord(kind="location", label=token)],
        event_kind="manual_note",
    )

    created = arango_notes_repository.create_note(payload)

    note_doc = arango_notes_repository.db.collection("note").get(created.note_id)
    assert note_doc is not None
    assert note_doc["current_content"] == f"Need to pick up my {token} tomorrow."
    assert note_doc["pending_about_labels"] == [token]
    assert note_doc["observed_at"] is not None
    assert note_doc["updated_at"] is not None

    note_ids = wait_for_search(
        arango_notes_repository,
        token,
        expected_note_id=created.note_id,
    )
    assert created.note_id in note_ids


def test_put_replaces_current_search_state_without_exposing_old_content(
    arango_notes_repository: ArangoNotesRepository,
) -> None:
    old_token = f"old-{uuid4().hex[:8]}"
    new_token = f"new-{uuid4().hex[:8]}"

    created = arango_notes_repository.create_note(
        NoteWritePayload(
            content=f"Track {old_token} in the original note.",
            observed_at=time_to_utc_iso_free(),
            event_kind="manual_note",
        )
    )
    wait_for_search(
        arango_notes_repository,
        old_token,
        expected_note_id=created.note_id,
    )

    updated = arango_notes_repository.create_revision(
        created.note_id,
        NoteWritePayload(
            content=f"Track {new_token} in the rewritten note.",
            observed_at=time_to_utc_iso_free(),
            event_kind="manual_edit",
        ),
        expected_version=1,
    )

    note_ids = wait_for_search(
        arango_notes_repository,
        new_token,
        expected_note_id=updated.note_id,
    )
    assert updated.note_id in note_ids

    old_ids = search_note_ids(arango_notes_repository, old_token)
    assert updated.note_id not in old_ids


def test_patch_conflict_is_enforced_in_real_repository(
    arango_notes_repository: ArangoNotesRepository,
) -> None:
    created = arango_notes_repository.create_note(
        NoteWritePayload(
            content=f"Version conflict check {uuid4().hex[:8]}",
            observed_at=time_to_utc_iso_free(),
            event_kind="manual_note",
        )
    )

    arango_notes_repository.create_revision(
        created.note_id,
        NoteWritePayload(
            content="Second version",
            observed_at=time_to_utc_iso_free(),
            event_kind="manual_edit",
        ),
        expected_version=1,
    )

    with pytest.raises(RepositoryVersionConflictError) as exc_info:
        arango_notes_repository.create_revision(
            created.note_id,
            NoteWritePayload(
                content="Stale third version",
                observed_at=time_to_utc_iso_free(),
                event_kind="manual_edit",
            ),
            expected_version=1,
        )

    assert exc_info.value.expected_version == 1
    assert exc_info.value.current_version == 2


def time_to_utc_iso_free():
    from datetime import UTC, datetime

    return datetime.now(UTC)
