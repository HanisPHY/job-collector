# -*- coding: utf-8 -*-
"""Round2 enrichment probe: anchored batches + prominence + N-sample aggregation."""
import os, json, time, sys, re
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
HERE = r"D:/OneDrive/work/school/project/Job"
key = None
for line in open(os.path.join(HERE, ".env"), encoding="utf-8-sig"):
    if line.strip().startswith("OPENAI_API_KEY="):
        key = line.split("=", 1)[1].strip()
from openai import OpenAI
client = OpenAI(api_key=key)
MODEL = "gpt-4o-mini"

# Anchors: famous names verified absent from the 680-company corpus. Their answers are
# discarded; they exist so a batch of 20 unknown names cannot collectively degrade into
# "everything is unknown" (eval A, blocking-4).
ANCHORS = ["Coca-Cola", "Nintendo", "Airbus", "Adecco", "Indeed"]
ANCHOR_EXPECT = {"coca-cola": 3, "nintendo": 3, "airbus": 3}

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


def ask(names, seed=None):
    listing = "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": INSTR + "\n\nCompanies:\n" + listing}]
    kw = dict(model=MODEL, messages=msgs, temperature=0,
              response_format={"type": "json_object"})
    if seed is not None:
        kw["seed"] = seed
    r = client.chat.completions.create(**kw)
    data = json.loads(r.choices[0].message.content)
    arr = data.get("companies") or next(v for v in data.values() if isinstance(v, list))
    return arr, r.usage


def make_batches(targets, size=20):
    """Interleave 5 anchors into every batch of `size` target companies."""
    out = []
    for i in range(0, len(targets), size):
        chunk = list(targets[i:i + size])
        step = max(1, len(chunk) // (len(ANCHORS) + 1))
        merged, ai = [], 0
        for j, n in enumerate(chunk):
            if ai < len(ANCHORS) and j > 0 and j % step == 0:
                merged.append(ANCHORS[ai]); ai += 1
            merged.append(n)
        merged.extend(ANCHORS[ai:])
        out.append((chunk, merged))
    return out


def run_pass(batches, seed):
    got, tin, tout, bad_anchor = {}, 0, 0, 0

    def one(b):
        chunk, merged = b
        last = None
        for _ in range(3):
            try:
                arr, u = ask(merged, seed=seed)
                return chunk, arr, u.prompt_tokens, u.completion_tokens
            except Exception as e:
                last = e; time.sleep(2)
        print("  BATCH FAILED:", repr(last)[:160])
        return chunk, [], 0, 0

    with ThreadPoolExecutor(max_workers=6) as ex:
        for chunk, arr, pi, po in ex.map(one, batches):
            tin += pi; tout += po
            by = {}
            for x in arr:
                nm = (x.get("name") or "").strip()
                if nm:
                    by[norm(nm)] = x
            for a, exp in ANCHOR_EXPECT.items():
                if by.get(a, {}).get("tier") != exp:
                    bad_anchor += 1
            for nm in chunk:
                k = norm(nm)
                x = by.get(k)
                got[k] = x if x else {"name": nm, "kind": "unknown", "tier": 0,
                                      "prom": 0, "conf": 0.0, "why": "LLM_NO_ROW"}
    return got, tin, tout, bad_anchor


if __name__ == "__main__":
    npass = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    rows = load()
    names = {}
    for r in rows:
        n = (r.get("company_name") or "").strip()
        if n:
            names.setdefault(norm(n), n)
    targets = sorted(names.values(), key=str.lower)
    batches = make_batches(targets, 20)
    print("targets=%d batches=%d passes=%d" % (len(targets), len(batches), npass))

    passes, TIN, TOUT, BAD = [], 0, 0, 0
    t0 = time.time()
    for p in range(npass):
        got, ti, to, ba = run_pass(batches, seed=1000 + p)
        passes.append(got); TIN += ti; TOUT += to; BAD += ba
        print("  pass %d: in=%d out=%d anchor_misses=%d" % (p + 1, ti, to, ba))
    wall = time.time() - t0
    cost = TIN * 0.15 / 1e6 + TOUT * 0.60 / 1e6
    print("TOTAL wall=%.1fs in=%d out=%d cost=$%.4f anchor_misses=%d" % (wall, TIN, TOUT, cost, BAD))
    json.dump(passes, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
              "passes_v4.json"), "w", encoding="utf-8"), ensure_ascii=False)
