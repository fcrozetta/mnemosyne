# Claim 0004: API and MCP Last in Sequence

## Statement

API and MCP are implemented only after directives, infra contracts, and data substrate claims are accepted.

## Scope

- API endpoints for collection requests and governance operations.
- MCP surface constrained to API-approved operations.
- Auditability and deny-by-default behavior for unsafe operations.

## Acceptance Checks

- API enforces registry access and constraints.
- MCP does not expose direct destructive or bypass paths.
