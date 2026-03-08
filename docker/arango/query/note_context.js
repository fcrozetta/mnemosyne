'use strict';

const db = require('@arangodb').db;

const result = db._query(`
FOR note IN note
  LET latest = FIRST(
    FOR rev IN OUTBOUND note latest_revision
      RETURN KEEP(rev, '_id', '_key', 'revision', 'content', 'created_at')
  )
  LET contexts = (
    FOR entity IN OUTBOUND latest about
      RETURN {
        edge: 'about',
        entity_id: entity._id,
        collection: PARSE_IDENTIFIER(entity._id).collection,
        key: entity._key,
      }
  )
  LET origin = FIRST(
    FOR ev IN OUTBOUND latest originates_from
      RETURN KEEP(ev, '_id', '_key', 'event_kind', 'source_system', 'created_at')
  )
  RETURN {
    note: KEEP(note, '_id', '_key', 'note_id'),
    latest_revision: latest,
    contexts,
    origin,
  }
`);

print(JSON.stringify(result.toArray(), null, 2));
