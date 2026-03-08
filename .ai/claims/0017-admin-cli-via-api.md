# Claim 0017: Admin and CLI Go Through API

## Statement

Operational actions run through admin API endpoints. CLI is a privileged API
client and does not write directly to the database.

## Scope

- No direct DB write path in operational tooling.
- Policy validation remains centralized in API.

## Acceptance Checks

- Admin runbooks call API operations only.
- CLI specification excludes direct DB mutation.
