# Claim 0039: Arango Uses Domain Graphs Plus an Umbrella Graph

## Statement

Arango bootstrap creates multiple named domain graphs plus one umbrella graph.
Collections and edge collections remain canonical storage; named graphs exist
for traversal, inspection, and UI clarity.

## Required Named Graphs

- `identity_graph`
- `notes_graph`
- `temporal_graph`
- `inventory_graph`
- `mnemosyne_graph`

## Acceptance Checks

- Bootstrap creates the domain graphs and umbrella graph.
- Named graphs are defined over shared collections rather than duplicated data.
