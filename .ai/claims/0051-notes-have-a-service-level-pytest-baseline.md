# Claim 0051: Notes Have a Service-Level pytest Baseline

## Statement

The notes runtime has a service-level pytest baseline that exercises the note
contract against the in-memory repository for fast feedback.

## Scope

- Tests cover:
  - create and get round-trip
  - patch addendum behavior
  - deterministic unresolved `about` dedupe
  - put semantics for fully specified new revisions
  - stale-version conflict handling
  - note-not-found behavior
  - latest-note search ranking through current note state
  - search matches against pending `about` labels
  - search reflects the latest note state after `PUT`
- The baseline uses `NotesService` plus `InMemoryNotesRepository` rather than
  requiring Docker for every test run.

## Rules

- Fast tests should validate note behavior independently of Arango integration.
- Service-level behavior coverage is the minimum baseline and should remain
  green even as integration coverage grows.

## Acceptance Checks

- `tests/` exists with service-level note tests.
- `uv run pytest -q` passes locally.
- `uv run ruff check app tests` passes locally.
