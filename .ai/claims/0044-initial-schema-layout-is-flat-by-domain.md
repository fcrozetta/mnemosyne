# Claim 0044: Initial API Schema Layout Is Flat by Domain

## Statement

The initial API schema layout starts with flat domain modules under
`app/schemas/`, not nested per-domain packages.

## Scope

- Start with:
  - `app/schemas/common.py`
  - `app/schemas/notes.py`
- Keep one schema module per domain until the domain grows enough to justify a
  subpackage.
- Do not mix API request/response schemas with persistence models casually; if
  internal document models become substantial, split them deliberately.

## Acceptance Checks

- Initial note schemas can live in `app/schemas/notes.py`.
- Shared schema helpers can live in `app/schemas/common.py`.
- Per-domain subpackages are deferred until there is clear structural pressure.
