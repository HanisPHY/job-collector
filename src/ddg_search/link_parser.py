"""
Turn DDG search results into structured job leads.

Recognizes job-posting URLs on the directly-scrapable ATS platforms and
extracts (platform, company_slug, job_url). Anything else is dropped.
"""

import re
from dataclasses import dataclass
from typing import Optional

# platform -> (url pattern, slug group index)
# NOTE: greenhouse serves boards on both boards.greenhouse.io and
# job-boards.greenhouse.io; both carry /{slug}/jobs/{id}
_PATTERNS = [
    ("greenhouse",
     re.compile(r"https?://(?:boards|job-boards)\.(?:greenhouse\.io|eu\.greenhouse\.io)"
                r"/([a-z0-9-]+)/jobs/(\d+)", re.I)),
    ("lever",
     re.compile(r"https?://jobs\.(?:eu\.)?lever\.co/([a-z0-9-]+)/([a-f0-9-]{16,})", re.I)),
    ("ashby",
     re.compile(r"https?://jobs\.ashbyhq\.com/([a-zA-Z0-9-]+)/([a-f0-9-]{16,})", re.I)),
    ("smartrecruiters",
     re.compile(r"https?://jobs\.smartrecruiters\.com/([a-zA-Z0-9-]+)/(\d+)", re.I)),
    ("workable",
     re.compile(r"https?://apply\.workable\.com/([a-z0-9-]+)/j/([A-Z0-9]+)", re.I)),
    ("jazzhr",
     re.compile(r"https?://([a-z0-9-]+)\.applytojob\.com/apply/([A-Za-z0-9]+)", re.I)),
    ("bamboohr",
     re.compile(r"https?://([a-z0-9-]+)\.bamboohr\.com/careers/(\d+)", re.I)),
    ("workday",
     re.compile(r"https?://([a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com/[^\s\"]+/job/", re.I)),
]

# SERP titles look like "Job Title - Company" / "Job Title | Company Careers".
# Splitting blindly on " - " would truncate titles like
# "Systems Software Engineer - New College Grad 2026", destroying the NG
# signal, so only segments that look like the company/site name are dropped.
_TITLE_SEP_RE = re.compile(r"\s+[-|–—]\s+|\s+at\s+", re.I)
_SITE_WORDS = ("careers", "jobs", "job board", "hiring", "greenhouse", "lever",
               "ashby", "workable", "smartrecruiters", "workday", "bamboohr")


def _clean_title(serp_title: str, company_slug: str) -> str:
    if not serp_title:
        return ""
    parts = [p.strip() for p in _TITLE_SEP_RE.split(serp_title) if p.strip()]
    if len(parts) <= 1:
        return serp_title.strip()
    company_words = set(company_slug.replace("-", " ").split())
    kept = list(parts)
    # drop trailing segments that are just the company name / site boilerplate
    while len(kept) > 1:
        low = kept[-1].lower()
        seg_words = set(low.split())
        if (seg_words <= company_words or company_words <= seg_words or
                any(w in low for w in _SITE_WORDS)):
            kept.pop()
        else:
            break
    return " - ".join(kept)


@dataclass
class JobLead:
    platform: str
    company_slug: str
    url: str
    title: str


def parse_result(url: str, serp_title: str) -> Optional[JobLead]:
    for platform, pattern in _PATTERNS:
        m = pattern.search(url)
        if m:
            slug = m.group(1).lower()
            return JobLead(platform=platform,
                           company_slug=slug,
                           url=url.split("?")[0],
                           title=_clean_title(serp_title, slug))
    return None
