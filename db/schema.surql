OPTION IMPORT;

DEFINE TABLE IF NOT EXISTS note_roots SCHEMAFULL TYPE NORMAL;
DEFINE TABLE IF NOT EXISTS note_revisions SCHEMAFULL TYPE NORMAL;
DEFINE TABLE IF NOT EXISTS about_refs SCHEMAFULL TYPE NORMAL;
DEFINE TABLE IF NOT EXISTS provenance_records SCHEMAFULL TYPE NORMAL;

DEFINE TABLE IF NOT EXISTS note_has_revision SCHEMAFULL TYPE RELATION IN note_roots OUT note_revisions ENFORCED;
DEFINE TABLE IF NOT EXISTS note_current_revision SCHEMAFULL TYPE RELATION IN note_roots OUT note_revisions ENFORCED;
DEFINE TABLE IF NOT EXISTS revision_previous SCHEMAFULL TYPE RELATION IN note_revisions OUT note_revisions ENFORCED;
DEFINE TABLE IF NOT EXISTS revision_has_provenance SCHEMAFULL TYPE RELATION IN note_revisions OUT provenance_records ENFORCED;
DEFINE TABLE IF NOT EXISTS note_about SCHEMAFULL TYPE RELATION IN note_roots OUT about_refs ENFORCED;

DEFINE FIELD IF NOT EXISTS note_id ON TABLE note_roots TYPE string;
DEFINE FIELD IF NOT EXISTS current_version ON TABLE note_roots TYPE int;
DEFINE FIELD IF NOT EXISTS created_at ON TABLE note_roots TYPE datetime;
DEFINE FIELD IF NOT EXISTS updated_at ON TABLE note_roots TYPE datetime;

DEFINE FIELD IF NOT EXISTS note_id ON TABLE note_revisions TYPE string;
DEFINE FIELD IF NOT EXISTS version ON TABLE note_revisions TYPE int;
DEFINE FIELD IF NOT EXISTS content ON TABLE note_revisions TYPE string;
DEFINE FIELD IF NOT EXISTS observed_at ON TABLE note_revisions TYPE datetime;
DEFINE FIELD IF NOT EXISTS created_at ON TABLE note_revisions TYPE datetime;

DEFINE FIELD IF NOT EXISTS kind ON TABLE about_refs TYPE string;
DEFINE FIELD IF NOT EXISTS identity ON TABLE about_refs TYPE string;
DEFINE FIELD IF NOT EXISTS collection ON TABLE about_refs TYPE option<string>;
DEFINE FIELD IF NOT EXISTS key ON TABLE about_refs TYPE option<string>;
DEFINE FIELD IF NOT EXISTS label ON TABLE about_refs TYPE option<string>;
DEFINE FIELD IF NOT EXISTS resolved ON TABLE about_refs TYPE bool;

DEFINE FIELD IF NOT EXISTS writer ON TABLE provenance_records TYPE option<string>;
DEFINE FIELD IF NOT EXISTS session_id ON TABLE provenance_records TYPE option<string>;
DEFINE FIELD IF NOT EXISTS source_type ON TABLE provenance_records TYPE option<string>;
DEFINE FIELD IF NOT EXISTS source_ref ON TABLE provenance_records TYPE option<string>;

DEFINE FIELD IF NOT EXISTS edge_key ON TABLE note_has_revision TYPE string;
DEFINE FIELD IF NOT EXISTS edge_key ON TABLE note_current_revision TYPE string;
DEFINE FIELD IF NOT EXISTS edge_key ON TABLE revision_previous TYPE string;
DEFINE FIELD IF NOT EXISTS edge_key ON TABLE revision_has_provenance TYPE string;
DEFINE FIELD IF NOT EXISTS edge_key ON TABLE note_about TYPE string;
DEFINE FIELD IF NOT EXISTS label ON TABLE note_about TYPE option<string>;

DEFINE INDEX IF NOT EXISTS note_roots_note_id_unique ON TABLE note_roots FIELDS note_id UNIQUE;
DEFINE INDEX IF NOT EXISTS note_revisions_note_id_version_unique ON TABLE note_revisions FIELDS note_id, version UNIQUE;
DEFINE INDEX IF NOT EXISTS about_refs_kind_identity ON TABLE about_refs FIELDS kind, identity UNIQUE;
DEFINE INDEX IF NOT EXISTS note_current_revision_in_unique ON TABLE note_current_revision FIELDS in UNIQUE;
