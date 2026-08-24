# -*- coding: utf-8 -*-
"""PM RULING PROBE - evidence for adjudicating impl_v1's 3 design_defects and the
two deviations that actually need a number (#4 first-screen DOM, #8 unenriched).

Nothing here writes to the repo or to logs/.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict

from _pm2_base import (CAP, CL, DB, N_CHOICES, SEGS, banner, days_back, load,
                       superseded, win_rows)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

DOM_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<div id="wrap"></div><pre id="out">P</pre><script>
function build(n){
  var t0 = performance.now();
  var h = '<table><tbody>';
  for (var i = 0; i < n; i++){
    h += '<tr data-k="' + i + '"><td class="co"><span class="t t3">T3</span> Company '
      + i + '</td><td class="ti"><a href="https://x/' + i
      + '">Software Engineer, New Grad ' + i + '</a></td><td class="sm">2026-08-20</td>'
      + '<td class="sm">LinkedIn</td><td class="num">7</td><td class="sm sig"></td></tr>';
  }
  h += '</tbody></table>';
  var d = document.createElement('div');
  d.innerHTML = h;
  document.getElementById('wrap').appendChild(d);
  void d.offsetHeight;                       /* force layout */
  return +(performance.now() - t0).toFixed(1);
}
var R = {};
[47, 153, 400, 800, 1600, 3200].forEach(function(n){ R[n] = build(n); });
R.tr = document.querySelectorAll('tr').length;
document.getElementById('out').textContent = JSON.stringify(R);
</script></body></html>
"""


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("PM RULING PROBE  D1 / deviation #4 / deviation #8")
    print("corpus %d rows, days %s, anchor %s" % (len(rows), ",".join(days), anchor))
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)

    # ------------------------------------------------------------------- D1
    print("")
    print("[D1] the two candidate predicates for the '新' marker")
    st = DB.read_state()
    pc = st.get("cutoff") or ""            # payload field prev_cutoff (last issue)
    cut_now = max((r.get("_recorded") or "") for r in rows)
    print("    payload cutoff      = max(_recorded) of this run = %s" % cut_now)
    print("    payload prev_cutoff = logs/last_report.json cutoff = %s" % pc)
    a = sum(1 for r in rows if (r.get("_recorded") or "") > cut_now)
    b = sum(1 for r in rows if (r.get("_recorded") or "") > pc)
    print("    rows with _recorded >  cutoff       : %d   <- section 3.6 taken literally"
          % a)
    print("    rows with _recorded >  prev_cutoff  : %d   <- B4 / section 5 / v1 behaviour"
          % b)
    src = io.open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "dashboard.py"),
        encoding="utf-8").read()
    print("    v1 dashboard.py passes %s into table_html: %s"
          % ("prev_cutoff", "table_html(R, shown, prev_cutoff)" in src
             or "prev_cutoff" in src))

    # ------------------------------------------------------------------- #4
    print("")
    print("[#4] how big is 'the whole cap2 head of the two default-open segments'?")
    print("    %-4s %8s %8s %8s %8s %10s"
          % ("N", "1a_t3", "B1", "sum", "visible", "bound(2*co)"))
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, anchor, n) if id(r) not in S]
        by = defaultdict(lambda: defaultdict(list))
        for r in kept:
            by[R.segment(r)][CL.norm(r["company_name"])].append(r)
        cap2 = {s: sum(min(CAP, len(v)) for v in by[s].values()) for s in SEGS}
        nco = {s: len(by[s]) for s in SEGS}
        vis = min(cap2["1a_t3"], 35) + min(cap2["B1"], 12)
        print("    %-4d %8d %8d %8d %8d %10d"
              % (n, cap2["1a_t3"], cap2["B1"], cap2["1a_t3"] + cap2["B1"], vis,
                 2 * (nco["1a_t3"] + nco["B1"])))
    print("    cap2 <= 2 x (number of companies in that segment): the DOM cost of")
    print("    deviation #4 is bounded by the company table, not by the row count.")

    # a 30-day projection out of the real rows (same method as _pm_07)
    print("")
    print("    30-day projection: how many distinct companies can reach (1) and (4)?")
    allco = {CL.norm(r["company_name"]) for r in rows}
    seg_co = defaultdict(set)
    for r in rows:
        seg_co[R.segment(r)].add(CL.norm(r["company_name"]))
    print("    corpus so far: %d companies; (1) %d, (4) %d -> 2x sum = %d rows of DOM"
          % (len(allco), len(seg_co["1a_t3"]), len(seg_co["B1"]),
             2 * (len(seg_co["1a_t3"]) + len(seg_co["B1"]))))
    print("    profile table holds %d companies, so even if EVERY tier-3 entry company"
          % len(profiles))
    print("    and every own-board company showed up in one 30-day window, the two")
    print("    segments' cap2 heads stay a few hundred rows, not tens of thousands.")

    # browser cost of that many <tr>
    if os.path.exists(CHROME):
        tmp = tempfile.mkdtemp(prefix="pm4dom_")
        io.open(os.path.join(tmp, "d.html"), "w", encoding="utf-8").write(DOM_PAGE)
        prof = tempfile.mkdtemp(prefix="pm4p_")
        try:
            p = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                 "--user-data-dir=" + prof, "--virtual-time-budget=20000", "--dump-dom",
                 "file:///" + os.path.join(tmp, "d.html").replace("\\", "/")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            m = re.search(r'<pre id="out">(.*?)</pre>',
                          p.stdout.decode("utf-8", "replace"), re.S)
        finally:
            shutil.rmtree(prof, ignore_errors=True)
        if m:
            d = json.loads(m.group(1))
            print("")
            print("    Chrome (headless, file://) cost of building N <tr> + forcing layout:")
            for k in ("47", "153", "400", "800", "1600", "3200"):
                print("       %5s rows -> %6.1f ms" % (k, d[k]))
        else:
            print("    (no DOM timing: chrome produced no output)")

    # ------------------------------------------------------------------- #8
    print("")
    print("[#8] unenriched: 'appeared today' vs 'appeared in the default 3-day window'")
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["_day"]].append(r)
    first_seen = {}
    for r in sorted(rows, key=lambda z: (z.get("_recorded") or "")):
        first_seen.setdefault(CL.norm(r["company_name"]), r["_day"])
    for label, scope in (("today only", days[-1:]),
                         ("default window (3 days)", days[-3:])):
        seen = {}
        for d in scope:
            for r in by_day[d]:
                seen.setdefault(CL.norm(r["company_name"]),
                                (r.get("company_name") or "").strip())
        un = [k for k in seen if R.profile(k).get("stage", 0) < 1]
        stale = [k for k in un if first_seen.get(k, days[-1]) < days[-1]]
        print("    %-26s companies %5d  unenriched %4d  of which first seen on an "
              "EARLIER day %4d" % (label, len(seen), len(un), len(stale)))
    print("    -> the ones first seen earlier have already survived at least one")
    print("       07:30 enrichment pass, so the v1 sentence 'they are waiting for")
    print("       tomorrow 07:30' is not true for them.")


if __name__ == "__main__":
    main()
