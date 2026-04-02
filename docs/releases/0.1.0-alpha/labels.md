# Suggested Labels for 0.1.0 (Alpha)

> [!NOTE]
> These are **suggested GitHub labels**. The available automation tooling in this chat cannot create labels directly.

## Type

- `type:epic`
- `type:feature`
- `type:bug`
- `type:docs`
- `type:release`
- `type:infra`
- `type:qa`

## Area

- `area:contract`
- `area:storage`
- `area:retrieval`
- `area:events`
- `area:entity-resolution`
- `area:docs`
- `area:devex`
- `area:release`

## Phase

- `phase:0`
- `phase:1`
- `phase:2`
- `phase:3`
- `phase:4`
- `phase:5`

## Priority

- `prio:p0`
- `prio:p1`
- `prio:p2`

## Status

- `status:blocked`
- `status:needs-decision`
- `status:ready`
- `status:in-progress`

## Milestone

Use the milestone title:

- `0.1.0 (Alpha)`

## Recommended mapping

| File | Suggested labels |
|---|---|
| `EPIC-00-release-train.md` | `type:epic`, `type:release`, `phase:0`, `prio:p0` |
| `EPIC-01-scope-contract.md` | `type:epic`, `area:contract`, `phase:0`, `prio:p0` |
| `EPIC-02-write-path-store.md` | `type:epic`, `area:storage`, `phase:1`, `prio:p0` |
| `EPIC-03-retrieval-context.md` | `type:epic`, `area:retrieval`, `phase:2`, `prio:p0` |
| `EPIC-04-install-docs-dx.md` | `type:epic`, `area:devex`, `area:docs`, `phase:3`, `prio:p0` |
| `EPIC-05-hardening-release.md` | `type:epic`, `area:release`, `type:qa`, `phase:4`, `phase:5`, `prio:p0` |
