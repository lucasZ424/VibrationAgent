"""Background worker: consumes ingestion jobs (PDF parse, OCR, chunking, embedding)."""
from __future__ import annotations


def run() -> None:
    # TODO(S1): pull jobs from redis queue, dispatch to ingestion.pipeline
    raise NotImplementedError


if __name__ == "__main__":
    run()
