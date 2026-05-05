# mnemosyne
Project that aims to be a place where humans and AI can share their brains.

## Working Docs

- [Alpha model](docs/alpha-model.md)
- [Alpha API contract](docs/alpha-api-contract.md)
- [Alpha error model](docs/alpha-error-model.md)

## Local Backend Skeleton

The alpha backend starts as a minimal FastAPI app with an in-memory storage
bootstrap path. It defines the note repository and service boundaries needed
before the write endpoints land.

```shell
uv run pytest -q
uv run ruff check .
```

Local SurrealDB bootstrap uses Docker Compose and the SurrealDB CLI. The
checked-in import files define schemafull tables, graph relation tables, and a
small sample note graph:

```shell
make db-up
make seed
```

`make seed` connects as root for bootstrap/import operations: it defines
namespace `mnemosyne`, database `mnemosyne`, database-scoped user `mnemosyne`,
then imports `db/schema.surql` and `db/seed.surql`. The `notes` materialized
view is defined from `db/views.surql` after import so `OPTION IMPORT` does not
suppress view population. Override local credentials with `SURREAL_ROOT_PASSWORD`
for root or `SURREAL_PASSWORD` for the database user.
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
make seed
```

The app entrypoint is `app.main:app`. The current health endpoint initializes
the alpha storage layout and reports whether the local repository is ready:

```shell
uv run fastapi dev app/main.py
```
