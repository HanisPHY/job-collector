# Job Collector

A scheduled pipeline that collects US new-grad SWE postings from three independent
sources, enriches every company through an LLM, sorts the result into six ranked
segments, and publishes a daily markdown report plus an offline HTML dashboard.

The point of the system is **not** collection volume — it is separating the few
postings worth applying to today from the agency spam, aggregator reposts and
senior roles that dominate the raw feeds.

---

## Architecture

```
  COLLECT (3 independent lanes, each own CSV, each own schedule)
  ├── scripts/main.py         LinkedIn via python-jobspy   → data/newgrad_classifications.csv
  ├── scripts/ats_direct.py   company ATS APIs             → data/ats_jobs.csv
  └── scripts/ddg_search.py   DuckDuckGo X-ray discovery   → data/ddg_jobs.csv
                                        │        │
                                        │        └─ --update-registry feeds newly
                                        │           discovered boards back into
                                        │           state/ats_registry.json
                                        ▼
  ENRICH
  └── scripts/enrich_companies.py   gpt-4o-mini, 2 stages  → state/company_profiles.json
                                    {kind, tier, prom, stage}
                                        │
                                        ▼
  DECIDE
  └── scripts/company_lane.py       row → segment          (1a_t3 | 1a_t2 | 1b | B1 | B2 | C)
      scripts/view.py               pure-data reference implementation
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
  PUBLISH                                         
  scripts/daily_report.py                         scripts/dashboard.py
  → logs/daily/YYYY-MM-DD.md                      → logs/dashboard/latest.html
    what to apply to today + health alerts          offline, zero-dependency bundle
```

Two properties are deliberate and load-bearing:

- **The three lanes never block each other.** Each writes its own CSV with its own
  `unique_id` dedup, so a broken lane degrades coverage instead of killing the run.
- **The report and the dashboard are independent.** `dashboard.py` imports nothing
  from `daily_report.py`. The markdown report is what gets read every morning and
  must not be able to regress because of a dashboard change.

Everything is scheduled through `tasks/run_logged.bat`, which captures output to
`logs/<script>/<timestamp>.log` and appends a run record to `logs/runs.jsonl`.
See [SCHEDULING.md](SCHEDULING.md).

---

## Setup

### 1. Create the environment

```bash
conda env create -f environment.yml
conda activate job-classifier
```

Or with pip:

```bash
python -m venv venv
venv\Scripts\activate          # Windows;  source venv/bin/activate on Mac/Linux
pip install -r requirements.txt
```

### 2. Install the project package — required

From the project root, with the environment active:

```bash
pip install -e .
```

This is not optional. `scripts/` imports `paths`, `job_collector`, `ats_direct` and
`ddg_search` from `src/`; without the editable install every entry point fails with
`ModuleNotFoundError: No module named 'paths'`.

### 3. Configure the API key

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# Mac/Linux
cp .env.example .env
```

Then put an `OPENAI_API_KEY` in `.env`. It is loaded automatically via
`python-dotenv` — no manual export needed.

Without a key the collectors still run, but `enrich_companies.py` cannot, so every
company stays at `stage 0` and the whole segmentation collapses to `B1`/`B2`.

> There is **no ChromeDriver / Selenium requirement.** Collection goes through
> `python-jobspy` and direct ATS HTTP APIs. `selenium` remains in
> `requirements.txt` as a leftover dependency but no live code imports it.

### 4. Verify

```bash
python -m unittest discover -s tests
```

89 tests. Three skips are by design — they need a live LLM key (`JOB_TEST_LLM=1`) or
a retired fixture.

Run this with the **environment's** interpreter, not a bare system Python. If you see
`ModuleNotFoundError: No module named 'paths'`, step 2 did not take effect in the
interpreter you just used.

Note that part of the suite asserts against the *live* CSVs and `company_profiles.json`,
not against fixtures, so a failure can mean the data is in a bad state rather than the
code. As of 2026-09-10 two such tests fail on this machine (`F9Degraded`,
`F27DedupCanary`) because enrichment has stopped consuming its backlog — see
[SCHEDULING.md](SCHEDULING.md) for the enrichment task.

---

## Usage

### Lane 1 — LinkedIn (`main.py`)

```bash
python scripts\main.py --query "software engineer new grad" --limit 50 \
    --time-filter 120 --exclude-senior --output data\newgrad_classifications.csv
```

| Flag | Meaning |
|---|---|
| `--query` | search query (default `software engineer`) |
| `--limit` | max jobs per query (default 50) |
| `--output` | output CSV (default `data/job_classifications.csv`) |
| `--time-filter MINUTES` | only postings newer than N minutes |
| `--exclude-senior` | drop senior/staff/principal/lead/manager titles |
| `--no-llm` | disable LLM company classification |

In practice this lane is driven by `tasks/run_newgrad_collector.bat`, which runs
nine queries in three precision tiers (explicit "new grad" phrasings, then the
untagged big-tech forms like `software engineer I`, then supplementary phrasings).
Duplicates across queries are absorbed by the `unique_id` dedup.

### Lane 2 — ATS direct (`ats_direct.py`)

Pulls straight from company ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters,
Workable, Workday, …). No search engine involved, so no rate-limit roulette and no
aggregator noise. This is the highest-signal lane.

```bash
python scripts\ats_direct.py --probe                      # resolve seed companies (one-time)
python scripts\ats_direct.py                              # collect from the resolved registry
python scripts\ats_direct.py --loose                      # keep any non-senior SDE title
python scripts\ats_direct.py --all-locations              # skip the US filter
python scripts\ats_direct.py --add-company "Name:platform:slug"
python scripts\ats_direct.py --max-companies 10           # smoke test on a subset
python scripts\ats_direct.py --expand                     # grow the registry
python scripts\ats_direct.py --cleanup                    # prune dead boards
```

The registry lives at `state/ats_registry.json`. Rate limits per platform are
documented in [src/ats_direct/RATE_LIMITS.md](src/ats_direct/RATE_LIMITS.md).

### Lane 3 — DuckDuckGo discovery (`ddg_search.py`)

A **discovery** source, not a volume source: it finds ATS-hosted new-grad postings
through X-ray queries and can feed the newly-found boards into lane 2's registry.

```bash
python scripts\ddg_search.py                    # 5 queries, write ddg_jobs.csv
python scripts\ddg_search.py --queries 3
python scripts\ddg_search.py --update-registry  # also grow ats_registry.json
python scripts\ddg_search.py --loose
```

DDG throttles aggressively (see [src/ddg_search/RATE_LIMITS.md](src/ddg_search/RATE_LIMITS.md)),
so each run makes only a handful of queries ~25s apart. **Schedule it a few times a
day at most — never hourly.**

### Company enrichment (`enrich_companies.py`)

```bash
python scripts\enrich_companies.py              # top up new companies (daily)
python scripts\enrich_companies.py --all        # re-ask everything
python scripts\enrich_companies.py --deep       # gpt-4o over the residue (manual, monthly)
python scripts\enrich_companies.py --dry-run
```

Steady-state cost is roughly $0.02/day at gpt-4o-mini prices, so there is no daily
quota. `--deep` is ~12× the price and buys back the intermediary recall mini gives
up; it is deliberately **not** part of the scheduled task.

### Report and dashboard

```bash
python scripts\daily_report.py                  # today  → logs/daily/YYYY-MM-DD.md
python scripts\daily_report.py --date 2026-08-19
python scripts\dashboard.py                     # → logs/dashboard/latest.html
python scripts\dashboard.py --date 2026-08-19 --out snapshot\   # frozen snapshot
```

The dashboard bundle is self-contained and opens offline by double-clicking
`latest.html` — no CDN, no fonts, no build step, no `fetch` (all blocked under
`file://`). Both are produced by the single `run_daily_report` scheduled task.

---

## The decision layer

### Sponsorship

Keyword scan over the job description for `visa`, `sponsor(ship)`, `H-1B`/`H1B`,
`OPT`/`CPT`/`STEM OPT`, `work authorization`, `work visa`, `immigration`,
`green card`, `permanent residency`. At least one hit → **Sponsor**, otherwise
**Not (Maybe Not) Sponsor**. This is a coarse signal and is treated as one: it
labels rows, it does not gate them.

### Company profile

`enrich_companies.py` asks the LLM for four independent fields per company, cached
in `state/company_profiles.json`:

- **`kind`** — what the company does with the person it hires:
  `employer` · `outsourcing` · `staffing` · `training` · `job_board` · `unknown`.
  Note that `job_board` means it aggregates *job postings*; a company that
  aggregates flights or listings (Kayak, Zillow, Expedia) is an `employer`.
- **`tier` 0–3** — how big/well-known the company is, *independent of `kind`*
  (Tata Consultancy Services is `outsourcing` **and** `tier 3`).
- **`prom` 0–100** — public prominence to a US new grad. Used only for ordering
  rows inside a segment, never for segmentation.
- **`stage`** — how far enrichment got. `stage 0` means the LLM never answered,
  which is *not* the same as "the LLM does not know this company".

### Segments

[scripts/company_lane.py](scripts/company_lane.py) resolves each row to one segment.
The order of the tests is load-bearing and must not be reshuffled:

| Step | Test |
|---|---|
| **O1** | a manual override in `config/company_overrides.json` wins over everything |
| **S1** | hard-intermediary kinds (`staffing`/`outsourcing`/`training`) and `job_board` → lane C |
| **A-blocking-2** | `stage < 1` can **never** reach lane C — this gate sits *before* the volume signal, so an API omission cannot push a real employer into the intermediary lane |
| **S5** | volume signal: `unknown` + `tier 0` + ≥5 rows in a 7-day window → lane C. Absolute threshold, no relative term |
| **V1** | company-level veto inside S5 — a company running its own ATS board is an employer regardless of volume |
| **row_lane** | evaluated *per row*, so a `job_board` that also runs its own board keeps its own-board rows out of lane C |

| Segment | Label | Meaning | Visible by default |
|---|---|---|---|
| `1a_t3` | 今日必看 | tier 3 company, entry-level title | ✅ |
| `1a_t2` | 大中公司应届岗 | tier 2 company, entry-level title | |
| `1b` | 大中公司其他岗位 | tier ≥ 2, title does not look entry-level | |
| `B1` | 有自有 ATS board 的小公司 | tier ≤ 1, but the company appears in the ATS/DDG lanes | ✅ |
| `B2` | 长尾 | everything else that is not an intermediary | |
| `C` | 中介 / 刷屏 | judged agency, aggregator, or pure volume spam | |

The segmentation criteria contain **no `prom` threshold**. `prom` only orders rows
within a segment (`sort_key`).

### Cross-check

[scripts/view.py](scripts/view.py) is a pure-data reference implementation (no HTML,
no I/O). [web/dashboard.js](web/dashboard.js) re-derives the same numbers in the
browser and is forced to agree with the Python via `JOB_INDEX.check`; `seq_hash()`
must stay bit-for-bit identical to `seqHash` in the JS, held together by fixture F29.
`tests/test_lane.py` asserts the same invariants.

---

## Output format

All three lanes write the same core columns. `ats_jobs.csv` and `ddg_jobs.csv` add
three more.

| Column | Notes |
|---|---|
| `unique_id` | dedup key across runs and queries |
| `job_title` | |
| `job_link` | |
| `company_name` | |
| `sponsorship_status` | `Sponsor` / `Not (Maybe Not) Sponsor` |
| `company_type` | `独角兽/上市公司/Big Tech` / `Others` |
| `date_posted`, `date_recorded` | |
| `category` | combined sponsorship × company_type, for spreadsheet grouping |
| `applied` | hand-edited; the daily report shows unapplied rows only |
| `source`, `platform`, `location` | ATS and DDG lanes only |

`company_type` and `category` are the original coarse labels and are kept for CSV
users. The report and the dashboard both use the segment model above instead.

---

## Layout

```
.
├── src/                 # importable packages (editable install via `pip install -e .`)
│   ├── paths.py         #   single source of truth for ROOT/DATA/CONFIG/STATE dirs
│   ├── job_collector/   #   LinkedIn lane: collectors, classifiers, pipeline, io, tracking
│   ├── ats_direct/      #   ATS lane: providers, registry, rate limiter, NG/US filters
│   ├── ddg_search/      #   DDG lane: client, link parser, collector
│   └── dashboard_loop/  #   dashboard v2 design notes and eval probes
├── scripts/             # entry points
│   ├── main.py                    #   lane 1 - LinkedIn
│   ├── ats_direct.py              #   lane 2 - ATS APIs
│   ├── ddg_search.py              #   lane 3 - DDG discovery
│   ├── enrich_companies.py        #   company profiles
│   ├── company_lane.py            #   segment resolver
│   ├── view.py                    #   pure-data reference implementation
│   ├── daily_report.py            #   markdown report
│   ├── dashboard.py               #   HTML bundle
│   ├── run_log.py                 #   runs.jsonl writer
│   ├── backfill_titles.py         #   one-off maintenance
│   └── download_company_lists.py  #   fetch Fortune 500 / unicorn CSVs
├── tasks/               # Task Scheduler wrappers: run_logged.bat, run_*.bat,
│                        #   resolve_python.bat, repoint_scheduled_tasks.ps1, ...
├── data/                # collected CSVs (newgrad_classifications, ats_jobs, ddg_jobs)
├── config/              # hand-maintained: company_overrides.json, priority_companies.txt
├── state/               # generated caches: company_profiles.json, ats_registry.json,
│                        #   title_verdicts.json, ddg_state.json, company_database_cache.json
├── web/                 # static dashboard assets (dashboard.css, dashboard.js)
├── tests/               # test_lane.py, test_title_filter.py, fixtures/
├── docs/                # requirements and design docs (docs/req/)
├── deprecated/          # old entry points, reference only
├── logs/                # run logs, runs.jsonl, daily reports, dashboard bundle (gitignored)
├── pyproject.toml       # package metadata (enables `pip install -e .`)
├── requirements.txt · environment.yml · setup_environment.bat
├── QUICKSTART.md        # 10-minute setup path
├── SCHEDULING.md        # Task Scheduler setup, logging, troubleshooting
└── README.md            # this file
```

`config/` is hand-edited and belongs in git. `state/` is machine-generated — safe to
delete, expensive to regenerate (`company_profiles.json` in particular costs real
API spend to rebuild).

---

## Extending

- **New collection lane** — add a package under `src/`, an entry point under
  `scripts/`, and a `tasks/run_*.bat` wrapper. Write your own CSV with the core
  column set; `company_lane.load_rows()` picks up any source listed in its `SOURCES`.
- **New ATS platform** — add a provider to
  [src/ats_direct/providers.py](src/ats_direct/providers.py) and a rate-limit entry.
- **Segment rule change** — change `company_lane.py` *and* the mirrored logic in
  `web/dashboard.js`, then run `tests/test_lane.py`. The two implementations are
  checked against each other at runtime; they will not silently diverge.
- **Company judgement** — prefer a `config/company_overrides.json` entry (O1 beats
  every automatic signal) over touching the prompt.

---

## Limitations

- **LinkedIn lane** is the noisiest and the most fragile — it depends on
  `python-jobspy` continuing to work and is subject to rate limiting.
- **DDG lane** throttles hard and is a discovery source, not a volume source.
- **LLM enrichment** costs money and can be wrong. `stage 0` (no answer) is
  recorded distinctly from `unknown` (answered, does not recognise) precisely
  because conflating them mislabels real employers.
- **Sponsorship classification** depends on the description being present and
  complete; a missing description yields a false negative.

## License

For personal/educational use. Respect the terms of service of every source.
