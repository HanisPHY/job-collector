"""
Company registry: maps company names to their ATS platform + slug.

Stored in ats_registry.json. Entries come from five sources:
  seed   - shipped with the repo (pre-verified where possible)
  probe  - auto-detected by trying each platform with slug candidates
  github - harvested from community NG job lists (expand_registry.py)
  ddg    - discovered by the ddg_search collector (--update-registry)
  manual - added by the user via --add-company
"""

import os
import re
import json
from datetime import datetime, timedelta
from typing import List, Optional

from .providers import PROVIDERS, PROBE_ORDER

REGISTRY_FILE = "ats_registry.json"

# Probe negatives are cached to avoid re-hammering the same misses, but only
# for a while: boards appear/disappear, and a transient outage must not
# blacklist a company forever. Exceptions are never cached (only real "no").
FAILED_PROBE_TTL_DAYS = 30

# Platform-qualified slug aliases for companies whose board slug does not
# derive from their name. Keyed by normalized (lowercased) company name.
# Each alias costs exactly one probe request and is validated before caching,
# so a stale alias cannot poison the registry.
KNOWN_ALIASES = {
    "doordash": [("greenhouse", "doordashusa")],
    "anduril": [("greenhouse", "andurilindustries")],
    "cruise": [("greenhouse", "getcruise")],
    "zipline": [("greenhouse", "flyzipline")],
    "mistral ai": [("lever", "mistral")],
    "kraken": [("lever", "kraken.com")],
    "scale ai": [("greenhouse", "scaleai")],
    "epic games": [("greenhouse", "epicgames")],
    "riot games": [("greenhouse", "riotgames")],
    "jane street": [("greenhouse", "janestreet")],
    "two sigma": [("greenhouse", "twosigma")],
    "de shaw": [("greenhouse", "deshaw")],
    "hudson river trading": [("greenhouse", "wehrtyou")],
}


def _norm_name(company_name: str) -> str:
    return re.sub(r"\s+", " ", company_name.lower().strip())


def slug_candidates(company_name: str) -> List[str]:
    """Generate likely ATS slugs from a company name."""
    name = _norm_name(company_name)
    # drop corporate suffixes
    name = re.sub(r"\b(inc|llc|corp|corporation|ltd|limited|co|technologies|labs)\.?$",
                  "", name).strip()
    joined = re.sub(r"[^a-z0-9]", "", name)          # "Scale AI" -> "scaleai"
    dashed = re.sub(r"[^a-z0-9]+", "-", name).strip("-")  # -> "scale-ai"
    cands = []
    for c in (joined, dashed):
        if c and c not in cands:
            cands.append(c)
    return cands


class Registry:
    def __init__(self, path: str = REGISTRY_FILE):
        self.path = path
        self.companies: List[dict] = []
        self.failed_probes: dict = {}   # {name: {probe_key: "YYYY-MM-DD"}}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.companies = data.get("companies", [])
            raw_failed = data.get("failed_probes", {})
            # migrate legacy list format {name: [key, ...]} -> dated dict
            today = datetime.now().strftime("%Y-%m-%d")
            self.failed_probes = {
                name: (v if isinstance(v, dict) else {k: today for k in v})
                for name, v in raw_failed.items()
            }
            self._expire_failed_probes()

    def _expire_failed_probes(self):
        cutoff = (datetime.now() - timedelta(days=FAILED_PROBE_TTL_DAYS)
                  ).strftime("%Y-%m-%d")
        for name in list(self.failed_probes):
            kept = {k: d for k, d in self.failed_probes[name].items() if d >= cutoff}
            if kept:
                self.failed_probes[name] = kept
            else:
                del self.failed_probes[name]

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"companies": self.companies,
                       "failed_probes": self.failed_probes,
                       "last_updated": datetime.now().isoformat()},
                      f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def resolved(self) -> List[dict]:
        return [c for c in self.companies if c.get("platform")]

    def has_company(self, name: str) -> bool:
        low = _norm_name(name)
        return any(_norm_name(c["name"]) == low for c in self.companies)

    def has_slug(self, platform: str, slug: str) -> bool:
        return any(c.get("platform") == platform and c.get("slug") == slug
                   for c in self.companies)

    def add(self, entry: dict) -> bool:
        """Add a resolved entry if not already present. Returns True if added."""
        if entry.get("slug") and self.has_slug(entry.get("platform", ""), entry["slug"]):
            return False
        if self.has_company(entry.get("name", "")):
            return False
        entry.setdefault("added", datetime.now().strftime("%Y-%m-%d"))
        self.companies.append(entry)
        return True

    def remove(self, name: str) -> bool:
        low = _norm_name(name)
        before = len(self.companies)
        self.companies = [c for c in self.companies if _norm_name(c["name"]) != low]
        # forget cached negatives so the company gets a fresh probe
        self.failed_probes.pop(name, None)
        return len(self.companies) < before

    def _probe_one(self, name: str, pkey: str, slug: str, limiter) -> Optional[dict]:
        """One platform x slug attempt; caches genuine negatives only."""
        probe_key = f"{pkey}:{slug}"
        if probe_key in self.failed_probes.get(name, {}):
            return None
        try:
            hit = PROVIDERS[pkey].probe(slug, limiter)
        except Exception:
            return None  # transient failure: never cached as a negative
        if hit:
            return {"name": name, "platform": pkey, "slug": slug, "source": "probe"}
        self.failed_probes.setdefault(name, {})[probe_key] = \
            datetime.now().strftime("%Y-%m-%d")
        return None

    def probe_company(self, name: str, limiter, verbose: bool = True) -> Optional[dict]:
        """Aliases first (platform-qualified), then generated slug candidates."""
        attempts = [(pkey, slug) for pkey, slug in
                    KNOWN_ALIASES.get(_norm_name(name), [])]
        for slug in slug_candidates(name):
            attempts += [(pkey, slug) for pkey in PROBE_ORDER]

        for pkey, slug in attempts:
            entry = self._probe_one(name, pkey, slug, limiter)
            if entry:
                if self.add(entry) and verbose:
                    print(f"  [+] {name} -> {pkey}/{slug}")
                return entry
        if verbose:
            print(f"  [-] {name}: no platform found ({len(attempts)} attempts)")
        return None

    def cleanup(self, limiter, verbose: bool = True) -> dict:
        """Re-validate every resolved entry (1 request each); drop the ones
        whose board no longer passes the >=1-posting probe, then re-probe
        those names from scratch (aliases included)."""
        stats = {"checked": 0, "dropped": 0, "recovered": 0}
        stale_names = []
        for entry in list(self.resolved()):
            pkey = entry["platform"]
            if pkey not in PROVIDERS or pkey == "workday":
                continue  # workday entries are hand-configured; trust them
            stats["checked"] += 1
            try:
                ok = PROVIDERS[pkey].probe(entry["slug"], limiter)
            except Exception:
                continue  # transient: keep the entry
            if not ok:
                if verbose:
                    print(f"  [x] dropping {entry['name']} "
                          f"({pkey}/{entry['slug']}: empty or gone)")
                self.remove(entry["name"])
                stale_names.append(entry["name"])
                stats["dropped"] += 1
        for name in stale_names:
            if self.probe_company(name, limiter, verbose=verbose):
                stats["recovered"] += 1
            self.save()
        self.save()
        return stats
