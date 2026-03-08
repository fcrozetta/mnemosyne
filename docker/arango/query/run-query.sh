#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: run-query.sh <query-name>" >&2
  exit 1
fi

ARANGO_ENDPOINT="tcp://${ARANGO_HOST:-arangodb}:${ARANGO_PORT:-8529}"
QUERY_FILE="/docker/arango/query/$1.js"

if [ ! -f "${QUERY_FILE}" ]; then
  echo "query file not found: ${QUERY_FILE}" >&2
  exit 1
fi

exec arangosh \
  --server.endpoint "${ARANGO_ENDPOINT}" \
  --server.username root \
  --server.password "${ARANGO_ROOT_PASSWORD:-root}" \
  --server.database "${ARANGO_DB:-mnemosyne}" \
  --javascript.execute "${QUERY_FILE}"
