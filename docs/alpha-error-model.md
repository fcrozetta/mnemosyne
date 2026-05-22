# Mnemosyne Alpha Error Model

The alpha API uses one JSON error shape across observation endpoints.

```json
{
  "error": "invalid_observation_patch",
  "details": [
    {
      "message": "Patch request must include at least one change.",
      "code": "invalid_observation_patch"
    }
  ],
  "request_id": null
}
```

## Current Errors

- `invalid_observation_request`
- `invalid_observation_patch`
- `observation_not_found`

## Rules

- Error names describe API behavior, not storage internals.
- Do not expose ArcadeDB type names, RIDs, SQL text, or graph edge names in
  public errors.
- Patch revision versions are assigned internally.
- API versioning is deferred.
