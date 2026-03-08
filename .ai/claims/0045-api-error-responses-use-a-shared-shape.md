# Claim 0045: API Error Responses Use a Shared Shape

## Statement

Mnemosyne API endpoints return a shared typed error payload rather than
endpoint-specific ad hoc error bodies.

## Shape

- `error`: stable top-level error identifier
- `details`: list of structured detail entries
- `request_id`: optional request correlation field

Each detail entry contains:

- `field`: optional field reference
- `message`: human-readable explanation
- `code`: stable machine-readable detail code
- `context`: optional structured metadata

## Rules

- Validation and service-layer failures should converge on the shared error
  shape.
- `404` and `409` responses for notes should use the shared error payload.
- Error payloads should remain typed in Pydantic for OpenAPI generation and
  handler reuse.

## Acceptance Checks

- Shared error schemas exist in `app/schemas/errors.py`.
- Notes endpoints document `400`, `404`, and `409` responses with the shared
  error model.
- Service-layer note failures can be mapped into the shared error payload.
