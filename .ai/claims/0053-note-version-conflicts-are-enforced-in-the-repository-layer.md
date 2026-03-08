# Claim 0053: Note Version Conflicts Are Enforced in the Repository Layer

## Statement

Note version conflicts are enforced in the repository layer, with the Arango
repository performing the version check inside the persistence boundary rather
than relying only on service-level prechecks.

## Scope

- Repository protocol supports `expected_version` on revision creation.
- In-memory repository enforces the same conflict contract for fast tests.
- Arango repository checks current version inside a database transaction before
  writing a new revision.
- Service layer translates repository version conflicts into the public `409`
  error contract.

## Acceptance Checks

- Repository implementations raise a typed repository version conflict.
- Service layer no longer depends on pre-write version checks as the sole
  protection.
- Direct repository smoke testing against local Arango rejects stale writes.
