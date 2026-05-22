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
        "CREATE INDEX IF NOT EXISTS ON Observation (observation_id) UNIQUE;"
        in schema
    )
    assert "CREATE INDEX IF NOT EXISTS ON Revision (revision_id) UNIQUE;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Entity (entity_id) UNIQUE;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Claim (claim_id) UNIQUE;" in schema
    assert "CREATE INDEX IF NOT EXISTS ON Source (source_id) UNIQUE;" in schema
    assert (
        "CREATE INDEX IF NOT EXISTS ON Entity (entity_type, normalized_label) UNIQUE;"
        in schema
    )


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
        password="root",
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
