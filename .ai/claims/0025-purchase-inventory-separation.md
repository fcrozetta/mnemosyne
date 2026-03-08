# Claim 0025: Purchase and Inventory Separation

## Statement

The graph separates transaction, item identity, ownership, and payment concerns
for purchases.

## Core Concepts

- `purchase`: the commercial transaction
- `purchase_item`: line items within a purchase
- `item`: the physical thing of interest
- `payment_obligation`: what is owed
- `payment`: what was actually paid
- `payment_method`: platform/card/account used
- `seller`: company or person you bought from
- `product_snapshot`: item details at purchase time

## Acceptance Checks

- Transaction and item identity are modeled separately.
- Product details remain queryable independently from payments.
