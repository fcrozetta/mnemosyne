OPTION IMPORT;

UPSERT note_roots:note_001 CONTENT {
    note_id: "note_001",
    current_version: 2,
    created_at: d'2026-04-06T17:00:00Z',
    updated_at: d'2026-04-06T18:05:00Z'
};

UPSERT note_roots:note_014 CONTENT {
    note_id: "note_014",
    current_version: 1,
    created_at: d'2026-04-05T09:30:00Z',
    updated_at: d'2026-04-05T09:30:00Z'
};

UPSERT note_revisions:note_001_v1 CONTENT {
    note_id: "note_001",
    version: 1,
    content: "Need to pick up my shirt.",
    observed_at: d'2026-04-06T17:00:00Z',
    created_at: d'2026-04-06T17:00:00Z'
};

UPSERT note_revisions:note_001_v2 CONTENT {
    note_id: "note_001",
    version: 2,
    content: "Need to pick up my shirt.\n\nAddendum:\nIt is the blue one.",
    observed_at: d'2026-04-06T18:05:00Z',
    created_at: d'2026-04-06T18:05:00Z'
};

UPSERT note_revisions:note_014_v1 CONTENT {
    note_id: "note_014",
    version: 1,
    content: "Blue PME Oxford shirt is at John's place.",
    observed_at: d'2026-04-05T09:30:00Z',
    created_at: d'2026-04-05T09:30:00Z'
};

UPSERT about_refs:about_item_item_shirt_001 CONTENT {
    kind: "item",
    identity: "item:item_shirt_001",
    collection: "item",
    key: "item_shirt_001",
    resolved: true
};

UPSERT about_refs:about_location_johns_place CONTENT {
    kind: "location",
    identity: "john's place",
    label: "John's place",
    resolved: false
};

UPSERT provenance_records:provenance_note_001_v2 CONTENT {
    writer: "alpha-seed",
    source_type: "seed",
    source_ref: "make seed"
};

UPSERT provenance_records:provenance_note_014_v1 CONTENT {
    writer: "alpha-seed",
    source_type: "seed",
    source_ref: "make seed"
};

DELETE note_has_revision:note_001_has_note_001_v1;
INSERT RELATION INTO note_has_revision {
    id: "note_001_has_note_001_v1",
    in: note_roots:note_001,
    out: note_revisions:note_001_v1,
    edge_key: "note_001_has_note_001_v1"
};

DELETE note_has_revision:note_001_has_note_001_v2;
INSERT RELATION INTO note_has_revision {
    id: "note_001_has_note_001_v2",
    in: note_roots:note_001,
    out: note_revisions:note_001_v2,
    edge_key: "note_001_has_note_001_v2"
};

DELETE note_has_revision:note_014_has_note_014_v1;
INSERT RELATION INTO note_has_revision {
    id: "note_014_has_note_014_v1",
    in: note_roots:note_014,
    out: note_revisions:note_014_v1,
    edge_key: "note_014_has_note_014_v1"
};

DELETE note_current_revision:note_001_current_note_001_v2;
INSERT RELATION INTO note_current_revision {
    id: "note_001_current_note_001_v2",
    in: note_roots:note_001,
    out: note_revisions:note_001_v2,
    edge_key: "note_001_current_note_001_v2"
};

DELETE note_current_revision:note_014_current_note_014_v1;
INSERT RELATION INTO note_current_revision {
    id: "note_014_current_note_014_v1",
    in: note_roots:note_014,
    out: note_revisions:note_014_v1,
    edge_key: "note_014_current_note_014_v1"
};

DELETE revision_previous:note_001_v2_previous_note_001_v1;
INSERT RELATION INTO revision_previous {
    id: "note_001_v2_previous_note_001_v1",
    in: note_revisions:note_001_v2,
    out: note_revisions:note_001_v1,
    edge_key: "note_001_v2_previous_note_001_v1"
};

DELETE revision_has_provenance:note_001_v2_has_provenance;
INSERT RELATION INTO revision_has_provenance {
    id: "note_001_v2_has_provenance",
    in: note_revisions:note_001_v2,
    out: provenance_records:provenance_note_001_v2,
    edge_key: "note_001_v2_has_provenance"
};

DELETE revision_has_provenance:note_014_v1_has_provenance;
INSERT RELATION INTO revision_has_provenance {
    id: "note_014_v1_has_provenance",
    in: note_revisions:note_014_v1,
    out: provenance_records:provenance_note_014_v1,
    edge_key: "note_014_v1_has_provenance"
};

DELETE note_about:note_001_about_item_shirt;
INSERT RELATION INTO note_about {
    id: "note_001_about_item_shirt",
    in: note_roots:note_001,
    out: about_refs:about_item_item_shirt_001,
    edge_key: "note_001_about_item_shirt"
};

DELETE note_about:note_001_about_location_johns_place;
INSERT RELATION INTO note_about {
    id: "note_001_about_location_johns_place",
    in: note_roots:note_001,
    out: about_refs:about_location_johns_place,
    edge_key: "note_001_about_location_johns_place"
};

DELETE note_about:note_014_about_item_shirt;
INSERT RELATION INTO note_about {
    id: "note_014_about_item_shirt",
    in: note_roots:note_014,
    out: about_refs:about_item_item_shirt_001,
    edge_key: "note_014_about_item_shirt"
};

DELETE note_about:note_014_about_location_johns_place;
INSERT RELATION INTO note_about {
    id: "note_014_about_location_johns_place",
    in: note_roots:note_014,
    out: about_refs:about_location_johns_place,
    edge_key: "note_014_about_location_johns_place"
};
