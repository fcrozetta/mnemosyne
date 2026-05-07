from __future__ import annotations

import json

import pytest

from app.repository.notes_in_memory import InMemoryNotesRepository
from app.service.notes import NotesService
from app.storage.bootstrap import (
    ALPHA_STORAGE_LAYOUT,
    IndexSpec,
    StorageBootstrapper,
    StorageLayoutConflict,
    TableSpec,
)
from app.storage.in_memory import InMemoryStorageBackend
from app.storage.surreal import SurrealStorageBackend, _define_database_user_sql


def test_service_initializes_alpha_storage_layout() -> None:
    repository = InMemoryNotesRepository()
    service = NotesService(repository=repository)

    result = service.initialize_storage()

    assert result.initialized is True
    assert result.created_tables == ALPHA_STORAGE_LAYOUT.table_names
    assert result.existing_tables == ()
    assert set(result.created_fields) == {
        field.identity for field in ALPHA_STORAGE_LAYOUT.fields
    }
    assert result.existing_fields == ()
    assert result.created_views == ("notes",)
    assert result.existing_views == ()
    assert set(result.created_indexes) == {
        index.identity for index in ALPHA_STORAGE_LAYOUT.indexes
    }
    assert repository.storage_initialized() is True


def test_storage_bootstrap_is_idempotent() -> None:
    repository = InMemoryNotesRepository()
    service = NotesService(repository=repository)

    service.initialize_storage()
    result = service.initialize_storage()

    assert result.created_tables == ()
    assert result.existing_tables == ALPHA_STORAGE_LAYOUT.table_names
    assert result.created_fields == ()
    assert set(result.existing_fields) == {
        field.identity for field in ALPHA_STORAGE_LAYOUT.fields
    }
    assert result.created_views == ()
    assert result.existing_views == ("notes",)
    assert result.created_indexes == ()
    assert set(result.existing_indexes) == {
        index.identity for index in ALPHA_STORAGE_LAYOUT.indexes
    }


def test_about_refs_identity_index_is_unique() -> None:
    about_refs_index = next(
        index
        for index in ALPHA_STORAGE_LAYOUT.indexes
        if index.identity == "about_refs_kind_identity"
    )

    assert about_refs_index.unique is True


def test_relation_tables_define_graph_endpoints() -> None:
    relation_specs = {
        table.name: table
        for table in ALPHA_STORAGE_LAYOUT.tables
        if table.kind == "relation"
    }

    assert relation_specs["note_has_revision"].from_table == "note_roots"
    assert relation_specs["note_has_revision"].to_table == "note_revisions"
    assert relation_specs["note_current_revision"].from_table == "note_roots"
    assert relation_specs["note_current_revision"].to_table == "note_revisions"
    assert relation_specs["revision_previous"].from_table == "note_revisions"
    assert relation_specs["revision_previous"].to_table == "note_revisions"
    assert relation_specs["revision_has_provenance"].from_table == "note_revisions"
    assert relation_specs["revision_has_provenance"].to_table == "provenance_records"
    assert relation_specs["note_about"].from_table == "note_roots"
    assert relation_specs["note_about"].to_table == "about_refs"


def test_schemafull_fields_are_defined_for_persisted_tables() -> None:
    field_types = {
        field.identity: field.type_name for field in ALPHA_STORAGE_LAYOUT.fields
    }

    assert field_types["note_roots.created_at"] == "datetime"
    assert field_types["note_revisions.observed_at"] == "datetime"
    assert field_types["about_refs.resolved"] == "bool"
    assert field_types["note_current_revision.edge_key"] == "string"


def test_surreal_field_validation_accepts_normalized_optional_types() -> None:
    backend = SurrealStorageBackend(
        base_url="http://127.0.0.1:8000",
        namespace="mnemosyne",
        database="mnemosyne",
    )
    field = next(
        field
        for field in ALPHA_STORAGE_LAYOUT.fields
        if field.identity == "about_refs.collection"
    )

    backend._validate_field(
        field,
        "DEFINE FIELD collection ON about_refs TYPE none | string PERMISSIONS FULL",
    )


def test_surreal_database_user_definition_is_database_scoped() -> None:
    statement = _define_database_user_sql(
        "mnemosyne",
        "mnemosyne",
        ("editor",),
    )

    assert statement == (
        "DEFINE USER OVERWRITE mnemosyne "
        'ON DATABASE PASSWORD "mnemosyne" ROLES EDITOR;'
    )


def test_surreal_database_user_signin_uses_database_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_send(
        self: SurrealStorageBackend,
        method: str,
        path: str,
        **kwargs: object,
    ) -> tuple[int, dict[str, str]]:
        calls.append({"method": method, "path": path, **kwargs})
        return 200, {"token": "signed-token"}

    monkeypatch.setattr(SurrealStorageBackend, "_send", fake_send)

    signed = SurrealStorageBackend(
        base_url="http://127.0.0.1:8000",
        namespace="mnemosyne",
        database="mnemosyne",
        username="mnemosyne",
        password="mnemosyne",
    ).sign_in()

    assert signed.token == "signed-token"
    assert signed._authorization_header() == "Bearer signed-token"
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/signin"
    assert calls[0]["authenticate"] is False
    assert calls[0]["include_namespace_database"] is False
    assert json.loads(calls[0]["body"].decode()) == {
        "ns": "mnemosyne",
        "db": "mnemosyne",
        "user": "mnemosyne",
        "pass": "mnemosyne",
    }


def test_surreal_upsert_relation_replaces_existing_in_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    def fake_record_exists(self: SurrealStorageBackend, record_id: str) -> bool:
        assert record_id == "note_current_revision:note_001_current_note_001_v2"
        return False

    def fake_query(self: SurrealStorageBackend, sql: str) -> None:
        queries.append(sql)
        return None

    monkeypatch.setattr(SurrealStorageBackend, "record_exists", fake_record_exists)
    monkeypatch.setattr(SurrealStorageBackend, "query", fake_query)

    backend = SurrealStorageBackend(
        base_url="http://127.0.0.1:8000",
        namespace="mnemosyne",
        database="mnemosyne",
    )

    created = backend.upsert_relation(
        "note_current_revision",
        "note_001_current_note_001_v2",
        "note_roots:note_001",
        "note_revisions:note_001_v2",
        {"edge_key": "note_001_current_note_001_v2"},
        replace_existing_in=True,
    )

    assert created is True
    assert queries == [
        "DELETE note_current_revision WHERE in = note_roots:note_001 "
        "AND id != note_current_revision:note_001_current_note_001_v2 RETURN NONE;",
        "RELATE note_roots:note_001->"
        "note_current_revision:note_001_current_note_001_v2->"
        "note_revisions:note_001_v2 CONTENT "
        '{"edge_key":"note_001_current_note_001_v2"} '
        "RETURN NONE;",
    ]


def test_surreal_matches_layout_returns_false_when_relation_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_database_info(self: SurrealStorageBackend) -> dict[str, object]:
        return {
            "tables": {
                spec.name: {"sql": "placeholder"}
                for spec in ALPHA_STORAGE_LAYOUT.tables
                if spec.name != "note_current_revision"
            }
        }

    monkeypatch.setattr(SurrealStorageBackend, "_database_info", fake_database_info)

    backend = SurrealStorageBackend(
        base_url="http://127.0.0.1:8000",
        namespace="mnemosyne",
        database="mnemosyne",
    )

    assert backend.matches_layout(ALPHA_STORAGE_LAYOUT) is False


def test_notes_is_latest_revision_view() -> None:
    notes_view = next(
        view for view in ALPHA_STORAGE_LAYOUT.views if view.name == "notes"
    )

    assert "FROM note_current_revision" in notes_view.query
    assert "out.content AS content" in notes_view.query
    assert "out.version AS version" in notes_view.query
    assert "type::record('notes', in.note_id) AS id" in notes_view.query


def test_storage_bootstrap_rejects_incompatible_existing_table() -> None:
    storage = InMemoryStorageBackend(
        tables={"note_roots": TableSpec("note_roots", "relation")}
    )

    with pytest.raises(StorageLayoutConflict):
        StorageBootstrapper(storage).initialize()


def test_storage_bootstrap_rejects_incompatible_existing_index() -> None:
    storage = InMemoryStorageBackend(
        tables={spec.name: spec for spec in ALPHA_STORAGE_LAYOUT.tables},
        indexes={
            "about_refs_kind_identity": IndexSpec(
                table="about_refs",
                fields=("kind", "identity"),
                unique=False,
                name="about_refs_kind_identity",
            )
        },
    )

    with pytest.raises(StorageLayoutConflict):
        StorageBootstrapper(storage).initialize()
