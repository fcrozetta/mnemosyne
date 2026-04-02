# Mnemosyne 0.1.0 (Alpha) Release Brief

> [!IMPORTANT]
> **Target release date:** **Friday, 2026-04-24**  
> **Recommended eventual tag:** `v0.1.0-alpha.1`  
> **Milestone display name:** `0.1.0 (Alpha)`

> [!WARNING]
> Calling an alpha simply `0.1.0` is semver-sloppy. Use the milestone name `0.1.0 (Alpha)` for planning, but prefer the actual git tag `v0.1.0-alpha.1` unless you intentionally want users to read this as a stable minor release.

## Goal

Ship the **first public developer preview** of Mnemosyne as a **self-hosted, single-user, API-first memory system** for agents and humans.

## Product cut

Mnemosyne 0.1.0 (Alpha) is **not** a general note app, not a hosted SaaS, and not a workflow engine.

It is:

- a canonical memory layer
- with versioned artifacts
- provenance-aware writes
- relationship-aware storage
- useful retrieval/context endpoints
- simple local install via Docker Compose

## Primary user

A technical user who wants persistent, inspectable memory for agents and humans without giving up control.

## Non-goals

- multi-user support
- hosted cloud service
- advanced UI
- plugin ecosystem
- Ananke/Moirai integration as a hard dependency
- perfect entity resolution
- generalized autonomous agent behavior

## Release gates

The release is allowed only if all of the following are true:

1. A new user can clone the repo and get the stack running in **<= 15 minutes**.
2. One-shot ingestion works for a realistic note containing **people, places, items, and follow-up intent**.
3. Writes preserve **version history** and **provenance**.
4. Retrieval can answer at least these queries:
   - what do I know about X?
   - what happened related to Y?
   - what notes mention Z?
   - what should I remember before talking to P?
5. The repo has usable docs, examples, and explicit non-goals.

## High-level scope

### In

- artifact model v0.1
- API contracts v0.1
- one-shot memory ingest
- versioned artifact updates
- entity + relationship + event + reminder support
- context retrieval endpoints
- Docker Compose install
- docs + examples + sample data
- alpha release notes

### Out

- auth beyond minimal local/developer setup
- teams/tenancy/permissions matrix
- full web UI
- background enrichment pipelines
- embeddings as mandatory core
- external source ingestion platform

## Timeline

| Phase | Window | Focus |
|---|---:|---|
| Phase 0 | 2026-04-02 → 2026-04-03 | Scope freeze + public contract |
| Phase 1 | 2026-04-04 → 2026-04-08 | Data model + write path skeleton |
| Phase 2 | 2026-04-09 → 2026-04-13 | Retrieval + context endpoints |
| Phase 3 | 2026-04-14 → 2026-04-18 | Install path + docs + examples |
| Phase 4 | 2026-04-19 → 2026-04-22 | Hardening + dogfooding |
| Phase 5 | 2026-04-23 → 2026-04-24 | Release prep + tag |

## Current repo state

- Repository exists and is public.
- `README.md` is currently a placeholder.
- No meaningful issue tracker structure exists yet.
- No existing issue set exists.

> [!NOTE]
> The available automation tooling for this chat can write files and open PRs, but **cannot create GitHub milestones/issues/labels/projects directly**. This release tracker is therefore stored in-repo as the source of truth and can later be copied into native GitHub issues if desired.

## Success definition

If 0.1.0 ships on 2026-04-24 with a clean quickstart, a credible ingest story, trustworthy write semantics, and useful retrieval, the release is successful.

If the release slips because of UI polish, plugin fantasies, or workflow-engine coupling, the project lost focus.
