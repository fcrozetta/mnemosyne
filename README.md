# mnemosyne
Project that aims to be a place where humans and AI can share their brains.

## Working Docs

- [Alpha model](docs/alpha-model.md)
- [Alpha API contract](docs/alpha-api-contract.md)
- [Alpha error model](docs/alpha-error-model.md)

## Local Backend Skeleton

The alpha backend starts as a minimal FastAPI app with repository and service
boundaries plus a SurrealDB-backed storage readiness check. Runtime defaults to
`MNEMOSYNE_STORAGE_BACKEND=surreal`; use `in-memory` only when you explicitly
want a no-DB skeleton.

```shell
uv run pytest -q
uv run ruff check .
```

Local SurrealDB bootstrap uses Docker Compose and the SurrealDB CLI. The
checked-in import files define schemafull tables, graph relation tables, and a
small sample note graph:

```shell
make up
make dev
```

`make up` starts the API on port `8180`, starts SurrealDB on port `8100`, and
prepares the database if needed by defining namespace `mnemosyne`, database
`mnemosyne`, database-scoped user `mnemosyne`, schema, indexes, and views.

`make dev` uses `docker-compose.dev.yml` on top of the base compose file and
also imports `db/seed.surql`. Use it when you want the sample note graph.
The `notes` materialized view is defined from `db/views.surql` after imports so
`OPTION IMPORT` does not suppress view population. Override local credentials
with `SURREAL_ROOT_PASSWORD` for root or `SURREAL_PASSWORD` for the database
user.
Agents should authenticate as `mnemosyne` with a database-scoped signin against
namespace `mnemosyne` and database `mnemosyne`, not root.

Export the current local database as a SurrealQL script:

```shell
make db-export
```

If an older local database has `notes` as a normal table, use a fresh
`SURREAL_DATABASE` value or reset the local SurrealDB volume before seeding.
The local reset command is destructive:

```shell
make db-clean
make dev
```

The app entrypoint is `app.main:app`. `/healthz` is now fail-closed: it returns
`503` unless the selected backend is actually usable. In `surreal` mode that
means the server is reachable, the `mnemosyne` database user can sign in, and
the expected schema/view/index layout is present.

```shell
uv run fastapi dev app/main.py --port 8000
```
