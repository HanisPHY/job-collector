"""
Minimal DuckDuckGo HTML-endpoint client (stdlib-adjacent: requests only).

Why not the `ddgs` library: it is a scraper around these same HTML endpoints,
carries a long history of RateLimitException issues, and hides the request
timing from us. Owning the single GET per query lets the rate budget in
RATE_LIMITS.md be enforced exactly.

Empirical basis for the timing constants (measured 2026-08-19 from a
residential IP, documented in RATE_LIMITS.md):
    - 2 queries 4s apart  -> second one answered HTTP 202 (JS challenge)
    - community reports:  sustained scraping needs >=15-30s gaps
Design: >=20s between queries + jitter, exponential backoff on 202/403,
hard cap on queries per run.
"""

import re
import time
import random
import requests
from html import unescape
from urllib.parse import unquote, quote_plus

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

MIN_INTERVAL_S = 20          # floor between any two queries
JITTER_S = 8                 # + uniform(0, JITTER_S)
BACKOFF_S = [60, 150]        # waits after 1st and 2nd challenge; then give up
MAX_QUERIES_PER_RUN = 10     # hard cap - stay far under the abuse radar

# organic result anchors on html.duckduckgo.com; ads route via duckduckgo.com/y.js
_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_UDDG_RE = re.compile(r"[?&]uddg=([^&]+)")


class DDGRateLimited(Exception):
    """Raised when DDG keeps answering with challenges after all backoffs."""


class DDGClient:
    def __init__(self):
        self._last_query_at = 0.0
        self.queries_sent = 0
        self.challenges_seen = 0

    def _wait_slot(self):
        gap = MIN_INTERVAL_S + random.uniform(0, JITTER_S)
        elapsed = time.monotonic() - self._last_query_at
        if elapsed < gap:
            time.sleep(gap - elapsed)

    def search(self, query: str):
        """
        Run one query; returns list of (url, title) organic results.
        Raises DDGRateLimited if the challenge persists through all backoffs,
        RuntimeError if the per-run query cap is reached.
        """
        if self.queries_sent >= MAX_QUERIES_PER_RUN:
            raise RuntimeError(f"query cap reached ({MAX_QUERIES_PER_RUN}/run)")

        attempt = 0
        while True:
            self._wait_slot()
            self._last_query_at = time.monotonic()
            self.queries_sent += 1
            r = requests.get(
                f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
                timeout=25,
                headers={"User-Agent": USER_AGENT,
                         "Accept": "text/html,application/xhtml+xml",
                         "Accept-Language": "en-US,en;q=0.9"})
            if r.status_code == 200 and "result__a" in r.text:
                return self._parse(r.text)
            # 202 = JS challenge, 403 = block; both mean "slow down"
            self.challenges_seen += 1
            if attempt >= len(BACKOFF_S):
                raise DDGRateLimited(
                    f"still challenged after {attempt} backoffs (HTTP {r.status_code})")
            wait = BACKOFF_S[attempt] + random.uniform(0, 15)
            print(f"    [rate-limited: HTTP {r.status_code}] backing off {wait:.0f}s...")
            time.sleep(wait)
            attempt += 1

    @staticmethod
    def _parse(html: str):
        results = []
        for href, title_html in _RESULT_RE.findall(html):
            title = unescape(_TAG_RE.sub("", title_html)).strip()
            m = _UDDG_RE.search(href)
            url = unquote(m.group(1)) if m else href
            # drop ad redirects and DDG-internal links
            if "duckduckgo.com" in url:
                continue
            results.append((url, title))
        return results
