from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from app.models.notes import (
    AboutKind,
    CreateNoteInput,
    Note,
    NoteRevision,
    PatchNoteInput,
    PendingAboutRef,
    Provenance,
    ResolvedAboutRef,
    VersionConflictError,
)
from app.repository.notes_surreal import SurrealNotesRepository
from app.storage.surreal import SurrealRequestError


@dataclass
class _FakeSurrealBackend:
    note_id_results: list[tuple[str, ...]] = field(default_factory=list)
    transaction_errors: list[Exception] = field(default_factory=list)
    current_version: int = 2
    about_rows: list[dict[str, object]] = field(default_factory=list)
    query_calls: list[str] = field(default_factory=list)

    def sign_in(self) -> _FakeSurrealBackend:
        return self

    def query(self, sql: str) -> object:
        self.query_calls.append(sql)

        if sql == "SELECT VALUE note_id FROM note_roots;":
            if self.note_id_results:
                return list(self.note_id_results.pop(0))
            return []

        if sql.startswith("SELECT VALUE current_version FROM ONLY note_roots:"):
            return self.current_version

        if sql.startswith("SELECT * FROM note_about "):
            return list(self.about_rows)

        if sql.startswith("BEGIN TRANSACTION;") and self.transaction_errors:
            error = self.transaction_errors.pop(0)
            raise error

        return []


def test_surreal_repository_create_note_uses_transactional_create_only_path() -> None:
    runtime = _FakeSurrealBackend(note_id_results=[("note_001", "note_014")])
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    expected = Note(
        note_id="note_015",
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            NoteRevision(
                version=1,
                content="Need to pick up my shirt.",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 1, tzinfo=UTC),
                pending_about=(
                    PendingAboutRef(kind=AboutKind.LOCATION, label="John's place"),
                ),
                provenance=Provenance(source_type="chat"),
            ),
        ),
    )
    repository._get_note = lambda _backend, _note_id: expected  # type: ignore[method-assign]

    note = repository.create_note(
        CreateNoteInput(
            content="Need to pick up my shirt.",
            about=(PendingAboutRef(kind=AboutKind.LOCATION, label="John's place"),),
            observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            provenance=Provenance(source_type="chat"),
        )
    )

    assert note == expected
    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert "array::first(SELECT VALUE id FROM about_refs" in transaction_sql
    assert 'kind = "location"' in transaction_sql
    assert 'identity = "john\'s place"' in transaction_sql
    assert "CREATE ONLY note_roots:note_015 CONTENT" in transaction_sql
    assert "CREATE ONLY note_revisions:note_015_v1 CONTENT" in transaction_sql
    assert (
        "LET $about_record_0 = IF $about_record_0_existing "
        in transaction_sql
    )
    assert (
        "LET $existing_relation = array::first(SELECT VALUE id FROM note_about "
        in transaction_sql
    )
    assert '"label":"John\'s place"' in transaction_sql
    assert (
        'INSERT RELATION INTO note_current_revision '
        '{ id: "note_015_current_note_015_v1"'
        in transaction_sql
    )
    assert "in: note_roots:note_015" in transaction_sql
    assert "out: note_revisions:note_015_v1" in transaction_sql


def test_surreal_repository_create_note_retries_when_note_id_conflicts() -> None:
    runtime = _FakeSurrealBackend(
        note_id_results=[("note_001",), ("note_001", "note_002")],
        transaction_errors=[
            SurrealRequestError("mnemosyne.create_conflict:note_002"),
        ],
    )
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    note = repository.create_note(CreateNoteInput(content="Retry on duplicate."))

    assert note.note_id == "note_003"
    transaction_sqls = [
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    ]
    assert len(transaction_sqls) == 2
    assert "CREATE ONLY note_roots:note_003 CONTENT" in transaction_sqls[-1]


def test_surreal_repository_create_note_retries_when_about_ref_create_conflicts(
) -> None:
    runtime = _FakeSurrealBackend(
        note_id_results=[(), ()],
        transaction_errors=[
            SurrealRequestError(
                "Database record "
                "`about_refs:about_location_6a6f686e277320706c616365` already exists"
            ),
        ],
    )
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    note = repository.create_note(
        CreateNoteInput(
            content="Retry shared about ref allocation.",
            about=(PendingAboutRef(kind=AboutKind.LOCATION, label="John's place"),),
        )
    )

    assert note.note_id == "note_001"
    transaction_sqls = [
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    ]
    assert len(transaction_sqls) == 2


def test_surreal_repository_patch_note_uses_atomic_version_guard() -> None:
    runtime = _FakeSurrealBackend()
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)

    current = Note(
        note_id="note_001",
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            NoteRevision(
                version=1,
                content="Need to pick up my shirt.",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    updated = Note(
        note_id="note_001",
        created_at=current.created_at,
        revisions=(
            current.revisions[0],
            NoteRevision(
                version=2,
                content="Need to pick up my shirt.\n\nAddendum:\nIt is the blue one.",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 5, tzinfo=UTC),
                resolved_about=(
                    ResolvedAboutRef(
                        kind=AboutKind.ITEM,
                        collection="item",
                        key="shirt_001",
                    ),
                ),
            ),
        ),
    )
    notes = [current, updated]
    repository._get_note = lambda _backend, _note_id: notes.pop(0)  # type: ignore[method-assign]

    note = repository.patch_note(
        "note_001",
        PatchNoteInput(
            version=1,
            addendum="It is the blue one.",
            add_about=(
                ResolvedAboutRef(
                    kind=AboutKind.ITEM,
                    collection="item",
                    key="shirt_001",
                ),
            ),
        ),
    )

    assert note == updated
    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert "WHERE current_version = 1 RETURN AFTER" in transaction_sql
    assert (
        "THROW \"mnemosyne.version_conflict:note_001:\" "
        "+ <string>$current_version;"
    ) in transaction_sql
    assert (
        "DELETE note_current_revision WHERE in = note_roots:note_001 "
        "AND id != note_current_revision:note_001_current_note_001_v2 RETURN NONE;"
    ) in transaction_sql


def test_surreal_repository_patch_note_translates_atomic_conflict_to_domain_error(
) -> None:
    runtime = _FakeSurrealBackend(
        transaction_errors=[
            SurrealRequestError("mnemosyne.version_conflict:note_001:2"),
        ],
        current_version=2,
    )
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, _note_id: Note(  # type: ignore[method-assign]
        note_id="note_001",
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            NoteRevision(
                version=1,
                content="Need to pick up my shirt.",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )

    with pytest.raises(VersionConflictError) as excinfo:
        repository.patch_note(
            "note_001",
            PatchNoteInput(version=1, addendum="Still the blue one."),
        )

    assert excinfo.value.current_version == 2
    assert excinfo.value.requested_version == 1


def test_surreal_repository_patch_note_retries_when_about_ref_create_conflicts(
) -> None:
    runtime = _FakeSurrealBackend(
        transaction_errors=[
            SurrealRequestError(
                "Cannot insert duplicate value into unique index "
                "about_refs_kind_identity"
            ),
        ]
    )
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    current = Note(
        note_id="note_001",
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(
            NoteRevision(
                version=1,
                content="Need to pick up my shirt.",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
            ),
        ),
    )
    updated = Note(
        note_id="note_001",
        created_at=current.created_at,
        revisions=(
            current.revisions[0],
            NoteRevision(
                version=2,
                content="Need to pick up my shirt.\n\nAddendum:\nAt John's place.",
                observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
                created_at=datetime(2026, 4, 6, 17, 5, tzinfo=UTC),
                pending_about=(
                    PendingAboutRef(kind=AboutKind.LOCATION, label="John's place"),
                ),
            ),
        ),
    )
    notes = [current, updated]
    repository._get_note = lambda _backend, _note_id: notes.pop(0)  # type: ignore[method-assign]

    note = repository.patch_note(
        "note_001",
        PatchNoteInput(
            version=1,
            addendum="At John's place.",
            add_about=(
                PendingAboutRef(kind=AboutKind.LOCATION, label="John's place"),
            ),
        ),
    )

    assert note == updated
    transaction_sqls = [
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    ]
    assert len(transaction_sqls) == 2


def test_surreal_repository_create_note_uses_unambiguous_about_record_keys() -> None:
    runtime = _FakeSurrealBackend(note_id_results=[()])
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    repository.create_note(
        CreateNoteInput(
            content="Track two distinct refs.",
            about=(
                ResolvedAboutRef(
                    kind=AboutKind.ITEM,
                    collection="item:shirt",
                    key="001",
                ),
                ResolvedAboutRef(
                    kind=AboutKind.ITEM,
                    collection="item",
                    key="shirt:001",
                ),
            ),
            observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        )
    )

    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert (
        "LET $about_record_0 = IF $about_record_0_existing "
        in transaction_sql
    )
    assert 'identity = "resolved:6974656d3a7368697274:303031"' in transaction_sql
    assert 'identity = "resolved:6974656d:73686972743a303031"' in transaction_sql


def test_surreal_repository_upserts_about_refs_by_identity_or_legacy_collection_key(
) -> None:
    runtime = _FakeSurrealBackend(note_id_results=[()])
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    repository.create_note(
        CreateNoteInput(
            content="Need to pick up my shirt.",
            about=(
                ResolvedAboutRef(
                    kind=AboutKind.ITEM,
                    collection="item",
                    key="item_shirt_001",
                ),
            ),
            observed_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        )
    )

    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert 'kind = "item"' in transaction_sql
    assert (
        'identity = "resolved:6974656d:6974656d5f73686972745f303031"'
        in transaction_sql
    )
    assert "array::first(SELECT VALUE id FROM about_refs" in transaction_sql
    assert (
        '(identity = "resolved:6974656d:6974656d5f73686972745f303031" '
        'OR (collection = "item" AND key = "item_shirt_001"))'
        in transaction_sql
    )
    assert (
        "CREATE ONLY "
        "about_refs:about_item_6974656d_6974656d5f73686972745f303031"
    ) in transaction_sql
    assert '"label":NULL' not in transaction_sql


def test_surreal_repository_load_about_prefers_note_local_pending_label() -> None:
    runtime = _FakeSurrealBackend(
        about_rows=[
            {
                "label": "john's  place",
                "out": {
                    "kind": "location",
                    "identity": "john's place",
                    "label": "John's place",
                    "resolved": False,
                },
            }
        ]
    )
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)

    _resolved, pending = repository._load_about(runtime, "note_001")

    assert pending == (
        PendingAboutRef(kind=AboutKind.LOCATION, label="john's  place"),
    )


def test_surreal_repository_omits_null_about_ref_fields_in_surreal_payloads() -> None:
    runtime = _FakeSurrealBackend(note_id_results=[()])
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    repository.create_note(
        CreateNoteInput(
            content="Need to pick up my shirt.",
            about=(
                ResolvedAboutRef(
                    kind=AboutKind.ITEM,
                    collection="item",
                    key="item_shirt_001",
                ),
                PendingAboutRef(kind=AboutKind.LOCATION, label="John's place"),
            ),
        )
    )

    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert '"label":NULL' not in transaction_sql
    assert '"collection":NULL' not in transaction_sql
    assert '"key":NULL' not in transaction_sql


def test_surreal_repository_omits_null_provenance_fields_in_surreal_payloads() -> None:
    runtime = _FakeSurrealBackend(note_id_results=[()])
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    repository.create_note(
        CreateNoteInput(
            content="Need to pick up my shirt.",
            provenance=Provenance(source_type="chat"),
        )
    )

    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert (
        "UPSERT provenance_records:provenance_note_001_v1 CONTENT "
        '{"source_type":"chat"}'
    ) in transaction_sql
    assert '"writer":NULL' not in transaction_sql
    assert '"session_id":NULL' not in transaction_sql
    assert '"source_ref":NULL' not in transaction_sql


def test_surreal_repository_load_provenance_uses_valid_surrealql_order() -> None:
    runtime = _FakeSurrealBackend()
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)

    repository._load_provenance(runtime, "note_001", 2)

    assert (
        "SELECT out FROM revision_has_provenance "
        "WHERE in = note_revisions:note_001_v2 LIMIT 1 FETCH out;"
    ) in runtime.query_calls


def test_surreal_repository_reuses_existing_note_about_edge_by_relation() -> None:
    runtime = _FakeSurrealBackend(note_id_results=[()])
    repository = SurrealNotesRepository(runtime=runtime, bootstrap=None)
    repository._get_note = lambda _backend, note_id: Note(  # type: ignore[method-assign]
        note_id=note_id,
        created_at=datetime(2026, 4, 6, 17, 0, tzinfo=UTC),
        revisions=(),
    )

    repository.create_note(
        CreateNoteInput(
            content="Reuse seeded about edge.",
            about=(
                ResolvedAboutRef(
                    kind=AboutKind.ITEM,
                    collection="item",
                    key="item_shirt_001",
                ),
            ),
        )
    )

    transaction_sql = next(
        sql for sql in runtime.query_calls if sql.startswith("BEGIN TRANSACTION;")
    )
    assert (
        "LET $existing_relation = array::first(SELECT VALUE id FROM note_about "
        "WHERE in = note_roots:note_001 AND out = $about_record_0 LIMIT 1);"
    ) in transaction_sql
    assert "ELSE IF $existing_relation {" in transaction_sql
    assert (
        'UPDATE ONLY $existing_relation MERGE {"edge_key":"note_001_about_'
        in transaction_sql
    )
