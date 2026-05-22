# ArcadeDB Observations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SurrealDB note-first alpha backend with an ArcadeDB-backed observation model centered on `Observation`, `Revision`, `Entity`, `Claim`, and `Source`.

**Architecture:** The public API moves from `/notes` to `/observations`. Notes become one observation subtype. Storage uses ArcadeDB HTTP/JSON commands with graph vertex and edge types, while the in-memory repository mirrors the same observation semantics for fast API tests.

**Tech Stack:** Python 3.12, FastAPI, pytest, Ruff, Docker Compose, ArcadeDB HTTP API.

---

## File Structure

- Create `app/models/observations.py`: domain dataclasses, enums, ID helpers, merge/search helpers.
- Create `app/repository/observations.py`: repository protocol for observation behavior.
- Create `app/repository/observations_in_memory.py`: in-memory implementation used by API tests.
- Create `app/repository/observations_arcade.py`: ArcadeDB implementation.
- Create `app/service/observations.py`: service wrapper over the repository.
- Create `app/storage/arcade.py`: ArcadeDB HTTP client and layout bootstrap.
- Create `db/schema.arcadesql`: ArcadeDB schema bootstrap script.
- Modify `app/main.py`: replace `/notes` routes with `/observations` routes.
- Modify `app/dependencies.py`: select `arcade` or `in-memory` observation repository.
- Modify `docker-compose.yml`, `docker-compose.dev.yml`, `Makefile`, `.env.example`, `README.md`, and docs to use ArcadeDB.
- Replace note/surreal tests with observation/arcade tests.
- Delete SurrealDB storage, repository, schema, seed, and view files after equivalent tests pass.

## Task 1: Observation Domain Model

**Files:**
- Create: `app/models/observations.py`
- Test: `tests/test_observations_model.py`

- [ ] **Step 1: Write failing model tests**

```python
from datetime import UTC, datetime

from app.models.observations import (
    EntityMentionInput,
    EntityType,
    Observation,
    ObservationRevision,
    ObservationType,
    SourceInput,
    create_revision_id,
    normalize_label,
)


def test_revision_id_is_scoped_to_observation_and_version() -> None:
    assert create_revision_id("obs_01ABC", 2) == "obs_01ABC:v2"


def test_entity_labels_normalize_for_lookup() -> None:
    mention = EntityMentionInput(type=EntityType.LOCATION, label="  John's   Place ")
    assert mention.normalized_label == "john's place"


def test_observation_latest_revision_returns_highest_version() -> None:
    created_at = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
    observation = Observation(
        observation_id="obs_01ABC",
        type=ObservationType.NOTE,
        created_at=created_at,
        updated_at=created_at,
        revisions=(
            ObservationRevision(
                revision_id="obs_01ABC:v1",
                observation_id="obs_01ABC",
                version=1,
                content="one",
                content_format="text/plain",
                observed_at=created_at,
                created_at=created_at,
            ),
            ObservationRevision(
                revision_id="obs_01ABC:v2",
                observation_id="obs_01ABC",
                version=2,
                content="two",
                content_format="text/plain",
                observed_at=created_at,
                created_at=created_at,
            ),
        ),
    )

    assert observation.latest_revision is not None
    assert observation.latest_revision.version == 2
```

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run pytest tests/test_observations_model.py -q`

Expected: fail because `app.models.observations` does not exist.

- [ ] **Step 3: Implement model**

Add enums and dataclasses for `ObservationType`, `EntityType`, `SourceType`, `EntityMentionInput`, `SourceInput`, `ObservationRevision`, `Observation`, `CreateObservationInput`, `PatchObservationInput`, `ObservationSearchResult`, and errors equivalent to not-found/version-conflict.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv run pytest tests/test_observations_model.py -q`

Expected: pass.

## Task 2: In-Memory Observation Repository

**Files:**
- Create: `app/repository/observations.py`
- Create: `app/repository/observations_in_memory.py`
- Test: `tests/test_observations_in_memory.py`

- [ ] **Step 1: Write failing repository flow test**

Test create, get, search, patch, version conflict, revision-scoped mentions, and context-equivalent related observations through the repository protocol.

- [ ] **Step 2: Run test and verify RED**

Run: `uv run pytest tests/test_observations_in_memory.py -q`

Expected: fail because repository files do not exist.

- [ ] **Step 3: Implement repository protocol and in-memory repository**

Implement `create_observation`, `get_observation`, `search_observations`, `patch_observation`, `get_observation_context`, `initialize_storage`, and `storage_initialized`.

- [ ] **Step 4: Run test and verify GREEN**

Run: `uv run pytest tests/test_observations_in_memory.py -q`

Expected: pass.

## Task 3: `/observations` API

**Files:**
- Create: `app/service/observations.py`
- Modify: `app/dependencies.py`
- Modify: `app/main.py`
- Test: `tests/test_observations_api.py`
- Replace/remove: `tests/test_notes_api.py`

- [ ] **Step 1: Write failing API tests**

Test:

- `POST /observations` accepts `{type:"note", content, mentions, source}` and returns `observation_id`, `type`, `version`, `content`, `mentions`, and `source`.
- `GET /observations/{observation_id}` returns latest revision.
- `PATCH /observations/{observation_id}` requires latest `version` and creates a new revision.
- stale patch returns `409 version_conflict` with `observation_id`.
- `GET /observations?q=shirt` searches latest revision content.
- `/notes` returns 404 because compatibility is intentionally broken.

- [ ] **Step 2: Run tests and verify RED**

Run: `MNEMOSYNE_STORAGE_BACKEND=in-memory uv run pytest tests/test_observations_api.py -q`

Expected: fail because `/observations` routes do not exist.

- [ ] **Step 3: Implement service, dependency, route parsing, serialization, and OpenAPI components**

Replace note-oriented route handlers with observation-oriented route handlers. Keep healthz fail-closed behavior.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `MNEMOSYNE_STORAGE_BACKEND=in-memory uv run pytest tests/test_observations_api.py -q`

Expected: pass.

## Task 4: ArcadeDB Schema Bootstrap

**Files:**
- Create: `app/storage/arcade.py`
- Create: `db/schema.arcadesql`
- Modify: `app/storage/bootstrap.py`
- Test: `tests/test_arcadedb_schema.py`
- Test: `tests/test_storage_bootstrap.py`

- [ ] **Step 1: Write failing schema tests**

Assert the schema defines vertex types `Observation`, `Note`, `DocumentObservation`, `MessageObservation`, `Revision`, `Entity`, `Person`, `Location`, `Item`, `Topic`, `UnknownEntity`, `Claim`, `Source`, edge types `HasRevision`, `CurrentRevision`, `PreviousRevision`, `ObservedFrom`, `Mentions`, `About`, `SupportedBy`, and unique indexes for domain IDs plus one current revision edge per observation.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run pytest tests/test_arcadedb_schema.py tests/test_storage_bootstrap.py -q`

Expected: fail because ArcadeDB schema files and layout are missing.

- [ ] **Step 3: Implement ArcadeDB layout and bootstrap client**

Use ArcadeDB HTTP API:

- `GET /api/v1/ready` for readiness.
- `POST /api/v1/server` with `{"command":"create database mnemosyne"}` for bootstrap.
- `POST /api/v1/command/{database}` with `{"language":"sqlscript","command":...}` for schema.
- Basic auth with `root` credentials for local alpha.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv run pytest tests/test_arcadedb_schema.py tests/test_storage_bootstrap.py -q`

Expected: pass.

## Task 5: ArcadeDB Observation Repository

**Files:**
- Create: `app/repository/observations_arcade.py`
- Modify: `app/dependencies.py`
- Test: `tests/test_observations_arcade_repository.py`

- [ ] **Step 1: Write failing SQL construction tests with a fake Arcade backend**

Assert create writes:

- `CREATE VERTEX Note`
- `CREATE VERTEX Revision`
- `CREATE EDGE HasRevision`
- `CREATE EDGE CurrentRevision`
- source upsert and `ObservedFrom`
- entity upsert and `Mentions`

Assert patch uses the current version guard and rewires `CurrentRevision`.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run pytest tests/test_observations_arcade_repository.py -q`

Expected: fail because repository does not exist.

- [ ] **Step 3: Implement ArcadeDB repository**

Implement using SQL scripts and parameters where practical. Keep all public domain IDs independent from ArcadeDB RIDs. Use `CREATE EDGE ... IF NOT EXISTS` plus unique indexes for idempotent edges.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv run pytest tests/test_observations_arcade_repository.py -q`

Expected: pass.

## Task 6: Compose, Makefile, and Docs

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.dev.yml`
- Modify: `Makefile`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/alpha-api-contract.md`
- Modify: `docs/alpha-model.md`

- [ ] **Step 1: Write failing config tests**

Update tests to assert ArcadeDB service, default host port `2480`, root password config via `JAVA_OPTS`, and no SurrealDB service.

- [ ] **Step 2: Run config tests and verify RED**

Run: `uv run pytest tests/test_storage_bootstrap.py -q`

Expected: fail while compose/docs still reference SurrealDB.

- [ ] **Step 3: Update config and docs**

Switch `MNEMOSYNE_STORAGE_BACKEND` default to `arcade`, replace SurrealDB docs with ArcadeDB, and document `/observations` as canonical.

- [ ] **Step 4: Run config tests and verify GREEN**

Run: `uv run pytest tests/test_storage_bootstrap.py -q`

Expected: pass.

## Task 7: Remove SurrealDB Code

**Files:**
- Delete: `app/storage/surreal.py`
- Delete: `app/repository/notes_surreal.py`
- Delete: `db/schema.surql`
- Delete: `db/seed.surql`
- Delete: `db/views.surql`
- Delete/replace: `tests/test_surrealql_import_files.py`
- Delete/replace: `tests/test_notes_surreal_repository.py`

- [ ] **Step 1: Delete dead SurrealDB files**

Remove storage/repository/schema files after ArcadeDB tests are green.

- [ ] **Step 2: Search for stale references**

Run: `rg "Surreal|SURREAL|surreal|/notes|note_id|notes_" app tests docs README.md Makefile docker-compose.yml docker-compose.dev.yml`

Expected: no stale active references except intentional historical notes in the schema design doc.

- [ ] **Step 3: Run full tests and lint**

Run:

```bash
uv run pytest -q
uv run ruff check .
```

Expected: pass.

## Self-Review

Spec coverage:

- `/observations` canonical API: Task 3.
- ArcadeDB graph schema: Task 4.
- Observation/revision/entity/source model: Tasks 1, 2, 4, 5.
- Claims in schema but not active API writes: Tasks 4 and 5 keep support edges available; claim API is deferred.
- SurrealDB deletion: Task 7.

Placeholder scan:

- No `TBD` or `TODO` entries.
- Claim API is explicitly deferred, not left unspecified inside the implementation scope.

Type consistency:

- Public ID is `observation_id`.
- Revision ID is `obs_...:vN`.
- Revision-to-entity edge is `Mentions`.
- Claim-to-entity edge is `About`.

