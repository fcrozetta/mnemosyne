# EPIC-03 · Retrieval and Context API

**Suggested milestone:** `0.1.0 (Alpha)`  
**Suggested labels:** `type:epic`, `area:retrieval`, `phase:2`, `prio:p0`

## Outcome

Ship retrieval that feels like memory retrieval, not database admin.

## Why this exists

Without useful retrieval, Mnemosyne is just a storage layer wearing a mythological mask.

## Lanes

### Lane A · Search
- [ ] search endpoint exists
- [ ] notes / entities / events are queryable
- [ ] filters and pagination are sane enough for alpha

### Lane B · Related context
- [ ] fetch-by-id exists
- [ ] related nodes / neighborhood context exists
- [ ] context bundle endpoint exists for agent use

### Lane C · Retrieval quality
- [ ] response shape is compact
- [ ] provenance surfaces in reads
- [ ] unresolved state is visible in reads
- [ ] irrelevant graph noise is kept low

### Lane D · Example queries
- [ ] “what do I know about X?” works
- [ ] “what happened related to Y?” works
- [ ] “what notes mention Z?” works
- [ ] “what should I remember before talking to P?” works

## Exit criteria

- retrieval answers the core alpha questions
- read responses are useful to both humans and agents
- provenance and uncertainty survive retrieval

## Risks

> [!WARNING]
> If retrieval is an afterthought, users will conclude Mnemosyne is just another DB wrapper and move on.
