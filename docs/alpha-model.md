# Mnemosyne Alpha Model

This document captures the intended `0.1.0-alpha` data model at a level that is concrete enough to build against without pretending the richer post-alpha taxonomy already exists.

See also: [Alpha API contract](./alpha-api-contract.md)

## Public Alpha Model

For alpha, Mnemosyne is a note-first memory system for agents.

- `Note` is the only required first-class persisted record.
- `AboutRef` carries explicit references or unresolved labels attached to a note.
- Public create requests may provide `source_channel`; the API stores it as
  provenance metadata but does not expose provenance fields in alpha responses.
- Updates create new versions of the same logical note instead of inventing unrelated notes.

```mermaid
classDiagram
    class Note {
      +id: string
      +content: string
      +version: number
      +created_at: datetime
      +observed_at: datetime
    }

    class AboutRef {
      +kind: person|location|item|topic|other
      +ref?: object
      +label?: string
    }

    class Provenance {
      +source_type?: string
    }

    Note "1" --> "0..*" AboutRef : about
    Note "1" --> "0..1" Provenance : provenance
```

Public alpha responses expose `created_at` and `observed_at`, not `updated_at`.
`updated_at`, `Provenance.writer`, `Provenance.session_id`, and
`Provenance.source_ref` exist only as internal or deferred storage fields for
alpha. Clients cannot set or read them through the public API yet.

## Storage Graph Sketch

This is the internal graph shape we are aiming at for alpha. It is an implementation sketch, not a promise that graph internals leak into the public API.

```mermaid
flowchart TD
    N[Note]
    RV1[Revision v1]
    RV2[Revision v2]
    AR1[AboutRef person ref]
    AR2[AboutRef location label]
    PR[Provenance]

    N -->|HAS_VERSION| RV1
    N -->|HAS_VERSION| RV2
    N -->|CURRENT_VERSION| RV2

    RV2 -->|PREVIOUS_VERSION| RV1
    RV2 -->|HAS_PROVENANCE| PR

    N -->|ABOUT| AR1
    N -->|ABOUT| AR2
```

## Minimum Alpha Semantics

- A new memory creates a new `Note` with version `1`.
- An update to an existing memory keeps the same `Note.id` and creates a new revision with version `n+1`.
- Previous revisions are retained.
- Normal reads return the latest note snapshot.
- Unresolved references stay unresolved as labels until a later explicit resolution step exists.

## `about.kind` Vocabulary

Alpha keeps the public `kind` vocabulary intentionally small:

- `person`
- `location`
- `item`
- `topic`
- `other`

`topic` is not a free-form tag system. It means the note is explicitly about a
subject area or discussion topic the writer wants to preserve as note context.
If it starts behaving like arbitrary label spam, the model has failed.

## Explicitly Out Of Scope For Alpha

- first-class `entity`, `relationship`, `event`, or `reminder` records
- automatic extraction or inference
- background enrichment pipelines
- pretending storage edges are the public product model
