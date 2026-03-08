# Claim 0038: Seeded Graph Query Scripts Exist for Inspection

## Statement

The local bootstrap includes non-mutating query scripts to inspect seeded graph
slices directly from ArangoDB.

## Scope

- Query scripts live under `docker/arango/query/`.
- Make targets expose the seeded graph views.
- Scripts are read-only and intended for schema/data validation.

## Initial Views

- `graph-note`
- `graph-followup`
- `graph-catalog`

## Acceptance Checks

- Query scripts exist under `docker/arango/query/`.
- Make targets invoke them without mutating the database.
