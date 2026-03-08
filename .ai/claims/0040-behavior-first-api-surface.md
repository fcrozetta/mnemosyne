# Claim 0040: Behavior-First API Surface

## Statement

The API surface is behavior-first, not collection CRUD-first.

## Rules

- Endpoints are task-oriented, such as `/notes` and `/follow-ups`.
- Clients do not create internal revision or edge records directly.
- Domain invariants are enforced behind behavior-oriented endpoints.

## Acceptance Checks

- Public endpoints are named after behaviors or task aggregates.
- Raw collection CRUD is not the primary public API surface.
