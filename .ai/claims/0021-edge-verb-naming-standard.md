# Claim 0021: Edge Verb Naming Standard

## Statement

Graph edge relation names must be verb phrases in `snake_case`.

## Naming Rule

- Edge semantics must read as: `source --verb_phrase--> target`.
- Do not use noun-only edge names.
- Keep direction stable once defined.

## v0 Examples

- `person --has_identity--> identity`
- `person --participates_in--> meeting`
- `note_revision --belongs_to--> note`
- `note --latest_revision--> note_revision`
- `note_revision --supersedes--> note_revision`
- `note_revision --about--> meeting`
- `note_revision --mentions--> person`
- `note_revision --originates_from--> event`
- `product_snapshot --describes--> item`
- `person --owns--> item`

## Acceptance Checks

- New edges follow verb-phrase naming.
- Existing edges are migrated or aliased before deprecating old names.
