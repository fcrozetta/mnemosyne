# Claim 0055: Notes Have Arango-Backed Integration Tests

## Statement

The notes runtime has Arango-backed integration tests that validate current-note
search behavior and repository-level version enforcement against a real local
database.

## Scope

- Integration tests cover:
  - note creation updating current searchable fields on `note`
  - `GET /notes`-equivalent repository search finding notes by current content
  - repository search finding notes by pending `about` labels after View refresh
  - `PUT`-style revision writes replacing current searchable state
  - repository-level stale-version conflict enforcement
- Search integration tests use short polling because ArangoSearch visibility is
  not guaranteed to be synchronous at the exact write boundary.

## Acceptance Checks

- `tests/test_notes_repository_arango.py` exists.
- Integration tests pass against a seeded local ArangoDB.
- Search integration validates current state on `note`, not a duplicate search
  collection.
