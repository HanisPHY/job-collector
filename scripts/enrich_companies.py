# -*- coding: utf-8 -*-
"""
Company enrichment - builds / tops up company_profiles.json.

Two stages, both gpt-4o-mini, both batch 20:

  stage 1  every company name that is not already in the cache, in batches of 20
           target names with 5 famous ANCHOR names interleaved. The anchors are
           discarded from the output; they exist so that a batch made entirely of
           names the model does not know cannot collectively degrade into
           "everything is unknown" (the batch-composition effect).
  stage 2  the stage-1 residue (kind == unknown and tier == 0) re-asked in dense
           batches of 20. Measured: batch 20 recovers 13-14/150 where batch 50
           recovers 1/150. Only upgrades are written back.

  --deep   run stage 2 with gpt-4o over the residue of the WHOLE cache. ~12x the
           price of mini and it is what buys back the intermediary recall that mini
           gives up (50-company sample: 16/50 -> 5/50). Manual, monthly-ish. It is
           deliberately NOT part of the scheduled task.

There is no daily quota: at gpt-4o-mini prices the steady-state day is ~$0.02.

Hard rules learned the hard way, do not remove:
  * the prompt must contain the literal word "JSON" or json_object mode 400s
  * back-fill answers BY NAME, never by position - the model does drop and reorder
  * a name the model never returned gets the fallback dict, and that dict carries
    "stage": 0. Recording an API omission as "the LLM says it does not know this
    company" is exactly the state the volume rule fires on, i.e. it would push a
    real employer into the intermediary lane.
  * when the retries are exhausted, PRINT the exception. A swallowed 400 once cost
    117 seconds and three empty passes before anyone noticed.
  * writes go through an atomic temp-file + os.replace: the cache lives in OneDrive.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths
import company_lane as CL          # noqa: E402
import run_log                     # noqa: E402

sys.path = [p for p in sys.path if p != HERE]
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402

SCRIPT = "run_enrich_companies"
STAGE1_MODEL = "gpt-4o-mini"
STAGE2_MODEL = "gpt-4o-mini"
DEEP_MODEL = "gpt-4o"
BATCH = 20
WORKERS = 6
RETRIES = 3
WALL_BUDGET_S = 300.0              # whole-run wall clock, section 6 / B5

ANCHORS = ["Coca-Cola", "Nintendo", "Airbus", "Adecco", "Indeed"]
ANCHOR_EXPECT = {"coca-cola": 3, "nintendo": 3, "airbus": 3}
ANCHOR_KEYS = {CL.norm(a) for a in ANCHORS}

SYSTEM = ("You label employers for a job-search triage tool. Answer only from knowledge you are "
          "confident about. \"unknown\" is a correct and valued answer; guessing from the company "
          "name is a serious error.")

INSTR = """Label each company below. Reply with a JSON object of the form
{"companies": [ ... ]} holding one JSON object per numbered input.

Field "kind" - what the company does with the person it hires:
  "employer"    - you become an employee working on that company own products, projects or
                  client engagements under its own brand. This INCLUDES management consultancies
                  (Deloitte, EY, Accenture Federal, Booz Allen, Slalom, Gartner), defense primes
                  and federal integrators (Leidos, L3Harris, SAIC, ManTech, Parsons, GDIT),
                  banks, hospitals, universities and government labs.
  "outsourcing" - global IT-services / offshore delivery firm whose model is staffing client
                  projects with rotating engineers (Tata Consultancy Services, Infosys, Wipro,
                  HCL, Cognizant, Capgemini, Synechron, NTT DATA, and small US-registered
                  Indian-owned body shops).
  "staffing"    - recruiting agency, headhunter or contract-placement firm; the job is at an
                  unnamed client, not at them (TEKsystems, Insight Global, Randstad, Robert Half,
                  Jobot, Aerotek).
  "training"    - trains or bootcamps candidates and then places them on client projects,
                  often with a training bond (Revature, SynergisticIT, Per Scholas).
  "job_board"   - a JOB board / JOB aggregator / recruiting marketplace that reposts other
                  companies OPENINGS under its own name (Jobright.ai, Jobgether, Hired,
                  Indeed, ZipRecruiter).
                  CRITICAL: this is about aggregating JOB POSTINGS only. A company whose
                  product aggregates anything else - flights, hotels, prices, restaurants,
                  real-estate listings, shopping, news - is an "employer", NOT a job_board.
                  Kayak, Booking, Expedia, Zillow, Yelp, Google are employers.
  "unknown"     - you do not actually recognise this company.

Field "tier" - how big / well-known the company itself is, INDEPENDENT of "kind":
  3 - household name or sector giant: mega-cap tech, Fortune 500, top defense prime, Big-4,
      bulge-bracket bank, famous AI lab, national laboratory.
  2 - large or well-known: public mid-cap, unicorn, well-known late-stage private, a major
      player inside its industry or region, elite quant/trading firm.
  1 - small but real: a startup or small firm that you genuinely recognise.
  0 - you do not recognise it at all, or the name is too generic to identify.

Field "prom" - public prominence, integer 0-100: how likely a random US software new-grad
  would recognise the name and be excited to work there. Calibration anchors:
  Google/Amazon/Microsoft/Apple = 100 | OpenAI/NVIDIA/SpaceX/Meta = 95 |
  Stripe/Palantir/Databricks/Anduril = 85 | Cisco/Adobe/Salesforce/Deloitte = 75 |
  Boeing/Ford/Cargill/Micron/Leidos = 60 | a well-known regional employer or a hot
  Series-B startup = 40 | a small firm you barely recognise = 15 | never heard of it = 0.
  Use the full range. prom must be 0 whenever tier is 0.

Field "conf" - 0.0-1.0, your probability that BOTH kind and tier are correct.
Field "why"  - at most 8 words, or "no knowledge".
Field "name" - the input name copied EXACTLY, character for character.

Hard rules:
- If you do not recognise the company, you MUST output tier 0, prom 0, kind "unknown",
  conf <= 0.3. Never infer kind or tier from words in the name such as Inc, LLC, Solutions,
  Technologies, Systems, Group or Consulting. A name is not evidence.
- "kind" and "tier" are independent: Tata Consultancy Services is outsourcing AND tier 3.
- Big-4 / strategy consultancies and defense primes are "employer", never "staffing".
- Output exactly one object for EVERY numbered input, including the ones you know nothing
  about. Do not skip, merge or reorder. The array length must equal the number of inputs."""


def no_row(name):
    """Fallback for a name the API never returned.

    "stage": 0 is not cosmetic. stage >= 1 means "a model looked at this company and
    had an opinion"; an omitted row means no model looked at it. Only the stage-0
    reading keeps the company out of the intermediary lane.
    """
    return {"name": name, "kind": "unknown", "tier": 0, "prom": 0, "conf": 0.0,
            "why": "LLM_NO_ROW", "stage": 0}


def make_batches(targets, size=BATCH, anchors=ANCHORS):
    """Interleave the anchors evenly into each batch of `size` target names."""
    out = []
    for i in range(0, len(targets), size):
        chunk = list(targets[i:i + size])
        if not anchors:
            out.append((chunk, list(chunk)))
            continue
        step = max(1, len(chunk) // (len(anchors) + 1))
        merged, ai = [], 0
        for j, n in enumerate(chunk):
            if ai < len(anchors) and j > 0 and j % step == 0:
                merged.append(anchors[ai])
                ai += 1
            merged.append(n)
        merged.extend(anchors[ai:])
        out.append((chunk, merged))
    return out


class Enricher:
    def __init__(self, client, deadline):
        self.client = client
        # One tracker per model: --deep mixes gpt-4o-mini and gpt-4o in a single run and
        # LLMCostTracker prices a whole tracker at the first model it saw.
        self.trackers = {}
        self.deadline = deadline
        self.failed_batches = 0
        self.timed_out_batches = 0
        self.anchor_misses = 0

    def ask(self, model, names, seed):
        listing = "\n".join("%d. %s" % (i, n) for i, n in enumerate(names, 1))
        r = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": INSTR + "\n\nCompanies:\n" + listing}],
            temperature=0,
            seed=seed,
            response_format={"type": "json_object"},
        )
        data = json.loads(r.choices[0].message.content)
        arr = data.get("companies")
        if arr is None:
            arr = next((v for v in data.values() if isinstance(v, list)), [])
        return arr, r.usage

    def run_stage(self, model, batches, seed, label, check_anchors=True):
        got = {}

        def one(b):
            chunk, merged = b
            if time.time() >= self.deadline:
                return chunk, [], None, "timeout"
            last = None
            for attempt in range(RETRIES):
                if time.time() >= self.deadline:
                    return chunk, [], None, "timeout"
                try:
                    arr, usage = self.ask(model, merged, seed)
                    return chunk, arr, usage, None
                except Exception as e:          # noqa: BLE001 - retried, then reported
                    last = e
                    time.sleep(min(2 * (attempt + 1), 5))
            # Never swallow: a 400 that dies silently costs a whole run.
            print("  [%s] BATCH FAILED after %d tries: %r" % (label, RETRIES, last))
            return chunk, [], None, "failed"

        self.trackers.setdefault(model, LLMCostTracker())
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for chunk, arr, usage, err in ex.map(one, batches):
                if err == "timeout":
                    self.timed_out_batches += 1
                elif err == "failed":
                    self.failed_batches += 1
                if usage is not None:
                    t = self.trackers.setdefault(model, LLMCostTracker())
                    t.record_usage(model, usage.prompt_tokens, usage.completion_tokens)
                by = {}
                for x in arr:
                    if not isinstance(x, dict):
                        continue
                    nm = (x.get("name") or "").strip()
                    if nm:
                        by[CL.norm(nm)] = x
                if check_anchors and arr:
                    for a, exp in ANCHOR_EXPECT.items():
                        if by.get(a, {}).get("tier") != exp:
                            self.anchor_misses += 1
                for nm in chunk:                      # back-fill BY NAME
                    k = CL.norm(nm)
                    x = by.get(k)
                    got[k] = coerce(x, nm) if x else no_row(nm)
        return got


def coerce(x, asked_name):
    """Normalise one LLM object. Keeps the name WE asked for as the display name."""
    out = {"name": asked_name}
    kind = str(x.get("kind") or "unknown").strip().lower()
    if kind not in {"employer", "outsourcing", "staffing", "training", "job_board", "unknown"}:
        kind = "unknown"
    out["kind"] = kind
    for k, lo, hi in (("tier", 0, 3), ("prom", 0, 100)):
        try:
            v = int(round(float(x.get(k) or 0)))
        except Exception:
            v = 0
        out[k] = max(lo, min(hi, v))
    try:
        out["conf"] = max(0.0, min(1.0, float(x.get("conf") or 0.0)))
    except Exception:
        out["conf"] = 0.0
    if out["tier"] == 0:
        out["prom"] = 0
    out["why"] = str(x.get("why") or "")[:80]
    return out


def collect_targets(profiles, refresh_all):
    rows = CL.load_rows(paths.DATA_DIR)
    names = {}
    for r in rows:
        n = (r.get("company_name") or "").strip()
        if n:
            names.setdefault(CL.norm(n), n)
    if refresh_all:
        targets = sorted(names.values(), key=str.lower)
    else:
        targets = sorted((v for k, v in names.items() if k not in profiles), key=str.lower)
    return names, [t for t in targets if CL.norm(t) not in ANCHOR_KEYS]


def open_client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        env = os.path.join(paths.ROOT, ".env")
        if os.path.exists(env):
            for line in open(env, encoding="utf-8-sig"):
                if line.strip().startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise SystemExit("OPENAI_API_KEY not found in the environment or in .env")
    from openai import OpenAI
    return OpenAI(api_key=key)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Top up company_profiles.json")
    ap.add_argument("--all", action="store_true",
                    help="re-ask every company, not only the ones missing from the cache")
    ap.add_argument("--deep", action="store_true",
                    help="run stage 2 with %s over the residue of the whole cache "
                         "(~12x the price; manual, monthly)" % DEEP_MODEL)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and exit without calling the API")
    ap.add_argument("--budget", type=float, default=WALL_BUDGET_S,
                    help="wall-clock budget in seconds (default %d)" % WALL_BUDGET_S)
    args = ap.parse_args(argv)

    t0 = time.time()
    deadline = t0 + args.budget
    profiles = CL.load_profiles()
    names, targets = collect_targets(profiles, args.all)

    if args.deep:
        residue = sorted((v.get("name") or k) for k, v in profiles.items()
                         if int(v.get("tier") or 0) == 0
                         and v.get("kind", "unknown") == "unknown"
                         and int(v.get("stage") or 0) >= 1)
    else:
        residue = []

    print("corpus companies=%d  cached=%d  stage1 targets=%d  deep residue=%d"
          % (len(names), len(profiles), len(targets), len(residue)))

    if args.dry_run:
        print("[dry-run] stage1 %s batch %d -> %d batch(es)"
              % (STAGE1_MODEL, BATCH, (len(targets) + BATCH - 1) // BATCH))
        print("[dry-run] stage2 %s batch %d over the stage-1 residue"
              % (DEEP_MODEL if args.deep else STAGE2_MODEL, BATCH))
        print("[dry-run] nothing written, no API call made")
        return 0

    if not targets and not residue:
        print("nothing to do: every company in the corpus is already in the cache")
        run_log.run_summary(SCRIPT, companies_total=len(names), companies_new=0,
                            dropped_rows=0, llm_api_calls=0, llm_cost_usd=0.0,
                            llm_tokens=0, wall_s=round(time.time() - t0, 1))
        return 0

    enr = Enricher(open_client(), deadline)

    # ---- stage 1 ----------------------------------------------------------
    s1 = {}
    if targets:
        batches = make_batches(targets, BATCH)
        print("stage1: %s, %d target(s) in %d batch(es)" % (STAGE1_MODEL, len(targets), len(batches)))
        s1 = enr.run_stage(STAGE1_MODEL, batches, seed=1000, label="stage1")
        dropped = sum(1 for v in s1.values() if v.get("why") == "LLM_NO_ROW")
        print("  answered=%d  dropped(no row)=%d  anchor_misses=%d"
              % (len(s1) - dropped, dropped, enr.anchor_misses))

    # ---- stage 2 ----------------------------------------------------------
    model2 = DEEP_MODEL if args.deep else STAGE2_MODEL
    resid = residue or sorted((v["name"] for v in s1.values()
                               if v["tier"] == 0 and v["kind"] == "unknown"
                               and v.get("why") != "LLM_NO_ROW"), key=str.lower)
    s2 = {}
    if resid and time.time() < deadline:
        b2 = make_batches(resid, BATCH, anchors=[])       # dense residue batches
        print("stage2: %s, %d residue name(s) in %d batch(es)" % (model2, len(resid), len(b2)))
        s2 = enr.run_stage(model2, b2, seed=7, label="stage2", check_anchors=False)
        up = sum(1 for v in s2.values() if v["tier"] > 0 or v["kind"] != "unknown")
        print("  recovered=%d" % up)
    elif resid:
        print("stage2: skipped, wall-clock budget exhausted")

    # ---- merge ------------------------------------------------------------
    merged = dict(profiles)
    new_keys = 0
    for k, v in s1.items():
        w = dict(v)
        # An omitted row keeps stage 0. Everything the model actually answered is stage 1.
        w["stage"] = 0 if w.get("why") == "LLM_NO_ROW" else 1
        if k not in merged:
            new_keys += 1
        merged[k] = w
    for k, v in s2.items():
        if v.get("why") == "LLM_NO_ROW":
            continue
        if v["tier"] > 0 or v["kind"] != "unknown":       # only write upgrades back
            w = dict(v)
            w["stage"] = 2
            if k not in merged:
                new_keys += 1
            merged[k] = w

    calls = sum(t.api_calls for t in enr.trackers.values())
    tokens = sum(t.total_input_tokens + t.total_output_tokens for t in enr.trackers.values())
    per_model = {m: t.calculate_cost() for m, t in enr.trackers.items() if t.api_calls}
    cost = None if any(c is None for c in per_model.values()) else sum(per_model.values())
    wall = time.time() - t0
    dropped = sum(1 for v in s1.values() if v.get("why") == "LLM_NO_ROW")

    if calls == 0:
        # Every batch came back empty. Do NOT overwrite a good cache with nothing and
        # do NOT let the scheduler record this as a healthy run.
        print("ERROR: every batch failed - %d failed, %d skipped for the wall clock. "
              "Cache left untouched." % (enr.failed_batches, enr.timed_out_batches))
        run_log.run_summary(SCRIPT, companies_total=len(names), companies_new=0,
                            dropped_rows=dropped, llm_api_calls=0, llm_cost_usd=0.0,
                            llm_tokens=0, llm_model=STAGE1_MODEL,
                            failed_batches=enr.failed_batches, wall_s=round(wall, 1),
                            status="error")
        return 1

    CL.atomic_write_json(CL.PROFILE_PATH, merged)

    print("wrote %s: %d entries (+%d new)  wall=%.1fs  calls=%d  tokens=%d  cost=%s"
          % (os.path.basename(CL.PROFILE_PATH), len(merged), new_keys, wall, calls, tokens,
             ("$%.4f" % cost) if cost is not None else "unpriced"))
    if enr.timed_out_batches:
        print("NOTE: %d batch(es) skipped, %.0fs wall budget exhausted. "
              "Those companies stay stage 0 and will be retried tomorrow."
              % (enr.timed_out_batches, args.budget))

    run_log.run_summary(SCRIPT,
                        companies_total=len(names), companies_new=new_keys,
                        companies_cached=len(merged), dropped_rows=dropped,
                        stage2_recovered=sum(1 for v in s2.values()
                                             if v["tier"] > 0 or v["kind"] != "unknown"),
                        failed_batches=enr.failed_batches,
                        skipped_batches=enr.timed_out_batches,
                        anchor_misses=enr.anchor_misses,
                        llm_model="+".join(sorted(per_model)), llm_api_calls=calls,
                        llm_tokens=tokens, llm_cost_usd=cost,
                        wall_s=round(wall, 1))
    # A run where every single batch failed already returned 1 above; partial failure
    # is survivable (the cache only grew) but still worth a non-zero exit if nothing
    # at all was learned.
    return 0 if (s1 or s2) else 1


if __name__ == "__main__":
    sys.exit(main())
