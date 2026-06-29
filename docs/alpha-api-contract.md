# Mnemosyne Alpha API Contract

This alpha can break compatibility. The canonical API is observation-centered.

See also:

- [ArcadeDB schema design](./arcadedb-schema-design.md)
- [Alpha error model](./alpha-error-model.md)

## Contract Rules

- `Observation` is the public write/read object.
- `Note` is one observation type.
- Public identity is `id`.
- Public `version` identifies the latest revision returned by reads; patch
  requests do not supply a version.
- Mentions are evidence navigation, not truth claims.
- Observations may carry `domain`, `sensitivity`, `subject`, and
  `allowed_purposes` metadata. These values are policy inputs, not separate
  authentication.
- First-class entity registry records exist for `person`, `location`, `store`,
  and `item`; all carry `scope`, `sensitivity`, and `allowed_purposes`.
- Claims are storage/schema-ready but claim-writing endpoints are deferred.
- Domain policy, access-context headers, safe projections, and audit logging are
  guarded by default-off feature flags.

## Health

- Base path: endpoints are mounted at the service root, for example
  `http://127.0.0.1:8180`.
- Request bodies must use `Content-Type: application/json`.
- Alpha observation endpoints do not require application-level client
  authentication.
  Deployment-level network or proxy auth is outside this API contract.
- Optional access features are controlled by environment flags, all defaulting
  to `false`:
  - `MNEMOSYNE_ACCESS_POLICY_ENABLED` gates domain/purpose/sensitivity policy
    checks and safe projections as one unit.
  - `MNEMOSYNE_ACCESS_CONTEXT_HEADERS_ENABLED`
  - `MNEMOSYNE_ACCESS_AUDIT_ENABLED`
- When the access pipeline is enabled, callers provide context using
  `X-Mnemosyne-Actor-User`, `X-Mnemosyne-Client-App`,
  `X-Mnemosyne-Service-Identity`, `X-Mnemosyne-Purpose`,
  `X-Mnemosyne-Scopes`, `X-Mnemosyne-Roles`, and
  `X-Mnemosyne-Projection` headers. Missing or insufficient context fails
  closed.
- `GET /healthz` returns service readiness:

```json
{
  "ok": true,
  "storage_initialized": true
}
```

If storage is not usable, the endpoint returns `503` with both values false.

## Create Observation

`POST /observations`

```json
{
  "type": "note",
  "content": "My blue shirt is at John's place.",
  "mentions": [
    { "type": "item", "label": "blue shirt" },
    { "type": "location", "label": "John's place" }
  ],
  "topics": ["personal:clothing:location"],
  "domain": "household",
  "sensitivity": "personal",
  "subject": "Sample User",
  "allowed_purposes": ["recall", "reminder"],
  "observed_at": "2026-04-06T17:00:00Z",
  "source": {
    "source_type": "agent",
    "label": "codex"
  }
}
```

`topics` is shorthand for topic mentions. Each string creates or reuses a
`topic` entity with the string as its label. Agents may use colon-separated
hierarchical topic names, for example `coding:fcrozetta:python:coding-style`.

`domain`, `sensitivity`, `subject`, and `allowed_purposes` are stored on the
immutable revision. They are used by safe projections when the access pipeline
is enabled. With feature flags off, the legacy raw response remains the default
alpha behavior.

Response `201`:

```json
{
  "id": "obs_01...",
  "type": "note",
  "version": 1,
  "current_revision": "obs_01...:v1",
  "content": "My blue shirt is at John's place.",
  "content_format": "text/plain",
  "domain": "household",
  "sensitivity": "personal",
  "subject": "Sample User",
  "allowed_purposes": ["recall", "reminder"],
  "observed_at": "2026-04-06T17:00:00Z",
  "created_at": "2026-04-06T17:00:00Z",
  "updated_at": "2026-04-06T17:00:00Z",
  "mentions": [
    {
      "id": "ent_01...",
      "type": "item",
      "label": "blue shirt",
      "resolution_status": "unresolved"
    }
  ],
  "source": {
    "id": "src_01...",
    "source_type": "agent",
    "label": "codex",
    "source_ref": null
  }
}
```

`domain`, `sensitivity`, `subject`, and `allowed_purposes` are included in raw
observation projections when safe-projection metadata is enabled. They are
omitted from the default unflagged response for compatibility with the earlier
alpha contract.

## Entity Registry

Entity mentions are evidence navigation. The `/entities` registry is the
first-class identity/profile path for durable world objects. Create/list/get
supports `person`, `location`, `store`, and `item` records. `topic` entities are
created through observation topic mentions rather than this registry endpoint.

### Create Entity

`POST /entities`

```json
{
  "type": "person",
  "label": "Mario Rossi",
  "scope": "contacts",
  "sensitivity": "confidential",
  "allowed_purposes": ["recall", "reminder"],
  "person": {
    "display_name": "Mario",
    "given_name": "Mario",
    "family_name": "Rossi",
    "contact_methods": [
      {
        "kind": "phone",
        "label": "mobile",
        "value": "+55 11 99999-0000",
        "sensitivity": "restricted"
      }
    ]
  }
}
```

For `location`, use a `location` object with optional address/geolocation
fields. For `store`, use `store_kind`, `website`, `categories`,
`country_scope`, `physical_store_status`, `source_urls`, and
`reference_notes`. For `item`, use `item_kind`, `category`, `subcategory`,
`brand`, `model`, `variant`, `color`, `size`, `serial_number`, and
`identifiers`.

Entity upsert identity is `(type, normalized_label, scope)`. Creating an entity
with the same identity updates the profile and keeps the original `created_at`.

### List Entities

`GET /entities?type=item&scope=possessions/pens&q=pilot&limit=25`

Filters are optional. `type` must be one of `person`, `location`, `store`, or
`item` when present. `limit` is clamped to `1..100`.

### Get Entity

`GET /entities/{id}` returns one entity record with shared metadata plus the
matching subtype profile.

## Search Observations

`GET /observations?q=shirt&limit=5`

Search evaluates only the latest/current revision content for each observation.
The current alpha scoring model is lexical-only:

- `q` is stripped and casefolded before matching.
- Content is casefolded before matching.
- If the full normalized query is a substring of the content, `score` is `1.0`.
- Otherwise, the query is split on whitespace and `score` is the fraction of
  query terms that appear in the content.
- Results with `score = 0` are omitted.
- Returned results sort by observation `updated_at`, then `id`, both
  descending. `score` is returned for lexical relevance insight, but it does
  not override recency ordering.

Scores are query-relative relevance signals in the range `(0, 1]` for returned
rows. They are useful inside one result set, but are not globally calibrated
across different queries. There is no stemming, BM25/TF-IDF,
embedding similarity, or hybrid reranking in the current implementation.
Stronger indexes are planned; when semantic/vector or hybrid ranking lands,
this contract should grow an explicit ranking mode and updated score semantics.

Response `200`:

```json
[
  {
    "id": "obs_01...",
    "type": "note",
    "version": 1,
    "content_preview": "My blue shirt is at John's place.",
    "observed_at": "2026-04-06T17:00:00Z",
    "updated_at": "2026-04-06T17:00:00Z",
    "score": 1.0
  }
]
```

## Recent Observations by Topic

`GET /topics/{topic}/observations?limit=5`

Returns recent current versions of note observations whose current revision
mentions a topic matching `{topic}`. The topic path segment may be a full topic
label or a partial substring, so `coding:fcrozetta:python` matches
`coding:fcrozetta:python:coding-style` and
`coding:fcrozetta:python:linting`. Results sort by observation `updated_at`,
then `id`, both descending.

Response `200`:

```json
[
  {
    "id": "obs_01...",
    "type": "note",
    "version": 2,
    "content_preview": "Prefer pathlib for local file handling.",
    "observed_at": "2026-04-08T10:00:00Z",
    "updated_at": "2026-04-08T10:30:00Z",
    "score": 1.0
  }
]
```

## Get Observation

`GET /observations/{id}`

Returns the latest observation revision projection.

## Patch Observation

`PATCH /observations/{id}`

```json
{
  "addendum": "It is the Oxford shirt.",
  "mentions": [
    { "type": "item", "label": "Oxford shirt" }
  ],
  "observed_at": "2026-04-06T18:05:00Z"
}
```

At least one of `addendum`, `mentions`, or `observed_at` is required.
The next revision version is assigned internally.

## Context

`GET /observations/{id}/context`

Returns the latest observation plus related observations found by mention
overlap.
