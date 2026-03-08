'use strict';

const db = require('@arangodb').db;

const graphs = db._query(`
FOR g IN _graphs
  SORT g._key ASC
  RETURN {
    name: g._key,
    edge_definitions: g.edgeDefinitions ? g.edgeDefinitions : [],
    orphan_collections: g.orphanCollections ? g.orphanCollections : []
  }
`).toArray();

print(JSON.stringify(graphs, null, 2));
