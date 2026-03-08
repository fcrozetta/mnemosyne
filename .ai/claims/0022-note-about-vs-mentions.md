# Claim 0022: Notes Use About in v0 and Defer Mentions

## Statement

v0 note revisions use `about` for asserted context. Separate `mentions` edges
are deferred until there is a concrete enrichment workflow that justifies them.

## Semantics

- `about`: primary subject or intended target of the note revision.
- `mentions`: future enrichment concept for content references that are not
  asserted note subject.

## Rules

- A note revision may have zero or many `about` edges.
- v0 bootstrap and v0 API contracts do not require a `mentions` edge
  collection.
- If `mentions` are introduced later, they must preserve provenance to the
  revision and originating event.

## Acceptance Checks

- Current v0 schema/docs distinguish implemented `about` semantics from deferred
  `mentions`.
- v0 note write payloads and bootstrap do not depend on `mentions`.
