# Stage targets for the Pacific administrative boundaries pipeline.
# Mirrors the cache -> process -> combine -> stac flow. Run with `make <target>`.
# Uses `uv run pab ...`; see README.md for setup.

PAB := uv run pab
ISO3 ?= FJI
# published HTTPS root (config/publish.yml https_base); STAC asset hrefs point there
HTTPS_BASE := $(shell awk '/^https_base:/ {print $$2}' config/publish.yml)

.PHONY: help env lint test cache cache-eez cache-all process process-eez process-all assign-eez combine stac stac-local qa publish-dryrun publish publish-verify validate all

validate: ## validate all source registers
	$(PAB) validate

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

env: ## create/refresh the uv environment
	uv sync

lint: ## ruff check + format
	uv run ruff check . && uv run ruff format .

test: ## run tests
	uv run pytest -q

cache-eez: ## (re)download the EEZ source per config/sources/EEZ.yml and verify manifest
	$(PAB) cache EEZ

cache: ## (re)download one country's selected sources: make cache ISO3=FJI
	$(PAB) cache $(ISO3)

cache-all: ## (re)download all countries
	$(PAB) cache --all

process-eez: ## EEZ polygons (config/eez_polygons.csv) -> data/processed/EEZ/pacific_eez.parquet
	$(PAB) process EEZ

process: ## raw -> data/processed/<ISO3>/<iso3>_admin.parquet: make process ISO3=FJI
	$(PAB) process $(ISO3)

process-all: ## process every country in config/countries.yml
	$(PAB) process --all

combine: ## per-country tables -> data/combined/pacific_admin.parquet + pacific_admin_finest.parquet
	$(PAB) combine

stac: ## STAC items beside each parquet + data/catalog.json, data/collection.json (published hrefs), validated and checked
	$(PAB) stac --base-url $(HTTPS_BASE) --check

stac-local: ## same, with relative asset hrefs for local use
	$(PAB) stac --check

qa: ## per-country QA reports to reports/
	$(PAB) qa --all

assign-eez: ## (re)stamp eez_uid on all per-country tables (after process-eez)
	$(PAB) assign-eez --all

publish-dryrun: ## list every object `pab publish` would upload (reports/publish_dryrun.md)
	$(PAB) publish --dry-run

publish: ## upload data/processed, data/combined and the STAC root to S3 (needs AWS credentials)
	$(PAB) publish

publish-verify: ## read the published catalog over HTTPS, validate, HEAD every asset, read one parquet
	$(PAB) publish --verify

all: process-eez process-all assign-eez combine stac qa ## full local build
