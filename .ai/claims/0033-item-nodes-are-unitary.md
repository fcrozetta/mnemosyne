# Claim 0033: Item Nodes Are Unitary Physical Units

## Statement

Each `item` node represents one concrete physical unit. If an item is lost and
replaced by the same model, the replacement is a new item node even when the
description is identical.

## Scope

- Physical identity is distinct from descriptive similarity.
- Replacements do not reuse old item identity.
- Multiple identical units are represented by multiple item nodes.

## Acceptance Checks

- Schema/examples allow duplicated product descriptions across different items.
- Lifecycle changes do not collapse replaced items into previous item nodes.
