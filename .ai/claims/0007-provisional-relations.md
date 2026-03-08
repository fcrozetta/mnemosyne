# Claim 0007: Verified-Only Relation State in v0

## Statement

v0 uses a single relation verification state: `verified`.

## Scope

- Keep v0 relation state simple for faster delivery.
- Defer `unverified` and `rejected` states to a later phase.

## Acceptance Checks

- Relation model for v0 includes only `verified`.
