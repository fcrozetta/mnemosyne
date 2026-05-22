# Mnemosyne Alpha Error Model

The alpha API uses one JSON error shape across observation endpoints.

```json
{
  "error": "version_conflict",
  "details": [
    {
      "field": "version",
      "message": "Version does not match latest observation version.",
      "code": "version_conflict",
      "context": {
        "observation_id": "obs_01...",
        "current_version": 2,
        "requested_version": 1
      }
    }
  ],
  "request_id": null
}
```

## Current Errors

- `invalid_observation_request`
- `invalid_observation_patch`
- `observation_not_found`
- `version_conflict`

## Rules

- Error names describe API behavior, not storage internals.
- Do not expose ArcadeDB type names, RIDs, SQL text, or graph edge names in
  public errors.
- `version` means optimistic concurrency for one observation.
- API versioning is deferred.
