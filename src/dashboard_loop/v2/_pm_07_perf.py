# -*- coding: utf-8 -*-
"""PROBE 7 - does N=30 at the steady-state rate actually survive in the browser?

req2 5.5 says "30 天视图一次性建几万个 <tr> 会卡死" but nobody measured the part that
is NOT DOM: parsing a multi-MB classic script off file:// and running the pure-data
pass (filter -> drop superseded -> group -> cap2 -> counts) over ~60k rows.

Synthesises a 30-day corpus at the rate req2 5.5 assumes (2000 rows/day) out of the
REAL rows (real titles, real links, real company distribution), writes it in the
proposed E4 column encoding, and times it in Chrome under file://.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict

from _pm_base import CL, banner, dkey, load

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>perf</title></head>
<body><pre id="out">PENDING</pre>
<script>window.__t0 = performance.now();</script>
<script src="data.js"></script>
<script>
var R = {};
R.parse_ms = +(performance.now() - window.__t0).toFixed(1);
R.bytes = window.__BYTES;
var D = window.JOB_DATA;
R.rows = D.c.length;

function pass(N){
  var t = performance.now();
  var lo = D.days.length - N; if (lo < 0) lo = 0;
  var raw = {}, grp = {}, i, k;
  for (i = 0; i < D.c.length; i++) {
    if (D.d[i] < lo) continue;
    if (D.x[i]) continue;
    var g = D.g[i];
    raw[g] = (raw[g] || 0) + 1;
    k = g + ':' + D.c[i];
    grp[k] = (grp[k] || 0) + 1;
  }
  var cap2 = {};
  for (k in grp) { var g2 = k.split(':')[0];
    cap2[g2] = (cap2[g2] || 0) + (grp[k] > 2 ? 2 : grp[k]); }
  var tot = 0; for (var s in raw) tot += raw[s];
  return {ms:+(performance.now()-t).toFixed(1), total:tot, raw:raw, cap2:cap2};
}
R.N = {};
[1,3,7,14,30].forEach(function(n){ R.N[n] = pass(n); });
// second run to show the warm number
R.warm30 = pass(30).ms;
// sort cost for one segment at N=30
var t = performance.now();
var arr = [];
for (var i = 0; i < D.c.length; i++) if (!D.x[i] && D.g[i] === 0) arr.push(i);
arr.sort(function(a,b){ return D.o[D.c[a]] - D.o[D.c[b]]; });
R.sort_ms = +(performance.now()-t).toFixed(1);
R.sorted = arr.length;
document.getElementById('out').textContent = JSON.stringify(R);
</script></body></html>
"""


def main():
    rows, profiles, overrides, priority = load()
    day = max(r["_day"] for r in rows)
    banner("PROBE 7  browser cost of a 30-day / 2000-rows-per-day payload")
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)

    # superseded flag (keep-NEWEST) on the real corpus
    grp = defaultdict(list)
    for r in rows:
        grp[dkey(r)].append(r)
    for g in grp.values():
        g.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))

    cos = sorted({CL.norm(r["company_name"]) for r in rows})
    cidx = {c: i for i, c in enumerate(cos)}
    rank = {c: i for i, c in enumerate(sorted(cos, key=R.sort_key))}
    segi = {s: i for i, s in enumerate(SEGS)}

    # ---- synthesise 30 days x 2000 rows out of the real ones ---------------
    base = list(rows)
    NDAYS, PERDAY = 30, 2000
    cols = {"c": [], "g": [], "t": [], "lp": [], "l": [], "s": [], "d": [],
            "r": [], "x": []}
    prefs = ["https://www.linkedin.com", "https://jobs.ashbyhq.com",
             "https://job-boards.greenhouse.io", "https://jobs.lever.co",
             "https://boards.greenhouse.io", "https://boards.greenhouse.io/embed"]
    pmap = {p: i for i, p in enumerate(prefs)}
    seen = {}
    src_i = {"newgrad": 0, "ats_direct": 1, "ddg": 2}
    for dnum in range(NDAYS):
        for j in range(PERDAY):
            r = base[(dnum * PERDAY + j) % len(base)]
            c = CL.norm(r["company_name"])
            # keep the real title, but make a fraction of them genuine cross-day
            # repeats so the superseded flag has something to do (measured rate
            # in PROBE 2 was 6.1% of rows in a cross-day key)
            t = (r.get("job_title") or "").strip()
            # the real corpus has 2491 rows; cycling them would make 90% of the
            # synthetic corpus a duplicate, which is nothing like reality. Make each
            # posting unique EXCEPT for a deliberate 6.1% cross-day repeat rate -
            # the rate measured on the real corpus in PROBE 2.
            if j % 16 == 0 and dnum > 0:
                t = t + " R%d" % (j // 16)          # repeats yesterday's posting
            else:
                t = t + " %d-%d" % (dnum, j)
            key = c + "\x00" + CL.tnorm(t)
            l = (r.get("job_link") or "").strip()
            p = "/".join(l.split("/")[:3])
            cols["c"].append(cidx[c])
            cols["g"].append(segi[R.segment(r)])
            cols["t"].append(t)
            cols["lp"].append(pmap.get(p, -1))
            cols["l"].append(l[len(p):] if p in pmap else l)
            cols["s"].append(src_i[r["_source"]])
            cols["d"].append(dnum)
            cols["r"].append(800 + (j % 900))
            cols["x"].append(0)
            if key in seen:
                cols["x"][seen[key]] = 1
            seen[key] = len(cols["c"]) - 1

    payload = {
        "generated": "2026-08-21 08:00",
        "days": ["2026-%02d-%02d" % (7 + (i // 28), 1 + (i % 28)) for i in range(NDAYS)],
        "co": [[R.profile(c).get("name") or c, R.profile(c)["tier"],
                R.profile(c)["prom"], R.window_count(c), 1 if c in R.board else 0]
               for c in cos],
        "o": [rank[c] for c in cos],
    }
    payload.update(cols)
    body = "window.JOB_DATA=" + J(payload) + ";window.__BYTES=%d;"
    tmp = tempfile.mkdtemp(prefix="pmperf_")
    txt = body % 0
    txt = body % len(txt.encode("utf-8"))
    path = os.path.join(tmp, "data.js")
    io.open(path, "w", encoding="utf-8").write(txt)
    io.open(os.path.join(tmp, "perf.html"), "w", encoding="utf-8").write(HTML)
    nb = os.path.getsize(path)
    print("synthetic corpus: %d days x %d rows = %d rows" % (NDAYS, PERDAY, NDAYS * PERDAY))
    print("data.js on disk: %d bytes (%.2f MB) = %.1f B/row"
          % (nb, nb / 2.0 ** 20, nb / float(NDAYS * PERDAY)))
    print("superseded rows in the synthetic corpus: %d (%.1f%%)"
          % (sum(cols["x"]), 100.0 * sum(cols["x"]) / len(cols["x"])))

    if not os.path.exists(CHROME):
        print("chrome not found, skipping the browser half")
        return
    url = "file:///" + os.path.join(tmp, "perf.html").replace("\\", "/")
    prof = tempfile.mkdtemp(prefix="pmperfprof_")
    try:
        p = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--user-data-dir=" + prof, "--virtual-time-budget=30000",
                            "--dump-dom", url],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        dom = p.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not m:
        print("no result; dom %d bytes" % len(dom))
        return
    d = json.loads(m.group(1))
    print("\nchrome (headless, file://):")
    print("   script parse+eval of the whole file : %.1f ms" % d["parse_ms"])
    print("   rows visible to JS                  : %d" % d["rows"])
    for n in ("1", "3", "7", "14", "30"):
        v = d["N"][n]
        print("   N=%-3s pure-data pass %7.1f ms   deduped rows %6d   cap2 %s"
              % (n, v["ms"], v["total"],
                 " ".join("%s=%d" % (SEGS[int(k)], vv) for k, vv in
                          sorted(v["cap2"].items()))))
    print("   warm N=30 pass                      : %.1f ms" % d["warm30"])
    print("   sort of segment (1) at N=30 by rank : %.1f ms over %d rows"
          % (d["sort_ms"], d["sorted"]))
    print("\ntemp dir %s" % tmp)


if __name__ == "__main__":
    main()
