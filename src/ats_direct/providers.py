"""
Per-platform ATS clients.

Every provider implements:
    probe(slug)        -> bool          (does this company exist on this platform?)
    fetch_jobs(entry)  -> list[RawJob]  (all public postings for the company)

All endpoints below were empirically verified on 2026-08-19 (see
VERIFIED_ATS_PLATFORMS.md for the full verification log).
"""

import re
import html as html_mod
import requests
from dataclasses import dataclass, field
from typing import List, Optional

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 20


@dataclass
class RawJob:
    title: str
    url: str
    company: str
    platform: str
    location: str = ""
    posted_at: str = ""
    description: str = ""
    # some platforms need an extra request to get the description
    detail_ref: Optional[dict] = field(default=None)


def _get(url, limiter, domain_key, **kwargs):
    limiter.acquire(domain_key)
    return requests.get(url, timeout=TIMEOUT,
                        headers={"User-Agent": USER_AGENT,
                                 "Accept": "application/json"}, **kwargs)


def _post(url, limiter, domain_key, json_body):
    limiter.acquire(domain_key)
    return requests.post(url, timeout=TIMEOUT, json=json_body,
                         headers={"User-Agent": USER_AGENT,
                                  "Accept": "application/json",
                                  "Content-Type": "application/json"})


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = html_mod.unescape(text)
    return re.sub(r"<[^>]+>", " ", text)


# ---------------------------------------------------------------- Greenhouse

class GreenhouseProvider:
    """boards-api.greenhouse.io/v1/boards/{slug}/jobs  (public JSON, no auth)"""
    key = "greenhouse"

    def probe(self, slug, limiter):
        r = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                 limiter, self.key)
        if r.status_code != 200:
            return False
        try:
            # require >=1 posting: a valid-shaped but empty response is
            # indistinguishable from a wrong slug (see RATE_LIMITS.md notes)
            return len(r.json().get("jobs", [])) > 0
        except Exception:
            return False

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        # content=true returns full descriptions in the SAME single request
        r = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
                 limiter, self.key)
        r.raise_for_status()
        jobs = []
        for j in r.json().get("jobs", []):
            jobs.append(RawJob(
                title=j.get("title", ""),
                url=j.get("absolute_url", ""),
                company=entry["name"],
                platform=self.key,
                location=(j.get("location") or {}).get("name", ""),
                posted_at=(j.get("updated_at") or "")[:10],
                description=_strip_html(j.get("content", ""))[:5000],
            ))
        return jobs


# --------------------------------------------------------------------- Lever

class LeverProvider:
    """api.lever.co/v0/postings/{slug}?mode=json  (public JSON, no auth)"""
    key = "lever"

    def probe(self, slug, limiter):
        r = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
                 limiter, self.key)
        if r.status_code != 200:
            return False
        try:
            return len(r.json()) > 0
        except Exception:
            return False

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        r = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json",
                 limiter, self.key)
        r.raise_for_status()
        jobs = []
        for j in r.json():
            cat = j.get("categories") or {}
            jobs.append(RawJob(
                title=j.get("text", ""),
                url=j.get("hostedUrl", ""),
                company=entry["name"],
                platform=self.key,
                location=cat.get("location", "") or "",
                posted_at="",
                description=(j.get("descriptionPlain") or "")[:5000],
            ))
        return jobs


# --------------------------------------------------------------------- Ashby

class AshbyProvider:
    """api.ashbyhq.com/posting-api/job-board/{slug}  (documented public API)"""
    key = "ashby"

    def probe(self, slug, limiter):
        r = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                 limiter, self.key)
        if r.status_code != 200:
            return False
        try:
            jobs = r.json().get("jobs")
            return isinstance(jobs, list) and len(jobs) > 0
        except Exception:
            return False

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        r = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                 limiter, self.key)
        r.raise_for_status()
        jobs = []
        for j in r.json().get("jobs", []):
            url = (j.get("jobUrl") or j.get("applyUrl")
                   or f"https://jobs.ashbyhq.com/{slug}/{j.get('id', '')}")
            jobs.append(RawJob(
                title=j.get("title", ""),
                url=url,
                company=entry["name"],
                platform=self.key,
                location=j.get("location", "") or "",
                posted_at=(j.get("publishedAt") or "")[:10],
                description=_strip_html(j.get("descriptionHtml", ""))[:5000],
            ))
        return jobs


# ----------------------------------------------------------- SmartRecruiters

class SmartRecruitersProvider:
    """api.smartrecruiters.com/v1/companies/{slug}/postings (public JSON)

    List response has no description; matched jobs get a detail request.
    """
    key = "smartrecruiters"

    def probe(self, slug, limiter):
        r = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
                 limiter, self.key)
        if r.status_code != 200:
            return False
        try:
            # SR answers 200 + totalFound:0 for ANY slug - requiring >0
            # is the only way to distinguish a real board (verified 2026-08-19)
            return r.json().get("totalFound", 0) > 0
        except Exception:
            return False

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        jobs, offset = [], 0
        while True:
            r = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
                     f"?limit=100&offset={offset}", limiter, self.key)
            r.raise_for_status()
            data = r.json()
            content = data.get("content", [])
            for j in content:
                loc = j.get("location") or {}
                loc_str = ", ".join(x for x in [loc.get("city"), loc.get("region"),
                                                loc.get("country")] if x)
                uuid = j.get("uuid", "")
                jobs.append(RawJob(
                    title=j.get("name", ""),
                    url=j.get("ref", "") or
                        f"https://jobs.smartrecruiters.com/{slug}/{uuid}",
                    company=entry["name"],
                    platform=self.key,
                    location=loc_str,
                    posted_at=(j.get("releasedDate") or "")[:10],
                    detail_ref={"slug": slug, "uuid": uuid},
                ))
            offset += len(content)
            if offset >= data.get("totalFound", 0) or not content:
                break
        return jobs

    def fetch_detail(self, job: RawJob, limiter) -> str:
        ref = job.detail_ref or {}
        r = _get(f"https://api.smartrecruiters.com/v1/companies/{ref['slug']}"
                 f"/postings/{ref['uuid']}", limiter, self.key)
        if r.status_code != 200:
            return ""
        sections = ((r.json().get("jobAd") or {}).get("sections") or {})
        parts = [(sections.get(k) or {}).get("text", "")
                 for k in ("jobDescription", "qualifications", "additionalInformation")]
        return _strip_html(" ".join(parts))[:5000]


# ------------------------------------------------------------------ Workable

class WorkableProvider:
    """apply.workable.com/api/v1/widget/accounts/{slug}?details=true (public JSON)"""
    key = "workable"

    def probe(self, slug, limiter):
        r = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
                 limiter, self.key)
        if r.status_code != 200:
            return False
        try:
            return len(r.json().get("jobs", [])) > 0
        except Exception:
            return False

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        r = _get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true",
                 limiter, self.key)
        r.raise_for_status()
        jobs = []
        for j in r.json().get("jobs", []):
            jobs.append(RawJob(
                title=j.get("title", ""),
                url=j.get("url", "") or j.get("application_url", ""),
                company=entry["name"],
                platform=self.key,
                location=", ".join(x for x in [j.get("city"), j.get("country")] if x),
                posted_at=(j.get("published_on") or "")[:10],
                description=_strip_html(j.get("description", ""))[:5000],
            ))
        return jobs


# ------------------------------------------------------------------- Workday

class WorkdayProvider:
    """{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs (POST JSON)

    Unofficial but stable CxS API. Auto-probe is impractical (tenant + wd
    number + site name all vary), so registry entries must carry:
        {"platform": "workday", "host": "nvidia.wd5.myworkdayjobs.com",
         "tenant": "nvidia", "site": "NVIDIAExternalCareerSite"}
    """
    key = "workday"
    SEARCH_TERMS = ["software engineer"]
    MAX_PAGES = 5  # 5 x 20 = up to 100 postings per search term

    def probe(self, slug, limiter):
        return False  # never auto-probed; explicit registry entries only

    def fetch_jobs(self, entry, limiter):
        host, tenant, site = entry["host"], entry["tenant"], entry["site"]
        base = f"https://{host}/wday/cxs/{tenant}/{site}"
        jobs, seen = [], set()
        for term in self.SEARCH_TERMS:
            for page in range(self.MAX_PAGES):
                r = _post(f"{base}/jobs", limiter, self.key,
                          {"limit": 20, "offset": page * 20,
                           "searchText": term, "appliedFacets": {}})
                if r.status_code != 200:
                    break
                data = r.json()
                postings = data.get("jobPostings", [])
                for j in postings:
                    path = j.get("externalPath", "")
                    if not path or path in seen:
                        continue
                    seen.add(path)
                    jobs.append(RawJob(
                        title=j.get("title", ""),
                        url=f"https://{host}/en-US/{site}{path}",
                        company=entry["name"],
                        platform=self.key,
                        location=j.get("locationsText", "") or "",
                        posted_at="",
                        detail_ref={"base": base, "path": path},
                    ))
                if (page + 1) * 20 >= data.get("total", 0) or not postings:
                    break
        return jobs

    def fetch_detail(self, job: RawJob, limiter) -> str:
        ref = job.detail_ref or {}
        limiter.acquire(self.key)
        r = requests.get(f"{ref['base']}{ref['path']}", timeout=TIMEOUT,
                         headers={"User-Agent": USER_AGENT,
                                  "Accept": "application/json"})
        if r.status_code != 200:
            return ""
        info = (r.json().get("jobPostingInfo") or {})
        return _strip_html(info.get("jobDescription", ""))[:5000]


# ------------------------------------------- long-tail HTML/JSON platforms

class JazzHRProvider:
    """{slug}.applytojob.com/apply/  (plain HTML; invalid tenants redirect
    to jazzhr.com marketing site, which is how probe() detects them)"""
    key = "jazzhr"
    _LINK = re.compile(
        r'href="(https://[a-z0-9-]+\.applytojob\.com/apply/[A-Za-z0-9]+/([^"]+))"')

    def probe(self, slug, limiter):
        limiter.acquire(self.key)
        try:
            r = requests.get(f"https://{slug}.applytojob.com/apply/",
                             timeout=TIMEOUT, headers={"User-Agent": USER_AGENT},
                             allow_redirects=True)
        except requests.RequestException:
            return False
        return r.status_code == 200 and ".applytojob.com" in r.url

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        limiter.acquire(self.key)
        r = requests.get(f"https://{slug}.applytojob.com/apply/",
                         timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        jobs, seen = [], set()
        for url, title_slug in self._LINK.findall(r.text):
            if url in seen:
                continue
            seen.add(url)
            jobs.append(RawJob(
                title=title_slug.replace("-", " "),
                url=url, company=entry["name"], platform=self.key,
            ))
        return jobs


class BambooHRProvider:
    """{slug}.bamboohr.com/careers/list  (JSON; invalid tenants redirect)"""
    key = "bamboohr"

    def probe(self, slug, limiter):
        limiter.acquire(self.key)
        try:
            r = requests.get(f"https://{slug}.bamboohr.com/careers/list",
                             timeout=TIMEOUT, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "application/json"},
                             allow_redirects=False)
        except requests.RequestException:
            return False
        return (r.status_code == 200 and
                "json" in r.headers.get("Content-Type", ""))

    def fetch_jobs(self, entry, limiter):
        slug = entry["slug"]
        limiter.acquire(self.key)
        r = requests.get(f"https://{slug}.bamboohr.com/careers/list",
                         timeout=TIMEOUT, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json"})
        r.raise_for_status()
        jobs = []
        for j in r.json().get("result", []):
            loc = j.get("location") or {}
            jobs.append(RawJob(
                title=j.get("jobOpeningName", ""),
                url=f"https://{slug}.bamboohr.com/careers/{j.get('id', '')}",
                company=entry["name"], platform=self.key,
                location=", ".join(x for x in [loc.get("city"), loc.get("state")] if x),
            ))
        return jobs


PROVIDERS = {
    "greenhouse": GreenhouseProvider(),
    "lever": LeverProvider(),
    "ashby": AshbyProvider(),
    "smartrecruiters": SmartRecruitersProvider(),
    "workable": WorkableProvider(),
    "workday": WorkdayProvider(),
    "jazzhr": JazzHRProvider(),
    "bamboohr": BambooHRProvider(),
}

# order used when auto-detecting a company's platform (most common first)
PROBE_ORDER = ["greenhouse", "lever", "ashby", "smartrecruiters", "workable"]
