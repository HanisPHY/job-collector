"""
Registry expansion via community-maintained GitHub new-grad job lists.

Answer to the "sustainable company-list growth" question: these lists are
curated by the target cohort itself, updated hourly/daily, and every row's
apply link ENCODES the company's ATS platform + slug. Each candidate is
still validated with one probe request before entering the registry, so a
stale listing cannot poison it.

Sources (raw markdown, 2 HTTP requests total per run):
  - speedyapply/2027-SWE-College-Jobs  NEW_GRAD_USA.md
  - vanshb03/New-Grad-2027             README.md (dev branch)

Run weekly (or add --expand to any ats_direct.py run).
"""

import re
import sys
import requests

if __package__ in (None, ""):
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ats_direct.registry import Registry
    from ats_direct.providers import PROVIDERS
    from ats_direct.rate_limiter import make_default_limiter
else:
    from .registry import Registry
    from .providers import PROVIDERS
    from .rate_limiter import make_default_limiter

import paths

SOURCES = [
    ("speedyapply/2027-SWE-College-Jobs",
     "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md"),
    ("vanshb03/New-Grad-2027",
     "https://raw.githubusercontent.com/vanshb03/New-Grad-2027/dev/README.md"),
]

# platform -> slug-capturing regex (kept local: ats_direct must not import
# from ddg_search - the two collection paths stay decoupled by design)
ATS_URL_PATTERNS = [
    ("greenhouse", re.compile(
        r"https?://(?:boards|job-boards)\.(?:eu\.)?greenhouse\.io/([a-z0-9]+)/jobs/\d+", re.I)),
    ("greenhouse", re.compile(   # embed variant: .../embed/job_app?for={slug}
        r"https?://boards\.(?:eu\.)?greenhouse\.io/embed/job_app\?[^\s\")]*for=([a-z0-9]+)", re.I)),
    ("lever", re.compile(
        r"https?://jobs\.(?:eu\.)?lever\.co/([a-zA-Z0-9-]+)/[a-f0-9-]{16,}", re.I)),
    ("ashby", re.compile(
        r"https?://jobs\.ashbyhq\.com/([a-zA-Z0-9-]+)/[a-f0-9-]{16,}", re.I)),
    ("smartrecruiters", re.compile(
        r"https?://jobs\.smartrecruiters\.com/([a-zA-Z0-9]+)/\d+", re.I)),
    ("workable", re.compile(
        r"https?://apply\.workable\.com/([a-z0-9-]+)/j/", re.I)),
]

# first markdown table cell -> display name ("| **[DoorDash](url)** | ..." -> DoorDash)
_MD_DECOR_RE = re.compile(r"\*\*|__|\[|\]\([^)]*\)|<[^>]+>")


def _row_company_name(line: str) -> str:
    cells = line.split("|")
    if len(cells) < 2:
        return ""
    name = _MD_DECOR_RE.sub("", cells[1]).strip()
    # sub-rows of a multi-posting company use ↳ / arrows; no usable name
    if not name or name in ("↳", "->", "→"):
        return ""
    return name[:60]


def expand(registry_path: str = str(paths.STATE_DIR / "ats_registry.json"),
           verbose: bool = True, validate: bool = True) -> dict:
    registry = Registry(registry_path)
    limiter = make_default_limiter()
    stats = {"sources_ok": 0, "urls_seen": 0, "unique_boards": 0,
             "validated_ok": 0, "validated_fail": 0, "added": 0}
    found = {}  # (platform, slug) -> {"count": n, "name": best display name}

    for src_name, url in SOURCES:
        try:
            r = requests.get(url, timeout=30,
                             headers={"User-Agent": "ng-job-collector"})
            r.raise_for_status()
        except requests.RequestException as e:
            if verbose:
                print(f"  [!] {src_name}: {e}")
            continue
        stats["sources_ok"] += 1
        for line in r.text.splitlines():
            for platform, pattern in ATS_URL_PATTERNS:
                for slug in pattern.findall(line):
                    slug = slug.lower()
                    stats["urls_seen"] += 1
                    rec = found.setdefault((platform, slug), {"count": 0, "name": ""})
                    rec["count"] += 1
                    if not rec["name"]:
                        rec["name"] = _row_company_name(line)

    stats["unique_boards"] = len(found)
    # most-listed boards first: they are the most active NG employers
    for (platform, slug), rec in sorted(found.items(), key=lambda kv: -kv[1]["count"]):
        display = rec["name"] or slug.replace("-", " ").title()
        if registry.has_slug(platform, slug) or registry.has_company(display):
            continue
        if validate:
            try:
                if not PROVIDERS[platform].probe(slug, limiter):
                    stats["validated_fail"] += 1
                    continue
            except Exception:
                stats["validated_fail"] += 1
                continue
            stats["validated_ok"] += 1
        if registry.add({"name": display, "platform": platform, "slug": slug,
                         "source": "github"}):
            stats["added"] += 1
            if verbose:
                print(f"  [+] {display} -> {platform}/{slug} "
                      f"({rec['count']} postings listed)")
            registry.save()  # incremental: an interrupt loses nothing
    registry.save()
    return stats


if __name__ == "__main__":
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("Expanding registry from community NG job lists...")
    s = expand()
    print(f"\nsources_ok={s['sources_ok']} urls_seen={s['urls_seen']} "
          f"unique_boards={s['unique_boards']} validated_ok={s['validated_ok']} "
          f"validated_fail={s['validated_fail']} added={s['added']}")
