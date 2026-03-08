# Claim 0047: Note Persistence Models Are Separate from API Schemas

## Statement

Internal note persistence models are defined separately from public API schemas
so Arango document and edge shapes do not leak into request or response
contracts.

## Scope

- Internal note models live under `app/models/`.
- Public API note schemas remain under `app/schemas/`.
- Note persistence models include Arango-style documents and edges for:
  - note anchors
  - note revisions
  - provenance events
  - note graph edges such as `belongs_to`, `latest_revision`, `supersedes`,
    `originates_from`, and `about`

## Acceptance Checks

- Internal note models exist outside `app/schemas/`.
- Public note schemas do not carry Arango `_key`, `_from`, or `_to` fields.
- Repository code can persist note state without reusing public API schema
  classes as storage records.
