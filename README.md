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

## Alpha API

The public alpha contract is observation-centered. First-class entities and
safe projections exist to support the shared graph, but observations remain how
new evidence enters the system.

Optional access-policy features are default-off and enabled only when their
environment flags are set:

- `MNEMOSYNE_ACCESS_POLICY_ENABLED` gates domain/purpose/sensitivity policy
  checks and safe projections as one unit.
- `MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED` enables reading request context
  from `X-Mnemosyne-*` headers.
- `MNEMOSYNE_ACCESS_AUDIT_ENABLED`

### Observation API

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

Patch an observation. The next revision version is assigned internally:

```shell
curl -sS -X PATCH http://127.0.0.1:8180/observations/obs_... \
  -H 'Content-Type: application/json' \
  -d '{"addendum": "It is the Oxford shirt."}'
```

Search current observation revisions:

```shell
curl -sS 'http://127.0.0.1:8180/observations?q=blue%20shirt&limit=5'
```

Search scoring is lexical-only in the current alpha. The server strips and
casefolds `q`, matches it against each observation's latest revision content,
and returns only matches with `score > 0`. A full-query substring match scores
`1.0`; otherwise the score is the fraction of whitespace-separated query terms
present in the content. Results sort by observation `updated_at`, then `id`,
both descending; `score` does not override recency ordering. Scores are relative
to one query result set, not calibrated across different queries. Stemming,
BM25/TF-IDF, embeddings, and hybrid reranking are not active yet; stronger
indexes are planned.

### Entity Registry

The `/entities` registry supports first-class `person`, `location`, `store`, and
`item` records. Entity mentions inside observations remain evidence navigation;
registry entities are the identity/profile records with `scope`, `sensitivity`,
`allowed_purposes`, and subtype-specific fields.

```shell
curl -sS http://127.0.0.1:8180/entities \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "item",
    "label": "Pilot Custom 823 Amber",
    "scope": "possessions/pens",
    "sensitivity": "personal",
    "item": {
      "item_kind": "pen",
      "category": "writing_instrument",
      "subcategory": "fountain_pen",
      "brand": "Pilot",
      "model": "Custom 823",
      "variant": "Amber"
    }
  }'
```

```shell
curl -sS 'http://127.0.0.1:8180/entities?type=item&q=pilot&limit=25'
```
