# EPIC-04 · Install Path, Docs, and Developer Experience

**Suggested milestone:** `0.1.0 (Alpha)`  
**Suggested labels:** `type:epic`, `area:devex`, `area:docs`, `phase:3`, `prio:p0`

## Outcome

Make Mnemosyne installable and understandable by a new technical user.

## Why this exists

A product that technically works but cannot be installed in one sitting is dead-on-arrival for a public alpha.

## Lanes

### Lane A · Install
- [ ] Docker Compose stack exists
- [ ] `.env.example` exists
- [ ] health check works
- [ ] first boot path is documented

### Lane B · Quickstart
- [ ] clone → boot → ingest → retrieve flow is documented
- [ ] sample requests exist
- [ ] expected responses are shown

### Lane C · Documentation
- [ ] README explains what Mnemosyne is
- [ ] docs explain the trust model
- [ ] docs explain core concepts
- [ ] docs explain non-goals and known limits

### Lane D · Sample data / examples
- [ ] seed or example dataset exists
- [ ] one realistic end-to-end example exists
- [ ] API docs are not embarrassing

## Exit criteria

- a competent engineer can get to first successful ingest in <= 15 minutes
- docs explain enough to prevent immediate misunderstanding
- the project homepage/repo no longer looks unfinished

## Risks

> [!WARNING]
> Overbuilding docs infrastructure is a waste. The alpha needs clarity, not a cathedral.
