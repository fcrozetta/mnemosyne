# Claim 0028: Purchase-Level Installments and Raw Product Fields First

## Statement

Installment obligations belong to `purchase`, not `purchase_item`. Product
attributes are stored as raw fields in v0, with normalization deferred.

## Scope

- Payment plans mirror how finance apps represent the transaction.
- Product details such as size, color, fabric, and notes are preserved in raw
  fields before taxonomy normalization.

## Acceptance Checks

- Installment model attaches to purchase.
- Product detail capture does not require normalized category/material nodes.
