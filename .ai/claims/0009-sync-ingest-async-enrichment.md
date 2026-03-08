# Claim 0009: Sync Ingest, Async Enrichment

## Statement

Ingest accepts and persists synchronously; enrichment runs asynchronously.

## Scope

- Keep ingest latency predictable.
- Decouple heavy processing from write path.

## Acceptance Checks

- API contract separates ingest acknowledgment from enrichment completion.
