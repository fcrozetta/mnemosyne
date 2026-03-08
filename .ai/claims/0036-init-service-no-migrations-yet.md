# Claim 0036: Init Service, No Migrations Yet

## Statement

v0 bootstrap uses an explicit init service to create and seed ArangoDB.
There is no migration framework yet, and hidden startup mutation is forbidden.

## Scope

- No SQL-style migration layer is introduced now.
- Initialization is explicit and repeatable.
- API startup must not mutate the database implicitly.

## Acceptance Checks

- Bootstrap uses a dedicated init path or service.
- API runtime does not auto-create or auto-mutate schema on start.
