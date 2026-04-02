# 0.1.0 (Alpha) Phase Board

> [!TIP]
> This board is optimized for **one developer**. Keep WIP low. Do not start the next lane until the current lane has a clean exit.

## Swim lanes

- **Lane A · Product / Contract**
- **Lane B · Core Backend**
- **Lane C · Retrieval / Context**
- **Lane D · DevEx / Packaging**
- **Lane E · Docs / Release**

## Phase 0 · Scope Freeze and Public Contract

**Target:** 2026-04-02 → 2026-04-03

| Lane | Status | Exit criteria |
|---|---|---|
| A | TODO | release brief committed |
| B | TODO | artifact model v0.1 drafted |
| C | TODO | retrieval response shape drafted |
| D | TODO | install path assumptions frozen |
| E | TODO | non-goals and release gates documented |

## Phase 1 · Data Model and Write Path

**Target:** 2026-04-04 → 2026-04-08

| Lane | Status | Exit criteria |
|---|---|---|
| A | TODO | API schemas for core writes are frozen |
| B | TODO | artifact/entity/event/reminder persistence path works |
| C | TODO | provenance is stored on writes |
| D | TODO | optimistic concurrency/versioning rules exist |
| E | TODO | write examples are documented |

## Phase 2 · Retrieval and Context

**Target:** 2026-04-09 → 2026-04-13

| Lane | Status | Exit criteria |
|---|---|---|
| A | TODO | search contract frozen |
| B | TODO | search + related-context endpoints respond correctly |
| C | TODO | context bundle is compact and agent-usable |
| D | TODO | retrieval examples run against sample data |
| E | TODO | limitations are documented honestly |

## Phase 3 · Install Path, Docs, and Examples

**Target:** 2026-04-14 → 2026-04-18

| Lane | Status | Exit criteria |
|---|---|---|
| A | TODO | quickstart is deterministic |
| B | TODO | compose stack boots cleanly |
| C | TODO | sample seed/example flow exists |
| D | TODO | docs explain trust model + architecture |
| E | TODO | README is no longer embarrassing |

## Phase 4 · Hardening and Dogfooding

**Target:** 2026-04-19 → 2026-04-22

| Lane | Status | Exit criteria |
|---|---|---|
| A | TODO | critical bugs triaged |
| B | TODO | one realistic end-to-end memory flow passes |
| C | TODO | edge cases for unresolved entities handled sanely |
| D | TODO | backup/export basics work |
| E | TODO | known limitations list is written |

## Phase 5 · Release Prep

**Target:** 2026-04-23 → 2026-04-24

| Lane | Status | Exit criteria |
|---|---|---|
| A | TODO | release checklist fully green |
| B | TODO | changelog drafted |
| C | TODO | sample requests tested one last time |
| D | TODO | image/docs/repo metadata cleaned up |
| E | TODO | tag and announcement text ready |

## Execution rules

> [!WARNING]
> Do **not** add major UI work, plugin work, or workflow-engine coupling during this release train.

1. No more than **2 active tasks** at the same time.
2. Every phase must end with a written **exit decision**: green / amber / red.
3. If a task spans more than 2 days, split it.
4. Any architectural debt introduced for speed must be:
   - explicit
   - local
   - reversible
   - documented with an exit condition

## Green / amber / red gates

- **Green**: ready to continue, no scope correction needed
- **Amber**: continue, but cut optional work immediately
- **Red**: release date at risk, freeze all non-critical work
