# Claim 0031: Product Snapshot Describes Item

## Statement

`product_snapshot --describes--> item` is the preferred direction for item
detail snapshots.

## Scope

- Snapshot semantics remain explicit.
- Item identity and descriptive purchase-time metadata stay distinct.

## Acceptance Checks

- Graph examples use `describes` from snapshot to item.
- Item detail modeling does not collapse snapshot into item identity.
