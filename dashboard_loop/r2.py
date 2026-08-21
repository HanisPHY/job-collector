# -*- coding: utf-8 -*-
"""Round 2 resolver + measurement harness."""
import os, json, sys, re
from datetime import datetime, timedelta
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:/OneDrive/work/school/project/Job"
INTER = {"staffing", "outsourcing", "training", "job_board"}
# LLM kinds that the ATS veto may NOT overturn at company level.
HARD_INTER = {"staffing", "outsourcing", "training"}
WINDOW_DAYS = 7
S5_MIN = 5
S5_RATE = 0.004


def build_profiles():
    """stage1 (gpt-4o-mini, anchored batch 20) + stage2 (gpt-4o on the unknown residue)."""
    passes = json.load(open(os.path.join(HERE, "passes_v4.json"), encoding="utf-8"))
    s1 = passes[0]
    s2 = json.load(open(os.path.join(HERE, "stage2_gpt-4o.json"), encoding="utf-8"))
    P = {}
    for k, v in s1.items():
        v = dict(v); v["stage"] = 1
        P[k] = v
    for k, v in s2.items():
        if v.get("tier", 0) > 0 or v.get("kind") != "unknown":
            w = dict(v); w["stage"] = 2
            P[k] = w
    for k, v in P.items():
        v.setdefault("prom", 0)
        if not isinstance(v.get("prom"), int):
            try: v["prom"] = int(v["prom"])
            except Exception: v["prom"] = 0
    return P


def load_overrides():
    p = os.path.join(HERE, "company_overrides.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def load_priority():
    p = os.path.join(HERE, "priority_companies.txt")
    if not os.path.exists(p):
        return set()
    out = set()
    for line in open(p, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if line:
            out.add(norm(line))
    return out


def tnorm(t):
    return re.sub(r"\W+", " ", (t or "").lower()).strip()


class Resolver:
    def __init__(self, rows, P, day, window_days=WINDOW_DAYS):
        self.P, self.ov = P, load_overrides()
        self.prio = load_priority()
        self.day = day
        lo = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=window_days - 1)).strftime("%Y-%m-%d")
        self.win = [r for r in rows if lo <= r["_day"] <= day]
        self.win_total = len(self.win) or 1
        self.win_by_co = defaultdict(list)
        for r in self.win:
            self.win_by_co[norm(r["company_name"])].append(r)
        # a company is an "own-board employer" if any row of it ever came from ats_direct
        self.has_board = {c for c in {norm(r["company_name"]) for r in rows}}
        self.board_cos = {norm(r["company_name"]) for r in rows if r["_source"] != "newgrad"}

    def prof(self, c):
        """Total function - a company missing from profiles must never raise."""
        v = self.P.get(c) or {"name": c, "kind": "unknown", "tier": 0, "prom": 0,
                              "conf": 0.0, "why": "not enriched", "stage": 0}
        o = self.ov.get(c)
        if o:
            v = dict(v); v.update({k: o[k] for k in ("kind", "tier", "prom") if k in o})
            v["why"] = "manual override"
        return v

    def company_lane(self, c):
        """-> (verdict, signals). verdict in ok / inter / review."""
        v = self.prof(c)
        sig = []
        if c in self.ov:
            return ("inter" if v["kind"] in INTER else "ok"), ["override"]
        if v["kind"] in HARD_INTER:
            return "inter", ["LLM:" + v["kind"]]
        if v["kind"] == "job_board":
            # eval A blocking-3 (KAYAK): a job_board that runs its own ATS board is not
            # auto-condemned; its own-board jobs are real. Company stays flagged but
            # its ats_direct rows escape at row level (see row_lane).
            return "inter", ["LLM:job_board"]
        n = len(self.win_by_co.get(c, []))
        if v["kind"] == "unknown" and v["tier"] == 0 and n >= S5_MIN and n / self.win_total >= S5_RATE:
            if c in self.board_cos:
                return "ok", ["unknown+rate%d/%dd(VETOED: own ATS board)" % (n, WINDOW_DAYS)]
            return "inter", ["unknown+rate %d in %dd" % (n, WINDOW_DAYS)]
        return "ok", sig

    def row_lane(self, r):
        """Per-row lane. The ATS veto is a property of the ROW, not the company."""
        c = norm(r["company_name"])
        verdict, sig = self.company_lane(c)
        if verdict == "inter" and r["_source"] != "newgrad":
            # this row came off the company's own Greenhouse/Lever/Ashby board
            return "ok", sig + ["row from own ATS board"]
        return verdict, sig

    def bucket(self, r):
        lane, sig = self.row_lane(r)
        if lane == "inter":
            return "C", sig
        c = norm(r["company_name"]); v = self.prof(c)
        if c in self.prio:
            return "A0", sig
        if v["tier"] == 3:
            return "A1", sig
        if v["tier"] == 2:
            return "A2", sig
        if c in self.board_cos:
            return "B1", sig
        return "B2", sig

    def sortkey(self, c):
        v = self.prof(c)
        return (0 if c in self.prio else 1, -v["tier"], -v.get("prom", 0),
                -len(self.win_by_co.get(c, [])), v["name"].lower())


def day_rows(rows, day):
    """uid dedup already done by load(); add (company,title) collapse."""
    seen, out, dropped = set(), [], defaultdict(int)
    for r in rows:
        if r["_day"] != day:
            continue
        k = (norm(r["company_name"]), tnorm(r["job_title"]))
        if k in seen:
            dropped[k] += 1
            continue
        seen.add(k); out.append(r)
    return out, dropped
