# Claim 0052: Notes Have an API-Level Test Baseline

## Statement

The notes runtime has an API-level test baseline that exercises the FastAPI
routes with dependency overrides, not just the service layer.

## Scope

- API tests cover:
  - note creation response shape
  - note search response shape
  - successful patch response shape
  - search against pending `about` labels
  - shared `404` error payload shape
  - shared `409` conflict payload shape
- API tests use `TestClient` with dependency overrides so they stay fast and do
  not require Docker for the baseline.

## Acceptance Checks

- `tests/test_notes_api.py` exists.
- API tests run through the real FastAPI app.
- Error responses are validated against the shared top-level error shape rather
  than FastAPI's default `detail` wrapper.
