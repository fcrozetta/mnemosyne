# Claim 0018: System Collections Are Server-Managed

## Statement

System collections are not writable by client-facing API operations.

## Scope

- Client endpoints can trigger workflows.
- API server writes internal system collections.

## Non-client-writable System Collections

- `collection_registry`
- `audit_log`
- `schema_migrations`
- `idempotency_ledger`
- `job_queue`
- `job_dead_letter`
- `auth_principals`
- `api_keys`
- `system_config`
- `policy_rules`

## Acceptance Checks

- Client API surface has no raw write endpoint for system collections.
- System writes occur only in trusted server paths.
