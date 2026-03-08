'use strict';

const db = require('@arangodb').db;

const result = db._query(`
FOR followUp IN follow_up
  LET targets = (
    FOR entity IN OUTBOUND followUp targets
      RETURN {
        entity_id: entity._id,
        collection: PARSE_IDENTIFIER(entity._id).collection,
        key: entity._key,
        kind: entity.kind ? entity.kind : null,
        status: entity.status ? entity.status : null,
      }
  )
  RETURN {
    follow_up: KEEP(followUp, '_id', '_key', 'cadence', 'status', 'due_at', 'next_due_at'),
    targets,
  }
`);

print(JSON.stringify(result.toArray(), null, 2));
