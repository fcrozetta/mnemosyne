# Claim 0019: v0 Basic Collection Contract

## Statement

v0 uses a deliberately small fixed set of document and edge collections to
support current-note search, append-only notes, temporal state, follow-ups, and
basic item/location context. Purchase, payment, queue, and identity-expansion
subsystems are deferred.

## Client-Writable Domain Collections (via business endpoints)

### Document Collections

- `person`
  - Purpose: global person entities.
  - Required fields: `_key`, `display_name`, `created_at`, `created_by`.
  - Index intent: hash index on normalized name.
- `meeting`
  - Purpose: meeting entities anchored by generated `meeting_id`.
  - Required fields: `_key`, `meeting_id`, `title`, `started_at`, `created_at`,
    `created_by`.
  - Index intent: unique index on `meeting_id`.
- `note`
  - Purpose: stable anchor for a logical note across revisions and current
    searchable state.
  - Required fields: `_key`, `note_id`, `created_at`, `created_by`.
  - Search fields carried on the anchor: current content, current context
    labels, aliases, and current timestamps.
  - Index intent: unique index on `note_id` plus ArangoSearch inverted index on
    current searchable fields.
- `note_revision`
  - Purpose: immutable note revisions attached to a note anchor.
  - Required fields: `_key`, `note_id`, `revision`, `content`, `observed_at`,
    `created_at`, `created_by`.
  - Index intent: unique composite on (`note_id`, `revision`).
- `event`
  - Purpose: immutable provenance/event node for ingestion and manual actions.
  - Required fields: `_key`, `event_kind`, `source_system`, `created_at`,
    `created_by`.
  - Index intent: hash index on (`event_kind`, `source_system`).
- `state`
  - Purpose: time-sensitive condition applied to another entity.
  - Required fields: `_key`, `kind`, `status`, `starts_at`, `created_at`,
    `created_by`.
- `follow_up`
  - Purpose: actionable reminder/attention contract over time.
  - Required fields: `_key`, `status`, `cadence`, `created_at`, `created_by`.
- `item`
  - Purpose: one concrete item anchor that can participate in ownership and
    location context.
  - Required fields: `_key`, `item_kind`, `created_at`, `created_by`.
- `location`
  - Purpose: physical location relevant to items, states, or notes.
  - Required fields: `_key`, `name`, `created_at`, `created_by`.

### Edge Collections

- `participates_in`
  - Purpose: connect people to meetings.
  - Required fields: `_from`, `_to`, `verified`, `created_at`, `created_by`.
- `belongs_to`
  - Purpose: connect note revisions to their note anchor.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `latest_revision`
  - Purpose: connect note anchors to their current revision shortcut.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `originates_from`
  - Purpose: connect entities to originating event nodes.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `about`
  - Purpose: connect note revisions to asserted subject entities.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `supersedes`
  - Purpose: connect newer note revisions to prior revisions.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `owns`
  - Purpose: connect a person to an item they own.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `located_at`
  - Purpose: connect an item or state to a relevant location.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `applies_to`
  - Purpose: connect a state to the entity it applies to.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `targets`
  - Purpose: connect a follow_up to the entity or state it targets.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.

## System-Internal Collections (Server-Managed)

- `collection_registry`
- `audit_log`

## Deferred From v0

- `identity`
- `follow_up_event`
- `mentions`
- purchase, payment, seller, and product-detail collections
- queue and idempotency collections

## Notes

- v0 relation state is verified-only.
- Media artifact collections are deferred.
- Migrations are deferred; bootstrap currently uses an explicit init service.
- Edge naming convention uses verb phrases in `snake_case` and each edge must
  read as a sentence: `source --verb--> target`.
- Notes support asserted context via `about`. `mentions` are deferred.
- `GET /notes` searches current note state only, not historical revisions.
