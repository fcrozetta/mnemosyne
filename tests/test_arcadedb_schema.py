from __future__ import annotations

from pathlib import Path

from app.storage.arcade import ArcadeStorageBackend

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _schema() -> str:
    return (PROJECT_ROOT / "db/schema.arcadesql").read_text()


def test_arcadedb_schema_defines_observation_truth_graph() -> None:
    schema = _schema()

    assert "CREATE VERTEX TYPE Observation IF NOT EXISTS;" in schema
    assert "CREATE VERTEX TYPE Note IF NOT EXISTS EXTENDS Observation;" in schema
    assert (
        "CREATE VERTEX TYPE DocumentObservation IF NOT EXISTS EXTENDS Observation;"
        in schema
    )
    assert (
        "CREATE VERTEX TYPE MessageObservation IF NOT EXISTS EXTENDS Observation;"
        in schema
    )
    assert "CREATE VERTEX TYPE Revision IF NOT EXISTS;" in schema
    assert "CREATE VERTEX TYPE Entity IF NOT EXISTS;" in schema
    assert "CREATE VERTEX TYPE Person IF NOT EXISTS EXTENDS Entity;" in schema
    assert "CREATE VERTEX TYPE Location IF NOT EXISTS EXTENDS Entity;" in schema
    assert "CREATE VERTEX TYPE Item IF NOT EXISTS EXTENDS Entity;" in schema
    assert "CREATE VERTEX TYPE Topic IF NOT EXISTS EXTENDS Entity;" in schema
    assert "CREATE VERTEX TYPE UnknownEntity IF NOT EXISTS EXTENDS Entity;" in schema
    assert "CREATE VERTEX TYPE Claim IF NOT EXISTS;" in schema
    assert "CREATE VERTEX TYPE Source IF NOT EXISTS;" in schema


def test_arcadedb_schema_defines_edges_and_current_revision_index() -> None:
    schema = _schema()

    assert "CREATE EDGE TYPE HasRevision IF NOT EXISTS;" in schema
    assert "CREATE EDGE TYPE CurrentRevision IF NOT EXISTS;" in schema
    assert "CREATE EDGE TYPE PreviousRevision IF NOT EXISTS;" in schema
    assert "CREATE EDGE TYPE ObservedFrom IF NOT EXISTS;" in schema
    assert "CREATE EDGE TYPE Mentions IF NOT EXISTS;" in schema
    assert "CREATE EDGE TYPE About IF NOT EXISTS;" in schema
    assert "CREATE EDGE TYPE SupportedBy IF NOT EXISTS;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON CurrentRevision (`@out`) UNIQUE;" in schema


def test_arcadedb_schema_defines_domain_id_indexes() -> None:
    schema = _schema()

    assert (
        "UPDATE Revision SET observation = observation_id "
        "WHERE observation IS NULL AND observation_id IS NOT NULL;"
        in schema
    )
    assert "UPDATE Observation SET id = observation_id" in schema
    assert "UPDATE Revision SET id = revision_id" in schema
    assert "UPDATE Entity SET id = entity_id" in schema
    assert "UPDATE Claim SET id = claim_id" in schema
    assert "UPDATE Source SET id = source_id" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Observation (id) UNIQUE;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Revision (id) UNIQUE;" in schema
    assert (
        "CREATE INDEX IF NOT EXISTS ON Revision (observation, version) UNIQUE;"
        in schema
    )
    assert "CREATE INDEX IF NOT EXISTS ON Entity (id) UNIQUE;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Claim (id) UNIQUE;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Source (id) UNIQUE;" in schema
    assert (
        "CREATE INDEX IF NOT EXISTS ON Entity (entity_type, normalized_label) UNIQUE;"
        in schema
    )
    assert (
        "CREATE INDEX IF NOT EXISTS ON Source (source_type, label, source_ref) "
        "UNIQUE NULL_STRATEGY INDEX;"
        in schema
    )


def test_arcadedb_schema_drops_legacy_identity_indexes() -> None:
    schema = _schema()

    assert "DROP INDEX `Observation[observation_id]` IF EXISTS;" in schema
    assert "DROP INDEX `Revision[revision_id]` IF EXISTS;" in schema
    assert "DROP INDEX `Revision[observation_id,version]` IF EXISTS;" in schema
    assert "DROP INDEX `Entity[entity_id]` IF EXISTS;" in schema
    assert "DROP INDEX `Claim[claim_id]` IF EXISTS;" in schema
    assert "DROP INDEX `Source[source_id]` IF EXISTS;" in schema


def test_arcade_backend_applies_schema_one_statement_at_a_time() -> None:
    calls: list[tuple[str, str, object | None]] = []

    class _FakeBackend(ArcadeStorageBackend):
        def _send(
            self,
            method: str,
            path: str,
            *,
            body: object | None = None,
        ) -> object:
            calls.append((method, path, body))
            return {"result": "ok"}

    backend = _FakeBackend(
        base_url="http://127.0.0.1:2480",
        database="mnemosyne",
        username="root",
        password="mnemosyne-root",
    )

    backend.apply_schema(
        "CREATE PROPERTY Observation.id IF NOT EXISTS STRING;\n\n"
        "UPDATE Observation SET id = observation_id;"
    )

    assert calls == [
        (
            "POST",
            "/api/v1/command/mnemosyne",
            {
                "language": "sqlscript",
                "command": "CREATE PROPERTY Observation.id IF NOT EXISTS STRING;",
            },
        ),
        (
            "POST",
            "/api/v1/command/mnemosyne",
            {
                "language": "sqlscript",
                "command": "UPDATE Observation SET id = observation_id;",
            },
        ),
    ]


def test_arcade_backend_creates_database_and_applies_schema() -> None:
    calls: list[tuple[str, str, object | None]] = []

    class _FakeBackend(ArcadeStorageBackend):
        def _send(
            self,
            method: str,
            path: str,
            *,
            body: object | None = None,
        ) -> object:
            calls.append((method, path, body))
            if path == "/api/v1/exists/mnemosyne":
                return {"result": False}
            return {"result": "ok"}

    backend = _FakeBackend(
        base_url="http://127.0.0.1:2480",
        database="mnemosyne",
        username="root",
        password="mnemosyne-root",
    )

    backend.ensure_database()
    backend.apply_schema("CREATE VERTEX TYPE Observation IF NOT EXISTS;")

    assert calls == [
        ("GET", "/api/v1/exists/mnemosyne", None),
        (
            "POST",
            "/api/v1/server",
            {"command": "create database mnemosyne"},
        ),
        (
            "POST",
            "/api/v1/command/mnemosyne",
            {
                "language": "sqlscript",
                "command": "CREATE VERTEX TYPE Observation IF NOT EXISTS;",
            },
        ),
    ]
