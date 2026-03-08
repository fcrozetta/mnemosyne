# Claim 0020: API Sanitization and Server Stamping

## Statement

API sanitizes input with strict allowlists and stamps protected provenance
fields from authenticated token context.

## Scope

- Unknown fields are removed or rejected per endpoint contract.
- `created_by`, timestamps, and protected provenance fields are server-managed.
- Principal identity is derived from token and cannot be overridden by payload.

## Acceptance Checks

- Endpoint schemas define allowed fields and type constraints.
- Protected fields from client payload are ignored/rejected.
- Persisted records show token-derived principal in provenance fields.
