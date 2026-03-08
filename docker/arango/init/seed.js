'use strict';

const internal = require('internal');
const db = require('@arangodb').db;
const graphModule = require('@arangodb/general-graph');

const targetDb = internal.env.ARANGO_DB || 'mnemosyne';

const documentCollections = [
  'person',
  'meeting',
  'note',
  'note_revision',
  'event',
  'state',
  'follow_up',
  'item',
  'location',
  'collection_registry',
  'audit_log',
];

const edgeCollections = [
  'participates_in',
  'belongs_to',
  'latest_revision',
  'supersedes',
  'originates_from',
  'about',
  'owns',
  'located_at',
  'applies_to',
  'targets',
];

const noteContextTargets = [
  'person',
  'meeting',
  'state',
  'follow_up',
  'item',
  'location',
  'note',
];

const temporalTargets = ['state', 'person', 'meeting', 'item', 'note'];

const relations = {
  participates_in: graphModule._relation('participates_in', ['person'], ['meeting']),
  belongs_to: graphModule._relation('belongs_to', ['note_revision'], ['note']),
  latest_revision: graphModule._relation('latest_revision', ['note'], ['note_revision']),
  supersedes: graphModule._relation('supersedes', ['note_revision'], ['note_revision']),
  originates_from: graphModule._relation(
    'originates_from',
    ['note_revision', 'follow_up', 'state'],
    ['event']
  ),
  about: graphModule._relation('about', ['note_revision'], noteContextTargets),
  owns: graphModule._relation('owns', ['person'], ['item']),
  located_at: graphModule._relation('located_at', ['item', 'state'], ['location']),
  applies_to: graphModule._relation('applies_to', ['state'], temporalTargets),
  targets: graphModule._relation('targets', ['follow_up'], temporalTargets),
};

const graphDefinitions = [
  {
    name: 'people_graph',
    edges: [relations.participates_in],
  },
  {
    name: 'notes_graph',
    edges: [
      relations.belongs_to,
      relations.latest_revision,
      relations.supersedes,
      relations.originates_from,
      relations.about,
    ],
  },
  {
    name: 'temporal_graph',
    edges: [
      relations.applies_to,
      relations.targets,
      relations.belongs_to,
      relations.originates_from,
      relations.about,
    ],
  },
  {
    name: 'inventory_graph',
    edges: [
      relations.owns,
      relations.located_at,
    ],
  },
  {
    name: 'mnemosyne_graph',
    edges: [
      relations.participates_in,
      relations.belongs_to,
      relations.latest_revision,
      relations.supersedes,
      relations.originates_from,
      relations.about,
      relations.owns,
      relations.located_at,
      relations.applies_to,
      relations.targets,
    ],
  },
];

function ensureDatabase(name) {
  db._useDatabase('_system');
  if (!db._databases().includes(name)) {
    db._createDatabase(name);
    print(`created database ${name}`);
  }
  db._useDatabase(name);
}

function ensureCollection(name, type) {
  if (db._collection(name)) {
    return;
  }

  if (type === 'edge') {
    db._createEdgeCollection(name);
  } else {
    db._createDocumentCollection(name);
  }

  print(`created ${type} collection ${name}`);
}

function ensureGraph(name, edgeDefinitions) {
  if (graphModule._exists(name)) {
    return;
  }

  graphModule._create(name, edgeDefinitions);
  print(`created graph ${name}`);
}

function ensureInvertedIndex(collectionName, definition) {
  const collection = db._collection(collectionName);
  const existing = collection.indexes().find((index) => index.name === definition.name);
  if (existing) {
    return;
  }

  collection.ensureIndex(definition);
  print(`created inverted index ${definition.name} on ${collectionName}`);
}

function ensureSearchAliasView(name, indexes) {
  const view = db._view(name);
  if (view) {
    return;
  }

  db._createView(name, 'search-alias', { indexes });
  print(`created search-alias view ${name}`);
}

function upsert(collectionName, doc) {
  db._query(
    'UPSERT { _key: @key } INSERT @doc UPDATE @doc IN @@collection',
    {
      '@collection': collectionName,
      key: doc._key,
      doc,
    }
  );
}

ensureDatabase(targetDb);
documentCollections.forEach((name) => ensureCollection(name, 'document'));
edgeCollections.forEach((name) => ensureCollection(name, 'edge'));
graphDefinitions.forEach((graph) => ensureGraph(graph.name, graph.edges));
ensureInvertedIndex('note', {
  type: 'inverted',
  name: 'note_current_search_inv',
  primaryKeyCache: true,
  fields: [
    'note_id',
    { name: 'current_content', analyzer: 'text_en', cache: true },
    { name: 'pending_about_labels[*]', analyzer: 'text_en', cache: true },
    { name: 'resolved_about_labels[*]', analyzer: 'text_en', cache: true },
    { name: 'aliases[*]', analyzer: 'text_en', cache: true },
    'updated_at',
    'observed_at',
  ],
});
ensureSearchAliasView('note_current_view', [
  { collection: 'note', index: 'note_current_search_inv' },
]);

const registryDocs = documentCollections.map((name) => ({
  _key: name,
  collection_name: name,
  kind: 'document',
  owner: ['collection_registry', 'audit_log'].includes(name)
    ? 'system'
    : 'fer',
  soren_access: ['collection_registry', 'audit_log'].includes(name)
    ? 'none'
    : 'ro',
  purpose: `bootstrap ${name} collection`,
  created_at: '2026-02-27T22:21:50Z',
  created_by: 'api',
  status: 'active',
})).concat(
  edgeCollections.map((name) => ({
    _key: name,
    collection_name: name,
    kind: 'edge',
    owner: 'fer',
    soren_access: 'ro',
    purpose: `bootstrap ${name} edge collection`,
    created_at: '2026-02-27T22:21:50Z',
    created_by: 'api',
    status: 'active',
  }))
);

registryDocs.forEach((doc) => upsert('collection_registry', doc));

const docs = {
  person: [
    { _key: 'fer', display_name: 'Fer', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
    { _key: 'friend_001', display_name: 'Friend', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
  ],
  meeting: [
    {
      _key: 'mtg_001',
      meeting_id: 'mtg_001',
      title: 'Weekly Sync',
      started_at: '2026-02-27T14:00:00Z',
      created_at: '2026-02-27T22:21:50Z',
      created_by: 'seed',
    },
  ],
  note: [
    {
      _key: 'note_001',
      note_id: 'note_001',
      current_content: 'Need to pick up my blue PME Oxford shirt next Saturday.',
      pending_about_labels: ['friend house'],
      resolved_about_labels: ['weekly sync', 'forgotten shirt', 'shirt follow up'],
      aliases: ['shirt note', 'blue shirt note'],
      observed_at: '2026-02-27T22:26:50Z',
      updated_at: '2026-02-27T22:26:50Z',
      created_at: '2026-02-27T22:21:50Z',
      created_by: 'seed',
    },
  ],
  note_revision: [
    {
      _key: 'nr_001',
      note_id: 'note_001',
      revision: 1,
      content: 'I forgot my PME Oxford shirt at my friend\'s house.',
      observed_at: '2026-02-27T22:21:50Z',
      created_at: '2026-02-27T22:21:50Z',
      created_by: 'seed',
    },
    {
      _key: 'nr_002',
      note_id: 'note_001',
      revision: 2,
      content: 'Need to pick up my blue PME Oxford shirt next Saturday.',
      observed_at: '2026-02-27T22:26:50Z',
      created_at: '2026-02-27T22:26:50Z',
      created_by: 'seed',
    },
  ],
  event: [
    {
      _key: 'ev_001',
      event_kind: 'manual_note',
      source_system: 'manual_notes',
      created_at: '2026-02-27T22:21:50Z',
      created_by: 'seed',
    },
    {
      _key: 'ev_002',
      event_kind: 'manual_edit',
      source_system: 'manual_notes',
      created_at: '2026-02-27T22:26:50Z',
      created_by: 'seed',
    },
  ],
  state: [
    {
      _key: 'state_001',
      kind: 'item_left_somewhere',
      status: 'active',
      starts_at: '2026-02-27',
      created_at: '2026-02-27T22:21:50Z',
      created_by: 'seed',
    },
  ],
  follow_up: [
    {
      _key: 'fu_001',
      cadence: 'once',
      status: 'active',
      due_at: '2026-02-28',
      created_at: '2026-02-27T22:21:50Z',
      created_by: 'seed',
    },
  ],
  item: [
    { _key: 'item_shirt_001', item_kind: 'physical', created_at: '2026-02-27T22:30:50Z', created_by: 'seed' },
  ],
  location: [
    { _key: 'friend_house_001', name: 'Friend House', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
  ],
  audit_log: [
    {
      _key: 'bootstrap_seed',
      action_type: 'bootstrap_seed',
      principal: 'seed',
      target: targetDb,
      decision: 'approved',
      reason: 'bootstrap local development database',
      timestamp: '2026-02-27T22:21:50Z',
    },
  ],
};

Object.keys(docs).forEach((collectionName) => {
  docs[collectionName].forEach((doc) => upsert(collectionName, doc));
});

const edges = {
  participates_in: [
    { _key: 'fer_participates_in_mtg_001', _from: 'person/fer', _to: 'meeting/mtg_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed', verified: true },
    { _key: 'friend_participates_in_mtg_001', _from: 'person/friend_001', _to: 'meeting/mtg_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed', verified: true },
  ],
  belongs_to: [
    { _key: 'nr_001_belongs_to_note_001', _from: 'note_revision/nr_001', _to: 'note/note_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
    { _key: 'nr_002_belongs_to_note_001', _from: 'note_revision/nr_002', _to: 'note/note_001', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
  ],
  latest_revision: [
    { _key: 'note_001_latest_revision_nr_002', _from: 'note/note_001', _to: 'note_revision/nr_002', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
  ],
  supersedes: [
    { _key: 'nr_002_supersedes_nr_001', _from: 'note_revision/nr_002', _to: 'note_revision/nr_001', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
  ],
  originates_from: [
    { _key: 'nr_001_originates_from_ev_001', _from: 'note_revision/nr_001', _to: 'event/ev_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
    { _key: 'nr_002_originates_from_ev_002', _from: 'note_revision/nr_002', _to: 'event/ev_002', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
  ],
  about: [
    { _key: 'nr_002_about_item_shirt_001', _from: 'note_revision/nr_002', _to: 'item/item_shirt_001', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
    { _key: 'nr_002_about_state_001', _from: 'note_revision/nr_002', _to: 'state/state_001', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
    { _key: 'nr_002_about_fu_001', _from: 'note_revision/nr_002', _to: 'follow_up/fu_001', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
    { _key: 'nr_002_about_mtg_001', _from: 'note_revision/nr_002', _to: 'meeting/mtg_001', created_at: '2026-02-27T22:26:50Z', created_by: 'seed' },
  ],
  owns: [
    { _key: 'fer_owns_item_shirt_001', _from: 'person/fer', _to: 'item/item_shirt_001', created_at: '2026-02-27T22:30:50Z', created_by: 'seed' },
  ],
  located_at: [
    { _key: 'item_shirt_001_located_at_friend_house_001', _from: 'item/item_shirt_001', _to: 'location/friend_house_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
    { _key: 'state_001_located_at_friend_house_001', _from: 'state/state_001', _to: 'location/friend_house_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
  ],
  applies_to: [
    { _key: 'state_001_applies_to_item_shirt_001', _from: 'state/state_001', _to: 'item/item_shirt_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
  ],
  targets: [
    { _key: 'fu_001_targets_state_001', _from: 'follow_up/fu_001', _to: 'state/state_001', created_at: '2026-02-27T22:21:50Z', created_by: 'seed' },
  ],
};

Object.keys(edges).forEach((collectionName) => {
  edges[collectionName].forEach((edge) => upsert(collectionName, edge));
});

upsert('audit_log', {
  _key: 'bootstrap_summary',
  action_type: 'bootstrap_summary',
  principal: 'seed',
  target: targetDb,
  decision: 'approved',
  reason: 'collections and sample graph are ready',
  timestamp: '2026-02-27T22:31:50Z',
});

print(`database ${targetDb} is seeded`);
