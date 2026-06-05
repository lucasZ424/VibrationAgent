"""Small in-memory API rate limiter for local deployments."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_seconds: float = 60.0) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def clear(self) -> None:
        self._hits.clear()
