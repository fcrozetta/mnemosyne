DOCKER_COMPOSE ?= docker compose
PROJECT_NAME ?= mnemosyne
ARANGO_CONTAINER := $(PROJECT_NAME)-arangodb
ARANGO_QUERY_RUN = $(DOCKER_COMPOSE) run --rm --entrypoint /bin/sh arango-init /docker/arango/query/run-query.sh

.PHONY: db seed clean ps logs graph graph-note graph-followup graph-catalog

db:
	$(DOCKER_COMPOSE) up -d arangodb
	$(DOCKER_COMPOSE) run --rm arango-init
	$(DOCKER_COMPOSE) ps

seed:
	$(DOCKER_COMPOSE) run --rm arango-init

clean:
	-docker rm -f $(ARANGO_CONTAINER)
	$(DOCKER_COMPOSE) down -v --remove-orphans

ps:
	$(DOCKER_COMPOSE) ps

logs:
	$(DOCKER_COMPOSE) logs -f arangodb

graph: db graph-catalog

graph-note:
	$(ARANGO_QUERY_RUN) note_context

graph-followup:
	$(ARANGO_QUERY_RUN) follow_up_view

graph-catalog:
	$(ARANGO_QUERY_RUN) graph_catalog
