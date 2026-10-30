"""Token-bucket rate limiter, per (tool, agent, tenant) key."""

from __future__ import annotations

import time


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._tokens = capacity
        self._last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self._tokens = min(
            self.capacity, self._tokens + (now - self._last) * self.refill_per_second
        )
        self._last = now
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False


class RateLimiter:
    """One bucket per key; capacity defaults to the tool's per-minute limit."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def allow(self, key: str, per_minute: int) -> bool:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(float(per_minute), per_minute / 60.0)
            self._buckets[key] = bucket
        return bucket.allow()
