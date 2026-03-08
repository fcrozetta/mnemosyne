# Claim 0001: Agent Directives Baseline

## Statement

Mnemosyne execution follows repository directives in `AGENTS.md` as the default contract.

## Scope

- API boundary is authoritative for management-level operations.
- Collection ownership/access must be enforced via registry metadata.
- Destructive operations are blocked by default.

## Acceptance Checks

- Project decisions reference `AGENTS.md` constraints.
- No direct DB management bypasses API controls.
