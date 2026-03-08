# agents.md — Mnemosyne (Mnemo) — Project Directives (v0.3)

## Scope

- Mnemosyne is **personal-use / non-commercial**
- Purpose: **memory + provenance substrate** with explicit safety boundaries and low blast radius.

## Storage model

- Single **ArangoDB** database (for now).
- External raw files may exist (e.g., protected folder/NAS), but anything Soren can see must be explicitly stored or explicitly exposed via API.

## Collection ownership (CRITICAL)

- `fer_*` and `soren_*` are **conceptual ownership labels only** used in discussion.
- **Real collection names will NOT use these prefixes.**
- Enforce ownership via an explicit **collection-ownership registry** (metadata/ACL), not naming.

### Access policy

- **Fer-owned collections:** Soren = **RO**
- **Soren-owned collections:** Soren = **RW**
- **System/admin collections:** Soren = **NONE** unless explicitly granted

## API boundary (CRITICAL)

All “management-level” operations are performed via the API. The API validates and executes or denies.

### Must-go-through-API

- Create new collections (Soren requests; API validates, quotas, naming rules, ownership registry update)
- Create/modify indexes
- Schema-affecting operations
- Any destructive operations (blocked by default)

### Defense-in-depth

- DB RBAC is **defense-in-depth**.
- The API is the **source of truth** for allowed operations.

## Soren workspace bootstrap

Start with exactly two Soren-owned collections:

1) `soren_documents` — Soren artifacts/notes/derived models (name conceptual; real name may differ)
2) `soren_relationships` — edges/link structures (name conceptual; real name may differ)

Additional Soren collections require explicit API-approved creation.

## Preventing destructive edits: versioned artifacts (append-only)

### Core rule

Anything that is “mutable content” must be represented as **append-only versions** attached to a stable entity.

#### Example: meeting notes on an event

- Stable node: `event/{meeting_id}`
- Notes stored as versioned artifacts:
  - `event_notes_versions` (append-only)
  - optional `event_notes_current` pointer to latest version
- People relate to the **event**, not to a notes version.
- The event links to the current notes version.

### Write semantics

- **No in-place overwrite** of note content.
- API writes a **new version document** per change and updates the “current pointer”.

### Safety validations (API enforced)

- Reject empty/meaningless updates (e.g., whitespace-only)
- Use optimistic concurrency:
  - require `expected_current_version`
  - mismatch → **409 Conflict**
- Support patch ops to reduce wipe risk:
  - `append`, `addendum`, `add_section`, etc.
- “Delete” is a **tombstone version**, never a physical delete.

## Data handling invariants

- Never fabricate or infer missing medical content.
- Treat redacted content as the canonical visibility limit.
- Prefer pointers/IDs + derived metadata in Soren workspace over copying sensitive raw content.

## Operational constraints

- Workspace must be **wipeable** without affecting Fer-owned collections.
- Collection creation must be rate/quantity limited to prevent “creation spirals”.

## Decision persistence

- Soren must persist settled decisions into `.ai/claims` as soon as they are
  stable enough to matter.
- If a discussion changes an existing contract, Soren must update the existing
  claim doc and the relevant topic index, not leave them stale.
- If a new stable rule or contract is introduced, Soren must add it to the
  relevant claims and keep the topic files organized.
- “Remember this” requests are not session-memory tasks; they require repo
  updates.
- `.ai` is for public project memory only. User-local agent state and
  workstation-specific metadata must not be stored under `.ai`.

---

## Collection ownership registry (REQUIRED)

Ownership must not depend on collection names. The API must maintain a registry that defines who owns what and what Soren can do.

### Registry requirements

- Registry is authoritative for:
  - Ownership classification (Fer-owned vs Soren-owned vs System/admin)
  - Allowed operations per principal (at minimum: Soren)
  - Quotas and limits (collection count, indexes, size caps if tracked)
- Registry updates happen **only** via the API (admin-only endpoint).
- Registry mutations must be **audited** (append-only log).

### Minimal schema (conceptual)

Collection: `collection_registry` (name conceptual)

Each entry:

- `collection_name`: string (actual Arango collection name)
- `kind`: enum (`document` | `edge`)
- `owner`: enum (`fer` | `soren` | `system`)
- `soren_access`: enum (`none` | `ro` | `rw`)
- `purpose`: short string (human-readable intent)
- `created_at`: timestamp
- `created_by`: enum (`fer` | `api` | `soren_request`)
- `status`: enum (`active` | `deprecated` | `blocked`)
- `constraints` (optional):
  - `max_docs` (int)
  - `max_indexes` (int)
  - `allowed_indexes` (list of patterns/types)
  - `allowed_fields` (allowlist for writes; if you want stricter control)

### Invariants (must enforce)

- If `owner=fer` then `soren_access` MUST be `ro` or `none` (never `rw`).
- If `owner=soren` then `soren_access` MAY be `rw` (default) but can be downgraded.
- If `owner=system` then `soren_access` MUST be `none` unless explicitly granted.
- API must reject any operation where:
  - requested target collection is missing from registry, OR
  - requested operation exceeds `soren_access`, OR
  - requested operation violates `status`/`constraints`.

### Soren collection creation request flow

- Endpoint: `POST /soren/collections/request`
- Input: `{ proposed_name, kind, purpose }`
- Validation:
  - enforce quotas (max collections, max edges, etc.)
  - enforce naming rules (safe charset; length)
  - deny collisions with system/admin collections
  - write registry entry if approved: `owner=soren`, `soren_access=rw`, `status=active`
- Create Arango collection only after registry entry is committed.

### Audit log (conceptual)

Collection: `audit_log` (append-only)

- Record every approved/denied management action:
  - action type, principal, target, request payload hash, decision, reason, timestamp
- Prefer append-only + tombstones over physical deletes.
