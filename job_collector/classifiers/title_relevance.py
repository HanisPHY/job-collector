# -*- coding: utf-8 -*-
"""
LLM adjudicator for the GRAY band of ng_filter.title_verdict().

Only titles the regex cannot decide reach this module. In the 2026-08-16..22 sample
that was 1,213 of 2,016 distinct titles; the other 803 were settled by DROP/KEEP at
zero cost and zero sampling noise.

Two properties this module exists to guarantee:

  fail OPEN   The LinkedIn lane drops hard, so an unanswered title is KEPT. An API
              outage must degrade the filter to "regex only", never to "silently
              collect nothing". Every failure path below returns True.

  determinism A verdict is cached against the normalised title and reused forever,
              so the same string never gets two different answers on two days. Same
              approach the dashboard already takes with `prom` (one sample, frozen).
"""

import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ats_direct.ng_filter import DROP, GRAY, title_verdict   # noqa: E402


def normalise(title):
    """Cache key. Case and punctuation carry no signal for this question."""
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


class TitleAdjudicator:
    """Decides whether a gray-band title is a software engineering role."""

    def __init__(self, client=None, cache_path=None, cost_tracker=None, batch_size=40):
        self.client = client
        self.cache_path = cache_path
        self.cost_tracker = cost_tracker
        self.batch_size = batch_size
        self._cache = self._load_cache()

    # ---------------------------------------------------------------- cache
    def _load_cache(self):
        if not self.cache_path or not os.path.exists(self.cache_path):
            return {}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            # A corrupt cache must not take the collector down with it; the worst
            # case is that today's gray titles get re-judged.
            return {}

    def _save_cache(self):
        if not self.cache_path:
            return
        d = os.path.dirname(os.path.abspath(self.cache_path))
        try:
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self.cache_path)
        except OSError:
            pass

    # ---------------------------------------------------------------- judging
    def judge(self, titles):
        """titles -> {title: is_software}. Never raises, never returns a partial map."""
        verdicts = {}
        unknown = []
        pending = set()
        for t in titles:
            key = normalise(t)
            if key in self._cache:
                verdicts[t] = bool(self._cache[key])
                continue
            verdicts[t] = True          # fail open until proven otherwise
            # One slot per DISTINCT title: a day's collection repeats the same
            # string across queries and companies, and asking twice buys nothing.
            if key not in pending:
                pending.add(key)
                unknown.append(t)

        if not unknown or self.client is None:
            return verdicts

        for i in range(0, len(unknown), self.batch_size):
            batch = unknown[i:i + self.batch_size]
            answers = self._ask(batch)
            answered = False
            for t in batch:
                if t in answers:
                    verdicts[t] = bool(answers[t])
                    self._cache[normalise(t)] = bool(answers[t])
                    answered = True
            # Persist per batch, not once at the end: a backfill is ~32 sequential
            # calls and a killed process must not throw away the batches already
            # paid for. The write is atomic (temp file + os.replace).
            if answered:
                self._save_cache()

        # Only one spelling of each title was sent, so fan the answer back out to
        # every caller-supplied variant ("System Engineer" / "SYSTEM  ENGINEER").
        for t in verdicts:
            key = normalise(t)
            if key in self._cache:
                verdicts[t] = bool(self._cache[key])

        return verdicts

    def _ask(self, batch):
        """One batch -> {title: bool}. Returns {} on any failure (fail open)."""
        try:
            raw = self.client.complete(self._prompt(batch))
        except Exception:
            return {}
        if not raw:
            return {}
        try:
            parsed = json.loads(self._extract_json(raw))
        except (ValueError, TypeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {k: v for k, v in parsed.items() if isinstance(v, bool)}

    @staticmethod
    def _extract_json(raw):
        """Tolerate a fenced or prose-wrapped object; anything else fails to parse
        and is handled by the caller as a fail-open."""
        s = str(raw).strip()
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end > start:
            return s[start:end + 1]
        return s

    @staticmethod
    def _prompt(batch):
        listing = "\n".join("- %s" % t for t in batch)
        return (
            "You are screening job titles for a new-grad SOFTWARE ENGINEERING job "
            "search.\n\n"
            "For each title below, answer true if the role's main work is building "
            "software (writing, testing, shipping or operating code). Answer false "
            "for hardware, mechanical, electrical, civil, clinical, laboratory, IT "
            "support / helpdesk, network administration, sales, marketing, finance, "
            "design and analyst roles that do not build software.\n\n"
            "Borderline guidance: data engineering, ML/AI engineering, DevOps, SRE, "
            "embedded and firmware all count as software (true). Systems engineering "
            "counts only when the system is software.\n\n"
            "Reply with ONLY a JSON object mapping each title, verbatim, to true or "
            "false. No prose.\n\n"
            "%s" % listing
        )


class TitleFilter:
    """Partitions collected jobs into (kept, dropped).

    Mirrors SeniorityFilter.filter_jobs so the call site in job_pipeline keeps its
    shape. Regex settles the two ends for free; only the gray band costs an LLM
    call, and only once per distinct title.
    """

    def __init__(self, adjudicator=None, drop_log_path=None):
        self.adjudicator = adjudicator
        self.drop_log_path = drop_log_path

    def filter_jobs(self, jobs, record=True):
        """record=False plans the partition without filing anything in the drop log,
        which is what a dry run needs: nothing was actually removed."""
        kept, dropped, drops = [], [], []
        gray = []

        for job in jobs:
            verdict, reason = title_verdict(getattr(job, "job_title", ""))
            if verdict == DROP:
                dropped.append(job)
                drops.append((job, reason, "regex"))
            elif verdict == GRAY:
                gray.append(job)
            else:
                kept.append(job)

        if gray:
            titles = [j.job_title for j in gray]
            answers = (self.adjudicator.judge(titles) if self.adjudicator
                       else dict.fromkeys(titles, True))
            for job in gray:
                if answers.get(job.job_title, True):
                    kept.append(job)
                else:
                    dropped.append(job)
                    drops.append((job, "not a software role (adjudicated)", "llm"))

        if record:
            self._record(drops)
        return kept, dropped

    def _record(self, drops):
        """Append one JSON object per dropped row. A hard drop keeps nothing in the
        CSV, so this file is the only way back to what was discarded - but failing
        to write it must never cost us the collection itself."""
        if not self.drop_log_path or not drops:
            return
        try:
            d = os.path.dirname(os.path.abspath(self.drop_log_path))
            os.makedirs(d, exist_ok=True)
            with open(self.drop_log_path, "a", encoding="utf-8") as f:
                for job, reason, stage in drops:
                    f.write(json.dumps({
                        "title": getattr(job, "job_title", ""),
                        "company": getattr(job, "company_name", ""),
                        "reason": reason,
                        "stage": stage,
                    }, ensure_ascii=False) + "\n")
        except OSError:
            pass


# gpt-4o-mini rather than the gpt-3.5-turbo the company classifier uses: it is
# 3.3x cheaper on input ($0.15 vs $0.50 per 1M) and this is a one-bit question.
# Must stay a key of LLMCostTracker.MODEL_PRICING or the daily report prints
# "unpriced" instead of a number.
ADJUDICATOR_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = ("You screen job titles for a new-grad software engineering search. "
                  "Reply with only a valid JSON object mapping each title to true or false.")


class OpenAIChatClient:
    """Thin `complete(prompt) -> str` seam over the OpenAI SDK.

    Every failure path returns "" rather than raising: TitleAdjudicator reads an
    empty answer as "keep everything", which is the fail-open behaviour a hard drop
    requires. Raising here would abort the collection run instead.
    """

    def __init__(self, api_key=None, model=ADJUDICATOR_MODEL, cost_tracker=None,
                 sdk_client=None):
        self.model = model
        self.cost_tracker = cost_tracker
        self._client = sdk_client if sdk_client is not None else self._build(api_key)

    @staticmethod
    def _build(api_key):
        if not api_key:
            return None
        try:
            from openai import OpenAI
            return OpenAI(api_key=api_key)
        except Exception:
            return None

    def complete(self, prompt):
        if self._client is None:
            return ""
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": _SYSTEM_PROMPT},
                          {"role": "user", "content": prompt}],
                temperature=0,
            )
            text = response.choices[0].message.content or ""
        except Exception:
            return ""

        if self.cost_tracker is not None:
            try:
                usage = response.usage
                self.cost_tracker.record_usage(
                    self.model,
                    getattr(usage, "prompt_tokens", 0) or 0,
                    getattr(usage, "completion_tokens", 0) or 0,
                )
            except Exception:
                pass
        return text.strip()
