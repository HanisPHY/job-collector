# -*- coding: utf-8 -*-
"""
Acceptance fixtures F1-F12, F14-F19 from round3_spec.md section 7.

    set PYTHONIOENCODING=utf-8
    python -m unittest discover -s tests -v          (from the repo root)
    python tests/test_lane.py                        (same thing, prettier)

F13 was deleted from the spec: "the share of segment-1 rows that are entry-level" is
vacuous, because is_entry() IS the definition of segment 1. It is a manual sign-off
item now, printed at the bottom of a direct run of this file.

F1/F2 need a full live enrichment pass. They are skipped by default - P0 starts from
the paid-for gpt-4o cache - and can be run with  JOB_TEST_LLM=1  in the environment.
"""

import contextlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

import paths

# job_collector must be imported (pulling in the installed ats_direct package)
# before scripts/ is put on sys.path below - scripts/ats_direct.py is an
# unrelated CLI script that shares its module name with the installed
# ats_direct package, and would shadow it for this process if scripts/ were
# searched first.
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402

sys.path.insert(0, str(paths.ROOT / "scripts"))

import company_lane as CL           # noqa: E402
import dashboard as DASH            # noqa: E402
import view as VIEW                 # noqa: E402

HARVEST_DAY = "2026-08-19"          # ats_direct first-day full harvest
STEADY_DAY = "2026-08-20"           # ordinary day

_ROWS = CL.load_rows(paths.DATA_DIR)
_PROFILES = CL.load_profiles()
_OVERRIDES = CL.load_overrides()
_PRIORITY = CL.load_priority()

SEED_CACHE = os.path.join(paths.ROOT, "dashboard_loop", "company_profiles.round2.json")

ANCHOR_DAY = max(r["_day"] for r in _ROWS)   # what a real run generates for


def resolver(day, profiles=None, overrides=None, rows=None):
    return CL.LaneResolver(rows if rows is not None else _ROWS,
                           _PROFILES if profiles is None else profiles,
                           day,
                           overrides=_OVERRIDES if overrides is None else overrides,
                           priority=_PRIORITY)


_STATE = DASH.read_state()
_PAYLOAD_CACHE = {}


def payload(day, profiles=None, overrides=None, rows=None, retain=VIEW.RETAIN_DAYS):
    """The bytes the browser gets. Everything below asserts against THIS rather
    than against the CSVs, so a serialisation that loses rows is inside the
    assertion instead of behind it."""
    plain = (profiles is None and overrides is None and rows is None
             and retain == VIEW.RETAIN_DAYS)
    if plain and day in _PAYLOAD_CACHE:
        return _PAYLOAD_CACHE[day]
    p = VIEW.build_payload(day,
                           _ROWS if rows is None else rows,
                           _PROFILES if profiles is None else profiles,
                           _OVERRIDES if overrides is None else overrides,
                           _PRIORITY, _STATE, retain=retain)
    if plain:
        _PAYLOAD_CACHE[day] = p
    return p


def window_counts(day, n, view="all", profiles=None, overrides=None, rows=None):
    """-> (raw, cap2, dedup_total) for the N-day window ending on `day`.

    The window replaces the single natural day everywhere (R2). Only the SCOPE is
    wider: cap2 still bounds one company inside one segment, raw still counts every
    surviving row, and their sum still has to be the deduped total (I1)."""
    wv = VIEW.window_view(payload(day, profiles, overrides, rows), n, view)
    segs = CL.SEGMENT_ORDER
    return ({s: wv["raw"][i] for i, s in enumerate(segs)},
            {s: wv["cap2"][i] for i, s in enumerate(segs)},
            wv["dedup"])


def segment_counts(day, **kw):
    """The old name, kept so F6/F7/F19 read the same. One natural day is just the
    N=1 window now - and it goes through the SAME dedup rule as every other N,
    which is the point of A3: the tests no longer depend on two rules agreeing."""
    return window_counts(day, 1, **kw)


def coord_rows(day, rows=None):
    """The rows of one natural day in payload column order, so a [day, row]
    coordinate can be turned back into the CSV row it came from."""
    rs = _ROWS if rows is None else rows
    return [r for r in rs if r["_day"] == day]


def window_head(day, n, seg, view="all", profiles=None, overrides=None, rows=None):
    """One segment's cap-2 head, as [(company display name, job title), ...] in
    render order. The old segment_head(day, seg) is window_head(day, 1, seg)."""
    p = payload(day, profiles, overrides, rows)
    idx = p["index"]
    out = []
    for d, i in VIEW.segment_head(p, n, seg, view):
        cols = p["days"][idx["days"][d]]
        out.append((idx["co"][cols["c"][i]][0], cols["t"][i]))
    return out


# 60 employers that are beyond argument: every one of them is a company you would be
# an employee OF. Hardcoded on purpose - a list derived from the profile table at
# runtime would be circular. The assertion reads the CACHE, it never calls a model.
REAL_EMPLOYERS_60 = [
    "Deloitte", "SpaceX", "Palantir", "Booz Allen Hamilton", "Amazon", "Appian",
    "L3Harris Technologies", "Esri", "Accenture Federal Services", "Leidos",
    "Micron Technology", "Twitch", "Google", "NetApp", "Anduril Industries", "Cisco",
    "Bosch", "Handshake", "Dematic", "NVIDIA", "Truist", "BAE Systems, Inc.",
    "Cargill", "Stellantis", "Qualcomm", "Gartner", "Notion", "Draper",
    "Lockheed Martin", "ECS", "Scale AI", "Stryker", "SAIC", "Slalom",
    "Morgan Stanley", "Broadcom", "Garmin", "Supermicro", "ClickHouse", "Adobe",
    "Salesforce", "Stripe", "Nuro", "Canonical", "NetJets", "Blue Origin",
    "Ericsson", "Coinbase", "General Motors", "Anthropic", "EY",
    "General Dynamics Mission Systems", "Citi", "Boeing", "GE Vernova", "Plaid",
    "Humana", "OpenAI", "Ford Motor Company", "Intel",
]

# Correctly-labelled outsourcing firms: they belong in lane C and must not be counted
# as false positives by F7.
KNOWN_OUTSOURCING = {CL.norm(x) for x in
                     ["Capgemini", "Infosys", "TCS", "Tata Consultancy Services", "Wipro",
                      "HCL", "Cognizant", "Synechron", "NTT DATA"]}


class F19Regex(unittest.TestCase):
    """Written first on purpose: get the regex wrong and every other segment
    assertion goes wrong downstream, but only F19 says WHICH branch died."""

    TRUE = ["Software Engineer, New Grad", "Entry Level Software Engineer",
            "Graduate Field Service Engineer", "AI Software Engineering Intern",
            "Associate Data Scientist", "Software Engineer I", "2027 Analyst Program"]
    FALSE = ["Senior Software Engineer", "Staff Engineer", "Engineering Manager",
             "Software Engineer II", "Principal Architect",
             "International Sales Engineer"]

    def test_F19_true(self):
        for t in self.TRUE:
            with self.subTest(title=t):
                self.assertTrue(CL.is_entry(t), "%r should be entry level" % t)

    def test_F19_false(self):
        for t in self.FALSE:
            with self.subTest(title=t):
                self.assertFalse(CL.is_entry(t), "%r should NOT be entry level" % t)

    def test_F19_body_is_case_insensitive_suffix_is_not(self):
        # the exact confusion that collapsed segment 1 from 28 rows to 9
        self.assertTrue(CL.is_entry("SOFTWARE ENGINEER NEW GRAD"))
        self.assertTrue(CL.is_entry("entry level software engineer"))
        self.assertTrue(CL.is_entry("Software Engineer I"))      # grade suffix
        self.assertFalse(CL.is_entry("Machine Learning Engineer for iOS and i"))

    def test_F19_is_a_criterion_not_a_filter(self):
        """No row may ever be dropped for failing the regex - it only changes segment."""
        raw, _cap2, total = segment_counts(STEADY_DAY)
        self.assertEqual(sum(raw.values()), total)
        self.assertGreater(raw["1b"], 0, "non-entry rows must land in segment 3, not vanish")

    def test_F19_is_a_criterion_not_a_filter_on_every_window(self):
        """The same on all five windows: widening the scope must not turn the
        relevance regex into a filter."""
        for n in VIEW.N_CHOICES:
            raw, _cap2, total = window_counts(STEADY_DAY, n)
            with self.subTest(n=n):
                self.assertEqual(sum(raw.values()), total)
                self.assertGreater(raw["1b"], 0)


def segment_head(day, seg):
    """The old single-day name. Same thing at N=1."""
    return window_head(day, 1, seg)


def expanded_rows(day, n=VIEW.N_DEFAULT, v="all"):
    """Rows a reader actually sees expanded on load: view.open_plan's total. The
    rest is inside a nested <details> - folded, never dropped."""
    return VIEW.window_view(payload(day), n, v)["open"]


class F10F11Segments(unittest.TestCase):
    """cap=2 bounds one company, not the day, so segment sizes track collector
    volume: 8/20 grew to 2068 newgrad rows and segment 1 went 28 -> 61. Asserting a
    band on the segment TOTAL just re-fails every heavy day. What has to stay bounded
    is what is expanded on load, and view.open_plan is what bounds it.

    Scope only: every assertion below now runs on all five windows instead of one
    natural day, and not one invariant was loosened to make that possible."""

    def test_F10_segment1_is_all_entry_level_whatever_its_size(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            for n in VIEW.N_CHOICES:
                _r, cap2, _t = window_counts(day, n)
                with self.subTest(day=day, n=n):
                    self.assertGreater(cap2["1a_t3"], 0, "segment 1 must not be empty")
                    for _name, title in window_head(day, n, "1a_t3"):
                        self.assertTrue(CL.is_entry(title),
                                        "%r is not an entry-level title" % title)

    def test_F11a_open_equals_the_closed_form(self):
        """An EQUALITY against view.open_expected, not a hand-written band: there is
        no boundary left to write down wrongly."""
        for day in (HARVEST_DAY, STEADY_DAY):
            for n in VIEW.N_CHOICES:
                _r, cap2, _t = window_counts(day, n)
                with self.subTest(day=day, n=n):
                    self.assertEqual(VIEW.open_plan(cap2)[1], VIEW.open_expected(cap2))
                    self.assertEqual(expanded_rows(day, n), VIEW.open_expected(cap2))

    def test_F11a_open_equals_the_closed_form_on_random_shapes(self):
        """The corpus only ever produces a handful of cap2 shapes. 2000 random ones
        plus the adversarial shapes that broke the OLD published bound."""
        rnd = random.Random(20260821)
        shapes = [{s: rnd.choice([0, 0, 1, 5, 11, 12, 13, 29, 30, 31, 34, 35, 36,
                                  rnd.randint(0, 400)])
                   for s in CL.SEGMENT_ORDER} for _ in range(2000)]
        shapes += [{"1a_t3": 0, "B1": 1000, "1a_t2": 0},
                   {"1a_t3": 0, "B1": 0, "1a_t2": 0},
                   {"1a_t3": 0, "B1": 0, "1a_t2": 1000},
                   {"1a_t3": 1000, "B1": 1000, "1a_t2": 1000},
                   {"1a_t3": 17, "B1": 0, "1a_t2": 4}, {"B1": 12}, {}]
        for c in shapes:
            plan, total = VIEW.open_plan(c)
            self.assertEqual(total, VIEW.open_expected(c), "cap2=%r" % c)
            self.assertEqual(total, sum(plan.values()), "cap2=%r" % c)

    def test_F11b_open_is_bounded_both_ways(self):
        """The upper bound is structural; the lower bound is a function of what the
        three openable segments can actually contribute once each is capped. Both
        sides are derived from SEG_OPEN_CAP - the literal 47 appears nowhere."""
        ceil = sum(VIEW.SEG_OPEN_CAP[s] for s in VIEW.ALWAYS_OPEN)
        for day in (HARVEST_DAY, STEADY_DAY):
            for n in VIEW.N_CHOICES:
                for v in VIEW.VIEWS:
                    wv = VIEW.window_view(payload(day), n, v)
                    cap2 = {s: wv["cap2"][i] for i, s in enumerate(CL.SEGMENT_ORDER)}
                    with self.subTest(day=day, n=n, view=v):
                        self.assertLessEqual(wv["open"], ceil)
                        self.assertGreaterEqual(
                            wv["open"], min(VIEW.FLOOR, VIEW.openable(cap2)))

    def test_F11_truncated_rows_are_folded_not_dropped(self):
        """The count cap is a truncation on the sort, never a filter: whatever it
        pushes down still renders inside the segment."""
        for n in VIEW.N_CHOICES:
            _r, cap2, _t = window_counts(STEADY_DAY, n)
            for s in VIEW.SEG_OPEN_CAP:
                folded = max(0, cap2[s] - VIEW.SEG_OPEN_CAP[s])
                with self.subTest(segment=s, n=n):
                    self.assertEqual(len(window_head(STEADY_DAY, n, s)), cap2[s],
                                     "segment %s lost rows: folded %d must stay in "
                                     "the cap2 view" % (s, folded))


class F12Invariant(unittest.TestCase):
    """An INVARIANT, never a hardcoded number: the corpus grows every day and the
    spec's own literal 931 == 931 went stale within two hours."""

    def test_F12_zero_loss(self):
        """3 views x 5 windows x 2 anchors, on the payload: the segments must sum to
        the deduped total AND to the trend bars. Two numbers that used to be
        different (2073 vs 2035) are one number now - only one dedup rule is left."""
        for day in (HARVEST_DAY, STEADY_DAY):
            for n in VIEW.N_CHOICES:
                for v in VIEW.VIEWS:
                    wv = VIEW.window_view(payload(day), n, v)
                    with self.subTest(day=day, n=n, view=v):
                        self.assertEqual(sum(wv["raw"]), wv["dedup"])
                        self.assertEqual(sum(wv["bars"]), wv["dedup"])

    def test_F12_every_row_gets_exactly_one_segment(self):
        """On the payload column the browser reads, not only on the resolver: a
        segment index that went out of range in serialisation is a silent
        mis-filing that nothing else would catch."""
        p = payload(STEADY_DAY)
        n_seg = len(CL.SEGMENT_ORDER)
        seen = 0
        for _d, cols in p["days"].items():
            self.assertEqual(len(cols["g"]), cols["n"])
            for g in cols["g"]:
                self.assertIsInstance(g, int)
                self.assertTrue(0 <= g < n_seg, "segment index %r out of range" % g)
                seen += 1
        self.assertGreater(seen, 0)
        R = resolver(STEADY_DAY)
        for r in CL.day_rows(_ROWS, STEADY_DAY):
            self.assertIn(R.segment(r), CL.SEGMENT_ORDER)


class F4F6F7LaneC(unittest.TestCase):
    def test_F4_sixty_real_employers_never_in_lane_C(self):
        offenders = []
        for day in (HARVEST_DAY, STEADY_DAY):
            R = resolver(day)
            for name in REAL_EMPLOYERS_60:
                c = CL.norm(name)
                if R.company_lane(c)[0] == "inter":
                    offenders.append((day, name, R.company_lane(c)[1]))
        self.assertEqual(offenders, [], "real employers pushed into lane C: %r" % offenders)

    def test_F6_empty_profile_table(self):
        raw, _c, _t = segment_counts(STEADY_DAY, profiles={}, overrides={})
        self.assertEqual(raw["C"], 0, "an empty profile table must produce an empty lane C")
        R = resolver(STEADY_DAY, profiles={}, overrides={})
        for name in ("Deloitte", "Amazon", "Booz Allen Hamilton"):
            with self.subTest(company=name):
                self.assertEqual(R.company_lane(CL.norm(name))[0], "ok")

    def test_F6_unparseable_profile_table_degrades_to_empty(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write('{"half a fi')                   # a torn OneDrive write
        try:
            self.assertEqual(CL.load_profiles(path), {})
        finally:
            os.unlink(path)

    def test_F7_stale_profile_table(self):
        """Only companies seen on 8/19 are enriched; 8/20's new arrivals are stage 0."""
        seen819 = {CL.norm(r["company_name"]) for r in _ROWS if r["_day"] <= HARVEST_DAY}
        stale = {k: v for k, v in _PROFILES.items() if k in seen819}
        R = resolver(STEADY_DAY, profiles=stale)
        in_c = {CL.norm(r["company_name"]) for r in CL.day_rows(_ROWS, STEADY_DAY)
                if R.segment(r) == "C"}
        fp = sorted(c for c in in_c
                    if c not in KNOWN_OUTSOURCING
                    and _PROFILES.get(c, {}).get("kind") == "employer"
                    and int(_PROFILES.get(c, {}).get("tier") or 0) >= 2)
        self.assertEqual(fp, [], "real employers in lane C under a stale table: %r" % fp)


class F5BackgroundTraffic(unittest.TestCase):
    """Background-traffic stress test. The OLD gate ('duplicate the same day') is void:
    by construction it could not see a relative term failing, because duplicating the
    day scales numerator and denominator together. This injects rows from INDEPENDENT
    NEW companies, which moves only the denominator - the exact thing an
    `n / win_total >= rate` term would have been fooled by."""

    LOADS = [0, 300, 700, 1100, 1500, 3000, 6000]

    @staticmethod
    def _hits(n_per_day, overrides):
        d0 = datetime.strptime(STEADY_DAY, "%Y-%m-%d")
        extra = []
        for k in range(1, 7):                       # the 6 days BEFORE 8/20
            day = (d0 - timedelta(days=k)).strftime("%Y-%m-%d")
            for i in range(n_per_day):
                extra.append({"unique_id": "bg_%d_%d" % (k, i),
                              "job_title": "Software Engineer", "job_link": "",
                              "company_name": "BG Filler Co %06d" % i,
                              "_source": "newgrad", "_day": day,
                              "_recorded": day + " 00:00"})
        R = CL.LaneResolver(_ROWS + extra, _PROFILES, STEADY_DAY,
                            overrides=overrides, priority=_PRIORITY)
        return sorted(c for c in R.win_by
                      if R.company_lane(c)[0] == "inter"
                      and any("unknown+vol" in s for s in R.company_lane(c)[1]))

    def test_F5_constant_under_background_load(self):
        seen = {n: self._hits(n, _OVERRIDES) for n in self.LOADS}
        counts = {n: len(v) for n, v in seen.items()}
        self.assertEqual(len(set(counts.values())), 1,
                         "S5 hit count moved with background traffic: %r" % counts)
        self.assertEqual(seen[0], seen[6000], "membership changed, not just the count")

    def test_F5_overrides_rescue_exactly_the_disputed_member(self):
        """The spec pinned this at 8, but that was a point value on a snapshot: real
        spam grows with the corpus (8 -> 11 as 8/20 went from 1018 to 1674 rows) and
        the number is SUPPOSED to track it. What must hold is the relationship - the
        shipped overrides rescue Yara AI, the one disputed member of lane C in the
        manual sign-off, and nothing else. The anti-drift property lives in
        test_F5_constant_under_background_load, which is the assertion that matters."""
        bare = self._hits(0, {})
        shipped = self._hits(0, _OVERRIDES)
        self.assertIn("yara ai", bare)
        self.assertNotIn("yara ai", shipped)
        self.assertEqual(set(bare) - set(shipped), {"yara ai"},
                         "overrides must rescue Yara AI and nobody else")

    def test_F5_no_known_real_employer_is_caught_by_volume(self):
        """S5 fires on 'lots of postings AND the LLM has never heard of it'. Any
        company the profile table does know is a bug in the stage gate, not spam."""
        for c in self._hits(0, _OVERRIDES):
            v = _PROFILES.get(c) or {}
            with self.subTest(company=c):
                self.assertEqual(int(v.get("tier") or 0), 0,
                                 "%s has tier>0 yet was flagged by volume" % c)


class F8F18ThirdState(unittest.TestCase):
    def test_F8_missing_company_is_total_and_stage_zero(self):
        R = resolver(STEADY_DAY, profiles={})
        for name in ("", "   ", "Company That Does Not Exist 12345", "フジアルテ株式会社"):
            with self.subTest(company=name):
                v = R.profile(CL.norm(name))         # must not raise
                self.assertEqual(v["stage"], 0)
                self.assertEqual(v["tier"], 0)
                self.assertEqual(v["kind"], "unknown")
                self.assertEqual(R.company_lane(CL.norm(name)), ("ok", ["not enriched"]))

    def test_F8_garbage_entries_do_not_raise(self):
        bad = {"a": None, "b": "not a dict", "c": [], "d": {"tier": "three", "prom": None},
               "e": {"kind": 7}}
        R = resolver(STEADY_DAY, profiles=bad)
        for k in bad:
            with self.subTest(key=k):
                v = R.profile(k)
                self.assertIsInstance(v["tier"], int)
                self.assertIsInstance(v["prom"], int)
                self.assertIn(R.company_lane(k)[0], ("ok", "inter"))

    def test_F18_LLM_NO_ROW_fallback_never_reaches_lane_C(self):
        """The third door of blocking-2. F8 only covers 'the table has no such
        company'; this covers 'the table HAS it, and the content is the omission
        fallback'. An API that dropped the row must not read as 'the model says it
        does not know this company', because that is exactly the volume trigger."""
        c = "ghostly systems"
        prof = {c: {"name": "Ghostly Systems", "kind": "unknown", "tier": 0, "prom": 0,
                    "conf": 0.0, "why": "LLM_NO_ROW", "stage": 0}}
        rows = [{"unique_id": "g%d" % i, "job_title": "Software Engineer", "job_link": "",
                 "company_name": "Ghostly Systems", "_source": "newgrad",
                 "_day": STEADY_DAY, "_recorded": STEADY_DAY + " 09:00"}
                for i in range(40)]
        R = CL.LaneResolver(rows, prof, STEADY_DAY, overrides={}, priority=set())
        self.assertEqual(R.window_count(c), 40)
        self.assertEqual(R.company_lane(c), ("ok", ["not enriched"]))
        self.assertNotEqual(R.segment(rows[0]), "C")

    def test_F18_enricher_fallback_carries_stage_zero(self):
        import enrich_companies as EC
        d = EC.no_row("Ghostly Systems")
        self.assertEqual(d["stage"], 0)
        self.assertEqual(d["why"], "LLM_NO_ROW")

    def test_F18_a_stage1_unknown_with_volume_DOES_reach_lane_C(self):
        """The mirror image: without it, F18 would pass on a resolver that never
        puts anything in lane C at all."""
        c = "loud signal labs"
        prof = {c: {"name": "Loud Signal Labs", "kind": "unknown", "tier": 0, "prom": 0,
                    "why": "no knowledge", "stage": 1}}
        rows = [{"unique_id": "l%d" % i, "job_title": "Software Engineer", "job_link": "",
                 "company_name": "Loud Signal Labs", "_source": "newgrad",
                 "_day": STEADY_DAY, "_recorded": STEADY_DAY + " 09:00"}
                for i in range(40)]
        R = CL.LaneResolver(rows, prof, STEADY_DAY, overrides={}, priority=set())
        self.assertEqual(R.company_lane(c)[0], "inter")


class F14PerRow(unittest.TestCase):
    def _rows_of(self, name):
        c = CL.norm(name)
        return [r for r in _ROWS if CL.norm(r["company_name"]) == c]

    def test_F14_kayak_own_board_rows_are_A(self):
        rows = [r for r in self._rows_of("KAYAK") if r["_source"] == "ats_direct"]
        # _ROWS is the live data/ CSVs, so the count grows whenever the ATS lane
        # picks up another KAYAK posting. Guard that the case still has data;
        # the assertion under test is the segment check below, not the count.
        self.assertTrue(rows, "expected at least one KAYAK ats_direct row")
        for r in rows:
            with self.subTest(title=r["job_title"]):
                R = resolver(r["_day"])
                self.assertIn(R.segment(r), ("1a_t3", "1a_t2"),
                              "KAYAK aggregates flights, not job postings")

    def test_F14_jobgether_newgrad_is_C_and_own_board_is_not(self):
        ng = [r for r in self._rows_of("Jobgether") if r["_source"] == "newgrad"]
        own = [r for r in self._rows_of("Jobgether") if r["_source"] != "newgrad"]
        self.assertTrue(ng and own, "need both a reposted row and an own-board row")
        for r in ng:
            with self.subTest(kind="repost", title=r["job_title"]):
                self.assertEqual(resolver(r["_day"]).segment(r), "C")
        for r in own:
            with self.subTest(kind="own board", title=r["job_title"]):
                self.assertNotEqual(resolver(r["_day"]).segment(r), "C")


class F3F15F16F17Wiring(unittest.TestCase):
    def test_F3_seed_cache(self):
        """680 seed entries, including the 105 paid-for gpt-4o answers. Asserted as a
        superset, not as == 680: enrich_companies.py adds entries every morning, so a
        point value would go red on day two for the healthiest possible reason."""
        if not os.path.exists(SEED_CACHE):
            self.skipTest(
                "seed fixture dashboard_loop/company_profiles.round2.json was "
                "intentionally removed by the dashboard_loop reorg - this test is "
                "skipped, not deleted, in case a substitute seed fixture is added "
                "later")
        seed = json.load(io.open(SEED_CACHE, encoding="utf-8"))
        self.assertEqual(len(seed), 680)
        self.assertGreaterEqual(len(_PROFILES), 680)
        missing = [k for k in seed if k not in _PROFILES]
        self.assertEqual(missing, [], "seed entries lost from company_profiles.json")
        self.assertGreaterEqual(sum(1 for v in seed.values() if v.get("stage") == 2), 100)

    def test_F15_gpt4o_mini_is_priced(self):
        t = LLMCostTracker()
        t.record_usage("gpt-4o-mini", 1_000_000, 1_000_000)
        cost = t.calculate_cost()
        self.assertIsNotNone(cost, "gpt-4o-mini must not report as unpriced")
        self.assertAlmostEqual(cost, 0.15 + 0.60, places=6)
        self.assertTrue(t.get_summary()["priced"])

    def test_F16_dashboard_runs_even_if_daily_report_fails(self):
        """run_daily_report.bat must invoke dashboard.py as its own statement: no &&,
        and no `exit /b` between the two, so a non-zero daily_report cannot skip it."""
        bat = io.open(os.path.join(paths.ROOT, "tasks", "run_daily_report.bat"), encoding="utf-8").read()
        # Match on the script, not the interpreter: the collectors stopped saying
        # `python` when they dropped `conda activate` for "%JOB_PYTHON%".
        def invocation(script):
            # The interpreter line now invokes scripts\<name>.py rather than a bare
            # filename, since the entry scripts moved into scripts/ - the optional
            # directory-prefix group tolerates that without caring which directory.
            m = re.search(r"(?m)^\s*\S*(?:python|PYTHON%\")\S*\s+-u\s+(?:\S*[\\/])?"
                          + re.escape(script), bat)
            self.assertIsNotNone(m, "%s is not invoked in run_daily_report.bat" % script)
            return m.start()
        i = invocation("daily_report.py")
        j = invocation("dashboard.py")
        self.assertLess(i, j)
        between = " ; ".join(l for l in bat[i:j].splitlines()
                             if not l.strip().upper().startswith("REM"))
        self.assertNotIn("&&", between)
        self.assertNotIn("exit /b", between.lower())

    def test_F16_dashboard_does_not_import_daily_report(self):
        src = io.open(os.path.join(paths.ROOT, "scripts", "dashboard.py"), encoding="utf-8").read()
        self.assertNotIn("import daily_report", src)

    def test_F17_daily_report_output_is_byte_identical(self):
        """Zero lines changed on daily_report.py's analysis/render path.

        The baseline is tests/fixtures/, NOT logs/daily/. Two reasons:

        1. logs/daily/*.md is the historical record. This test used to regenerate
           the archive in place and restore it from a copy in `finally`, so a
           killed test run left the record overwritten.
        2. The archive is a snapshot of what the data said on the day it ran. The
           2026-08-22 title-filter backfill removed 31 non-software rows from
           2026-08-19, so the archive (287) and the current data (256) legitimately
           disagree - and the archive must keep saying 287, because that is what
           was collected that day.

        JOB_LOG_ROOT sends daily_report.py's output to a temp tree, so nothing under
        logs/ is touched. 2026-08-19 has no records in runs.jsonl (it already had
        none when the archive was written), so an empty log root reproduces the
        report exactly and the fixture needs no runs.jsonl of its own.

        Regenerate the fixture ONLY when the row set for the day legitimately
        changes (another backfill):
            JOB_LOG_ROOT=<tmp> python -u daily_report.py --date 2026-08-19 --no-prune
            cp <tmp>/daily/2026-08-19.md tests/fixtures/daily_report-2026-08-19.md
        """
        fixture = os.path.join(paths.ROOT, "tests", "fixtures",
                               "daily_report-%s.md" % HARVEST_DAY)
        if not os.path.exists(fixture):
            self.skipTest("no fixture for %s" % HARVEST_DAY)
        expected = io.open(fixture, "rb").read()

        tmp_log_root = tempfile.mkdtemp(prefix="f17-logroot-")
        self.addCleanup(shutil.rmtree, tmp_log_root, True)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", JOB_LOG_ROOT=tmp_log_root)
        p = subprocess.run([sys.executable, "-u",
                            os.path.join("scripts", "daily_report.py"),
                            "--date", HARVEST_DAY, "--no-prune"],
                           cwd=paths.ROOT, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        self.assertEqual(p.returncode, 0, p.stdout.decode("utf-8", "replace"))

        produced = os.path.join(tmp_log_root, "daily", "%s.md" % HARVEST_DAY)
        self.assertTrue(os.path.exists(produced),
                        "daily_report.py ignored JOB_LOG_ROOT: %s"
                        % p.stdout.decode("utf-8", "replace"))
        self.assertEqual(expected, io.open(produced, "rb").read(),
                         "daily_report.py output changed")

    def test_F17_leaves_the_archived_report_alone(self):
        """The guard above must never write into logs/daily/. Regression test for the
        old in-place-regenerate-and-restore approach, which lost the archive whenever
        a test run was killed between the two steps."""
        archived = os.path.join(paths.ROOT, "logs", "daily", "%s.md" % HARVEST_DAY)
        if not os.path.exists(archived):
            self.skipTest("no archived report for %s" % HARVEST_DAY)
        before = io.open(archived, "rb").read()

        self.test_F17_daily_report_output_is_byte_identical()

        self.assertEqual(before, io.open(archived, "rb").read(),
                         "the historical record was modified by a test")


class F9Degraded(unittest.TestCase):
    def test_F9_dashboard_still_renders_after_an_enrichment_timeout(self):
        """Half the table missing = the enrichment run hit its 300 s wall clock. The
        page must still build, and it must say so at the top."""
        keys = sorted(_PROFILES)
        half = {k: _PROFILES[k] for k in keys[:len(keys) // 2]}
        files, state, stats = DASH.build_bundle(STEADY_DAY, _ROWS, half, _OVERRIDES,
                                                _PRIORITY, {})
        page = files["latest.html"]
        self.assertGreater(stats["unenriched"], 0)
        self.assertIn("家未分层", page)
        self.assertIn("%d 家未分层" % stats["unenriched"], page)
        self.assertEqual(sum(stats["raw"].values()), stats["total"])
        self.assertTrue(page.startswith("<!doctype html>"))

    def test_F9_dashboard_renders_with_no_profile_table_at_all(self):
        files, _s, stats = DASH.build_bundle(STEADY_DAY, _ROWS, {}, {}, set(), {})
        self.assertEqual(stats["raw"]["C"], 0)
        self.assertIn("家未分层", files["latest.html"])

    def test_F9_degraded_payload_functions_never_raise(self):
        """view.build_payload / view.window_view are TOTAL, like profile(): the
        unattended 08:00 job must not be able to die inside them."""
        for profiles in ({}, None, {"x": None}):
            pl = VIEW.build_payload(STEADY_DAY, _ROWS, profiles, {}, set(), {})
            for n in VIEW.N_CHOICES:
                for v in VIEW.VIEWS:
                    self.assertEqual(sum(VIEW.window_view(pl, n, v)["raw"]),
                                     VIEW.window_view(pl, n, v)["dedup"])
        empty = VIEW.build_payload(STEADY_DAY, [], {}, {}, set(), {})
        self.assertEqual(VIEW.window_view(empty, 3)["dedup"], 0)
        self.assertEqual(VIEW.window_view({}, 3)["dedup"], 0)
        self.assertEqual(VIEW.open_expected({}), 0)
        self.assertEqual(VIEW.carry_seq({}, 3), ([], []))

    def test_F9_the_banner_promise_is_self_guarding(self):
        """The banner tells the reader the unclassified companies will be picked up
        by tomorrow morning's 07:30 enrich_companies.py run. That promise is only
        true for a company seen for the FIRST time on the anchor day: one that has
        been sitting in the window for three days has already been through two
        enrichment runs and did not come back, so "wait for tomorrow" would be the
        wrong thing to tell somebody.

        Measured 2026-08-21: 98 companies counted, 0 of them first seen earlier.
        What is asserted is the IMPLICATION, not the 0 - the day a company starts
        lingering this goes red and the wording gets conditioned, instead of the
        page quietly making a promise it cannot keep."""
        p = payload(ANCHOR_DAY)
        health = p["index"]["health"]
        window = set(VIEW.days_back(ANCHOR_DAY, VIEW.N_DEFAULT))
        R = resolver(ANCHOR_DAY)
        seen = {}
        for r in _ROWS:
            if r["_day"] in window:
                seen.setdefault(CL.norm(r["company_name"]), True)
        counted = [c for c in seen if R.profile(c).get("stage", 0) < 1]
        self.assertEqual(len(counted), health["unenriched"],
                         "the banner counts a different set than this fixture does")
        first_seen = {}
        for r in _ROWS:
            c = CL.norm(r["company_name"])
            if c not in first_seen or r["_day"] < first_seen[c]:
                first_seen[c] = r["_day"]
        lingering = sorted(c for c in counted if first_seen[c] != ANCHOR_DAY)
        files, _s, _st = DASH.build_bundle(ANCHOR_DAY, _ROWS, _PROFILES, _OVERRIDES,
                                           _PRIORITY, _STATE)
        page = files["latest.html"]
        if lingering:
            self.assertNotIn(
                "等明早", page,
                "%d of the %d companies in the banner were already there before %s "
                "(e.g. %r) - tomorrow's 07:30 run has already failed to classify "
                "them, so the banner must stop promising it will"
                % (len(lingering), len(counted), ANCHOR_DAY, lingering[:5]))
        elif counted:
            self.assertIn("等明早", page)

    def test_F9_build_compat_shell_still_returns_the_page(self):
        """dashboard.build() keeps the exact signature this file has always used."""
        page, _s, stats = DASH.build(STEADY_DAY, _ROWS, _PROFILES, _OVERRIDES,
                                     _PRIORITY, {})
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertEqual(sum(stats["raw"].values()), stats["total"])

    def test_dashboard_has_no_external_dependency(self):
        """R4 means there IS a <script src> now, so the v1 body ("no <script> tag")
        would be asserting the wrong thing. The real invariant - offline, double
        click, no build step - is not relaxed by one inch: assert_offline() below
        was tried against six concrete attacks and caught all six."""
        files, _s, _st = DASH.build_bundle(STEADY_DAY, _ROWS, _PROFILES, _OVERRIDES,
                                           _PRIORITY, {})
        self.assertTrue(assert_offline(files))
        page = files["latest.html"]
        self.assertNotIn("cdn.", page)
        self.assertIn("prefers-color-scheme", files["dashboard.css"])
        self.assertIn("a:visited", files["dashboard.css"])
        self.assertIn("<details", page)

    def test_assert_offline_catches_the_six_ways_in(self):
        """A guard nobody has tried to break is an empty assertion."""
        good = {"latest.html": '<!doctype html><html><head>'
                               '<link rel="stylesheet" href="dashboard.css">'
                               '<script src="data-2026-08-21.js"></script>'
                               '<script src="dashboard.js"></script></head>'
                               '<body><details id="seg-x"></details></body></html>',
                "dashboard.css": "@media (prefers-color-scheme: dark){} a:visited{color:red}",
                "dashboard.js": 'var s=document.createElement("script");'
                                's.src=IDX.chunk[k];document.head.appendChild(s);',
                "data-index.js": 'window.JOB_INDEX={"v":2};',
                "data-2026-08-21.js":
                    '(window.JOB_DAY=window.JOB_DAY||{})["2026-08-21"]='
                    '{"n":1,"t":["Engineer, WebSockets and fetch("]};'}
        self.assertTrue(assert_offline(good))
        attacks = {
            "cdn script": dict(good, **{"latest.html": good["latest.html"].replace(
                'src="dashboard.js"', 'src="https://cdn.example.com/x.js"')}),
            "google fonts": dict(good, **{"latest.html": good["latest.html"].replace(
                'href="dashboard.css"', 'href="https://fonts.googleapis.com/css"')}),
            "es module": dict(good, **{"latest.html": good["latest.html"].replace(
                '<script src="dashboard.js">', '<script type="module" src="dashboard.js">')}),
            "fetch": dict(good, **{"dashboard.js": good["dashboard.js"] + "fetch('x');"}),
            "absolute chunk": dict(good, **{"dashboard.js":
                'var s=document.createElement("script");s.src="https://x/"+d+".js";'}),
            "parent dir": dict(good, **{"latest.html": good["latest.html"].replace(
                'href="dashboard.css"', 'href="../shared/dashboard.css"')}),
            "code smuggled into a data block": dict(good, **{"data-2026-08-21.js":
                '(window.JOB_DAY=window.JOB_DAY||{})["2026-08-21"]={};fetch("x");'}),
        }
        for label, files in attacks.items():
            with self.subTest(attack=label):
                self.assertRaises(AssertionError, assert_offline, files)


class F1F2Enrichment(unittest.TestCase):
    LIVE = os.environ.get("JOB_TEST_LLM") == "1"

    def test_F1_full_enrichment_drops_no_rows(self):
        if not self.LIVE:
            self.skipTest("needs a live full enrichment pass; P0 starts from the "
                          "paid-for gpt-4o cache. Set JOB_TEST_LLM=1 to run.")
        import enrich_companies as EC
        self.assertEqual(EC.main(["--all"]), 0)

    def test_F2_full_enrichment_wall_and_cost(self):
        if not self.LIVE:
            self.skipTest("needs a live full enrichment pass. Set JOB_TEST_LLM=1.")
        import enrich_companies as EC
        t0 = datetime.now()
        self.assertEqual(EC.main(["--all"]), 0)
        self.assertLess((datetime.now() - t0).total_seconds(), 300)

    def test_F2_wall_budget_is_wired(self):
        """Runs without the API: the 300 s budget must exist and be enforced."""
        import enrich_companies as EC
        self.assertEqual(EC.WALL_BUDGET_S, 300.0)
        self.assertEqual(EC.BATCH, 20)
        self.assertEqual(EC.STAGE1_MODEL, "gpt-4o-mini")
        self.assertEqual(EC.STAGE2_MODEL, "gpt-4o-mini")
        self.assertEqual(EC.DEEP_MODEL, "gpt-4o")
        self.assertEqual(len(EC.ANCHORS), 5)
        self.assertIn("JSON", EC.INSTR)          # json_object mode 400s without it
        # every batch of 20 targets carries all 5 anchors
        chunk, merged = EC.make_batches(["C%d" % i for i in range(20)])[0]
        self.assertEqual(len(chunk), 20)
        self.assertEqual(len(merged), 25)
        for a in EC.ANCHORS:
            self.assertIn(a, merged)

    def test_atomic_write_is_used_for_the_cache(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "x.json")
            CL.atomic_write_json(p, {"a": 1})
            self.assertEqual(json.load(io.open(p, encoding="utf-8")), {"a": 1})
            self.assertEqual([f for f in os.listdir(d) if f.startswith(".tmp_")], [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_no_module_shadows_the_stdlib(self):
        """A file called queue.py on sys.path breaks the openai -> httpcore ->
        trio import chain. Two people have burned time on it.

        The reorg put two directories on sys.path: scripts/, which Python makes
        sys.path[0] for every entry point, and src/, which the editable install
        adds. The repo root itself is on neither, so checking it proves nothing."""
        import queue as stdlib_queue
        self.assertTrue(hasattr(stdlib_queue, "SimpleQueue"))
        for d in ("scripts", "src"):
            for name in ("queue.py", "json.py", "types.py", "csv.py", "html.py", "logging.py"):
                self.assertFalse(os.path.exists(os.path.join(paths.ROOT, d, name)),
                                 "%s/%s shadows the stdlib" % (d, name))


# ---------------------------------------------------------------- v2 helpers
def assert_offline(files):
    """The real "zero external dependency" invariant, now that R4 means the bundle
    legitimately contains <script src> and <link href>.

    v1 asserted `"<script" not in page`, which happened to imply offline-ness only
    because v1 had no JS at all. These five clauses assert the property itself, and
    test_assert_offline_catches_the_six_ways_in tries to get past them.
    """
    page = files["latest.html"]
    # a) ES modules go through CORS and are blocked under file:// (measured)
    assert 'type="module"' not in page and "type='module'" not in page, "ES module"
    for name, txt in files.items():
        if name.endswith(".html"):
            continue
        assert not re.search(r"^\s*import\s+[\w{*]", txt, re.M), "%s imports" % name
        assert not re.search(r"^\s*export\s", txt, re.M), "%s exports" % name
    # b) every reference in the shell is same-directory and relative
    for m in re.finditer(r'\b(?:src|href)\s*=\s*"([^"]*)"', page):
        u = m.group(1)
        if u.startswith("#"):
            continue
        assert "://" not in u, "external reference in the shell: %r" % u
        assert not u.startswith("/") and ".." not in u, "not same-dir: %r" % u
    # c) the DATA files must be pure data - one assignment of one JSON literal.
    #    This is checked first and it is what makes (d) safe to scope: a job title
    #    reading "React | TypeScript | WebSockets" exists in the real corpus, so a
    #    substring scan over the data blocks is a false positive waiting to happen
    #    (it fired on 2026-08-21). Parsing the literal is the stronger statement:
    #    a JSON string cannot call anything.
    def pure_json(name, body):
        try:
            json.loads(body.rstrip().rstrip(";"))
        except Exception as e:
            raise AssertionError("%s is not one pure JSON literal (%s)" % (name, e))

    code = {}
    for name, txt in files.items():
        if not name.endswith(".js"):
            continue
        if name == "data-index.js":
            head = "window.JOB_INDEX="
            assert txt.startswith(head), "data-index.js is not a plain assignment"
            pure_json(name, txt[len(head):])
        elif name.startswith("data-"):
            m = re.match(r'^\(window\.JOB_DAY=window\.JOB_DAY\|\|\{\}\)'
                         r'\["\d{4}-\d{2}-\d{2}"\]=', txt)
            assert m, "%s is not a plain assignment" % name
            pure_json(name, txt[m.end():])
        else:
            code[name] = txt
    # d) no network API anywhere in the JS that is actually code
    for name, txt in code.items():
        for bad in ("fetch(", "XMLHttpRequest", "WebSocket", "importScripts",
                    "EventSource", "navigator.sendBeacon"):
            assert bad not in txt, "%s uses %s" % (name, bad)
        # and the dynamically injected chunk name never becomes an absolute URL
        for m in re.finditer(r"\.src\s*=\s*([^;\n]+)", txt):
            assert "://" not in m.group(1), "%s injects an absolute URL" % name
    assert code, "no code JS in the bundle at all"
    # e) what v1 promised the reader and v2 still owes them
    assert "prefers-color-scheme" in files.get("dashboard.css", ""), "no dark mode"
    assert "a:visited" in files.get("dashboard.css", ""), "no visited colour"
    assert "<details" in page, "no native disclosure"
    return True


def find_chromium():
    """Chrome only. Edge headless produces 0 bytes on this machine (three flag
    spellings tried), which is exactly why the double-click check stays a manual
    acceptance item instead of being folded into this file."""
    for cand in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(cand):
            return cand
    for n in ("chrome", "chromium", "chromium-browser", "google-chrome"):
        w = shutil.which(n)
        if w:
            return w
    return None


def dump_dom(exe, url, budget=30000):
    prof = tempfile.mkdtemp(prefix="dashprof_")
    try:
        r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--user-data-dir=" + prof,
                            "--virtual-time-budget=%d" % budget, "--dump-dom", url],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        return r.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def bundle_dir(day, into):
    files, _s, _st = DASH.build_bundle(day, _ROWS, _PROFILES, _OVERRIDES,
                                       _PRIORITY, _STATE)
    DASH.write_bundle(into, files)
    return files


class F20F21Payload(unittest.TestCase):
    """The serialisation itself. Once rendering moved to the browser, "the CSV row
    made it into the file the browser reads" stopped having anybody watching it."""

    def test_F20_no_row_is_lost_on_the_way_into_the_payload(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            p = payload(day)
            idx = p["index"]
            total = 0
            for i, d in enumerate(idx["days"]):
                expect = len(coord_rows(d))
                cols = p["days"].get(d)
                with self.subTest(day=day, block=d):
                    self.assertEqual(idx["nrows"][i], expect)
                    if expect:
                        self.assertIsNotNone(cols, "block %s never written" % d)
                        self.assertEqual(cols["n"], expect)
                        self.assertEqual(cols["d"], i)
                        for k in ("c", "g", "t", "lp", "l", "s", "r", "x"):
                            self.assertEqual(len(cols[k]), expect,
                                             "column %s of %s is ragged" % (k, d))
                        self.assertEqual(idx["chunk"][i], "data-%s.js" % d)
                    else:
                        self.assertIsNone(cols)
                        self.assertEqual(idx["chunk"][i], "")
                total += expect
            self.assertEqual(sum(idx["nrows"]), total)
            self.assertEqual(sum(c["n"] for c in p["days"].values()), total)
            in_window = [r for r in _ROWS if r["_day"] in set(idx["days"])]
            self.assertEqual(len(in_window), total,
                             "the payload and the CSVs disagree about the window")

    def test_F21_the_window_never_shows_the_same_job_twice(self):
        """And the scope of `x` is `_day <= day`, not global. Computing it globally
        lets a row recorded tomorrow supersede a row inside today's window, and the
        window then quietly loses it - the last assertion is what catches that."""
        for day in (HARVEST_DAY, STEADY_DAY):
            p = payload(day)
            idx = p["index"]
            per_day = {d: coord_rows(d) for d in idx["days"]}
            for n in VIEW.N_CHOICES:
                wdays = idx["days"][max(0, len(idx["days"]) - n):]
                keys = []
                for d in wdays:
                    cols = p["days"].get(d)
                    if not cols:
                        continue
                    for i, x in enumerate(cols["x"]):
                        if x:
                            continue
                        r = per_day[d][i]
                        keys.append((CL.norm(r["company_name"]),
                                     CL.tnorm(r["job_title"])))
                distinct = {(CL.norm(r["company_name"]), CL.tnorm(r["job_title"]))
                            for r in _ROWS if r["_day"] in set(wdays)}
                with self.subTest(day=day, n=n):
                    self.assertEqual(len(set(keys)), len(keys),
                                     "the same job survives twice in the window")
                    self.assertEqual(len(keys), VIEW.window_view(p, n)["dedup"])
                    self.assertEqual(len(keys), len(distinct),
                                     "x was not computed on the `_day <= %s` scope: "
                                     "%d survivors for %d distinct jobs"
                                     % (day, len(keys), len(distinct)))


class F22F28Check(unittest.TestCase):
    """`check` is the only truth the browser has. It has to be asserted here or the
    guard on I1 is worth nothing once rendering lives in JS."""

    def test_F22_check_is_exactly_window_view(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            p = payload(day)
            for f in VIEW.VIEWS:
                for n in VIEW.N_CHOICES:
                    with self.subTest(day=day, view=f, n=n):
                        self.assertEqual(p["index"]["check"][f][str(n)],
                                         VIEW.window_view(p, n, f))

    def test_F22_check_survives_the_json_round_trip(self):
        p = payload(STEADY_DAY)
        txt = VIEW.encode_index(p["index"])
        self.assertTrue(txt.startswith("window.JOB_INDEX="))
        back = json.loads(txt[len("window.JOB_INDEX="):].rstrip().rstrip(";"))
        self.assertEqual(back["check"], p["index"]["check"])
        self.assertEqual(back["v"], 2)
        for f in VIEW.VIEWS:
            for n in VIEW.N_CHOICES:
                c = back["check"][f][str(n)]
                for k in ("dedup", "raw", "cap2", "plan", "open", "bars", "head",
                          "anchors", "hsum", "osum", "w7_days"):
                    self.assertIn(k, c)

    def test_F28_every_view_and_window_satisfies_I1(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            chk = payload(day)["index"]["check"]
            for n in VIEW.N_CHOICES:
                base = chk[VIEW.VIEWS[0]][str(n)]
                for f in VIEW.VIEWS:
                    c = chk[f][str(n)]
                    with self.subTest(day=day, view=f, n=n):
                        self.assertEqual(sum(c["raw"]), c["dedup"])
                        self.assertEqual(sum(c["bars"]), c["dedup"])
                        self.assertLessEqual(c["dedup"], base["dedup"],
                                             "a filtered view cannot show MORE rows "
                                             "than the unfiltered one")
                        self.assertEqual(len(c["raw"]), len(CL.SEGMENT_ORDER))
                        self.assertEqual(len(c["bars"]), len(payload(day)["index"]["days"]))


class F23DivisionOfLabour(unittest.TestCase):
    """The line between "Python decides" and "JS frames" was a convention in v1.
    This turns it into a mechanism."""

    WORDS = ["tier", "prom", "stage", "kind", "staffing", "outsourcing", "job_board",
             "new grad", "entry level", "tnorm", "1a_t3", "1a_t2"]

    def _source(self):
        with io.open(os.path.join(paths.ROOT, "web", "dashboard.js"), encoding="utf-8") as fh:
            src = fh.read()
        return re.sub(r"/\*.*?\*/", " ", src, flags=re.S)

    def test_F23_no_judgement_vocabulary_in_dashboard_js(self):
        body = self._source().lower()
        for w in self.WORDS:
            with self.subTest(word=w):
                self.assertNotIn(w, body,
                                 "web/dashboard.js mentions %r - the judgement layer "
                                 "is leaking into the browser" % w)

    def test_F23_no_hardcoded_segment_order_array(self):
        """The other four segment keys (1b / B1 / B2 / C) are too generic to
        blacklist one by one, so this goes after the SHAPE instead."""
        body = self._source()
        m = re.search(r"""[\[\(]\s*(?:"|')1a_t3(?:"|')""", body)
        self.assertIsNone(m, "the segment order is hardcoded in dashboard.js")
        self.assertIn("data-gidx", body,
                      "segments must be located by index, not by name")

    def test_F23_the_shell_is_what_carries_the_segment_ids(self):
        files, _s, _st = DASH.build_bundle(STEADY_DAY, _ROWS, _PROFILES, _OVERRIDES,
                                           _PRIORITY, {})
        page = files["latest.html"]
        for g, seg in enumerate(CL.SEGMENT_ORDER):
            with self.subTest(segment=seg):
                self.assertIn('id="seg-%s" data-gidx="%d"' % (seg, g), page)


class F25F26Plumbing(unittest.TestCase):
    def test_F25_the_two_seven_days_never_get_mixed(self):
        """One "7 days" is the fixed judgement window (invariant I4); the other is
        whatever N the reader picked. The header text is built from the first one so
        the number and the words cannot drift apart."""
        p = payload(STEADY_DAY)
        self.assertEqual(p["index"]["w7_days"], CL.WINDOW_DAYS)
        for f in VIEW.VIEWS:
            for n in VIEW.N_CHOICES:
                self.assertEqual(p["index"]["check"][f][str(n)]["w7_days"],
                                 CL.WINDOW_DAYS)
        files, _s, _st = DASH.build_bundle(STEADY_DAY, _ROWS, _PROFILES, _OVERRIDES,
                                           _PRIORITY, {})
        self.assertIn("近 %d 天" % CL.WINDOW_DAYS, files["latest.html"])

    def test_F26_retention_bounds_the_output_directory(self):
        d = tempfile.mkdtemp(prefix="dashout_")
        try:
            keep = 3
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                for day in (HARVEST_DAY, STEADY_DAY):
                    self.assertEqual(DASH.main(["--date", day, "--no-watermark",
                                                "--out", d, "--retain", str(keep)]), 0)
            names = os.listdir(d)
            blocks = [f for f in names if re.match(r"^data-\d{4}-\d{2}-\d{2}\.js$", f)]
            self.assertTrue(blocks)
            self.assertLessEqual(len(blocks), keep,
                                 "the output directory grows without bound: %r" % blocks)
            self.assertEqual([f for f in names
                              if re.match(r"^\d{4}-\d{2}-\d{2}\.html$", f)], [],
                             "v2 must not write a per-day HTML page")
            for must in ("latest.html", "dashboard.css", "dashboard.js", "data-index.js"):
                self.assertIn(must, names)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_F26_out_never_deletes_a_file_the_user_put_there(self):
        """The data-block retention runs everywhere, but the leftover-v1-page
        cleanup runs only in the DEFAULT output directory. --out is a path the
        caller chose; removing a file there because its name looks like a date is
        not reversible, and the "no <day>.html" requirement is about
        logs/dashboard/ alone."""
        d = tempfile.mkdtemp(prefix="dashkeep_")
        try:
            keepers = ["2020-01-01.html", "notes.html", "2020-01-01.txt"]
            for k in keepers:
                with io.open(os.path.join(d, k), "w", encoding="utf-8") as f:
                    f.write("mine")
            stale = os.path.join(d, "data-1999-12-31.js")
            with io.open(stale, "w", encoding="utf-8") as f:
                f.write("stale")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(DASH.main(["--date", STEADY_DAY, "--no-watermark",
                                            "--out", d, "--retain", "3"]), 0)
            names = os.listdir(d)
            for k in keepers:
                self.assertIn(k, names, "--out deleted %s, which it did not write" % k)
            with io.open(os.path.join(d, "2020-01-01.html"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "mine")
            self.assertNotIn("data-1999-12-31.js", names,
                             "the data-block retention must still run under --out")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class F27DedupCanary(unittest.TestCase):
    """A3: v1 had two dedup rules alive at once (day-scoped first-come for the trend
    bars, window-scoped keep-NEWEST for everything else) and their agreement was a
    property of this corpus, not of the code. v2 has one rule. This canary watches
    the old one so that the day they part company somebody hears about it, instead
    of two test suites quietly measuring two different things.

    NOTE, and it is the reason this asserts what it asserts: the two rules ALREADY
    pick different physical rows (measured: 14 + 27 + 4 = 45 groups). What is
    currently a coincidence is that they never disagree about the SEGMENT, and that
    is precisely the coincidence F6/F7/F19 rest on. So the canary asserts the same
    jobs and the same segments, and reports the physical-row drift for a human."""

    def test_F27_the_old_day_rule_still_covers_the_same_jobs(self):
        drift = {}
        for d in sorted({r["_day"] for r in _ROWS}):
            old = CL.day_rows(_ROWS, d)
            sup = VIEW.superseded_flags([r for r in _ROWS if r["_day"] <= d], d)
            new = [r for r in _ROWS if r["_day"] == d and sup.get(id(r), 1) == 0]
            R = resolver(d)
            k_old = {(CL.norm(r["company_name"]), CL.tnorm(r["job_title"])): R.segment(r)
                     for r in old}
            k_new = {(CL.norm(r["company_name"]), CL.tnorm(r["job_title"])): R.segment(r)
                     for r in new}
            drift[d] = len({id(r) for r in old} ^ {id(r) for r in new}) // 2
            with self.subTest(day=d):
                self.assertEqual(len(old), len(new),
                                 "the two dedup rules keep a different NUMBER of rows")
                self.assertEqual(set(k_old), set(k_new),
                                 "the two dedup rules cover different jobs now")
                disagree = sorted(k for k in k_old if k_old[k] != k_new[k])
                self.assertEqual(disagree, [],
                                 "the two dedup rules now put the same job in "
                                 "different segments: %r" % disagree[:5])
        self.assertTrue(drift)


class F29Checksum(unittest.TestCase):
    """A6: the per-segment checksum is the only thing covering the ~99% of folded
    rows that three sampled anchors miss. If it is not identical on both sides, or
    not sensitive to order, the sixth reconciliation is decoration."""

    def _sequences(self, day=STEADY_DAY):
        p = payload(day)
        out = {}
        for f in VIEW.VIEWS:
            for n in VIEW.N_CHOICES:
                _raw, _bars, heads, overs = VIEW.segment_rows(p, n, f)
                for g in range(len(CL.SEGMENT_ORDER)):
                    out["%s|%d|%d|h" % (f, n, g)] = heads[g]
                    out["%s|%d|%d|o" % (f, n, g)] = overs[g]
        return out

    def test_F29a_python_and_the_shipped_js_agree_bit_for_bit(self):
        exe = find_chromium()
        if not exe:
            self.skipTest("no Chromium on this machine")
        with io.open(os.path.join(paths.ROOT, "web", "dashboard.js"), encoding="utf-8") as fh:
            src = fh.read()
        m_mix = re.search(r"function mix\(h, v\) \{[^}]*\}", src)
        m_seq = re.search(r"function seqHash\(pairs\) \{.*?\n  \}", src, re.S)
        self.assertIsNotNone(m_mix, "mix() not found in web/dashboard.js")
        self.assertIsNotNone(m_seq, "seqHash() not found in web/dashboard.js")
        seqs = self._sequences()
        d = tempfile.mkdtemp(prefix="dashsum_")
        try:
            with io.open(os.path.join(d, "seq.js"), "w", encoding="utf-8") as fh:
                fh.write("window.SEQ=" + json.dumps(seqs, separators=(",", ":")) + ";")
            with io.open(os.path.join(d, "h.html"), "w", encoding="utf-8") as fh:
                fh.write(
                '<!doctype html><html><head><meta charset="utf-8"></head><body>'
                '<pre id="out">PENDING</pre><script src="seq.js"></script><script>'
                + m_mix.group(0) + "\n" + m_seq.group(0) + "\n"
                + 'var R={};for(var k in window.SEQ){R[k]=seqHash(window.SEQ[k]);}'
                  'document.getElementById("out").textContent=JSON.stringify(R);'
                  "</script></body></html>")
            dom = dump_dom(exe, "file:///" + os.path.join(d, "h.html").replace("\\", "/"))
        finally:
            shutil.rmtree(d, ignore_errors=True)
        if not dom.strip():
            self.skipTest("headless browser produced no DOM")
        mm = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        self.assertIsNotNone(mm, dom[:400])
        js = json.loads(mm.group(1))
        self.assertEqual(len(js), len(seqs))
        bad = [k for k in seqs if js.get(k) != VIEW.seq_hash(seqs[k])]
        self.assertEqual(bad, [], "Python and JS checksums disagree on %d cells"
                         % len(bad))

    def test_F29b_the_checksum_moves_whenever_the_sequence_moves(self):
        rnd = random.Random(20260821)
        seqs = [v for v in self._sequences().values() if len(v) >= 2]
        self.assertTrue(seqs)
        trials = missed = 0
        for seq in seqs:
            base = VIEW.seq_hash(seq)
            for _ in range(20):
                a, b = rnd.sample(range(len(seq)), 2)
                if seq[a] == seq[b]:
                    continue
                q = list(seq)
                q[a], q[b] = q[b], q[a]
                trials += 1
                missed += (VIEW.seq_hash(q) == base)
            for a in range(min(len(seq) - 1, 150)):       # adjacent: the hardest case
                if seq[a] == seq[a + 1]:
                    continue
                q = list(seq)
                q[a], q[a + 1] = q[a + 1], q[a]
                trials += 1
                missed += (VIEW.seq_hash(q) == base)
            for a in rnd.sample(range(len(seq)), min(8, len(seq))):
                trials += 2
                missed += (VIEW.seq_hash(seq[:a] + seq[a + 1:]) == base)
                missed += (VIEW.seq_hash(seq[:a] + [seq[a]] + seq[a:]) == base)
        self.assertGreater(trials, 2000, "not enough mutations to mean anything")
        self.assertEqual(missed, 0,
                         "%d of %d disturbed sequences kept the same checksum"
                         % (missed, trials))

    def test_F29c_cross_day_groups_match_the_full_timestamp_oracle(self):
        """A9. hsum/osum only prove Python and JS agree; they cannot prove either is
        right, because a wrong ordering key is wrong identically on both sides. This
        asserts the ordering against an EXTERNAL oracle - the full `_recorded`
        string - on the groups where the two readings differ: rows spanning days."""
        day = STEADY_DAY
        p = payload(day)
        idx = p["index"]
        per_day = {d: coord_rows(d) for d in idx["days"]}
        checked = 0
        for n in (VIEW.N_CHOICES[-1],):
            _raw, _bars, heads, overs = VIEW.segment_rows(p, n, "all")
            for g, seg in enumerate(CL.SEGMENT_ORDER):
                everything, head_of = {}, {}
                for coord in list(heads[g]) + list(overs[g]):
                    r = per_day[idx["days"][coord[0]]][coord[1]]
                    everything.setdefault(CL.norm(r["company_name"]), []).append((coord, r))
                for coord in heads[g]:
                    r = per_day[idx["days"][coord[0]]][coord[1]]
                    head_of.setdefault(CL.norm(r["company_name"]), []).append(list(coord))
                for c, items in everything.items():
                    if len({x[0][0] for x in items}) < 2:
                        continue                      # single-day group: no ambiguity
                    oracle = sorted(items,
                                    key=lambda z: ((z[1].get("_recorded") or ""),
                                                   (z[1].get("job_title") or ""),
                                                   z[0][1]),
                                    reverse=True)
                    want = [list(x[0]) for x in oracle[:VIEW.CAP]]
                    with self.subTest(segment=seg, company=c):
                        self.assertEqual(head_of.get(c), want,
                                         "cap-2 head of a cross-day group does not "
                                         "match ordering by the full timestamp")
                    checked += 1
        self.assertGreater(checked, 0,
                           "no company spans two days in this corpus - the assertion "
                           "would be vacuous")


class F24Browser(unittest.TestCase):
    """L3. The one end-to-end assertion the JS side has: a real browser, a real
    file:// URL, the real bundle. Its structural limit is that it runs the same
    reconciliation code the page runs, so a reconciliation written backwards would
    agree with itself - which is why the deliberate-breakage pass stays a manual
    acceptance step."""

    def test_F24_headless_browser_reports_all_cells_ok(self):
        exe = find_chromium()
        if not exe:
            self.skipTest("no Chromium on this machine")
        d = tempfile.mkdtemp(prefix="dashbundle_")
        try:
            bundle_dir(STEADY_DAY, d)
            url = ("file:///" + os.path.join(d, "latest.html").replace("\\", "/")
                   + "#selfcheck")
            dom = dump_dom(exe, url)
            if not dom.strip():
                self.skipTest("headless browser produced no DOM")
            m = re.search(r'<pre id="selfcheck"[^>]*>(.*?)</pre>', dom, re.S)
            self.assertIsNotNone(m, "no #selfcheck output: %s" % dom[:400])
            txt = m.group(1)
            data = json.loads(txt[txt.index("{"):])
            cells = 0
            for f in VIEW.VIEWS:
                for n in VIEW.N_CHOICES:
                    cell = data[f][str(n)]
                    with self.subTest(view=f, n=n):
                        self.assertTrue(cell["ok"], "%s/%s failed: %r"
                                        % (f, n, cell.get("why")))
                    cells += 1
            self.assertEqual(cells, len(VIEW.VIEWS) * len(VIEW.N_CHOICES))
            self.assertIn("SELFCHECK ok", txt)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_F24_a_broken_check_really_does_light_the_banner(self):
        """The mirror image, and the only thing that keeps the test above from
        passing on a page whose reconciliation never fires: corrupt one number in
        `check` and the red banner must appear."""
        exe = find_chromium()
        if not exe:
            self.skipTest("no Chromium on this machine")
        d = tempfile.mkdtemp(prefix="dashbroken_")
        try:
            bundle_dir(STEADY_DAY, d)
            path = os.path.join(d, "data-index.js")
            with io.open(path, encoding="utf-8") as fh:
                txt = fh.read()
            head = "window.JOB_INDEX="
            obj = json.loads(txt[len(head):].rstrip().rstrip(";"))
            obj["check"][VIEW.VIEWS[0]][str(VIEW.N_DEFAULT)]["cap2"][0] += 1
            with io.open(path, "w", encoding="utf-8") as fh:
                fh.write(head + json.dumps(obj, ensure_ascii=False,
                                           separators=(",", ":")) + ";")
            dom = dump_dom(exe, "file:///" + os.path.join(d, "latest.html").replace("\\", "/"))
            if not dom.strip():
                self.skipTest("headless browser produced no DOM")
            m = re.search(r'<div id="recon"([^>]*)>(.*?)</div>\s*\n', dom, re.S)
            self.assertIsNotNone(m)
            self.assertNotIn("hidden", m.group(1),
                             "cap2 was corrupted and the reconciliation stayed quiet")
            self.assertIn("cap2", m.group(2))
        finally:
            shutil.rmtree(d, ignore_errors=True)


def _manual_signoff():
    """Not an assertion. The item that replaced the deleted F13."""
    R = resolver(STEADY_DAY)
    rows = [r for r in CL.day_rows(_ROWS, STEADY_DAY) if R.segment(r) == "1a_t3"]
    groups = DASH.group_segment(R, rows)
    head, _over = DASH.split_cap(groups)
    print("\n--- manual sign-off (replaces the deleted F13): segment 1, first 20 ---")
    for c, r in head[:20]:
        v = R.profile(c)
        print("   [T%d p%3d] %-26s | %s" % (v["tier"], v["prom"],
                                            (v.get("name") or c)[:26],
                                            (r.get("job_title") or "")[:58]))
    print("   read them: are they all genuinely new-grad / entry-level roles?")
    for day in (HARVEST_DAY, STEADY_DAY):
        raw, cap2, total = segment_counts(day)
        print("\n%s  raw total %d == deduped %d" % (day, sum(raw.values()), total))
        for s in CL.SEGMENT_ORDER:
            print("   %-6s raw %4d  cap2 %4d" % (s, raw[s], cap2[s]))
        print("   default visible (1+4) = %d" % (cap2["1a_t3"] + cap2["B1"]))


if __name__ == "__main__":
    r = unittest.main(exit=False, verbosity=2)
    _manual_signoff()
    sys.exit(0 if r.result.wasSuccessful() else 1)
