DEFINE TABLE OVERWRITE notes AS
    SELECT
        type::record('notes', in.note_id) AS id,
        in.note_id AS note_id,
        out.version AS version,
        out.content AS content,
        out.observed_at AS observed_at,
        in.created_at AS created_at,
        out.created_at AS revision_created_at
    FROM note_current_revision;
