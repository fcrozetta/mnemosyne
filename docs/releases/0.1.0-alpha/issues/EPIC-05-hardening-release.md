# EPIC-05 · Hardening, Dogfooding, and Release

**Suggested milestone:** `0.1.0 (Alpha)`  
**Suggested labels:** `type:epic`, `type:qa`, `area:release`, `phase:4`, `phase:5`, `prio:p0`

## Outcome

Stabilize the alpha, document its limits, and ship without pretending it is more mature than it is.

## Why this exists

Most early releases fail not because the core idea is bad, but because the final 20% is left to wishful thinking.

## Lanes

### Lane A · Hardening
- [ ] critical bug list exists
- [ ] correctness pass on core flows completed
- [ ] unhappy paths tested
- [ ] backup/export basics tested

### Lane B · Dogfooding
- [ ] at least one real memory scenario tested
- [ ] at least one skeptical technical user can follow quickstart
- [ ] failure points are recorded

### Lane C · Release assets
- [ ] changelog written
- [ ] release notes written
- [ ] known limitations written
- [ ] roadmap note for post-alpha written

### Lane D · Final decision
- [ ] green / amber / red release decision made
- [ ] tag format decided
- [ ] publish/no-publish decision recorded

## Exit criteria

- no p0 blocker remains open
- known limitations are explicit
- release notes are honest
- the alpha can be installed, exercised, and evaluated by an external developer

## Risks

> [!WARNING]
> Shipping a vague alpha is survivable. Shipping a dishonest alpha is corrosive.
