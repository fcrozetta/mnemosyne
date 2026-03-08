# .ai Directory

Public AI-agent metadata for Mnemosyne.

No private machine paths, secrets, credentials, or personal data should be
stored here.

`.ai` is not a place for user-local agent state or workstation-specific
metadata.

## Layout

- `claims.yaml`: root topic index for machine-readable claims.
- `claims/topics/`: topic-partitioned claim indexes.
- `claims/`: human-readable claim details and acceptance criteria.

## Claim Indexing Policy

- Claim IDs are stable: `mnemo-XXXX`.
- Claims are partitioned by topic in `claims/topics/*.yaml`.
- `claims.yaml` is the canonical router for topic indexes.
- Claim detail docs in `claims/` are optional and used only when needed.
- Claims are append-friendly: update status/history, avoid destructive
  rewrites.
