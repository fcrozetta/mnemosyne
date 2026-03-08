# Claim 0050: Notes Runtime Uses an Arango-Backed Repository by Default

## Statement

The default notes runtime path uses an Arango-backed repository with env-driven
settings, while the in-memory repository remains available only as a temporary
testing aid.

## Scope

- Runtime settings are loaded from environment variables.
- Dependency wiring builds an Arango database handle and injects an
  `ArangoNotesRepository`.
- The notes router uses the Arango-backed handler/service path by default.

## Rules

- Public note API contracts remain unchanged when swapping repository
  implementations.
- Arango persistence stores note anchors, revisions, provenance events, and
  graph edges behind the repository boundary.
- API startup connects to the configured database but does not mutate schema.

## Acceptance Checks

- Runtime settings exist for Arango host, port, db name, and credentials.
- Dependency wiring can build an `ArangoNotesRepository`.
- Real create/patch/put note flows succeed against the seeded local Arango
  instance.
