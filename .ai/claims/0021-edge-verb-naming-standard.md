# Claim 0021: Edge Verb Naming Standard

## Statement

Graph edge relation names must be verb phrases in `snake_case`.

## Naming Rule

- Edge semantics must read as: `source --verb_phrase--> target`.
- Do not use noun-only edge names.
- Keep direction stable once defined.

## v0 Examples

- `person --participates_in--> meeting`
- `note_revision --belongs_to--> note`
- `note --latest_revision--> note_revision`
- `note_revision --supersedes--> note_revision`
- `note_revision --about--> meeting`
- `note_revision --originates_from--> event`
- `person --owns--> item`
- `item --located_at--> location`
- `state --applies_to--> item`
- `follow_up --targets--> state`

## Acceptance Checks

- New edges follow verb-phrase naming.
- Existing edges are migrated or aliased before deprecating old names.
