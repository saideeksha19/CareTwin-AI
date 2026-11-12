"""Rate limiting for abuse-sensitive endpoints.

Default implementation is an in-memory sliding window, which is correct for the
single-process demo/dev runtime. A shared-store adapter interface is provided so
production deployments can back the limiter with Redis or another shared store;
this repository does not claim distributed enforcement is live without tests
against a real shared store.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from app.errors import ApiError

MESSAGES = {
    "upload": "Too many document uploads from this account. Wait before uploading again.",
    "assistant": "Too many assistant questions from this account. Wait before asking again.",
    "auth": "Too many authentication attempts. Wait before retrying.",
    "ai": "Too many AI requests from this account. Wait before retrying.",
}


class RateLimitStore(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Record a hit and return (allowed, current_count)."""


class MemoryRateLimitStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            queue = self._hits.setdefault(key, deque())
            while queue and now - queue[0] > window_seconds:
                queue.popleft()
            if len(queue) >= limit:
                return False, len(queue)
            queue.append(now)
            return True, len(queue)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class SlidingWindowLimiter:
    """Limiter facade used by the API.

    `backend` is informational for readiness/monitoring. Only the in-memory store
    is implemented in-repo; `memory` is the safe default everywhere.
    """

    def __init__(self, backend: str = "memory", store: RateLimitStore | None = None) -> None:
        self.backend = (backend or "memory").strip().lower()
        self._store = store or MemoryRateLimitStore()

    def hit(
        self,
        bucket: str,
        identity: str | None,
        limit: int,
        *,
        window_seconds: int = 3600,
    ) -> None:
        """Count one request, raising 429 when the window budget is used up."""
        budget = max(1, int(limit))
        # Avoid storing medical details in keys: bucket + opaque identity only.
        key = f"{bucket}:{identity or 'anonymous'}"
        allowed, _count = self._store.hit(key, budget, int(window_seconds))
        if not allowed:
            raise ApiError(
                429,
                f"{bucket}_rate_limited",
                MESSAGES.get(bucket, "Too many requests. Wait before retrying."),
                {"limit": budget, "windowSeconds": int(window_seconds)},
            )

    def reset(self) -> None:
        reset = getattr(self._store, "reset", None)
        if callable(reset):
            reset()

    @property
    def is_shared_store(self) -> bool:
        return self.backend not in {"", "memory", "local"}
