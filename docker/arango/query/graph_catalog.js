'use strict';

const graphModule = require('@arangodb/general-graph');

const graphs = graphModule._list().map((graph) => ({
  name: graph._key,
  edge_definitions: graph.edgeDefinitions,
  orphan_collections: graph.orphanCollections,
}));

print(JSON.stringify(graphs, null, 2));
