from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _schema() -> str:
    return (PROJECT_ROOT / "db/schema.surql").read_text()


def _seed() -> str:
    return (PROJECT_ROOT / "db/seed.surql").read_text()


def _views() -> str:
    return (PROJECT_ROOT / "db/views.surql").read_text()


def _makefile() -> str:
    return (PROJECT_ROOT / "Makefile").read_text()


def test_surrealql_import_files_use_import_mode() -> None:
    schema = _schema()
    seed = _seed()

    assert schema.startswith("OPTION IMPORT;\n")
    assert seed.startswith("OPTION IMPORT;\n")


def test_schema_import_defines_surreal_graph_relations() -> None:
    schema = _schema()

    assert (
        "DEFINE TABLE IF NOT EXISTS note_has_revision SCHEMAFULL TYPE RELATION "
        "IN note_roots OUT note_revisions ENFORCED;"
    ) in schema
    assert (
        "DEFINE TABLE IF NOT EXISTS note_current_revision SCHEMAFULL TYPE RELATION "
        "IN note_roots OUT note_revisions ENFORCED;"
    ) in schema
    assert (
        "DEFINE TABLE IF NOT EXISTS revision_previous SCHEMAFULL TYPE RELATION "
        "IN note_revisions OUT note_revisions ENFORCED;"
    ) in schema
    assert (
        "DEFINE TABLE IF NOT EXISTS revision_has_provenance SCHEMAFULL TYPE "
        "RELATION IN note_revisions OUT provenance_records ENFORCED;"
    ) in schema
    assert (
        "DEFINE TABLE IF NOT EXISTS note_about SCHEMAFULL TYPE RELATION "
        "IN note_roots OUT about_refs ENFORCED;"
    ) in schema


def test_schema_import_defines_unique_identity_indexes() -> None:
    schema = _schema()

    assert (
        "DEFINE INDEX IF NOT EXISTS about_refs_kind_identity "
        "ON TABLE about_refs FIELDS kind, identity UNIQUE;"
    ) in schema
    assert (
        "DEFINE INDEX IF NOT EXISTS note_current_revision_in_unique "
        "ON TABLE note_current_revision FIELDS in UNIQUE;"
    ) in schema


def test_notes_view_is_defined_outside_import_mode() -> None:
    schema = _schema()
    views = _views()

    assert "DEFINE TABLE IF NOT EXISTS notes" not in schema
    assert "OPTION IMPORT" not in views
    assert "DEFINE TABLE OVERWRITE notes AS" in views
    assert "FROM note_current_revision" in views


def test_seed_import_uses_relation_records() -> None:
    seed = _seed()

    assert "INSERT RELATION INTO note_current_revision" in seed
    assert "UPSERT note_current_revision" not in seed


def test_seed_import_keeps_current_revision_edges_idempotent() -> None:
    seed = _seed()

    assert "DELETE note_current_revision:note_001_current_note_001_v2;" in seed
    assert "DELETE note_current_revision:note_014_current_note_014_v1;" in seed


def test_make_seed_uses_surreal_cli_import_not_python_seed() -> None:
    makefile = _makefile()

    assert "seed: db-bootstrap" in makefile
    assert "$(SURREAL_CLI) import" in makefile
    assert "uv run python -m app.storage.seed" not in makefile


def test_make_bootstrap_keeps_root_and_database_credentials_separate() -> None:
    makefile = _makefile()

    assert "SURREAL_ROOT_USERNAME ?= root" in makefile
    assert "SURREAL_USERNAME ?= mnemosyne" in makefile
    assert "DEFINE USER OVERWRITE $(SURREAL_USERNAME) ON DATABASE" in makefile
