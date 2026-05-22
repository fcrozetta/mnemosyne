# Mnemosyne Alpha API Contract

This alpha can break compatibility. The canonical API is observation-centered.

See also:

- [ArcadeDB schema design](./arcadedb-schema-design.md)
- [Alpha error model](./alpha-error-model.md)

## Contract Rules

- `Observation` is the public write/read object.
- `Note` is one observation type.
- Public identity is `observation_id`.
- Public `version` is optimistic concurrency for the current revision.
- Mentions are evidence navigation, not truth claims.
- Claims are storage/schema-ready but claim-writing endpoints are deferred.

## Health

`GET /healthz`

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
  "observed_at": "2026-04-06T17:00:00Z",
  "source": {
    "source_type": "agent",
    "label": "codex"
  }
}
```

Response `201`:

```json
{
  "observation_id": "obs_01...",
  "type": "note",
  "version": 1,
  "current_revision_id": "obs_01...:v1",
  "content": "My blue shirt is at John's place.",
  "content_format": "text/plain",
  "observed_at": "2026-04-06T17:00:00Z",
  "created_at": "2026-04-06T17:00:00Z",
  "updated_at": "2026-04-06T17:00:00Z",
  "mentions": [
    {
      "entity_id": "ent_01...",
      "type": "item",
      "label": "blue shirt",
      "resolution_status": "unresolved"
    }
  ],
  "source": {
    "source_id": "src_01...",
    "source_type": "agent",
    "label": "codex",
    "source_ref": null
  }
}
```

## Search Observations

`GET /observations?q=shirt&limit=5`

Response `200`:

```json
[
  {
    "observation_id": "obs_01...",
    "type": "note",
    "version": 1,
    "content_preview": "My blue shirt is at John's place.",
    "observed_at": "2026-04-06T17:00:00Z",
    "score": 1.0
  }
]
```

## Get Observation

`GET /observations/{observation_id}`

Returns the latest observation revision projection.

## Patch Observation

`PATCH /observations/{observation_id}`

```json
{
  "version": 1,
  "addendum": "It is the Oxford shirt.",
  "mentions": [
    { "type": "item", "label": "Oxford shirt" }
  ],
  "observed_at": "2026-04-06T18:05:00Z"
}
```

At least one of `addendum`, `mentions`, or `observed_at` is required.

## Context

`GET /observations/{observation_id}/context`

Returns the latest observation plus related observations found by mention
overlap.
