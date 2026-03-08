# Claim 0024: Notes Can Target Follow-Ups and Related Entities

## Statement

A note revision may be about a follow_up and also about the underlying state,
person, meeting, or other related entities at the same time.

## Scope

- Follow-up notes remain connected to the actionable obligation.
- The same note may also preserve links to domain context entities.

## Acceptance Checks

- Note relation docs allow `about` edges to follow_up nodes.
- Note relation docs allow simultaneous `about` links to other entities.
