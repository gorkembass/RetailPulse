.DEFAULT_GOAL := help
.PHONY: help install db-up db-down ingest pipeline test test-unit lint format dashboard explain clean

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

POSTGRES_USER ?= retailpulse
POSTGRES_PASSWORD ?= retailpulse
POSTGRES_DB ?= retailpulse
POSTGRES_PORT ?= 5432

export DATABASE_URL ?= postgresql+psycopg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/$(POSTGRES_DB)
export RETAILPULSE_TEST_DATABASE_URL ?= postgresql+psycopg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:$(POSTGRES_PORT)/retailpulse_test

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Create the virtual environment and install the project with dev and dashboard extras
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dashboard,dev]"

db-up: ## Start PostgreSQL and wait until it accepts connections
	docker compose up -d --wait postgres

db-down: ## Stop PostgreSQL (data volume is kept)
	docker compose down

ingest: ## Download the UCI Online Retail dataset into data/raw
	$(BIN)/retailpulse ingest

pipeline: ## Run every step: ingest (if needed), clean, load, SQL analyses, pandas analytics, export
	$(BIN)/retailpulse run

test: ## Run unit and PostgreSQL integration tests
	$(BIN)/pytest

test-unit: ## Run only the tests that need no database
	$(BIN)/pytest -m "not integration"

lint: ## Check style and formatting
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: ## Apply formatting and safe lint fixes
	$(BIN)/ruff check . --fix
	$(BIN)/ruff format .

dashboard: ## Serve the Streamlit dashboard on http://localhost:8501
	$(BIN)/streamlit run dashboard/app.py

explain: ## Run the EXPLAIN ANALYZE index probes against the warehouse
	docker compose exec -T postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) < sql/performance/explain_analyze.sql

clean: ## Remove generated outputs (raw data is kept)
	rm -rf data/processed/* dashboard/exports/*.csv .pytest_cache .ruff_cache
	touch data/processed/.gitkeep
