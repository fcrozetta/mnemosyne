#!/bin/sh
set -eu

ARANGO_ENDPOINT="tcp://${ARANGO_HOST:-arangodb}:${ARANGO_PORT:-8529}"

exec arangosh \
  --server.endpoint "${ARANGO_ENDPOINT}" \
  --server.username root \
  --server.password "${ARANGO_ROOT_PASSWORD:-root}" \
  --javascript.execute /docker/arango/init/seed.js
