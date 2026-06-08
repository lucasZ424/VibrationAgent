.PHONY: install dev api worker cli ingest test test-fast test-contract test-full test-large test-nightly fmt bootstrap

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

test-contract:
	pytest tests/integration/test_phase2_end_to_end.py -q -m "not large_corpus"

test-full:
	pytest tests -q -m "not large_corpus"

test-large:
	pytest tests/integration/test_large_corpus.py -q -m large_corpus

test-nightly:
	pytest tests -q
	python scripts/bench_large_corpus.py tests/fixtures/raw/small_vibration_native.pdf --workspace data/tmp/make-nightly-large-corpus --output data/exports/nightly_large_corpus_baseline.json --max-pages 1 --top-k 2

fmt:
	ruff check --fix src apps scripts tests
