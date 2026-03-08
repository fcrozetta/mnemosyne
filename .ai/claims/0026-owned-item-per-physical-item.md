# Claim 0026: One Item per Physical Item

## Statement

Inventory tracks one `item` per physical item, even when the purchase quantity
is greater than one.

## Scope

- A single purchase line may result in multiple items.
- Item lifecycle is tracked per physical item.

## Acceptance Checks

- Quantity fan-out from purchase_item to item is supported.
- Individual items can diverge in lifecycle state.
