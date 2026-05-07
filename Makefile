ifneq (,$(wildcard .env))
include .env
endif

SURREAL_PORT ?= 8000
SURREAL_URL ?= http://127.0.0.1:$(SURREAL_PORT)
SURREAL_NAMESPACE ?= mnemosyne
SURREAL_DATABASE ?= mnemosyne
SURREAL_ROOT_USERNAME ?= root
SURREAL_ROOT_PASSWORD ?= $(or $(SURREAL_ROOT_PASS),root)
SURREAL_USERNAME ?= mnemosyne
SURREAL_PASSWORD ?= mnemosyne
SURREAL_DATABASE_ROLE ?= EDITOR
SURREAL_INTERNAL_URL ?= http://127.0.0.1:8000
SURREAL_CLI ?= docker compose exec -T surrealdb /surreal
SURREAL_SCHEMA_FILE ?= /db/schema.surql
SURREAL_SEED_FILE ?= /db/seed.surql
SURREAL_VIEWS_FILE ?= db/views.surql
SURREAL_EXPORT_FILE ?= /db/exports/mnemosyne.surql

.PHONY: clean db-clean db-up db-ready db-bootstrap seed db-export test lint

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find app tests -type d -name __pycache__ -prune -exec rm -rf {} +

db-clean:
	docker compose down -v --remove-orphans

db-up:
	SURREAL_PORT=$(SURREAL_PORT) SURREAL_ROOT_USERNAME=$(SURREAL_ROOT_USERNAME) SURREAL_ROOT_PASSWORD=$(SURREAL_ROOT_PASSWORD) docker compose up -d surrealdb

db-ready: db-up
	until $(SURREAL_CLI) is-ready --endpoint $(SURREAL_INTERNAL_URL) --log none; do sleep 1; done

db-bootstrap: db-ready
	printf 'DEFINE NAMESPACE IF NOT EXISTS $(SURREAL_NAMESPACE);\nUSE NS $(SURREAL_NAMESPACE);\nDEFINE DATABASE IF NOT EXISTS $(SURREAL_DATABASE);\nUSE DB $(SURREAL_DATABASE);\nDEFINE USER OVERWRITE $(SURREAL_USERNAME) ON DATABASE PASSWORD "$(SURREAL_PASSWORD)" ROLES $(SURREAL_DATABASE_ROLE);\n' | $(SURREAL_CLI) sql --endpoint $(SURREAL_INTERNAL_URL) --auth-level root --username $(SURREAL_ROOT_USERNAME) --password $(SURREAL_ROOT_PASSWORD) --namespace $(SURREAL_NAMESPACE) --database $(SURREAL_DATABASE) --hide-welcome --log none

seed: db-bootstrap
	$(SURREAL_CLI) import --endpoint $(SURREAL_INTERNAL_URL) --auth-level root --username $(SURREAL_ROOT_USERNAME) --password $(SURREAL_ROOT_PASSWORD) --namespace $(SURREAL_NAMESPACE) --database $(SURREAL_DATABASE) --log none $(SURREAL_SCHEMA_FILE)
	$(SURREAL_CLI) import --endpoint $(SURREAL_INTERNAL_URL) --auth-level root --username $(SURREAL_ROOT_USERNAME) --password $(SURREAL_ROOT_PASSWORD) --namespace $(SURREAL_NAMESPACE) --database $(SURREAL_DATABASE) --log none $(SURREAL_SEED_FILE)
	$(SURREAL_CLI) sql --endpoint $(SURREAL_INTERNAL_URL) --auth-level root --username $(SURREAL_ROOT_USERNAME) --password $(SURREAL_ROOT_PASSWORD) --namespace $(SURREAL_NAMESPACE) --database $(SURREAL_DATABASE) --hide-welcome --multi --log none < $(SURREAL_VIEWS_FILE)

db-export: db-ready
	$(SURREAL_CLI) export --endpoint $(SURREAL_INTERNAL_URL) --auth-level root --username $(SURREAL_ROOT_USERNAME) --password $(SURREAL_ROOT_PASSWORD) --namespace $(SURREAL_NAMESPACE) --database $(SURREAL_DATABASE) --log none $(SURREAL_EXPORT_FILE)

test:
	uv run pytest -q

lint:
	uv run ruff check .
