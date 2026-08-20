"""
New-grad SDE filter: keeps full-time entry-level software engineering roles.

Differs from job_collector's SeniorityFilter in two ways:
  1. It requires a POSITIVE software-engineering signal (SeniorityFilter only
     excludes seniority; here non-SDE roles like sales/recruiting must go).
  2. Interns/co-ops are EXCLUDED (the goal is full-time NG, and the existing
     LinkedIn pipeline already covers internships).

Two modes:
  strict=True  (default): title must also carry a new-grad signal
                          (new grad / university graduate / 2026/2027 / early
                          career / junior / associate / level I ...)
  strict=False: any non-senior, non-intern SDE title passes
"""

import re
from typing import Optional, Tuple

# Positive: looks like a software engineering role at all
SDE_PATTERNS = [
    r"software\s+(?:engineer|developer|development)",
    r"\bsoftware\s+dev\b",
    r"\b(?:backend|back[-\s]end|frontend|front[-\s]end|full[-\s]?stack|web|mobile|"
    r"ios|android|platform|infrastructure|cloud|embedded|firmware|systems?|"
    r"security|test|qa|ml|ai|machine\s+learning|data|devops|site\s+reliability|"
    r"reliability|graphics|gameplay|compiler|kernel)\s+(?:engineer|developer)\b",
    r"\b(?:swe|sde|sdet)\b",
    r"\bsoftware\s+engineering\b",
    r"\bengineer\s*(?:i|1|ii)?\s*,?\s*(?:software|early\s+career|new\s+grad)",
    # bare "developer" was a leak (matched "Product Developer" consumer-goods
    # roles); exclude the common non-software prefixes
    r"(?<!business\s)(?<!product\s)(?<!learning\s)(?<!content\s)\bdeveloper\b",
    r"\bmember\s+of\s+technical\s+staff\b",
]

# Non-software engineering domains that leak through the broad SDE patterns
# ("Fuel Cell Systems Engineer" matched "systems engineer"). Tight phrases
# only - and never applied when the title itself says "software" (an explicit
# software signal outranks a domain word: "Software Engineer, Battery
# Management Systems" must survive). embedded/firmware are deliberately NOT
# here - they are core NG SDE paths.
NON_SDE_DOMAIN_PATTERNS = [
    r"\bfuel\s+cell\b",
    r"\b(?:mechanical|electrical|civil|structural|geotechnical|thermal|"
    r"manufacturing|industrial|battery|chemical|materials|packaging|"
    r"facilities|hvac)\s+(?:systems?\s+)?engineer\b",
    r"\bprocess\s+engineer\b",
    r"\bproduct\s+developer\b",
]

# Positive: looks entry-level / new-grad (used only in strict mode)
NG_PATTERNS = [
    r"\bnew\s+grad(?:uate)?\b",
    r"\bnew\s+college\s+grad(?:uate)?\b",
    r"\b(?:college|university)\s+grad(?:uate)?\b",
    r"\bgrad(?:uate)?\s+(?:software|program|scheme|hire)\b",
    r"\bsoftware\s+engineer\s+graduate\b",
    r"\bearly\s+career\b",
    r"\bearly\s+in\s+career\b",
    r"\bentry[-\s]?level\b",
    r"\bcampus\b",
    r"\bjunior\b|\bjr\.?\b",
    r"\bassociate\b",
    r"\b20(?:2[5-9])\b",           # cohort years: 2025-2029
    r"(?:\b(?:i|1)\b)\s*$",        # trailing level: "Software Engineer I" / "... 1"
    r"\b(?:engineer|developer|sde|swe)\s+(?:i|1)\b",
]

# Negative: too senior (aligned with job_collector.classifiers.seniority,
# validated against 4898 real titles in this repo's dataset)
SENIOR_PATTERNS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\bprincipal\b",
    r"\bdistinguished\b", r"\bmanager\b", r"\bdirector\b", r"\bhead\s+of\b",
    r"\barchitect\b", r"\bvp\b", r"\bvice\s+president\b", r"\bfellow\b",
    r"\bexperienced\b", r"\bmid[-\s]?level\b",
    r"\b(?:II|III|IV|V)\b", r"\b[3-9]\b",
    r"^\s*lead\b", r"\btechnical\s+lead\b", r"\blead\s+associate\b",
    r"\blead\s+(?:software|data|security|infrastructure|market|developer|"
    r"engineer|capability)\b",
]

# Negative: not a full-time role
NON_FULLTIME_PATTERNS = [
    r"\bintern(?:ship)?\b", r"\bco[-\s]?op\b", r"\bapprentice(?:ship)?\b",
    r"\bcontract(?:or)?\b", r"\bpart[-\s]?time\b", r"\btemporary\b",
    r"\bfellowship\b",
]

_SDE = [re.compile(p, re.I) for p in SDE_PATTERNS]
_NG = [re.compile(p, re.I) for p in NG_PATTERNS]
_SENIOR = [re.compile(p, re.I) for p in SENIOR_PATTERNS]
_NONFT = [re.compile(p, re.I) for p in NON_FULLTIME_PATTERNS]
_NON_SDE_DOMAIN = [re.compile(p, re.I) for p in NON_SDE_DOMAIN_PATTERNS]
_SOFTWARE_WORD = re.compile(r"\bsoftware\b", re.I)


def classify_title(title: str, strict: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Returns (keep, reason). reason explains a rejection; None when kept.
    """
    if not title or not title.strip():
        return False, "empty title"
    t = title.strip()

    for pat in _NONFT:
        m = pat.search(t)
        if m:
            return False, f"not full-time ({m.group(0)})"

    for pat in _SENIOR:
        m = pat.search(t)
        if m:
            return False, f"too senior ({m.group(0)})"

    # explicit "software" outranks any domain word (reviewer guardrail)
    if not _SOFTWARE_WORD.search(t):
        for pat in _NON_SDE_DOMAIN:
            m = pat.search(t)
            if m:
                return False, f"non-SDE domain ({m.group(0)})"

    if not any(p.search(t) for p in _SDE):
        return False, "not an SDE role"

    if strict and not any(p.search(t) for p in _NG):
        return False, "no new-grad signal (strict mode)"

    return True, None
