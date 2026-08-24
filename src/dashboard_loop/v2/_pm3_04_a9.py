# -*- coding: utf-8 -*-
"""ROUND-3.1 PROBE - close A9: the in-group ordering was described two ways.

  3.5  : "same company ordered by (_recorded desc, title)"        <- day + time
  3.10 : "in group by (r desc, title desc), then (day idx, row idx) tie-break"
         but 3.2 defines r as HH*100+MM, i.e. the day is NOT in it.

For a company whose rows span two days the two readings pick different rows into
the CAP=2 head. And because Python and JS would BOTH follow the same wrong words,
hsum/osum would stay green - the checksum proves agreement, not correctness.

  A. measure the divergence on real data (cross-day groups, segment-1 examples)
  B. prove the corrected key (d desc, r desc, title desc, i desc) is identical to
     sorting by the full _recorded string
  C. make JS do the GROUPING AND SORTING itself with the corrected comparator, in
     real Chrome under file://, and compare its hsum/osum with Python's
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict

from _pm2_base import (CAP, CL, N_CHOICES, SEGS, banner, days_back, load,
                       superseded, win_rows)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
VIEWS = ("all", "new", "wm")
MASK = 0xFFFFFFFF


def mix(h, v):
    h = (h ^ (v & MASK)) & MASK
    return (h * 16777619) & MASK


def seq_hash(pairs):
    h = 2166136261
    for d, i in pairs:
        h = mix(h, d)
        h = mix(h, i)
    return mix(h, len(pairs))


JS = """
function mix(h,v){h=(h^(v>>>0))>>>0;return Math.imul(h,16777619)>>>0;}
function seqHash(p){var h=2166136261>>>0;var k;
  for(k=0;k<p.length;k++){h=mix(h,p[k][0]);h=mix(h,p[k][1]);}
  return mix(h,p.length);}
/* row = [rank, d, r, title, i]  -- CORRECTED comparator: day first, then r */
function cmpRow(a,b){
  if(a[1]!==b[1]) return b[1]-a[1];
  if(a[2]!==b[2]) return b[2]-a[2];
  if(a[3]!==b[3]) return a[3]<b[3]?1:-1;
  return b[4]-a[4];
}
function build(rows){
  var by={},k;
  for(k=0;k<rows.length;k++){var g=rows[k][0];(by[g]=by[g]||[]).push(rows[k]);}
  var ranks=Object.keys(by).map(Number).sort(function(a,b){return a-b;});
  var head=[],over=[];
  for(k=0;k<ranks.length;k++){
    var rs=by[ranks[k]];rs.sort(cmpRow);
    for(var j=0;j<rs.length;j++){(j<2?head:over).push([rs[j][1],rs[j][4]]);}
  }
  return {h:seqHash(head),o:seqHash(over),nh:head.length,no:over.length};
}
"""


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("ROUND-3.1 PROBE  A9: in-group ordering, r-only vs (d, r)")
    print("corpus %d rows, days %s, anchor %s" % (len(rows), ",".join(days), anchor))

    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)
    all_days = days_back(anchor, 30)
    didx = {d: i for i, d in enumerate(all_days)}
    ridx = {}
    for d in days:
        for i, r in enumerate([x for x in rows if x["_day"] == d]):
            ridx[id(r)] = i
    cos = sorted({CL.norm(r["company_name"]) for r in rows})
    rank = {c: k for k, c in enumerate(sorted(cos, key=R.sort_key))}
    hhmm = {}
    for r in rows:
        rec = r.get("_recorded") or ""
        hhmm[id(r)] = int(rec[11:13] + rec[14:16]) if len(rec) >= 16 else 0

    def key_full(r):
        """sorting by the complete _recorded string - the intent in 3.5"""
        return ((r.get("_recorded") or ""), (r.get("job_title") or ""),
                didx[r["_day"]], ridx[id(r)])

    def key_fixed(r):
        """the corrected canonical key that goes into the spec"""
        return (didx[r["_day"]], hhmm[id(r)], (r.get("job_title") or ""), ridx[id(r)])

    def key_ronly(r):
        """design_v3 3.10 taken literally: r first, day only as a tie-break"""
        return (hhmm[id(r)], (r.get("job_title") or ""), didx[r["_day"]], ridx[id(r)])

    # ------------------------------------------------------------------ A
    print("")
    print("[A] cross-day company groups: does the reading change the CAP=2 head?")
    kept30 = [r for r in win_rows(rows, anchor, 30) if id(r) not in S]
    groups = defaultdict(list)
    for r in kept30:
        groups[(R.segment(r), CL.norm(r["company_name"]))].append(r)
    cross = {k: v for k, v in groups.items() if len({x["_day"] for x in v}) > 1}
    diff = []
    for k, v in cross.items():
        a = [id(x) for x in sorted(v, key=key_full, reverse=True)[:CAP]]
        b = [id(x) for x in sorted(v, key=key_ronly, reverse=True)[:CAP]]
        if a != b:
            diff.append(k)
    print("    cross-day groups: %d ; head differs under r-only: %d (%.1f%%)"
          % (len(cross), len(diff), 100.0 * len(diff) / max(1, len(cross))))
    shown = 0
    for seg, c in sorted(diff, key=lambda kv: (SEGS.index(kv[0]), kv[1])):
        if seg != "1a_t3" or shown >= 3:
            continue
        shown += 1
        v = cross[(seg, c)]
        print("    example seg=%s  %s  (%d rows)" % (seg, c, len(v)))
        for label, kf in (("correct (d,r)", key_fixed), ("literal r-only", key_ronly)):
            picked = sorted(v, key=kf, reverse=True)[:CAP]
            print("        %-15s -> %s" % (label,
                  " | ".join("%s %04d" % (x["_day"][5:], hhmm[id(x)]) for x in picked)))

    # ------------------------------------------------------------------ B
    print("")
    print("[B] corrected key (d desc, r desc, title desc, i desc) == full _recorded?")
    bad = 0
    for k, v in groups.items():
        if [id(x) for x in sorted(v, key=key_full, reverse=True)] != \
           [id(x) for x in sorted(v, key=key_fixed, reverse=True)]:
            bad += 1
    print("    groups whose FULL ordering differs between the two keys: %d / %d"
          % (bad, len(groups)))

    # ------------------------------------------------------------------ C
    print("")
    print("[C] JS groups and sorts on its own with the corrected comparator, then its")
    print("    hsum/osum is compared with Python's")
    st = __import__("dashboard").read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    payload, py = {}, {}
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, anchor, n) if id(r) not in S]
        for f in VIEWS:
            if f == "all":
                sel = kept
            elif f == "new":
                sel = [r for r in kept if (r.get("_recorded") or "") > pc]
            else:
                sel = [r for r in kept if pp < (r.get("_recorded") or "") <= pc]
            by = defaultdict(list)
            for r in sel:
                by[R.segment(r)].append(r)
            for s in SEGS:
                key = "%s|%d|%s" % (f, n, s)
                payload[key] = [[rank[CL.norm(r["company_name"])], didx[r["_day"]],
                                 hhmm[id(r)], (r.get("job_title") or ""), ridx[id(r)]]
                                for r in by.get(s, [])]
                g = defaultdict(list)
                for r in by.get(s, []):
                    g[rank[CL.norm(r["company_name"])]].append(r)
                head, over = [], []
                for rk in sorted(g):
                    rs = sorted(g[rk], key=key_fixed, reverse=True)
                    head.extend([didx[x["_day"]], ridx[id(x)]] for x in rs[:CAP])
                    over.extend([didx[x["_day"]], ridx[id(x)]] for x in rs[CAP:])
                py[key] = {"h": seq_hash(head), "o": seq_hash(over),
                           "nh": len(head), "no": len(over)}
    tmp = tempfile.mkdtemp(prefix="pm3a9_")
    io.open(os.path.join(tmp, "d.js"), "w", encoding="utf-8").write(
        "window.D=" + json.dumps(payload, ensure_ascii=False,
                                 separators=(",", ":")) + ";")
    io.open(os.path.join(tmp, "a.html"), "w", encoding="utf-8").write(
        '<!doctype html><html><head><meta charset="utf-8"></head><body>'
        '<pre id="out">P</pre><script src="d.js"></script><script>' + JS +
        'var R={};for(var k in window.D){R[k]=build(window.D[k]);}'
        'document.getElementById("out").textContent=JSON.stringify(R);'
        '</script></body></html>')
    js = None
    if os.path.exists(CHROME):
        prof = tempfile.mkdtemp(prefix="pm3a9p_")
        try:
            p = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                 "--user-data-dir=" + prof, "--virtual-time-budget=25000", "--dump-dom",
                 "file:///" + os.path.join(tmp, "a.html").replace("\\", "/")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            m = re.search(r'<pre id="out">(.*?)</pre>',
                          p.stdout.decode("utf-8", "replace"), re.S)
            js = json.loads(m.group(1)) if m else None
        finally:
            shutil.rmtree(prof, ignore_errors=True)
    if js is None:
        print("    chrome unavailable -- CANNOT CONFIRM")
    else:
        bad2 = [k for k in py if js.get(k) != py[k]]
        print("    cells: %d (3 views x %d N x %d segs); rows shipped to JS: %d"
              % (len(py), len(N_CHOICES), len(SEGS),
                 sum(len(v) for v in payload.values())))
        print("    Python vs JS (JS grouped and sorted itself): disagreements %d"
              % len(bad2))
        for k in bad2[:5]:
            print("       %s js=%s py=%s" % (k, js[k], py[k]))
    print("")
    print("temp dir %s" % tmp)


if __name__ == "__main__":
    main()
