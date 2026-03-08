# Claim 0046: Notes Runtime Starts with Router Handler Service Boundaries

## Statement

The initial notes runtime is scaffolded using router, handler, service, and
repository boundaries before Arango persistence models are introduced.

## Scope

- `app/main.py` includes the notes router.
- `app/router/notes.py` owns HTTP route declarations.
- `app/handler/notes.py` maps service errors to HTTP responses.
- `app/service/notes.py` owns note behavior and version checks.
- `app/repository/notes.py` remains an interface boundary until persistence work
  is implemented.

## Rules

- API request and response schemas stay separate from persistence concerns.
- Temporary in-memory behavior is acceptable to validate contracts before the
  repository implementation exists.
- Persistence document models can be introduced later without rewriting the
  public API contract.

## Acceptance Checks

- Notes runtime files exist for router, handler, service, and repository.
- `app/main.py` wires the notes router into the FastAPI application.
- Repository remains an explicit dependency boundary rather than leaking DB
  calls into router or handler code.
