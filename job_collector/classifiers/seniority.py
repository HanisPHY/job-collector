"""
Seniority filter for excluding non-entry-level job titles.
"""

import re
from typing import List, Optional, Tuple


class SeniorityFilter:
    """Filters out senior/experienced job titles based on title keywords."""

    # Titles matching these patterns are excluded as too senior.
    # Word boundaries prevent false positives (e.g. 'lead' must not match 'leadership',
    # 'sr' must not match 'sram').
    EXCLUDE_PATTERNS = [
        r'\bsenior\b',
        r'\bsr\.?\b',
        r'\bstaff\b',
        r'\bprincipal\b',
        r'\bdistinguished\b',
        r'\bmanager\b',
        r'\bdirector\b',
        r'\bhead\s+of\b',
        r'\barchitect\b',
        r'\bvp\b',
        r'\bvice\s+president\b',
        r'\bfellow\b',
        r'\bexperienced\b',
        r'\bmid[-\s]?level\b',
        # Level suffixes: II/III/IV and 3/4/5 signal post-entry roles.
        # Level I / 1 is deliberately NOT excluded - it is the standard
        # new grad level at Amazon, Uber, Twitch, Cisco etc.
        r'\b(?:II|III|IV|V)\b',
        r'\b[3-9]\b',
    ]

    # 'lead' is excluded only when it heads the title or is a standalone rank.
    # It must NOT match domain names where 'lead' is part of the team/product
    # (e.g. 'Software Engineer Project Intern (Lead Ads)') nor Booz Allen's
    # 'Lead Associate' rank appearing after a comma in otherwise entry titles.
    LEAD_PATTERNS = [
        r'^\s*lead\b',
        r'\blead\s+(?:software|data|security|infrastructure|market|developer|engineer|capability)\b',
        r'\btechnical\s+lead\b',
        r'\blead\s+associate\b',
    ]

    # Entry-level signals. If a title carries one of these it is kept even when
    # an exclude pattern also matches, since the entry signal is more specific
    # (e.g. 'Applied Scientist II Intern / Co-op').
    ENTRY_OVERRIDE_PATTERNS = [
        r'\bintern(?:ship)?\b',
        r'\bco[-\s]?op\b',
        r'\bnew\s+grad(?:uate)?\b',
        r'\bnew\s+college\s+grad(?:uate)?\b',
        r'\bcollege\s+grad(?:uate)?\b',
        r'\buniversity\s+grad(?:uate)?\b',
        r'\bearly\s+career\b',
        r'\bentry[-\s]?level\b',
        r'\bcampus\b',
    ]

    @classmethod
    def is_excluded(cls, job_title: str) -> Tuple[bool, Optional[str]]:
        """
        Determine whether a job title is too senior to keep.

        Args:
            job_title: Job title text

        Returns:
            Tuple of (should_exclude, matched_reason). matched_reason is None
            when the title is kept.
        """
        if not job_title:
            return False, None

        title = job_title.strip()

        # Entry-level signals win over seniority markers.
        for pattern in cls.ENTRY_OVERRIDE_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return False, None

        for pattern in cls.EXCLUDE_PATTERNS:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return True, match.group(0)

        for pattern in cls.LEAD_PATTERNS:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return True, match.group(0)

        return False, None

    @classmethod
    def filter_jobs(cls, jobs: List) -> Tuple[List, List]:
        """
        Split jobs into kept and excluded lists based on title seniority.

        Args:
            jobs: List of JobPosting objects

        Returns:
            Tuple of (kept_jobs, excluded_jobs)
        """
        kept = []
        excluded = []

        for job in jobs:
            should_exclude, _ = cls.is_excluded(job.job_title)
            if should_exclude:
                excluded.append(job)
            else:
                kept.append(job)

        return kept, excluded
