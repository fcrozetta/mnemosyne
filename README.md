# mnemosyne

Truth-center backend for a user's life facts.

## Working Docs

- [ArcadeDB schema design](docs/arcadedb-schema-design.md)
- [Alpha model](docs/alpha-model.md)
- [Alpha API contract](docs/alpha-api-contract.md)
- [Alpha error model](docs/alpha-error-model.md)

## Local Backend

The alpha backend exposes observations. A note is one observation type, not the
center of the model.

```shell
uv run pytest -q
uv run ruff check .
```

ArcadeDB is the default storage backend. The local Compose stack starts
ArcadeDB Studio/API on port `2480` and the FastAPI app on port `8180`.

```shell
make up
```

`make up` builds the API image, starts ArcadeDB, creates the `mnemosyne`
database when needed, and applies `db/schema.arcadesql`.

Use `make dev` for the same stack with local dev overrides.

The app entrypoint is `app.main:app`. `/healthz` is fail-closed: it returns
`503` unless the selected backend is usable.

```shell
uv run fastapi dev app/main.py --port 8000
```

## Observation API

Create a note observation:

```shell
curl -sS http://127.0.0.1:8180/observations \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "note",
    "content": "My blue shirt is at John'\''s place.",
    "mentions": [
      {"type": "item", "label": "blue shirt"},
      {"type": "location", "label": "John'\''s place"}
    ],
    "source": {"source_type": "agent", "label": "codex"}
  }'
```

Patch an observation with the latest observed `version`:

```shell
curl -sS -X PATCH http://127.0.0.1:8180/observations/obs_... \
  -H 'Content-Type: application/json' \
  -d '{"version": 1, "addendum": "It is the Oxford shirt."}'
```
