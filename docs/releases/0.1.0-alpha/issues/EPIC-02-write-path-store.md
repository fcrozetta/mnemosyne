# EPIC-02 · Core Write Path and Store Semantics

**Suggested milestone:** `0.1.0 (Alpha)`  
**Suggested labels:** `type:epic`, `area:storage`, `phase:1`, `prio:p0`

## Outcome

Implement the first trustworthy write path for Mnemosyne.

## Why this exists

“AI memory” dies the moment writes become unauditable, destructive, or semantically loose.

## Lanes

### Lane A · Persistence skeleton
- [ ] storage bootstrap exists
- [ ] core collections / structures exist
- [ ] repository/service layer exists

### Lane B · Ingest
- [ ] one-shot ingest endpoint exists
- [ ] note + structured memory can be accepted in one request
- [ ] people / places / items / events can be linked in one flow

### Lane C · Trust model
- [ ] provenance captured on write
- [ ] append-only or versioned updates implemented
- [ ] destructive empty updates rejected
- [ ] optimistic concurrency or equivalent guard exists

### Lane D · Resolution model
- [ ] unresolved entities supported
- [ ] manual resolution path designed
- [ ] confidence / ambiguity is not silently flattened

## Exit criteria

- a realistic note can be ingested end to end
- writes preserve provenance
- updates do not silently overwrite prior meaning
- unresolved entities are explicit, not hidden guesses

## Risks

> [!WARNING]
> If agents can write arbitrary raw edges directly, the graph will rot into hallucinated spaghetti.
