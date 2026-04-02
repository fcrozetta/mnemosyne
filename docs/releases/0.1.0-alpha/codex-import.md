# Codex CLI Import Guide for GitHub Issues and Project

> [!IMPORTANT]
> This guide exists so **Codex CLI** can translate the release tracker into **native GitHub objects**:
>
> - milestone
> - labels
> - parent issues
> - sub-issues
> - project
> - project custom fields
> - project views

> [!WARNING]
> Use **Project custom fields**, not **GitHub Issue Fields**.
>
> Reason:
> - this repository is public
> - project custom fields are the portable option
> - issue fields are not the right dependency for this release tracker

## Source of truth

Codex must treat the following as authoritative, in this order:

1. `docs/releases/0.1.0-alpha/github-import.manifest.yaml`
2. `docs/releases/0.1.0-alpha/README.md`
3. `docs/releases/0.1.0-alpha/board.md`
4. `docs/releases/0.1.0-alpha/issues/*.md`

If there is a conflict, the **manifest wins**.

## Required GitHub model

Codex should create:

- one milestone: `0.1.0 (Alpha)`
- one project: `Mnemosyne 0.1.0 Alpha`
- project custom fields:
  - `Status`
  - `Phase`
  - `Area`
  - `Priority`
- parent issues for each epic
- child issues linked as **sub-issues** to the correct parent issue

## Project layout

### Preferred views

1. **Board by Status**
   - layout: board
   - group by: `Status`

2. **Board by Parent Issue**
   - layout: board
   - group by: `Parent issue`

3. **Table by Phase**
   - layout: table
   - group by: `Phase`

If view creation is not supported through the available CLI/API route, Codex must:

- still create the project and fields
- still add all issues to the project
- print a short manual follow-up list instead of failing the import

## Idempotency rules

Codex must be conservative.

### Milestone
- create only if missing
- reuse if title already exists

### Labels
- create only if missing
- do not duplicate by spelling variant

### Parent issues
- if an issue with the exact title already exists, reuse it
- if reused, ensure labels/milestone/project membership are aligned

### Child issues
- if an issue with the exact title already exists, reuse it
- if reused, ensure it is linked to the correct parent
- do not create duplicate children under multiple parents

### Project items
- if the issue is already in the project, update fields instead of re-adding a duplicate item

## Failure policy

Codex must not stop at the first non-critical failure.

### Hard failures
- GitHub auth unavailable
- repository not writable
- manifest unreadable

### Soft failures
- project view creation unsupported
- some label colors rejected
- sub-issue linking requires GraphQL fallback

For soft failures, Codex should continue and print a concise remediation summary.

## Allowed implementation routes

Codex may use either or both:

- `gh` CLI
- GitHub REST / GraphQL via `gh api`

Codex should choose the smallest working route.

## Import sequence

1. verify GitHub auth and repo access
2. read the manifest
3. create/reuse milestone
4. create/reuse labels
5. create/reuse project
6. create/reuse project custom fields
7. create/reuse parent issues
8. create/reuse child issues
9. link child issues to parent issues
10. add all issues to the project
11. set project field values
12. create preferred views if supported
13. print a summary of created/reused/manual items

## Constraints

> [!CAUTION]
> Codex must **not** improvise extra epics, extra phases, or extra fields.

> [!CAUTION]
> Codex must **not** replace parent/sub-issue hierarchy with labels-only pseudo-epics.

> [!CAUTION]
> Codex must **not** use GitHub Issue Fields for this import.

## Suggested Codex CLI prompt

```text
Read docs/releases/0.1.0-alpha/github-import.manifest.yaml and import it into GitHub for repo fcrozetta/mnemosyne.

Requirements:
- create or reuse milestone `0.1.0 (Alpha)`
- create or reuse labels from the manifest
- create or reuse project `Mnemosyne 0.1.0 Alpha`
- create project custom fields Status, Phase, Area, Priority
- create or reuse parent issues from the manifest
- create or reuse child issues from the manifest
- link child issues as sub-issues to the correct parent issues
- add all created/reused issues to the project
- set project field values from the manifest
- prefer parent/sub-issues over label-only epic simulation
- use project custom fields, not GitHub Issue Fields
- be idempotent: do not duplicate existing issues by title
- if view creation is unsupported, continue and print manual follow-up steps
- at the end, print:
  - created objects
  - reused objects
  - failed objects
  - manual follow-up items
```

## Expected outcome

After a successful import:

- the release train exists as native GitHub items
- epics are represented as parent issues
- execution tasks are represented as sub-issues
- the project can be grouped by `Parent issue`, `Status`, and `Phase`
- the tracker remains aligned with the release docs
