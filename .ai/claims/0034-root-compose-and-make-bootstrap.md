# Claim 0034: Root Compose and Make Bootstrap

## Statement

Infrastructure bootstrap starts from a root-level `docker-compose.yml` and a
root `Makefile`.

## Scope

- `docker-compose.yml` lives at repo root.
- `docker/*` contains bootstrap scripts for Arango setup and seeding.
- `make db` prepares ArangoDB and seeds sample data.
- `make clean` stops compose services and removes containers and volumes.

## Acceptance Checks

- Compose file exists at repo root.
- Docker bootstrap scripts live under `docker/`.
- Make targets `db` and `clean` exist and match the contract.
