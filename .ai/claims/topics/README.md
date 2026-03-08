# Topic Claim Indexes

Each topic file contains only claims for that topic.

## Naming

- File name matches topic key: `<topic>.yaml`.
- Topic key uses lowercase kebab-case.
- Empty topic indexes are valid and should use `claims: []` until populated.

## Required fields per claim

- `id`
- `title`
- `status`
- `statement`
- `source`
- `doc`
- `updated_at`
- `validation`

## Current Topic Keys

- `agent-directives`
- `local-deploy-infra`
- `build-on-top`
- `api-and-mcp`
- `runtime-local`
- `deploy-target`
- `observability`
- `security-boundaries`
