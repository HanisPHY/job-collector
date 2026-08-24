"""
Token-bucket rate limiter with per-domain buckets.

QPS values are set per platform based on the research documented in
RATE_LIMITS.md (official docs where available, empirical testing otherwise).
"""

import time
import random
import threading


class TokenBucket:
    """Simple blocking token bucket: acquire() sleeps until a token is free."""

    def __init__(self, rate: float, capacity: float = None):
        """
        Args:
            rate: tokens added per second (i.e. sustained QPS)
            capacity: max burst size (default: 1 token -> no bursting)
        """
        self.rate = rate
        self.capacity = capacity if capacity is not None else 1.0
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self):
        """Block until a token is available, then consume it."""
        while True:
            with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity,
                                  self.tokens + (now - self.last_refill) * self.rate)
                self.last_refill = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            # Small jitter so scheduled runs don't produce metronome-regular traffic
            time.sleep(wait + random.uniform(0, 0.25))


class DomainRateLimiter:
    """Holds one TokenBucket per API domain, created lazily from a QPS map."""

    def __init__(self, qps_map: dict, default_qps: float = 0.5):
        """
        Args:
            qps_map: {domain_key: qps} e.g. {"greenhouse": 1.0, "lever": 1.0}
            default_qps: rate for domains not present in the map
        """
        self.qps_map = qps_map
        self.default_qps = default_qps
        self._buckets = {}
        self._lock = threading.Lock()

    def acquire(self, domain_key: str):
        with self._lock:
            bucket = self._buckets.get(domain_key)
            if bucket is None:
                qps = self.qps_map.get(domain_key, self.default_qps)
                bucket = TokenBucket(rate=qps)
                self._buckets[domain_key] = bucket
        bucket.acquire()


# Platform QPS budget - justification in RATE_LIMITS.md.
# All values are deliberately far below the documented/observed ceilings.
PLATFORM_QPS = {
    "greenhouse": 1.0,       # documented 50 req/10s (5 QPS) -> use 1/5 of it
    "lever": 1.0,            # documented 10 req/s steady    -> use 1/10 of it
    "ashby": 0.5,            # undocumented public API       -> conservative
    "smartrecruiters": 1.0,  # public anonymous API          -> conservative
    "workable": 0.5,         # undocumented widget API       -> conservative
    "workday": 0.4,          # unofficial per-tenant CxS API -> most conservative
    "jazzhr": 0.5,           # plain HTML page fetch
    "bamboohr": 0.5,         # plain JSON page fetch
    "jobvite": 0.5,          # plain HTML page fetch
}


def make_default_limiter() -> DomainRateLimiter:
    return DomainRateLimiter(PLATFORM_QPS, default_qps=0.4)
