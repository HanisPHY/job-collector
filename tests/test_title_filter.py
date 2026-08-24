# -*- coding: utf-8 -*-
"""
Title relevance filter for the LinkedIn lane.

    set PYTHONIOENCODING=utf-8
    python -m unittest discover -s tests -v          (from the repo root)
    python -m unittest tests.test_title_filter -v    (this file only)

Context: the LinkedIn collector was the only one of the three lanes with no
positive software-engineering gate, so 41% of what it recorded was not a
software job at all (Junior Motion Designer, Mechanical Associate I,
Analyst - Real Estate Accounting). ATS and DDG both call ng_filter and leak
0/195 and 0/27 respectively.

The verdict is THREE-way, not two-way, because the drop is hard (the row never
reaches the CSV) and a false drop is therefore permanent data loss:

    DROP  - provably not a full-time software role. Regex only, zero LLM.
    KEEP  - provably a software role. Regex only, zero LLM.
    GRAY  - genuinely ambiguous ("System Engineer", "Embedded SW Engineer").
            Routed to the LLM adjudicator, which caches by title so the same
            string always gets the same answer.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

from ats_direct.ng_filter import DROP, GRAY, KEEP, title_verdict
from job_collector.classifiers.title_relevance import (
    OpenAIChatClient,
    TitleAdjudicator,
    TitleFilter,
)
from job_collector.tracking.cost_tracker import LLMCostTracker

import paths

sys.path.insert(0, str(paths.ROOT / "scripts"))

from backfill_titles import backfill_csv   # noqa: E402


class ReportedLeaks(unittest.TestCase):
    """The four titles the user reported on 2026-08-22, verbatim from
    newgrad_classifications.csv. Each must be dropped outright - no LLM call,
    because none of them is ambiguous."""

    REPORTED = [
        "Junior Designer, Automotive Design",   # BMW Group
        "Data Engineer Intern",                 # Weave
        "Junior Motion Designer",               # Universal Music Group
        "Mechanical Associate I",               # Michael Baker International
    ]

    def test_reported_titles_are_dropped(self):
        for title in self.REPORTED:
            with self.subTest(title=title):
                verdict, reason = title_verdict(title)
                self.assertEqual(
                    verdict, DROP,
                    "%r must be dropped outright, got %s (%s)" % (title, verdict, reason),
                )
                self.assertTrue(reason, "a DROP must carry a reason for the drop log")


class UnambiguousSoftware(unittest.TestCase):
    """Titles carrying an explicit software signal must resolve on the regex fast
    path. Letting these fall to GRAY would spend an LLM call to answer a question
    the string already answers."""

    KEEPS = [
        "Software Engineer",
        "Software Engineer I",
        "Associate Software Engineer",
        "Software Development Engineer, AWS Central SDE Team",
        "Full Stack Software Engineer - Simulation & Flight Systems",
        "Backend Engineer",
        "Full Stack Engineer",
        "Web Developer",
        "Member of Technical Staff",
    ]

    def test_explicit_software_titles_are_kept(self):
        for title in self.KEEPS:
            with self.subTest(title=title):
                verdict, reason = title_verdict(title)
                self.assertEqual(
                    verdict, KEEP,
                    "%r is unambiguously software, got %s (%s)" % (title, verdict, reason),
                )


class GrayZone(unittest.TestCase):
    """The titles the two-way filter got WRONG. None of them may be decided by a
    regex: each must reach the adjudicator.

    Both lists are real titles taken from logs/run_newgrad_collector/*.log over
    2026-08-16..22 (1,982 distinct titles, of which 106 were wrongly dropped and 47
    wrongly kept)."""

    # classify_title said "not an SDE role" - all four are software jobs.
    WRONGLY_DROPPED = [
        "Embedded SW Engineer",            # "SW" abbreviation absent from SDE_PATTERNS
        "DevOps Automation Engineer",      # pattern needs devops ADJACENT to engineer
        "DevOps Build & Release Engineer",
        "API Engineer",
        "Compiler Code Gen Engineer",
        "Computer Programmer",             # "Programmer" absent from SDE_PATTERNS
        "Cloud Ops Engineer",
        ".NET Developer",
    ]

    # classify_title kept these on the broad "systems? engineer" alternative -
    # none of them is a software job.
    WRONGLY_KEPT = [
        "Junior Rail Systems Engineer - Traction Power and Electrical",
        "Spaceship Avionics Systems Engineer",
        "Clinical System Engineer I",
        "Associate Systems Engineer - Assay Development",
        "Semiconductor Test Engineer",
        "System Engineer",
    ]

    def test_ambiguous_software_titles_reach_the_adjudicator(self):
        for title in self.WRONGLY_DROPPED:
            with self.subTest(title=title):
                verdict, reason = title_verdict(title)
                self.assertEqual(
                    verdict, GRAY,
                    "%r is a real software job the regex used to drop; it must go to "
                    "the adjudicator, got %s (%s)" % (title, verdict, reason),
                )

    def test_ambiguous_non_software_titles_reach_the_adjudicator(self):
        for title in self.WRONGLY_KEPT:
            with self.subTest(title=title):
                verdict, reason = title_verdict(title)
                self.assertEqual(
                    verdict, GRAY,
                    "%r is not a software job but carries an engineer token; it must "
                    "go to the adjudicator, got %s (%s)" % (title, verdict, reason),
                )


class AdjudicatorFailsOpen(unittest.TestCase):
    """The drop is hard, so the adjudicator must fail OPEN: when the LLM cannot
    answer, the title is KEPT. A closed failure would let one bad API key silently
    empty a day's collection, and nothing downstream would notice - the CSV would
    just be short."""

    GRAY_TITLES = ["System Engineer", "Embedded SW Engineer", "Computer Programmer"]

    def _adjudicator(self, client):
        cache = os.path.join(self.tmp, "verdicts.json")
        return TitleAdjudicator(client=client, cache_path=cache)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="titlecache-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_keeps_everything_when_the_llm_raises(self):
        class Exploding:
            def complete(self, prompt):
                raise RuntimeError("connection reset")

        verdicts = self._adjudicator(Exploding()).judge(self.GRAY_TITLES)

        self.assertEqual(set(verdicts), set(self.GRAY_TITLES))
        for title in self.GRAY_TITLES:
            self.assertTrue(verdicts[title], "%r must survive an LLM outage" % title)

    def test_keeps_everything_when_the_response_is_unparseable(self):
        class Garbling:
            def complete(self, prompt):
                return "I'm sorry, I can't help with that."

        verdicts = self._adjudicator(Garbling()).judge(self.GRAY_TITLES)

        for title in self.GRAY_TITLES:
            self.assertTrue(verdicts[title], "%r must survive a bad response" % title)

    def test_keeps_titles_the_llm_omitted_from_its_answer(self):
        class Forgetful:
            def complete(self, prompt):
                return json.dumps({"System Engineer": False})

        verdicts = self._adjudicator(Forgetful()).judge(self.GRAY_TITLES)

        self.assertFalse(verdicts["System Engineer"], "an explicit false is honoured")
        self.assertTrue(verdicts["Embedded SW Engineer"], "an omitted title is kept")
        self.assertTrue(verdicts["Computer Programmer"], "an omitted title is kept")


class Exploding:
    """Any call is a test failure: the cache was supposed to answer."""

    def complete(self, prompt):
        raise AssertionError("the LLM was consulted for an already-judged title")


class AdjudicatorIsDeterministic(unittest.TestCase):
    """A title is judged once, ever. Re-judging it would let the same string land in
    segment 1 on Monday and vanish on Tuesday, which is the failure mode the
    dashboard already documents for `prom` and freezes by caching."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="titlecache-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cache = os.path.join(self.tmp, "verdicts.json")

    def _answering(self, mapping):
        class Answering:
            def complete(self, prompt):
                return json.dumps(mapping)
        return Answering()

    def test_second_lookup_does_not_consult_the_llm(self):
        titles = ["System Engineer", "Embedded SW Engineer"]
        client = self._answering({"System Engineer": False, "Embedded SW Engineer": True})

        first = TitleAdjudicator(client=client, cache_path=self.cache).judge(titles)
        second = TitleAdjudicator(client=Exploding(), cache_path=self.cache).judge(titles)

        self.assertEqual(first, second)
        self.assertFalse(second["System Engineer"])
        self.assertTrue(second["Embedded SW Engineer"])

    def test_verdict_survives_a_new_process(self):
        TitleAdjudicator(
            client=self._answering({"System Engineer": False}), cache_path=self.cache
        ).judge(["System Engineer"])

        self.assertTrue(os.path.exists(self.cache), "the verdict must be persisted")
        reloaded = TitleAdjudicator(client=Exploding(), cache_path=self.cache)
        self.assertFalse(reloaded.judge(["System Engineer"])["System Engineer"])

    def test_cache_key_ignores_case_and_punctuation(self):
        TitleAdjudicator(
            client=self._answering({"System Engineer": False}), cache_path=self.cache
        ).judge(["System Engineer"])

        reloaded = TitleAdjudicator(client=Exploding(), cache_path=self.cache)
        self.assertFalse(reloaded.judge(["SYSTEM  ENGINEER"])["SYSTEM  ENGINEER"])

    def test_each_batch_is_persisted_before_the_next_one_starts(self):
        """A backfill is ~32 sequential calls. If the scheduler kills the process at
        batch 30, the 29 batches already paid for must still be on disk."""
        seen_on_disk = []

        class TwoBatches:
            def __init__(self, cache_path):
                self.cache_path = cache_path
                self.n = 0

            def complete(self, prompt):
                self.n += 1
                if self.n == 2:
                    # what a killed process would have left behind
                    try:
                        with open(self.cache_path, "r", encoding="utf-8") as f:
                            seen_on_disk.append(json.load(f))
                    except (OSError, ValueError):
                        seen_on_disk.append(None)
                    return json.dumps({"Title B": False})
                return json.dumps({"Title A": False})

        client = TwoBatches(self.cache)
        adj = TitleAdjudicator(client=client, cache_path=self.cache, batch_size=1)

        adj.judge(["Title A", "Title B"])

        self.assertEqual(len(seen_on_disk), 1, "the second batch must have run")
        self.assertIsNotNone(seen_on_disk[0],
                             "batch 1 was not on disk when batch 2 started")
        self.assertIn("title a", seen_on_disk[0])

    def test_a_repeated_title_is_paid_for_once(self):
        """A day's collection repeats the same title across queries and companies -
        the backfill sent 2,578 gray rows as 63 batches when there were only ~1,254
        distinct titles among them, doubling the bill for no extra information."""
        asked = []

        class Counting:
            def complete(self, prompt):
                asked.append(prompt)
                return json.dumps({"System Engineer": False})

        adj = TitleAdjudicator(client=Counting(), cache_path=self.cache, batch_size=40)

        verdicts = adj.judge(["System Engineer"] * 100)

        self.assertEqual(len(asked), 1, "100 copies of one title must be one batch")
        self.assertEqual(asked[0].count("System Engineer"), 1,
                         "the title must appear once in the prompt")
        self.assertFalse(verdicts["System Engineer"])

    def test_a_corrupt_cache_does_not_take_the_collector_down(self):
        with open(self.cache, "w", encoding="utf-8") as f:
            f.write("{ this is not json")

        verdicts = TitleAdjudicator(client=None, cache_path=self.cache).judge(["System Engineer"])

        self.assertTrue(verdicts["System Engineer"], "fail open on a corrupt cache")


class FakeJob:
    """Stands in for job_collector.models.JobPosting - filter_jobs only reads the
    title, and constructing a real JobPosting would drag in the collector."""

    def __init__(self, job_title):
        self.job_title = job_title


class FilterJobsPartition(unittest.TestCase):
    """The seam job_pipeline calls. Mirrors SeniorityFilter.filter_jobs so the call
    site at job_pipeline.py:93 keeps its shape: (kept, dropped)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="titlefilter-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cache = os.path.join(self.tmp, "verdicts.json")
        self.droplog = os.path.join(self.tmp, "dropped.jsonl")

    def _filter(self, client=None):
        return TitleFilter(
            adjudicator=TitleAdjudicator(client=client, cache_path=self.cache),
            drop_log_path=self.droplog,
        )

    def test_partitions_on_the_regex_alone_when_no_title_is_ambiguous(self):
        jobs = [FakeJob("Software Engineer I"), FakeJob("Junior Motion Designer")]

        kept, dropped = self._filter(client=Exploding()).filter_jobs(jobs)

        self.assertEqual([j.job_title for j in kept], ["Software Engineer I"])
        self.assertEqual([j.job_title for j in dropped], ["Junior Motion Designer"])

    def test_gray_titles_follow_the_adjudicator(self):
        class Answering:
            def complete(self, prompt):
                return json.dumps({"System Engineer": False, "Embedded SW Engineer": True})

        jobs = [FakeJob("System Engineer"), FakeJob("Embedded SW Engineer")]

        kept, dropped = self._filter(client=Answering()).filter_jobs(jobs)

        self.assertEqual([j.job_title for j in kept], ["Embedded SW Engineer"])
        self.assertEqual([j.job_title for j in dropped], ["System Engineer"])

    def test_every_drop_is_recorded_with_its_reason(self):
        jobs = [FakeJob("Software Engineer"), FakeJob("Data Engineer Intern"),
                FakeJob("Mechanical Associate I")]

        self._filter(client=Exploding()).filter_jobs(jobs)

        with open(self.droplog, "r", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]

        logged = {e["title"]: e for e in entries}
        self.assertEqual(set(logged), {"Data Engineer Intern", "Mechanical Associate I"},
                         "a hard drop must leave the row recoverable from the log")
        for title, entry in logged.items():
            self.assertTrue(entry.get("reason"), "%r logged without a reason" % title)
            self.assertIn(entry.get("stage"), ("regex", "llm"))

    def test_an_unwritable_drop_log_does_not_lose_the_collection(self):
        unwritable = os.path.join(self.tmp, "nope.jsonl", "deeper.jsonl")
        f = TitleFilter(
            adjudicator=TitleAdjudicator(client=None, cache_path=self.cache),
            drop_log_path=unwritable,
        )

        kept, dropped = f.filter_jobs([FakeJob("Software Engineer"), FakeJob("Junior Designer")])

        self.assertEqual([j.job_title for j in kept], ["Software Engineer"])
        self.assertEqual([j.job_title for j in dropped], ["Junior Designer"])


class FakeSDK:
    """Shape of openai>=1.0 `OpenAI()`: client.chat.completions.create(...)."""

    def __init__(self, content="{}", prompt_tokens=100, completion_tokens=20):
        self.calls = []
        self._content = content
        self._pt, self._ct = prompt_tokens, completion_tokens
        outer = self

        class _Completions:
            def create(self, **kw):
                outer.calls.append(kw)
                return type("R", (), {
                    "choices": [type("C", (), {
                        "message": type("M", (), {"content": outer._content})()
                    })()],
                    "usage": type("U", (), {
                        "prompt_tokens": outer._pt,
                        "completion_tokens": outer._ct,
                    })(),
                })()

        self.chat = type("Chat", (), {"completions": _Completions()})()


class ChatClientAdapter(unittest.TestCase):
    """The seam between TitleAdjudicator and the OpenAI SDK. Its whole job is to
    return text and bill the existing LLMCostTracker, so a title-filter run shows up
    in the daily report like every other LLM spend."""

    def test_returns_the_message_content(self):
        client = OpenAIChatClient(sdk_client=FakeSDK(content='{"System Engineer": false}'))

        self.assertEqual(client.complete("prompt"), '{"System Engineer": false}')

    def test_records_token_usage_against_the_tracker(self):
        tracker = LLMCostTracker()
        client = OpenAIChatClient(
            sdk_client=FakeSDK(prompt_tokens=1500, completion_tokens=300),
            model="gpt-4o-mini",
            cost_tracker=tracker,
        )

        client.complete("prompt")

        self.assertEqual(tracker.api_calls, 1)
        self.assertEqual(tracker.total_input_tokens, 1500)
        self.assertEqual(tracker.total_output_tokens, 300)
        self.assertEqual(tracker.model_used, "gpt-4o-mini")
        self.assertIsNotNone(tracker.calculate_cost(), "gpt-4o-mini must be priced")

    def test_without_an_api_key_it_returns_nothing_rather_than_raising(self):
        """The adjudicator turns an empty answer into 'keep everything'. Raising here
        would instead take down the whole collection run."""
        client = OpenAIChatClient(api_key=None, sdk_client=None)

        self.assertFalse(client.complete("prompt"))

    def test_an_sdk_failure_becomes_an_empty_answer(self):
        class Failing:
            def __init__(self):
                class _C:
                    def create(self, **kw):
                        raise RuntimeError("429 rate limited")
                self.chat = type("Chat", (), {"completions": _C()})()

        self.assertFalse(OpenAIChatClient(sdk_client=Failing()).complete("prompt"))


class PipelineAppliesTheFilter(unittest.TestCase):
    """The whole point of the exercise: a non-software title collected from LinkedIn
    must never reach the CSV. Before this, job_pipeline ran SeniorityFilter alone,
    which has no positive software gate and treats "intern" as a signal to KEEP."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pipeline-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _pipeline(self, titles):
        from job_collector.models import JobPosting
        from job_collector.pipeline.job_pipeline import JobClassificationPipeline

        collected = [
            JobPosting(job_title=t, job_link="https://example.com/%d" % i,
                       company_name="Acme", job_description="", unique_id=str(i),
                       date_posted="", date_recorded="2026-08-22 01:00")
            for i, t in enumerate(titles)
        ]

        class FakeCollector:
            def collect_jobs(self, query, limit, time_filter_minutes=None):
                return list(collected)

        p = JobClassificationPipeline(use_llm=False, exclude_senior=True)
        p.collector = FakeCollector()
        p.title_filter = TitleFilter(
            adjudicator=TitleAdjudicator(client=None,
                                         cache_path=os.path.join(self.tmp, "v.json")),
            drop_log_path=os.path.join(self.tmp, "dropped.jsonl"),
        )
        return p

    def test_non_software_titles_never_reach_the_output(self):
        titles = ["Software Engineer I", "Junior Motion Designer",
                  "Data Engineer Intern", "Mechanical Associate I"]
        p = self._pipeline(titles)

        jobs = p.process("software engineer new grad", limit=10,
                         output_file=os.path.join(self.tmp, "out.csv"))

        got = sorted(j.job_title for j in jobs)
        self.assertEqual(got, ["Software Engineer I"],
                         "only the software role may survive, got %r" % got)

    def test_the_run_summary_counts_what_the_title_filter_removed(self):
        """main.py folds last_run_stats into logs/runs.jsonl. A silent filter would
        make 'collected nothing' indistinguishable from 'filtered everything'."""
        p = self._pipeline(["Junior Motion Designer", "Mechanical Associate I"])

        p.process("q", limit=10, output_file=os.path.join(self.tmp, "out.csv"))

        self.assertEqual(p.last_run_stats.get("title_filtered"), 2)


class BackfillIsReversible(unittest.TestCase):
    """Rewriting newgrad_classifications.csv is destructive and the dashboard reads
    it directly, so the safety properties matter more than the cleaning itself."""

    HEADER = ["unique_id", "job_title", "job_link", "company_name",
              "sponsorship_status", "company_type", "date_posted", "date_recorded",
              "category", "applied"]

    ROWS = [
        ["1", "Software Engineer I", "u1", "Acme", "s", "t", "", "2026-08-21", "c", ""],
        ["2", "Junior Motion Designer", "u2", "UMG", "s", "t", "", "2026-08-21", "c", ""],
        ["3", "Data Engineer Intern", "u3", "Weave", "s", "t", "", "2026-08-21", "c", ""],
    ]

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="backfill-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.csv_path = os.path.join(self.tmp, "newgrad.csv")
        self._write(self.ROWS)
        self.original = self._read_raw()

    def _write(self, rows):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self.HEADER)
            w.writerows(rows)

    def _read_raw(self):
        with open(self.csv_path, "r", encoding="utf-8-sig") as f:
            return f.read()

    def _filter(self):
        return TitleFilter(
            adjudicator=TitleAdjudicator(client=None,
                                         cache_path=os.path.join(self.tmp, "v.json")),
            drop_log_path=os.path.join(self.tmp, "dropped.jsonl"),
        )

    def test_dry_run_reports_without_touching_the_file(self):
        result = backfill_csv(self.csv_path, self._filter(), apply=False)

        self.assertEqual(self._read_raw(), self.original, "dry run must not write")
        self.assertEqual(result["dropped"], 2)
        self.assertEqual(result["kept"], 1)
        self.assertIsNone(result["backup"])

    def test_apply_writes_a_backup_holding_the_original_bytes(self):
        result = backfill_csv(self.csv_path, self._filter(), apply=True)

        self.assertTrue(os.path.exists(result["backup"]), "no backup was written")
        with open(result["backup"], "r", encoding="utf-8-sig") as f:
            self.assertEqual(f.read(), self.original)

    def test_apply_keeps_only_the_software_rows_and_all_their_columns(self):
        backfill_csv(self.csv_path, self._filter(), apply=True)

        with open(self.csv_path, "r", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        self.assertEqual([r["job_title"] for r in rows], ["Software Engineer I"])
        self.assertEqual(sorted(rows[0]), sorted(self.HEADER), "columns must survive")
        self.assertEqual(rows[0]["company_name"], "Acme")

    def test_dry_run_does_not_pollute_the_drop_log(self):
        """The drop log is the only record of rows a hard drop removed. A dry run
        removes nothing, so writing to it would file drops that never happened and
        make the log useless for recovery."""
        droplog = os.path.join(self.tmp, "dropped.jsonl")
        f = TitleFilter(
            adjudicator=TitleAdjudicator(client=None,
                                         cache_path=os.path.join(self.tmp, "v.json")),
            drop_log_path=droplog,
        )

        backfill_csv(self.csv_path, f, apply=False)

        self.assertFalse(os.path.exists(droplog),
                         "a dry run must leave the drop log alone")

    def test_a_row_you_marked_applied_is_never_dropped(self):
        rows = [r[:] for r in self.ROWS]
        rows[1][-1] = "2026-08-21"        # you applied to the Motion Designer role
        self._write(rows)

        backfill_csv(self.csv_path, self._filter(), apply=True)

        with open(self.csv_path, "r", newline="", encoding="utf-8-sig") as f:
            titles = [r["job_title"] for r in csv.DictReader(f)]

        self.assertIn("Junior Motion Designer", titles,
                      "an applied-to row must survive the filter")


if __name__ == "__main__":
    unittest.main(verbosity=2)
