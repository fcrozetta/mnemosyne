# Claim 0016: Media Storage Deferred, AI Pipeline Preserved

## Statement

Media storage backend decision (NAS vs MinIO) is deferred, but architecture must
preserve compatibility with later AI-based media analysis.

## Scope

- Store contract hooks for artifact pointers/metadata now.
- Decide backend in later phase without breaking ingest contracts.

## Acceptance Checks

- Ingest schema reserves stable fields for future artifacts.
- Roadmap includes media backend decision + AI processing stage.
