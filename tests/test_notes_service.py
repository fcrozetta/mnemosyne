import pytest

from app.schemas.common import EntityRef
from app.schemas.notes import (
    CreateNoteRequest,
    PatchNoteRequest,
    PutNoteRequest,
    ResolvedAboutInput,
    UnresolvedAboutInput,
)
from app.service.notes import NoteNotFoundError, NotesService, NoteVersionConflictError


def dump_models(models: list) -> list[dict]:
    return [model.model_dump() for model in models]


def test_create_and_get_note_round_trip(notes_service: NotesService) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(
            content="Need to pick up my shirt.",
            about=[
                ResolvedAboutInput(
                    kind="item",
                    ref=EntityRef(collection="item", key="item_shirt_001"),
                ),
                UnresolvedAboutInput(kind="location", label="John's place"),
            ],
        )
    )

    fetched = notes_service.get_note(created.note_id)

    assert created.note_id == "note_001"
    assert created.version == 1
    assert fetched == created
    assert dump_models(fetched.resolved_about) == [
        {"kind": "item", "collection": "item", "key": "item_shirt_001"}
    ]
    assert dump_models(fetched.pending_about) == [
        {"kind": "location", "label": "John's place"}
    ]


def test_patch_addendum_and_pending_about_dedupe(
    notes_service: NotesService,
) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(
            content="Need to pick up my shirt.",
            about=[UnresolvedAboutInput(kind="location", label="John's place")],
        )
    )

    patched = notes_service.patch_note(
        created.note_id,
        PatchNoteRequest(
            addendum="It is the blue one.",
            add_about=[
                UnresolvedAboutInput(kind="location", label="  john's   place  "),
                ResolvedAboutInput(
                    kind="item",
                    ref=EntityRef(collection="item", key="item_shirt_001"),
                ),
                ResolvedAboutInput(
                    kind="item",
                    ref=EntityRef(collection="item", key="item_shirt_001"),
                ),
            ],
            version=1,
        ),
    )

    assert patched.version == 2
    assert (
        patched.content == "Need to pick up my shirt.\n\nAddendum:\nIt is the blue one."
    )
    assert dump_models(patched.pending_about) == [
        {"kind": "location", "label": "John's place"}
    ]
    assert dump_models(patched.resolved_about) == [
        {"kind": "item", "collection": "item", "key": "item_shirt_001"}
    ]


def test_put_creates_fully_specified_revision_without_inheriting_context(
    notes_service: NotesService,
) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(
            content="Need to pick up my shirt.",
            about=[UnresolvedAboutInput(kind="location", label="John's place")],
        )
    )

    replaced = notes_service.put_note(
        created.note_id,
        PutNoteRequest(
            content="Need to pick up my blue shirt on Saturday.",
            about=[
                ResolvedAboutInput(
                    kind="item",
                    ref=EntityRef(collection="item", key="item_shirt_001"),
                )
            ],
            version=1,
        ),
    )

    assert replaced.version == 2
    assert replaced.content == "Need to pick up my blue shirt on Saturday."
    assert dump_models(replaced.resolved_about) == [
        {"kind": "item", "collection": "item", "key": "item_shirt_001"}
    ]
    assert dump_models(replaced.pending_about) == []


def test_put_with_stale_version_raises_conflict(
    notes_service: NotesService,
) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(content="Need to pick up my shirt.")
    )
    notes_service.patch_note(
        created.note_id,
        PatchNoteRequest(addendum="It is the blue one.", version=1),
    )

    with pytest.raises(NoteVersionConflictError) as exc_info:
        notes_service.put_note(
            created.note_id,
            PutNoteRequest(content="Need to pick it up tomorrow.", version=1),
        )

    assert exc_info.value.error == "version_conflict"
    assert exc_info.value.details[0].context == {
        "note_id": created.note_id,
        "current_version": 2,
        "requested_version": 1,
    }


def test_get_missing_note_raises_not_found(notes_service: NotesService) -> None:
    with pytest.raises(NoteNotFoundError) as exc_info:
        notes_service.get_note("note_missing")

    assert exc_info.value.error == "note_not_found"
    assert exc_info.value.details[0].context == {"note_id": "note_missing"}


def test_search_notes_returns_ranked_results(notes_service: NotesService) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(content="Need to pick up my blue PME Oxford shirt.")
    )
    notes_service.create_note(CreateNoteRequest(content="Buy more blue ink."))

    results = notes_service.search_notes("shirt note")

    assert results[0].note_id == created.note_id
    assert results[0].version == 1
    assert results[0].content_preview == "Need to pick up my blue PME Oxford shirt."
    assert results[0].observed_at == created.observed_at
    assert results[0].score > 0


def test_search_notes_uses_pending_about_labels_from_latest_revision(
    notes_service: NotesService,
) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(
            content="Need to pick up my notebook.",
            about=[UnresolvedAboutInput(kind="location", label="Utrecht Central")],
        )
    )

    results = notes_service.search_notes("utrecht")

    assert results[0].note_id == created.note_id


def test_put_updates_search_to_latest_note_state(notes_service: NotesService) -> None:
    created = notes_service.create_note(
        CreateNoteRequest(content="Track alpha-token in the first revision.")
    )

    notes_service.put_note(
        created.note_id,
        PutNoteRequest(
            content="Track beta-token in the second revision.",
            version=1,
        ),
    )

    beta_results = notes_service.search_notes("beta-token")
    alpha_results = notes_service.search_notes("alpha-token")

    assert beta_results[0].note_id == created.note_id
    assert all(result.note_id != created.note_id for result in alpha_results)
