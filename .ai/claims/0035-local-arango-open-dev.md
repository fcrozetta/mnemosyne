# Claim 0035: Local Arango Uses Root Password

## Statement

Local infrastructure uses the latest stable ArangoDB Enterprise image with root
password authentication for development.

## Scope

- Configuration comes from `.env`.
- Local bootstrap authenticates with root credentials.
- Backup/restore is deferred from the first bootstrap phase.

## Acceptance Checks

- Compose config uses `.env`-driven Arango settings.
- Local bootstrap authenticates to Arango with root password.
