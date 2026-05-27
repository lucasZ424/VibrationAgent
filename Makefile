.PHONY: install dev api worker cli ingest test test-fast test-full fmt bootstrap

install:
	pip install -e .
	pip install -r requirements-full.txt

bootstrap:
	python scripts/bootstrap_db.py

api:
	uvicorn apps.api.main:app --reload --port 8000

worker:
	python -m apps.worker.main

cli:
	python -m apps.cli.main

ingest:
	python scripts/ingest_folder.py --src data/raw

test: test-fast

test-fast:
	pytest -q -m "not integration"

test-full:
	pytest -q

fmt:
	ruff check --fix src apps scripts tests
