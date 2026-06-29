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

## Mnemosyne MCP

The package ships a custom stdio MCP server for agent-facing curated memory
operations. It intentionally does **not** mirror the FastAPI routes as generic
MCP tools; tools expose provenance-first memory intents and call the HTTP API
internally.

Initial tools:

- `create_document` creates a provenance document using the observation API.
- `find_entities` searches the curated entity registry before new writes.
- `create_entity` creates or updates a curated person, location, store, or item.
- `get_entity` fetches one curated entity by id.

Run it locally against the default API URL:

```shell
uv run mnemosyne-mcp
```

Configure the target API with `MNEMOSYNE_API_URL` when needed. MCP requests send
access-context headers by default (`mnemosyne.query mnemosyne.write`) so local
deployments with the optional access pipeline enabled can still use the server.
Those defaults can be overridden with `MNEMOSYNE_MCP_*` environment variables.

Example Hermes configuration:

```yaml
mcp_servers:
  mnemosyne:
    command: "uv"
    args: ["run", "--project", "/path/to/mnemosyne", "mnemosyne-mcp"]
    env:
      MNEMOSYNE_API_URL: "http://127.0.0.1:8180"
```

### Agent setup prompt

Use this prompt when asking an MCP-capable agent to install Mnemosyne's MCP:

```text
Install and verify the Mnemosyne MCP as a custom curated-memory MCP, not a
FastAPI endpoint mirror.

Inputs:
- Mnemosyne repository path: <path-to-mnemosyne>
- Mnemosyne API URL: http://127.0.0.1:8180 unless I provide another URL

Steps:
1. Verify the repository exists and contains `pyproject.toml` with the
   `mnemosyne-mcp` console script.
2. From the repository, run `uv sync` so the `mcp` and `httpx` runtime
   dependencies are installed.
3. Configure the MCP client to launch the stdio server with:
   `uv run --project <path-to-mnemosyne> mnemosyne-mcp`
   and set `MNEMOSYNE_API_URL` to the API URL above.
4. Test MCP discovery and confirm the available tools are exactly the curated
   memory tools: `create_document`, `find_entities`, `create_entity`, and
   `get_entity`.
5. Restart or reload the MCP-capable agent if required by the client.

Usage rules:
- Use this MCP only for already-curated, durable information with provenance.
- Before creating an entity, call `find_entities` to avoid duplicates.
- Write provenance first with `create_document` when recording a new durable
  fact source.
- Do not use this MCP for casual conversation logs or uncurated scratch notes.
- Do not install `fastapi-mcp` for this; the Mnemosyne MCP intentionally exposes
  memory intents rather than raw API routes.
```

For Hermes specifically, the setup command is:

```shell
MNEMOSYNE_REPO=/path/to/mnemosyne
MNEMOSYNE_API_URL=http://127.0.0.1:8180
printf 'Y\n' | hermes mcp add mnemosyne \
  --command "$(command -v uv)" \
  --env MNEMOSYNE_API_URL="$MNEMOSYNE_API_URL" \
  --args run --project "$MNEMOSYNE_REPO" mnemosyne-mcp
hermes mcp test mnemosyne
hermes mcp list
```

## Observation API

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
