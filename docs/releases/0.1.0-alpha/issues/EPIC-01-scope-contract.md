# EPIC-01 · Scope Freeze and Public Contract

**Suggested milestone:** `0.1.0 (Alpha)`  
**Suggested labels:** `type:epic`, `area:contract`, `phase:0`, `prio:p0`

## Outcome

Freeze the public product cut and external contracts for 0.1.0 alpha.

## Why this exists

If the public contract is fuzzy, the implementation will hard-code accidental assumptions and the first release will be unstable by design.

## Lanes

### Lane A · Product cut
- [ ] define exactly who 0.1.0 is for
- [ ] define what is in
- [ ] define what is out
- [ ] define release gates

### Lane B · Artifact model
- [ ] list core artifact types
- [ ] define minimum required fields
- [ ] define versioning semantics
- [ ] define unresolved entity state

### Lane C · API contract
- [ ] define ingest request shape
- [ ] define search request shape
- [ ] define context response shape
- [ ] define update/version write semantics
- [ ] define error model

### Lane D · Naming and compatibility
- [ ] separate public API terms from internal DB terms
- [ ] version schema/contracts explicitly
- [ ] avoid Arango-specific leakage in API payloads

## Exit criteria

- external contracts are written down
- a client can target the API without needing DB internals
- the team can say “no” to out-of-scope asks using this document

## Risks

> [!WARNING]
> Exposing collections or raw graph primitives as product concepts will calcify internal implementation too early.
