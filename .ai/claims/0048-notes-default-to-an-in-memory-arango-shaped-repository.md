# Claim 0048: Notes Default to an In-Memory Arango-Shaped Repository

## Statement

Until the real Arango repository is implemented, notes use an in-memory
repository that stores Arango-shaped note documents, revision documents, event
documents, and edges behind the repository boundary.

## Rules

- Service logic should depend on the repository protocol, not on in-memory view
  storage.
- The temporary repository should mirror the intended persistence model closely
  enough to validate note versioning and graph wiring behavior.
- Replacing the in-memory repository with an Arango-backed implementation should
  not require changing the public note API contract.

## Acceptance Checks

- A concrete in-memory notes repository exists behind the repository protocol.
- Service code no longer stores `NoteView` as its internal persistence layer.
- The in-memory repository stores note write artifacts using internal models
  rather than API response schemas.
