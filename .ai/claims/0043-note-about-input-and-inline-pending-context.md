# Claim 0043: Note About Input Uses Resolved and Unresolved Targets

## Statement

The `about` input for note writes is split into resolved and unresolved target
shapes. Resolved targets become graph edges; unresolved targets remain inline on
the created `note_revision`.

## Rules

- `about` input uses two distinct shapes:
  - resolved target: `kind` plus entity reference
  - unresolved target: `kind` plus user-facing `label`
- Unresolved `about` targets are valid write input and must not block note
  creation.
- Unresolved targets are stored inline on `note_revision` as pending context,
  not in a separate collection in v0.
- Resolved targets become `about` edges attached to the created revision.
- Unresolved targets are deduped within the resulting revision context by:
  - same `kind`
  - same normalized label

## Normalization

- Trim leading and trailing whitespace.
- Collapse repeated internal whitespace.
- Lowercase for comparison.

## Acceptance Checks

- Write schemas distinguish resolved and unresolved `about` inputs.
- API can create a note revision with unresolved context only.
- Persisted revision docs can carry unresolved pending context inline.
- Repeated unresolved labels in the same revision context dedupe
  deterministically.
