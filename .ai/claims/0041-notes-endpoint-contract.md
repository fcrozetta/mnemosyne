# Claim 0041: Notes Endpoint Contract

## Statement

`notes` is the reference behavior-first endpoint family for v0.

## Endpoints

- `POST /notes`
  - Creates a new `note` anchor and first `note_revision`.
- `GET /notes`
  - Searches latest-note state and returns ranked candidates for client-side
    note selection.
- `PUT /notes/{note_id}`
  - Creates a fully specified new `note_revision`, links it with `supersedes`,
    and updates `latest_revision`.
- `PATCH /notes/{note_id}`
  - Creates a derived new `note_revision` from the current latest revision by
    applying patch operations such as `addendum` and `add_about`.
- `GET /notes/{note_id}`
  - Returns only the latest note view for now.

## Rules

- API hides internal revision mechanics from the client.
- Client submits note content and concrete `note_id` targets, not revision
  wiring.
- Client owns conversational context and note targeting.
- API does not interpret chat references such as “this note” or “the shirt
  note”.
- `GET /notes` is the search primitive clients use when they need help finding
  a concrete `note_id`.
- Client-facing concurrency uses `version` as an integer and does not expose
  revision internals.
- `PUT /notes/{note_id}` does not inherit prior revision content or context.
- `PATCH /notes/{note_id}` derives a new revision from the latest revision,
  supports structured `addendum`, and merges `add_about` into the new revision
  context with deterministic dedupe.
- `mentions` are deferred from enrichment/manual review and are not required in
  initial write payloads.

## Acceptance Checks

- Note writes do not require clients to manage revision edges.
- Note writes do not require clients to manage revision numbers directly.
- Latest revision is maintained server-side.
- `GET /notes` returns ranked search results over latest-note state only.
- `GET /notes/{note_id}` returns the latest revision only.
- `PATCH /notes/{note_id}` creates a new revision rather than mutating the
  current one.
