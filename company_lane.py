# -*- coding: utf-8 -*-
"""
Company lane / segment resolver.

This is the round-3 spec section 4 decision order, transcribed literally. Nothing
here calls an LLM and nothing here writes: it reads the three collector CSVs plus
`company_profiles.json` (built by enrich_companies.py) and answers, for one day:

    row -> segment    ("1a_t3" | "1a_t2" | "1b" | "B1" | "B2" | "C")

The order of the tests in company_lane() is load bearing and must not be reshuffled:

  O1  a manual override wins over everything
  S1  the LLM's own hard-intermediary kinds
  A-blocking-2 gate:  stage < 1 (never enriched, or enrichment never came back)
                      can NEVER reach lane C - it sits BEFORE the volume signal
  S5  volume-only signal, absolute threshold, no relative term
  V1  company-level veto inside S5: a company with its own ATS board is an employer
  row_lane  is evaluated PER ROW so a job_board that also runs its own board
            (KAYAK, Jobgether) keeps its own-board rows out of lane C

The segmentation criteria contain NO prom threshold; prom only orders rows inside a
segment (sort_key).
"""

import csv
import json
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))

PROFILE_PATH = os.environ.get("JOB_PROFILE_PATH") or os.path.join(HERE, "company_profiles.json")
OVERRIDE_PATH = os.path.join(HERE, "company_overrides.json")
PRIORITY_PATH = os.path.join(HERE, "priority_companies.txt")

# (file, source label). The label matters: everything that is not "newgrad" came off a
# company's own ATS board and is therefore, by construction, a real employer.
SOURCES = [
    ("newgrad_classifications.csv", "newgrad"),
    ("ats_jobs.csv", "ats_direct"),
    ("ddg_jobs.csv", "ddg"),
]

HARD_INTER = {"staffing", "outsourcing", "training"}
S5_MIN, WINDOW_DAYS = 5, 7

# ---------------------------------------------------------------- relevance regex
# Spec section 3.1. This is the PRIMARY segmentation criterion and it is a pure string
# match, so its sampling noise is 0.
#
# The body alternatives are case-INSENSITIVE; only the suffix grade marker stays
# case-sensitive, because "Engineer I" is an entry grade and a lowercase "i" is not.
# Writing the whole thing case-sensitive silently kills the new grad / entry level /
# associate / graduate / intern branches and collapses segment 1 from 28 rows to 9.
REL_BODY = re.compile(r"new\s*grad|new college|entry[ -.]level|university|campus|graduat|"
                      r"intern(?!ational)|202[6-8]|junior|associate|apprentic|"
                      r"early career|rotational", re.I)      # body: case-insensitive
REL_SUF = re.compile(r"\b(?:I|1)$")                          # grade suffix: case-sensitive
REL_EXC = re.compile(r"senior|principal|staff engineer|manager|director|architect|"
                     r"\bsr\b|\bII\b|\bIII\b|\blead\b|years of experience", re.I)


def is_entry(title):
    """New-grad relevance. A SEGMENTATION criterion, never a filter: a row that returns
    False is not dropped, it lands in segment 3."""
    t = (title or "").strip()
    return bool(REL_BODY.search(t) or REL_SUF.search(t)) and not REL_EXC.search(t)


# ---------------------------------------------------------------- names / rows
_SUFFIXES = [" inc", " llc", " ltd", " corp", " corporation", " co", " company",
             " limited", " plc", " lp", " llp", " group", " gmbh", " pvt",
             " private limited"]


def norm(name):
    """Company key. Same normalisation the enrichment cache was built with."""
    s = (name or "").strip().lower()
    s = re.sub(r"[.,]", "", s)
    s = re.sub(r"\s+", " ", s)
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[:-len(suf)].strip()
    return s


def tnorm(title):
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def load_rows(root=HERE):
    """All three CSVs, deduped across sources by unique_id (ddg and ats do overlap)."""
    seen, rows = set(), []
    for fn, label in SOURCES:
        path = os.path.join(root, fn)
        if not os.path.exists(path):
            continue
        with open(path, "r", newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                uid = r.get("unique_id")
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                r["_source"] = label
                r["_recorded"] = (r.get("date_recorded") or "").strip()
                r["_day"] = r["_recorded"][:10]
                rows.append(r)
    return rows


def dedup_rows(rows):
    """Collapse (company, normalised title) duplicates. Returns (kept, dropped)."""
    seen, out, dropped = set(), [], 0
    for r in rows:
        k = (norm(r.get("company_name")), tnorm(r.get("job_title")))
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        out.append(r)
    return out, dropped


def day_rows(rows, day):
    """One natural day, deduped. This set is what the segment invariant (F12) sums to."""
    return dedup_rows([r for r in rows if r["_day"] == day])[0]


# ---------------------------------------------------------------- persistence
def atomic_write_json(path, obj):
    """Write via a temp file in the same directory + os.replace.

    The project tree lives inside OneDrive; a half-written company_profiles.json would
    break EVERY subsequent dashboard run, not just this one.
    """
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_profiles(path=None):
    """Enrichment cache. A parse failure degrades to an EMPTY table, never to a crash:
    combined with the stage gate an empty table means 'nobody is classified', which is
    the safe direction (lane C becomes empty)."""
    path = path or PROFILE_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        print("Warning: could not read %s (%s); continuing with an empty table" % (path, e))
        return {}


def load_overrides(path=None):
    path = path or OVERRIDE_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    # keys are written by a human, so normalise them here rather than demanding
    # the human types the normalised form
    return {norm(k): v for k, v in data.items()
            if isinstance(v, dict) and not k.startswith("_")}


def load_priority(path=None):
    path = path or PRIORITY_PATH
    out = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    out.add(norm(line))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- resolver
class LaneResolver:
    def __init__(self, rows, profiles, day, overrides=None, priority=None,
                 window_days=WINDOW_DAYS):
        self.P = profiles or {}
        self.ov = {} if overrides is None else overrides
        self.prio = set() if priority is None else priority
        self.day = day
        self.window_days = window_days
        lo = (datetime.strptime(day, "%Y-%m-%d")
              - timedelta(days=window_days - 1)).strftime("%Y-%m-%d")
        self.win_lo = lo
        self.win = [r for r in rows if lo <= r["_day"] <= day]
        self.win_by = defaultdict(list)
        for r in self.win:
            self.win_by[norm(r["company_name"])].append(r)
        # BOARD_COMPANIES: everything ever seen in ats_jobs.csv or ddg_jobs.csv.
        # Deliberately NOT ats_registry.json - measured to add 2 companies / 3 rows.
        self.board = {norm(r["company_name"]) for r in rows if r["_source"] != "newgrad"}

    # -- signals -------------------------------------------------------------
    def profile(self, c):
        """TOTAL function. A company missing from the table, a table that failed to
        parse, a garbage entry - none of it may raise, because this runs inside the
        daily unattended job."""
        v = self.P.get(c)
        if not isinstance(v, dict):
            v = None
        if v is None:
            v = {"name": c, "kind": "unknown", "tier": 0, "prom": 0, "stage": 0,
                 "why": "not enriched"}
        else:
            v = dict(v)
        v.setdefault("name", c)
        v.setdefault("kind", "unknown")
        v.setdefault("why", "")
        for k in ("tier", "prom", "stage"):
            try:
                v[k] = int(v.get(k) or 0)
            except Exception:
                v[k] = 0
        o = self.ov.get(c)
        if o:
            v = {**v, **{k: o[k] for k in ("kind", "tier", "prom") if k in o},
                 "why": o.get("why") or "manual override",
                 "stage": max(v.get("stage", 0), 1)}
            for k in ("tier", "prom", "stage"):
                try:
                    v[k] = int(v.get(k) or 0)
                except Exception:
                    v[k] = 0
        return v

    def window_count(self, c):
        return len(self.win_by.get(c, ()))

    # -- decision order (spec section 4) -------------------------------------
    def company_lane(self, c):
        """-> ("inter" | "ok", signals)"""
        v = self.profile(c)
        if c in self.ov:                                          # O1 manual, highest
            return ("inter" if v["kind"] in HARD_INTER | {"job_board"} else "ok"), ["override"]
        if v["kind"] in HARD_INTER:                               # S1a hard intermediary
            return "inter", ["LLM:" + v["kind"]]
        if v["kind"] == "job_board":                              # S1b job board
            return "inter", ["LLM:job_board"]
        if v.get("stage", 0) < 1:                                 # blocking-2 gate
            return "ok", ["not enriched"]
        n = self.window_count(c)
        if v["kind"] == "unknown" and v["tier"] == 0 and n >= S5_MIN:   # S5, absolute only
            if c in self.board:                                   # V1 company-level veto
                return "ok", ["VETO: own ATS board"]
            return "inter", ["unknown+vol %d/%dd" % (n, self.window_days)]
        return "ok", []

    def row_lane(self, row):
        """Per-row. KAYAK / Jobgether: the company is flagged, but the rows that came
        off its own board are real jobs and escape."""
        c = norm(row["company_name"])
        verdict, sig = self.company_lane(c)
        if verdict == "inter" and row.get("_source") != "newgrad":
            return "ok", sig + ["own-board row"]
        return verdict, sig

    def segment(self, row):
        if self.row_lane(row)[0] == "inter":
            return "C"
        c = norm(row["company_name"])
        v = self.profile(c)
        if v["tier"] >= 2:
            if is_entry(row.get("job_title")):
                return "1a_t3" if v["tier"] == 3 else "1a_t2"
            return "1b"
        return "B1" if c in self.board else "B2"

    def sort_key(self, c):
        """prom appears here and nowhere else."""
        v = self.profile(c)
        return (0 if c in self.prio else 1, -v["prom"], -v["tier"],
                -self.window_count(c), str(v.get("name") or c).lower())


# Segment metadata shared by the dashboard and the tests.
SEGMENTS = [
    ("1a_t3", "今日必看", "tier 3 大公司的应届岗", True),
    ("1a_t2", "大中公司应届岗", "tier 2 公司的应届岗", False),
    ("1b", "大中公司其他岗位", "tier >= 2，标题不像应届岗", False),
    ("B1", "有自有 ATS board 的小公司", "tier <= 1，但公司出现在 ats/ddg 采集里", True),
    ("B2", "长尾", "其余非中介行", False),
    ("C", "中介 / 刷屏", "被判为中介、聚合站或纯量刷屏", False),
]
SEGMENT_ORDER = [s[0] for s in SEGMENTS]
DEFAULT_VISIBLE = ("1a_t3", "B1")
