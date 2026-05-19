"""Redis cache-key helpers and dry-run cache preparation.

Redis is only a cache/job-state layer in Phase 0. It is not a durable fact
source; document facts must live in structured exports or Postgres/Qdrant.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

DEFAULT_TTL_SECONDS = 3600


@dataclass(frozen=True)
class RedisCacheItem:
    key: str
    value: str
    ttl_seconds: int = DEFAULT_TTL_SECONDS


@dataclass(frozen=True)
class RedisCachePlan:
    items: list[RedisCacheItem]

    def dry_run(self, *, preview: int = 5) -> dict[str, Any]:
        return {
            "status": "dry_run",
            "target": "redis",
            "role": "cache_only",
            "item_count": len(self.items),
            "preview": [item.__dict__ for item in self.items[:preview]],
        }


def manifest_cache_key(doc_id: str) -> str:
    return f"vibration_agent:manifest:{doc_id}"


def prepare_manifest_cache(manifest: Mapping[str, Any], *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> RedisCachePlan:
    doc_id = str(manifest["doc_id"])
    item = RedisCacheItem(
        key=manifest_cache_key(doc_id),
        value=json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        ttl_seconds=ttl_seconds,
    )
    return RedisCachePlan(items=[item])


def dry_run_manifest_cache(manifest: Mapping[str, Any], *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict[str, Any]:
    return prepare_manifest_cache(manifest, ttl_seconds=ttl_seconds).dry_run()


def client(url: str):
    """Redis runtime access is deferred; target 10 only prepares cache items."""
    raise NotImplementedError("Redis runtime access is deferred; use prepare_manifest_cache(...).dry_run() for Target 10.")