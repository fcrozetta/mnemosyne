ifneq (,$(wildcard .env))
include .env
endif

API_PORT ?= 8180
ARCADE_PORT ?= 2480
ARCADE_URL ?= http://127.0.0.1:$(ARCADE_PORT)
ARCADE_DATABASE ?= mnemosyne
ARCADE_USERNAME ?= root
ARCADE_PASSWORD ?= mnemosyne-root
COMPOSE ?= docker compose
COMPOSE_DEV ?= docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: clean db-clean db-up db-ready db-bootstrap seed up dev down test lint

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find app tests -type d -name __pycache__ -prune -exec rm -rf {} +

db-clean:
	$(COMPOSE_DEV) down -v --remove-orphans

up:
	API_PORT=$(API_PORT) ARCADE_PORT=$(ARCADE_PORT) $(COMPOSE) up -d --build

dev:
	API_PORT=$(API_PORT) ARCADE_PORT=$(ARCADE_PORT) $(COMPOSE_DEV) up -d --build

down:
	$(COMPOSE_DEV) down --remove-orphans

db-up:
	ARCADE_PORT=$(ARCADE_PORT) ARCADE_PASSWORD=$(ARCADE_PASSWORD) $(COMPOSE) up -d arcadedb

db-ready: db-up
	until curl -fsS "$(ARCADE_URL)/api/v1/ready" >/dev/null; do sleep 1; done

db-bootstrap: db-ready
	ARCADE_URL=$(ARCADE_URL) ARCADE_DATABASE=$(ARCADE_DATABASE) ARCADE_USERNAME=$(ARCADE_USERNAME) ARCADE_PASSWORD=$(ARCADE_PASSWORD) uv run python -c 'from app.storage.arcade import ArcadeStorageBackend; backend = ArcadeStorageBackend(base_url="$(ARCADE_URL)", database="$(ARCADE_DATABASE)", username="$(ARCADE_USERNAME)", password="$(ARCADE_PASSWORD)"); backend.ensure_database(); backend.apply_default_schema()'

seed: db-bootstrap

test:
	uv run pytest -q

lint:
	uv run ruff check .
