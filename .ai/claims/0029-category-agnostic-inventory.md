# Claim 0029: Category-Agnostic Inventory with Raw Product Attributes

## Statement

The inventory model must work across categories such as clothes, fountain pens,
inks, and others. Category-specific details live as raw structured attributes
on `product_snapshot` in v0.

## Scope

- Core ownership and purchase model is shared across categories.
- `product_snapshot` includes category plus flexible raw attributes.
- Normalized taxonomies are deferred until reuse pressure justifies them.

## Acceptance Checks

- Inventory schema supports multiple domains without domain-specific core forks.
- Product detail capture supports raw structured attributes per category.
