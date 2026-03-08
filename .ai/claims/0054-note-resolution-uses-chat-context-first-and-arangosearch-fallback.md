# Claim 0054: Notes Search Is a Stateless GET /notes Endpoint Backed by ArangoSearch

## Statement

The API remains stateless for chat session context. Notes discovery happens via
`GET /notes`, which performs ArangoSearch-backed retrieval over current
searchable fields stored on the `note` anchor without interpreting
conversational context.

## Rules

- The chat/orchestration layer owns short-lived session context and note
  targeting.
- The API does not store or interpret conversational session state.
- `GET /notes` accepts plain search inputs such as `q` and `limit`.
- Search results return ranked note candidates only; selection remains a client
  concern.
- Search indexes current note state on `note` rather than a duplicate search
  collection.

## Search Design

- Do not use ArangoDB fulltext indexes for notes search.
- Use inverted indexes plus a `search-alias` View for search and ranking.
- Search current note-anchor fields rather than raw revision history.
- Search ranking should combine relevance with recency.

## Indexed Fields

The searchable fields on `note` should carry enough current-state material for
note search, including:

- `note_id`
- current note content
- unresolved pending context labels
- resolved context labels
- aliases derived from current content when useful
- timestamps used for recency tie-breaking

## Acceptance Checks

- API design keeps conversational note state outside the API runtime.
- `GET /notes` exists as the note search endpoint.
- Search planning uses ArangoSearch primitives instead of deprecated fulltext.
- Search targets current note state on `note` rather than all historical
  revisions or a duplicate search collection.
