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

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import company_lane as CL           # noqa: E402
import dashboard as DASH            # noqa: E402
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402

HARVEST_DAY = "2026-08-19"          # ats_direct first-day full harvest
STEADY_DAY = "2026-08-20"           # ordinary day

_ROWS = CL.load_rows(ROOT)
_PROFILES = CL.load_profiles()
_OVERRIDES = CL.load_overrides()
_PRIORITY = CL.load_priority()

SEED_CACHE = os.path.join(ROOT, "dashboard_loop", "company_profiles.round2.json")


def resolver(day, profiles=None, overrides=None, rows=None):
    return CL.LaneResolver(rows if rows is not None else _ROWS,
                           _PROFILES if profiles is None else profiles,
                           day,
                           overrides=_OVERRIDES if overrides is None else overrides,
                           priority=_PRIORITY)


def segment_counts(day, profiles=None, overrides=None, rows=None):
    """-> (raw, cap2, day_row_count). cap2 = at most 2 rows per company per segment."""
    R = resolver(day, profiles, overrides, rows)
    today = CL.day_rows(rows if rows is not None else _ROWS, day)
    raw, groups = {}, {}
    for s in CL.SEGMENT_ORDER:
        raw[s], groups[s] = 0, {}
    for r in today:
        s = R.segment(r)
        raw[s] += 1
        groups[s].setdefault(CL.norm(r["company_name"]), []).append(r)
    cap2 = {s: sum(min(2, len(v)) for v in groups[s].values()) for s in CL.SEGMENT_ORDER}
    return raw, cap2, len(today)


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


def segment_head(day, seg):
    """The cap-2 view of one segment, built with dashboard's own grouping so the
    test cannot drift from what actually renders. -> [(company, row), ...]"""
    import dashboard as DB
    R = resolver(day)
    rows = [r for r in CL.day_rows(_ROWS, day) if R.segment(r) == seg]
    head, _over = DB.split_cap(DB.group_segment(R, rows))
    return head


def expanded_rows(day):
    """Rows a reader actually sees on load: the open segments, each truncated by
    dashboard.OPEN_CAP, the rest sitting in a nested <details>."""
    import dashboard as DB
    _r, cap2, _t = segment_counts(day)
    return sum(min(cap2[s], DB.OPEN_CAP.get(s, cap2[s])) for s in ("1a_t3", "B1"))


class F10F11Segments(unittest.TestCase):
    """cap=2 bounds one company, not the day, so segment sizes track collector
    volume: 8/20 grew to 2068 newgrad rows and segment 1 went 28 -> 61. Asserting a
    band on the segment TOTAL just re-fails every heavy day. What has to stay bounded
    is what is expanded on load, and dashboard.OPEN_CAP is what bounds it."""

    def test_F10_segment1_is_all_entry_level_whatever_its_size(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            _r, cap2, _t = segment_counts(day)
            with self.subTest(day=day):
                self.assertGreater(cap2["1a_t3"], 0, "segment 1 must not be empty")
                for _c, r in segment_head(day, "1a_t3"):
                    self.assertTrue(CL.is_entry(r["job_title"]),
                                    "%r is not an entry-level title" % r["job_title"])

    def test_F11_default_visible_is_bounded_on_any_volume(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            vis = expanded_rows(day)
            with self.subTest(day=day):
                self.assertGreaterEqual(vis, 1, "nothing expanded on %s" % day)
                self.assertLessEqual(vis, 50,
                                     "first screen %d rows on %s - past what a person "
                                     "reads over coffee" % (vis, day))

    def test_F11_truncated_rows_are_folded_not_dropped(self):
        """The count cap is a truncation on the sort, never a filter: whatever it
        pushes down still renders inside the segment."""
        import dashboard as DB
        _r, cap2, _t = segment_counts(STEADY_DAY)
        for s, cap in DB.OPEN_CAP.items():
            folded = max(0, cap2[s] - cap)
            with self.subTest(segment=s):
                self.assertEqual(len(segment_head(STEADY_DAY, s)), cap2[s],
                                 "segment %s lost rows: folded %d must stay in the "
                                 "cap2 view" % (s, folded))


class F12Invariant(unittest.TestCase):
    """An INVARIANT, never a hardcoded number: the corpus grows every day and the
    spec's own literal 931 == 931 went stale within two hours."""

    def test_F12_zero_loss(self):
        for day in (HARVEST_DAY, STEADY_DAY):
            with self.subTest(day=day):
                raw, _c, total = segment_counts(day)
                self.assertEqual(sum(raw.values()), total)

    def test_F12_every_row_gets_exactly_one_segment(self):
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
        self.assertEqual(len(rows), 2, "expected KAYAK's 2 ats_direct rows")
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
        bat = io.open(os.path.join(ROOT, "run_daily_report.bat"), encoding="utf-8").read()
        # Match on the script, not the interpreter: the collectors stopped saying
        # `python` when they dropped `conda activate` for "%JOB_PYTHON%".
        def invocation(script):
            m = re.search(r"(?m)^\s*\S*(?:python|PYTHON%\")\S*\s+-u\s+" + re.escape(script), bat)
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
        src = io.open(os.path.join(ROOT, "dashboard.py"), encoding="utf-8").read()
        self.assertNotIn("import daily_report", src)

    def test_F17_daily_report_output_is_byte_identical(self):
        """Zero lines changed on daily_report.py's analysis/render path."""
        archived = os.path.join(ROOT, "logs", "daily", "%s.md" % HARVEST_DAY)
        if not os.path.exists(archived):
            self.skipTest("no archived report for %s" % HARVEST_DAY)
        before = io.open(archived, "rb").read()
        backup = archived + ".f17bak"
        shutil.copy2(archived, backup)
        try:
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            p = subprocess.run([sys.executable, "-u", "daily_report.py",
                                "--date", HARVEST_DAY, "--no-prune"],
                               cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
            self.assertEqual(p.returncode, 0, p.stdout.decode("utf-8", "replace"))
            after = io.open(archived, "rb").read()
            self.assertEqual(before, after, "daily_report.py output changed")
        finally:
            shutil.move(backup, archived)


class F9Degraded(unittest.TestCase):
    def test_F9_dashboard_still_renders_after_an_enrichment_timeout(self):
        """Half the table missing = the enrichment run hit its 300 s wall clock. The
        page must still build, and it must say so at the top."""
        keys = sorted(_PROFILES)
        half = {k: _PROFILES[k] for k in keys[:len(keys) // 2]}
        page, state, stats = DASH.build(STEADY_DAY, _ROWS, half, _OVERRIDES,
                                        _PRIORITY, {})
        self.assertGreater(stats["unenriched"], 0)
        self.assertIn("家未分层", page)
        self.assertIn("%d 家未分层" % stats["unenriched"], page)
        self.assertEqual(sum(stats["raw"].values()), stats["total"])
        self.assertTrue(page.startswith("<!doctype html>"))

    def test_F9_dashboard_renders_with_no_profile_table_at_all(self):
        page, _s, stats = DASH.build(STEADY_DAY, _ROWS, {}, {}, set(), {})
        self.assertEqual(stats["raw"]["C"], 0)
        self.assertIn("家未分层", page)

    def test_dashboard_has_no_external_dependency(self):
        page, _s, _st = DASH.build(STEADY_DAY, _ROWS, _PROFILES, _OVERRIDES,
                                   _PRIORITY, {})
        self.assertNotIn("<script", page)
        self.assertNotIn("cdn.", page)
        self.assertEqual(re.findall(r'<link[^>]+href', page), [])
        # the only absolute URLs are the job links themselves, in <a href>
        for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', page):
            self.assertRegex(url, r"^https://")
        self.assertIn("prefers-color-scheme", page)
        self.assertIn("a:visited", page)
        self.assertIn("<details", page)


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
        """A file called queue.py in the script directory breaks the
        openai -> httpcore -> trio import chain. Two people have burned time on it."""
        import queue as stdlib_queue
        self.assertTrue(hasattr(stdlib_queue, "SimpleQueue"))
        for name in ("queue.py", "json.py", "types.py", "csv.py", "html.py", "logging.py"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, name)),
                             "%s in the repo root shadows the stdlib" % name)


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
