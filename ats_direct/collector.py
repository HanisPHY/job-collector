"""
ATS-direct collection pipeline:
    registry -> per-company fetch (rate-limited) -> NG title filter
             -> description fetch for matched jobs (where needed)
             -> sponsorship + company-type classification -> dedup -> CSV
"""

import os
import sys
import csv
import time
from datetime import datetime
from typing import List

# reuse the existing package's classifiers and ID logic (read-only imports)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from job_collector.classifiers.sponsorship import SponsorshipClassifier
from job_collector.database.company_db import CompanyDatabase
from job_collector.utils import generate_job_id

from .providers import PROVIDERS, RawJob
from .registry import Registry
from .ng_filter import classify_title
from .us_filter import is_probably_us
from .rate_limiter import make_default_limiter

FIELDNAMES = ["unique_id", "job_title", "job_link", "company_name",
              "sponsorship_status", "company_type", "date_posted",
              "date_recorded", "category", "applied", "source", "platform",
              "location"]


class RunStats:
    """Quantified per-run metrics used by the test criteria."""

    def __init__(self):
        self.companies_attempted = 0
        self.companies_ok = 0
        self.companies_zero_jobs = 0
        self.http_errors = 0
        self.rate_limit_hits = 0        # 429 or challenge responses
        self.jobs_fetched = 0
        self.jobs_matched = 0
        self.jobs_dropped_non_us = 0
        self.jobs_new = 0
        self.started = time.time()

    def summary(self) -> dict:
        return {
            "companies_attempted": self.companies_attempted,
            "companies_ok": self.companies_ok,
            "companies_zero_jobs": self.companies_zero_jobs,
            "http_errors": self.http_errors,
            "rate_limit_hits": self.rate_limit_hits,
            "jobs_fetched": self.jobs_fetched,
            "jobs_matched": self.jobs_matched,
            "jobs_dropped_non_us": self.jobs_dropped_non_us,
            "jobs_new": self.jobs_new,
            "elapsed_s": round(time.time() - self.started, 1),
        }


def _load_existing_ids(output_file: str):
    ids, rows = set(), []
    if os.path.exists(output_file):
        with open(output_file, "r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("unique_id"):
                    ids.add(row["unique_id"])
                    rows.append(row)
    return ids, rows


def _atomic_write(rows: List[dict], output_file: str):
    tmp = output_file + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, output_file)


def collect(registry_path: str = "ats_registry.json",
            output_file: str = "ats_jobs.csv",
            strict: bool = True,
            us_only: bool = True,
            max_companies: int = None,
            verbose: bool = True) -> RunStats:
    registry = Registry(registry_path)
    limiter = make_default_limiter()
    stats = RunStats()
    sponsorship = SponsorshipClassifier()
    company_db = CompanyDatabase()

    companies = registry.resolved()
    if max_companies:
        companies = companies[:max_companies]

    existing_ids, existing_rows = _load_existing_ids(output_file)
    new_rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for entry in companies:
        stats.companies_attempted += 1
        provider = PROVIDERS.get(entry["platform"])
        if provider is None:
            continue
        try:
            jobs = provider.fetch_jobs(entry, limiter)
            stats.companies_ok += 1
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429:
                stats.rate_limit_hits += 1
            stats.http_errors += 1
            if verbose:
                print(f"  [!] {entry['name']} ({entry['platform']}): {e}")
            continue

        if not jobs:
            # a "successful" empty fetch usually means a wrong slug or a
            # migrated board - surfaced here so it can't hide again
            stats.companies_zero_jobs += 1
        stats.jobs_fetched += len(jobs)
        matched = []
        for job in jobs:
            keep, _ = classify_title(job.title, strict=strict)
            if keep and us_only and not is_probably_us(job.location):
                stats.jobs_dropped_non_us += 1
                keep = False
            if keep:
                matched.append(job)
        stats.jobs_matched += len(matched)
        if verbose:
            print(f"  {entry['name']:<24} [{entry['platform']}] "
                  f"{len(jobs):>4} jobs -> {len(matched)} NG SDE")

        for job in matched:
            uid = generate_job_id(job.url)
            if uid in existing_ids:
                continue
            existing_ids.add(uid)

            # fetch description only for matched jobs on platforms whose
            # list endpoint doesn't include one (keeps request count minimal)
            if not job.description and job.detail_ref and hasattr(provider, "fetch_detail"):
                try:
                    job.description = provider.fetch_detail(job, limiter)
                except Exception:
                    pass

            spon = sponsorship.classify(job.description)
            ctype = ("独角兽/上市公司/Big Tech"
                     if company_db.is_big_tech_or_public(job.company) else "Others")
            new_rows.append({
                "unique_id": uid,
                "job_title": job.title,
                "job_link": job.url,
                "company_name": job.company,
                "sponsorship_status": spon,
                "company_type": ctype,
                "date_posted": job.posted_at,
                "date_recorded": now,
                "category": f"{spon} & {ctype}",
                "applied": "",
                "source": "ats_direct",
                "platform": job.platform,
                "location": job.location,
            })

    stats.jobs_new = len(new_rows)
    if new_rows:
        _atomic_write(new_rows + existing_rows, output_file)
    registry.save()  # persist any failed_probes bookkeeping
    return stats
