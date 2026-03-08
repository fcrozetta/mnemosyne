# Claim 0022: Note About vs Mentions Semantics

## Statement

Note revisions support two distinct semantic relations: `about` and `mentions`.

## Semantics

- `about`: primary subject or intended target of the note revision.
- `mentions`: referenced entities found in content, including later AI-derived
  extraction.

## Rules

- A note revision may have zero or many `about` edges.
- A note revision may have zero or many `mentions` edges.
- AI enrichment may add `mentions` edges later, but these must preserve
  provenance to the revision and originating event.

## Acceptance Checks

- Schema/docs distinguish `about` from `mentions`.
- Enrichment design keeps derived semantic edges auditable.
