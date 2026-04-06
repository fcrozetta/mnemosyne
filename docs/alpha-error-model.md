# Mnemosyne Alpha Error Model And Schema Versioning

This document defines the shared error payload and the schema-version signaling
rules for `0.1.0-alpha`.

See also: [Alpha API contract](./alpha-api-contract.md)

## Decision

For alpha, Mnemosyne uses:

- one shared JSON error shape across note endpoints
- one explicit response header for schema-version signaling
- stable public error codes that do not leak DB or graph internals

That is enough for alpha. Anything more elaborate is ceremony.

## Shared Error Shape

All application-level error responses should converge on this payload:

```json
{
  "error": "version_conflict",
  "details": [
    {
      "field": "version",
      "message": "Version does not match latest note version.",
      "code": "version_conflict",
      "context": {
        "note_id": "note_001",
        "current_version": 2,
        "requested_version": 1
      }
    }
  ],
  "request_id": null
}
```

Top-level fields:

- `error`: stable high-level error identifier
- `details`: structured detail entries
- `request_id`: optional correlation id for logs and tracing

Detail fields:

- `field`: optional field or parameter reference
- `message`: human-readable explanation
- `code`: stable machine-readable detail code
- `context`: optional structured metadata

## Error Flow

```mermaid
flowchart TD
    A[Client request] --> B{Valid request?}
    B -- no --> C[400 ErrorResponse]
    B -- yes --> D{Latest version matches?}
    D -- no --> E[409 ErrorResponse]
    D -- yes --> F{Target note exists?}
    F -- no --> G[404 ErrorResponse]
    F -- yes --> H[2xx success response]
```

## Alpha Error Catalog

The exact catalog can grow, but alpha should at least reserve these stable
top-level identifiers:

- `validation_error`
- `invalid_note_patch`
- `note_not_found`
- `version_conflict`
- `internal_error`

Detail `code` values may be narrower, but should remain aligned with the same
public vocabulary.

## Public Naming Rules

- error names must describe API behavior, not storage internals
- do not expose collection names, edge names, AQL terms, or Arango-specific
  implementation details in `error` or `code`
- `note_not_found` is acceptable
- `latest_revision_edge_missing` is not

## Schema Version Signaling

Alpha uses one response header:

```http
X-Mnemosyne-Schema-Version: 0.1.0-alpha
```

Rules:

- success and error responses should expose the same schema version header
- payload bodies do not need an extra `schema_version` field in alpha
- the public contract version is signaled at the HTTP layer, not by leaking
  storage revision ids
- breaking API contract changes require a schema-version bump and updated docs

## Version Semantics

Do not conflate schema version with note version.

- `X-Mnemosyne-Schema-Version` describes the public API contract version
- `version` inside note payloads describes optimistic concurrency for one note

Those are different things and should stay different.

## Current Alpha Scope

For `0.1.0-alpha`, the required guarantees are:

- `400`, `404`, and `409` use the shared `ErrorResponse` shape
- note writes and reads use stable public error names
- schema-version signaling exists and is explicit
- public docs refer to public API terms, not DB internals

## Deferred

- path or media-type versioning
- multi-schema negotiation
- endpoint-specific error envelopes
- graph/path-specific error formats
