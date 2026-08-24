# -*- coding: utf-8 -*-
"""ROUND-2 PROBE 10 - the single consolidated snapshot design_v2.md cites.

Evaluator A's A4: v1 mixed numbers from 02:19 and 02:32 in the same section. Every
corpus number in design_v2.md comes from ONE run of this script. Re-run it to
refresh; the numbers WILL move (the corpus grows hourly) which is why no assertion
downstream may hard-code one.

    export PYTHONIOENCODING=utf-8
    D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_pm2_10_snapshot.py
"""
import json
import os
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from _pm2_base import (ALWAYS_OPEN, CAP, CEIL, CL, DB, FLOOR, N_CHOICES, N_DEFAULT,
                       OPEN_ORDER, SEG_OPEN_CAP, SEGS, banner, cap2_map, days_back,
                       dkey, first_screen_keys, load, open_expected, open_plan,
                       openable, superseded, win_rows)

J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def wm(anchor, k):
    d0 = datetime.strptime(anchor, "%Y-%m-%d")
    return (d0 - timedelta(days=k)).strftime("%Y-%m-%d") + " 08:00"


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("ROUND-2 CONSOLIDATED SNAPSHOT")
    print("python      %s" % sys.version.split()[0])
    print("interpreter %s" % sys.executable)
    print("platform    %s" % platform.platform())
    print("PYTHONIOENCODING=%r" % os.environ.get("PYTHONIOENCODING"))
    print("constants   CAP=%d FLOOR=%d CEIL=%d SEG_OPEN_CAP=%s N_DEFAULT=%d"
          % (CAP, FLOOR, CEIL, SEG_OPEN_CAP, N_DEFAULT))
    print("corpus      %d rows, days %s, companies %d, profiles %d, overrides %d"
          % (len(rows), ",".join(days), len({CL.norm(r["company_name"]) for r in rows}),
             len(profiles), len(overrides)))
    per_day = Counter(r["_day"] for r in rows)

    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)
    bar = Counter(r["_day"] for r in rows if id(r) not in S and r["_day"] <= anchor)
    for d in days:
        print("            %s raw %5d  ONE-RULE bar %5d  (v1 per-day dedup %5d)"
              % (d, per_day[d], bar[d], len(CL.day_rows(rows, d))))

    # ------------------------------------------------------------------ [T1]
    print("\n[T1] window view, anchor %s, one dedup rule (keep-newest, _day<=anchor)" % anchor)
    print("     %-4s %7s %7s %7s  %s  %6s %5s %6s"
          % ("N", "rawwin", "dedup", "dropped", " ".join("%6s" % s for s in SEGS),
             "cap2S", "open", "Sbar"))
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept = [r for r in w if id(r) not in S]
        raw = Counter(R.segment(r) for r in kept)
        c2 = cap2_map(R, kept)
        _p, opened = open_plan(c2)
        sbar = sum(bar[d] for d in days_back(anchor, n))
        assert sum(raw.values()) == len(kept) == len({dkey(r) for r in w}) == sbar
        assert opened == open_expected(c2)
        assert min(FLOOR, openable(c2)) <= opened <= CEIL
        print("     %-4d %7d %7d %7d  %s  %6d %5d %6d"
              % (n, len(w), len(kept), len(w) - len(kept),
                 " ".join("%6d" % raw.get(s, 0) for s in SEGS), sum(c2.values()),
                 opened, sbar))
    print("     asserted for every N: I1 (Sraw==dedup==distinct keys==Sbar),")
    print("     open==closed form, min(FLOOR,openable)<=open<=CEIL")

    # ------------------------------------------------------------------ [T2]
    print("\n[T2] first screen AT 08:00 (the hour run_daily_report.bat generates it)")
    print("     %-12s %-4s %7s %7s %7s %7s %7s"
          % ("anchor", "N", "open", "openable", "new", "new%", "repeat"))
    prev_keys = {}
    for d in days:
        sub = [r for r in rows if (r.get("_recorded") or "") <= d + " 08:00"]
        if not sub:
            continue
        Rd = CL.LaneResolver(sub, profiles, d, overrides=overrides, priority=priority)
        Sd = superseded(sub, d)
        for n in N_CHOICES:
            kept = [r for r in win_rows(sub, d, n) if id(r) not in Sd]
            c2 = cap2_map(Rd, kept)
            _p, opened = open_plan(c2)
            scr = first_screen_keys(Rd, kept)
            pc = wm(d, 1)
            new = sum(1 for _s, _c, r in scr if (r.get("_recorded") or "") > pc)
            ks = {dkey(r) for _s, _c, r in scr}
            rep = len(prev_keys.get(n, set()) & ks)
            prev_keys[n] = ks
            print("     %-12s %-4d %7d %7d %7d %6d%% %7d"
                  % (d, n, opened, openable(c2), new,
                     100 * new // max(1, len(scr)), rep))

    # ------------------------------------------------------------------ [T3]
    print("\n[T3] the three watermark-derived views (no persisted user state at all)")
    print("     %-12s %-4s | %6s %6s %6s | %5s %5s %5s | repeat(new)"
          % ("anchor", "N", "all", "new", "wm", "op-a", "op-n", "op-w"))
    prevn = {}
    for d in days:
        sub = [r for r in rows if (r.get("_recorded") or "") <= d + " 08:00"]
        if not sub:
            continue
        Rd = CL.LaneResolver(sub, profiles, d, overrides=overrides, priority=priority)
        Sd = superseded(sub, d)
        pp, pc = wm(d, 2), wm(d, 1)
        for n in N_CHOICES:
            kept = [r for r in win_rows(sub, d, n) if id(r) not in Sd]
            f = {"all": kept,
                 "new": [r for r in kept if (r.get("_recorded") or "") > pc],
                 "wm": [r for r in kept if pp < (r.get("_recorded") or "") <= pc]}
            ops = {}
            for k, sel in f.items():
                _p, ops[k] = open_plan(cap2_map(Rd, sel))
            ks = {dkey(r) for _s, _c, r in first_screen_keys(Rd, f["new"])}
            rep = len(prevn.get(n, set()) & ks)
            prevn[n] = ks
            print("     %-12s %-4d | %6d %6d %6d | %5d %5d %5d | %d/%d"
                  % (d, n, len(f["all"]), len(f["new"]), len(f["wm"]),
                     ops["all"], ops["new"], ops["wm"], rep, len(ks)))

    # ------------------------------------------------------------------ [T4]
    print("\n[T4] section 7 (rows the last issue showed that the window does NOT cover)")
    st = DB.read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    pool = [r for r in rows if pp < (r.get("_recorded") or "") <= pc and id(r) not in S]
    p124 = [r for r in pool if R.segment(r) in ("1a_t3", "1a_t2", "B1")]
    print("     shipped watermark: prev_prev=%s prev_cutoff=%s" % (pp, pc))
    print("     interval holds %d deduped rows, %d of them in (1)(2)(4)"
          % (len(pool), len(p124)))
    for n in N_CHOICES:
        wk = {dkey(r) for r in win_rows(rows, anchor, n)}
        out = [r for r in p124 if dkey(r) not in wk]
        print("     N=%-3d section 7 shows %3d   (the other %3d are inside the window)"
              % (n, len(out), len(p124) - len(out)))

    # ------------------------------------------------------------------ [T5]
    print("\n[T5] payload, encoding E4 (column arrays, interned day/segment/prefix)")
    cos = sorted({CL.norm(r["company_name"]) for r in rows})
    cidx = {c: i for i, c in enumerate(cos)}
    segi = {s: i for i, s in enumerate(SEGS)}
    prefs = ["https://www.linkedin.com", "https://jobs.ashbyhq.com",
             "https://job-boards.greenhouse.io", "https://jobs.lever.co",
             "https://boards.greenhouse.io"]
    pmap = {p: i for i, p in enumerate(prefs)}
    tot = 0
    for d in days:
        sub = [r for r in rows if r["_day"] == d]
        col = defaultdict(list)
        for r in sub:
            l = (r.get("job_link") or "").strip()
            p = "/".join(l.split("/")[:3])
            rec = r.get("_recorded") or ""
            col["c"].append(cidx[CL.norm(r["company_name"])])
            col["g"].append(segi[R.segment(r)])
            col["t"].append((r.get("job_title") or "").strip())
            col["lp"].append(pmap.get(p, -1))
            col["l"].append(l[len(p):] if p in pmap else l)
            col["s"].append({"newgrad": 0, "ats_direct": 1, "ddg": 2}[r["_source"]])
            col["r"].append(int(rec[11:13] + rec[14:16]) if len(rec) >= 16 else 0)
            col["x"].append(1 if id(r) in S else 0)
        b = len(J(dict(col)).encode("utf-8"))
        tot += b
        print("     data-%s.js %5d rows %8d B  %.1f B/row" % (d, len(sub), b,
                                                              b / float(len(sub))))
    idx = {"co": [[R.profile(c).get("name") or c, R.profile(c)["tier"],
                   R.profile(c)["prom"], R.window_count(c), 1 if c in R.board else 0]
                  for c in cos],
           "o": list(range(len(cos))), "days": days_back(anchor, 30)}
    ib = len(J(idx).encode("utf-8"))
    print("     index co/o/days                 %8d B  (%d companies)" % (ib, len(cos)))
    print("     + pre-rendered chrome for 5 N   ~  30000 B  (measured in _pm2_03_size)")
    print("     total written today             %8d B  (%.2f MB)"
          % (tot + ib + 30000, (tot + ib + 30000) / 2.0 ** 20))
    bpr = tot / float(len(rows))
    print("     projection at 2000 rows/day: %.0f B/day, 30 retained days = %.2f MB"
          % (2000 * bpr, 2000 * bpr * 30 / 2 ** 20))


if __name__ == "__main__":
    main()
