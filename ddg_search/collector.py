"""
DDG-search collection pipeline:
    query set -> DDG (heavily rate-limited) -> ATS link extraction
              -> NG title filter -> dedup -> CSV
    optional: feed newly-discovered company slugs into the ATS registry

Role: supplementary DISCOVERY source. The per-run query cap means the direct
yield is small by design; its main value is surfacing companies/boards the
registry doesn't know yet, which ats_direct then covers in full.
"""

import os
import sys
import csv
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from job_collector.utils import generate_job_id
from job_collector.database.company_db import CompanyDatabase
from ats_direct.ng_filter import classify_title

from .ddg_client import DDGClient, DDGRateLimited
from .link_parser import parse_result

FIELDNAMES = ["unique_id", "job_title", "job_link", "company_name",
              "sponsorship_status", "company_type", "date_posted",
              "date_recorded", "category", "applied", "source", "platform",
              "location"]

# Query set: rotated round-robin across runs (cursor persisted in state file)
# so successive scheduled runs cover different platform x keyword slices
# while staying inside the per-run query cap.
QUERY_SET = [
    'site:boards.greenhouse.io "new grad" software engineer',
    'site:jobs.lever.co "new grad" software engineer',
    'site:jobs.ashbyhq.com "new grad" software engineer',
    'site:boards.greenhouse.io software engineer "university graduate"',
    'site:jobs.lever.co software engineer 2027',
    'site:jobs.ashbyhq.com software engineer "early career"',
    'site:jobs.smartrecruiters.com "new grad" software engineer',
    'site:boards.greenhouse.io "software engineer, new grad"',
    'site:apply.workable.com "new grad" software engineer',
    'site:jobs.lever.co "software engineer" "entry level"',
    'site:job-boards.greenhouse.io "new grad" software engineer',
    'site:jobs.ashbyhq.com "software engineer" 2027',
]

STATE_FILE = "ddg_state.json"


def _load_state(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cursor": 0}


def _save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def _load_existing(output_file):
    ids, rows = set(), []
    if os.path.exists(output_file):
        with open(output_file, "r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("unique_id"):
                    ids.add(row["unique_id"])
                    rows.append(row)
    return ids, rows


def _atomic_write(rows, output_file):
    tmp = output_file + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, output_file)


def collect(output_file: str = "ddg_jobs.csv",
            queries_per_run: int = 5,
            strict: bool = True,
            update_registry: bool = False,
            state_file: str = STATE_FILE):
    state = _load_state(state_file)
    cursor = state.get("cursor", 0)
    queries = [QUERY_SET[(cursor + i) % len(QUERY_SET)]
               for i in range(min(queries_per_run, len(QUERY_SET)))]

    client = DDGClient()
    company_db = CompanyDatabase()
    existing_ids, existing_rows = _load_existing(output_file)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    stats = {"queries_attempted": 0, "queries_ok": 0, "results_total": 0,
             "ats_links": 0, "ng_matched": 0, "jobs_new": 0,
             "challenges": 0, "new_companies": 0}
    new_rows, discovered = [], {}

    for q in queries:
        stats["queries_attempted"] += 1
        print(f"  query: {q}")
        try:
            results = client.search(q)
        except DDGRateLimited as e:
            print(f"    [!] giving up on this run: {e}")
            break
        except RuntimeError as e:
            print(f"    [!] {e}")
            break
        stats["queries_ok"] += 1
        stats["results_total"] += len(results)

        for url, serp_title in results:
            lead = parse_result(url, serp_title)
            if lead is None:
                continue
            stats["ats_links"] += 1
            discovered.setdefault((lead.platform, lead.company_slug), 0)
            discovered[(lead.platform, lead.company_slug)] += 1

            keep, _ = classify_title(lead.title, strict=strict)
            if not keep:
                continue
            stats["ng_matched"] += 1
            uid = generate_job_id(lead.url)
            if uid in existing_ids:
                continue
            existing_ids.add(uid)
            company = lead.company_slug.replace("-", " ").title()
            ctype = ("独角兽/上市公司/Big Tech"
                     if company_db.is_big_tech_or_public(company) else "Others")
            spon = "Not (Maybe Not) Sponsor"  # no description available via SERP
            new_rows.append({
                "unique_id": uid, "job_title": lead.title, "job_link": lead.url,
                "company_name": company, "sponsorship_status": spon,
                "company_type": ctype, "date_posted": "", "date_recorded": now,
                "category": f"{spon} & {ctype}", "applied": "",
                "source": "ddg_search", "platform": lead.platform, "location": "",
            })

    stats["challenges"] = client.challenges_seen
    stats["jobs_new"] = len(new_rows)

    if new_rows:
        _atomic_write(new_rows + existing_rows, output_file)

    # feed discovered boards into the ATS registry (data-file coupling only)
    if update_registry and discovered:
        from ats_direct.registry import Registry
        registry = Registry()
        for (platform, slug) in discovered:
            if platform == "workday":  # needs tenant/site details, skip
                continue
            if registry.add({"name": slug.replace("-", " ").title(),
                             "platform": platform, "slug": slug,
                             "source": "ddg"}):
                stats["new_companies"] += 1
        registry.save()

    state["cursor"] = (cursor + stats["queries_attempted"]) % len(QUERY_SET)
    _save_state(state_file, state)
    return stats
