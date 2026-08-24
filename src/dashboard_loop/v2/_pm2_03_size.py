# -*- coding: utf-8 -*-
"""ROUND-2 PROBE 3 - what the subtractions actually cost.

(1) B9 + a subtraction: ship every non-row-table block (trend SVG, stacked bar,
    legend, panel 2', panel 3, hero, segment summaries) as PYTHON-RENDERED HTML,
    one string per N, and let JS do `el.innerHTML = chrome[n][slot]`. That deletes
    the SVG renderer, the panel renderer and the summary renderer from dashboard.js
    entirely. Measure what those strings weigh for 5 N.

(2) A1 + a subtraction: stop writing per-day <day>.html. Quantify what is lost
    (drift rows that a pinned page would have shown differently) and what is saved.

(3) B3: sampling anchors for the folded segments - measure the cost of adding
    two [day,row] coordinates per segment per N to check.
"""
import json
import os
from collections import Counter, defaultdict

from _pm2_base import (CL, DB, N_CHOICES, SEGS, banner, cap2_map, dkey, load,
                       open_plan, superseded, win_rows, days_back)

J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
B = lambda s: len(s.encode("utf-8")) if isinstance(s, str) else len(J(s).encode("utf-8"))


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("ROUND-2 PROBE 3  cost of the v2 subtractions")
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)

    # ---------------------------------------------------------------- (1) chrome
    print("\n[1] Python-rendered chrome, one set of strings per N")
    bar = Counter(r["_day"] for r in rows if id(r) not in S and r["_day"] <= anchor)
    total = 0
    for n in N_CHOICES:
        ds = days_back(anchor, n)
        kept = [r for r in win_rows(rows, anchor, n) if id(r) not in S]
        raw = Counter(R.segment(r) for r in kept)
        c2 = cap2_map(R, kept)
        _p, opened = open_plan(c2)
        # trend: reuse dashboard.py's own SVG writer, N bars instead of 7
        old_td = DB.TREND_DAYS
        try:
            DB.TREND_DAYS = n
            svg_t = DB.svg_trend(anchor, {d: bar.get(d, 0) for d in ds})
        finally:
            DB.TREND_DAYS = old_td
        svg_s = DB.svg_stack(raw)
        legend = "".join('<span><i style="background:var(--s%s)"></i>%s %s %d</span>'
                         % (DB.SEG_META[s]["step"] or "", DB.SEG_META[s]["n"],
                            DB.SEG_META[s]["title"], raw.get(s, 0)) for s in SEGS)
        # panel 2' : intermediary share, top 25 companies in the window
        cco = Counter(CL.norm(r["company_name"]) for r in kept if R.segment(r) == "C")
        p2 = []
        for c, k in sorted(cco.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
            v = R.profile(c)
            p2.append("<tr><td>%s</td><td>%d</td><td>%d</td><td>%s</td></tr>"
                      % (DB.esc(v.get("name") or c), k, R.window_count(c),
                         DB.esc(", ".join(R.company_lane(c)[1]))))
        # panel 3 : repost evidence, top 15
        at = [r for r in kept if " at " in (r.get("job_title") or "")]
        atc = Counter(CL.norm(r["company_name"]) for r in at)
        p3 = []
        for c, k in sorted(atc.items(), key=lambda kv: (-kv[1], kv[0]))[:15]:
            ex = next(r for r in at if CL.norm(r["company_name"]) == c)
            p3.append("<tr><td>%s</td><td>%d</td><td>%s</td></tr>"
                      % (DB.esc(R.profile(c).get("name") or c), k,
                         DB.esc((ex.get("job_title") or "")[:60])))
        summ = "".join('<span data-gidx="%d">raw %d &middot; cap2 %d</span>'
                       % (i, raw.get(s, 0), c2[s]) for i, s in enumerate(SEGS))
        hero = ('<div class="v">%d</div><div class="v">%d</div><div class="v">%d</div>'
                % (c2["1a_t3"], opened, len(kept)))
        chrome = {"trend": svg_t, "stack": svg_s, "legend": legend,
                  "p2": "".join(p2), "p3": "".join(p3), "summ": summ, "hero": hero}
        sz = B(chrome)
        total += sz
        print("   N=%-3d trend %5d  stack %4d  legend %4d  p2 %5d  p3 %4d  summ %4d "
              " hero %3d  = %6d B"
              % (n, B(svg_t), B(svg_s), B(legend), B("".join(p2)), B("".join(p3)),
                 B(summ), B(hero), sz))
    print("   all 5 N together: %d B (%.1f KB) -> this is the whole price of deleting"
          % (total, total / 1024.0))
    print("   the SVG renderer, the panel renderer and the summary renderer from JS.")

    # ---------------------------------------------------------------- (2) day html
    print("\n[2] dropping per-day <day>.html")
    outdir = DB.OUT_DIR
    tot_b = 0
    for f in sorted(os.listdir(outdir)):
        if f.endswith(".html") and f != "latest.html":
            b = os.path.getsize(os.path.join(outdir, f))
            tot_b += b
            print("   today on disk: %-20s %8d B" % (f, b))
    print("   v1 cost: ~%d B per retained day; v2 skeleton would be ~2 KB per day"
          % (tot_b // max(1, len([f for f in os.listdir(outdir)
                                  if f.endswith('.html') and f != 'latest.html'])))
          )
    # what a pinned page would show differently from latest.html
    for pin in days[:-1]:
        Rp = CL.LaneResolver(rows, profiles, pin, overrides=overrides, priority=priority)
        Sp = superseded(rows, pin)
        day_rows_ = [r for r in rows if r["_day"] == pin]
        gdiff = sum(1 for r in day_rows_ if Rp.segment(r) != R.segment(r))
        xdiff = sum(1 for r in day_rows_ if (id(r) in Sp) != (id(r) in S))
        both = sum(1 for r in day_rows_
                   if Rp.segment(r) != R.segment(r) or (id(r) in Sp) != (id(r) in S))
        print("   pin=%s : %d rows; judged today vs judged on its own day -> "
              "g differs %d, x differs %d, union %d (%.2f%%)"
              % (pin, len(day_rows_), gdiff, xdiff, both,
                 100.0 * both / max(1, len(day_rows_))))
    print("   -> that union is EXACTLY what a pinned page would have shown differently.")
    print("      Dropping <day>.html loses that; the N-day window still shows every")
    print("      one of those rows, under today's judgement, with its date.")

    # ---------------------------------------------------------------- (3) anchors
    print("\n[3] B3 sampling anchors for the folded segments")
    idx_of = {}
    for d in days:
        for i, r in enumerate([x for x in rows if x["_day"] == d]):
            idx_of[id(r)] = (days.index(d), i)
    check = {}
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, anchor, n) if id(r) not in S]
        by = defaultdict(lambda: defaultdict(list))
        for r in kept:
            by[R.segment(r)][CL.norm(r["company_name"])].append(r)
        anch = {}
        for s in SEGS:
            groups = sorted(by[s].items(), key=lambda kv: R.sort_key(kv[0]))
            head = []
            for c, rs in groups:
                rs = sorted(rs, key=lambda r: ((r.get("_recorded") or ""),
                                               r.get("job_title") or ""), reverse=True)
                head.extend(rs[:2])
            if head:
                anch[s] = [idx_of[id(head[0])], idx_of[id(head[-1])],
                           idx_of[id(head[len(head) // 2])]]
        check[str(n)] = anch
    print("   3 coordinates (first / middle / last of each segment's cap2 head) x 6 "
          "segments x 5 N = %d B" % B(check))
    print("   sample N=7: %s" % J(check["7"])[:160])


if __name__ == "__main__":
    main()
