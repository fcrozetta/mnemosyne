# Claim 0019: v0 Basic Collection Contract

## Statement

v0 uses a fixed minimal set of document and edge collections to support manual
notes ingestion, temporal tracking, and purchase/inventory graph growth.

## Client-Writable Domain Collections (via business endpoints)

### Document Collections

- `person`
  - Purpose: global person entities.
  - Required fields: `_key`, `display_name`, `created_at`, `created_by`.
  - Index intent: hash index on normalized name.
- `identity`
  - Purpose: source-specific identifiers mapped to people.
  - Required fields: `_key`, `source_system`, `source_id`, `created_at`,
    `created_by`.
  - Index intent: unique composite on (`source_system`, `source_id`).
- `meeting`
  - Purpose: meeting entities anchored by generated `meeting_id`.
  - Required fields: `_key`, `meeting_id`, `title`, `started_at`, `created_at`,
    `created_by`.
  - Index intent: unique index on `meeting_id`.
- `note`
  - Purpose: stable anchor for a logical note across revisions.
  - Required fields: `_key`, `note_id`, `created_at`, `created_by`.
  - Index intent: unique index on `note_id`.
- `note_revision`
  - Purpose: immutable note revisions attached to a note anchor.
  - Required fields: `_key`, `note_id`, `revision`, `content`, `created_at`,
    `created_by`.
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
- `follow_up_event`
  - Purpose: immutable lifecycle log for follow-ups.
  - Required fields: `_key`, `kind`, `created_at`, `created_by`.
- `purchase`
  - Purpose: commercial transaction anchor.
  - Required fields: `_key`, `purchased_at`, `currency`, `created_at`,
    `created_by`.
- `purchase_item`
  - Purpose: line item inside a purchase.
  - Required fields: `_key`, `quantity`, `unit_price`, `created_at`,
    `created_by`.
- `item`
  - Purpose: one concrete physical unit.
  - Required fields: `_key`, `item_kind`, `created_at`, `created_by`.
- `product_snapshot`
  - Purpose: purchase-time description of an item with raw attributes.
  - Required fields: `_key`, `category`, `attributes`, `created_at`,
    `created_by`.
- `seller`
  - Purpose: company or person the purchase came from.
  - Required fields: `_key`, `name`, `created_at`, `created_by`.
- `payment_method`
  - Purpose: platform/card/account used to pay.
  - Required fields: `_key`, `provider`, `created_at`, `created_by`.
- `payment_obligation`
  - Purpose: installment or outstanding payment obligation.
  - Required fields: `_key`, `total_amount`, `created_at`, `created_by`.
- `payment`
  - Purpose: actual payment event.
  - Required fields: `_key`, `amount`, `paid_at`, `created_at`, `created_by`.
- `place`
  - Purpose: physical location relevant to items, states, or events.
  - Required fields: `_key`, `name`, `created_at`, `created_by`.

### Edge Collections

- `has_identity`
  - Purpose: connect people to source identities with verb-oriented naming.
  - Required fields: `_from`, `_to`, `verified`, `created_at`, `created_by`.
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
  - Purpose: connect entities/edges to originating event nodes.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `about`
  - Purpose: connect note revisions to primary subject entities.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `mentions`
  - Purpose: connect note revisions to referenced entities discovered later.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `supersedes`
  - Purpose: connect newer note revisions to prior revisions.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `owns`
  - Purpose: connect a person to an item they own.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `located_at`
  - Purpose: connect an entity to its relevant place.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `applies_to`
  - Purpose: connect a state to the entity it applies to.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `targets`
  - Purpose: connect a follow_up to the state or entity it targets.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `describes`
  - Purpose: connect a product snapshot to the item it describes.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `bought_from`
  - Purpose: connect a purchase to its seller.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `paid_via`
  - Purpose: connect a purchase to its payment method.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `includes`
  - Purpose: connect a purchase to its purchase items.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `results_in`
  - Purpose: connect a purchase item to the physical items it yields.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `creates`
  - Purpose: connect a purchase to a payment obligation it creates.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.
- `settles`
  - Purpose: connect a payment to the obligation it settles.
  - Required fields: `_from`, `_to`, `created_at`, `created_by`.

## System-Internal Collections (Server-Managed)

- `collection_registry`
- `audit_log`
- `idempotency_ledger`
- `job_queue` (deferred runtime use)
- `job_dead_letter` (deferred runtime use)

## Notes

- v0 relation state is verified-only.
- Media artifact collections are deferred.
- Migrations are deferred; bootstrap currently uses an explicit init service.
- Worker queue collections may exist before worker runtime is enabled.
- Edge naming convention uses verb phrases in `snake_case` and each edge must
  read as a sentence: `source --verb--> target`.
- `about` and `mentions` are distinct semantics: `about` is asserted subject;
  `mentions` captures explicit or AI-derived references.
- Notes are not anchored to meetings. A note revision may point to zero or many
  context entities via `about` and `mentions`.
