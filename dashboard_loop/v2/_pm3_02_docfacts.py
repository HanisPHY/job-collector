# -*- coding: utf-8 -*-
"""ROUND-3 PROBE 2 - the facts behind the four nice-to-haves adopted this round.

A7 / B2-2 : where the stale "writes <day>.html" sentence still lives, and what grep
            criterion the acceptance step can actually use.
B2-1      : does a regex aimed at the SHAPE of a hardcoded segment-order array fire
            on the thing we want to catch and stay quiet on normal JS?
B9-residual: the size of the gap between the hero/stack numbers (view=all) and what
            a segment actually shows after switching to view=new.
"""
import io
import os
import re
import subprocess
from collections import Counter, defaultdict

from _pm2_base import CL, N_CHOICES, ROOT, SEGS, banner, load, superseded, win_rows


def main():
    rows, profiles, overrides, priority = load()
    banner("ROUND-3 PROBE 2  facts for A7 / B2-2 / B2-1 / B9-residual")

    # ------------------------------------------------------------- A7 / B2-2
    print("\n[A7/B2-2] every place that still promises a per-day html file")
    pat = re.compile(r"day\.html|<day>\.html|logs/dashboard")
    hits = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "__pycache__", "node_modules", "logs")]
        rel_base = os.path.relpath(base, ROOT).replace("\\", "/")
        for fn in files:
            if not fn.endswith((".py", ".md", ".bat")):
                continue
            p = os.path.join(base, fn)
            rel = (rel_base + "/" + fn).lstrip("./")
            try:
                txt = io.open(p, encoding="utf-8").read()
            except Exception:
                continue
            for i, line in enumerate(txt.splitlines(), 1):
                if pat.search(line):
                    hits.append((rel, i, line.strip()))
    outside = [h for h in hits if not h[0].startswith("dashboard_loop/")]
    print("    matches outside dashboard_loop/ : %d" % len(outside))
    for rel, i, line in outside:
        print("      %-40s :%-4d %s" % (rel, i, line[:78]))
    print("    (dashboard_loop/ has %d more, all of them design history)"
          % (len(hits) - len(outside)))
    src = io.open(os.path.join(ROOT, "dashboard.py"), encoding="utf-8").read().splitlines()
    print("\n    dashboard.py line 9 verbatim: %r" % src[8])
    sch = io.open(os.path.join(ROOT, "SCHEDULING.md"), encoding="utf-8").read().splitlines()
    print("    SCHEDULING.md line 204 verbatim: %r" % sch[203][:110])
    print("\n    -> acceptance-12 grep criterion that is actually satisfiable:")
    print('       grep -rn "logs/dashboard/<day>\\|<day>.html" --include=*.py '
          '--include=*.md --include=*.bat . | grep -v "^./dashboard_loop/" '
          '| grep -v "^./docs/req/"')
    print("       must print NOTHING (docs/req/ is the frozen requirement, "
          "dashboard_loop/ is design history)")

    # ------------------------------------------------------------------ B2-1
    print("\n[B2-1] regex for the SHAPE 'hardcoded segment-order array literal'")
    rx = re.compile(r"""[\[\(]\s*(?:"|')1a_t3(?:"|')""")
    good = [
        'var el = document.querySelector(\'[data-gidx="\' + g + \'"]\');',
        'var open = JOB_INDEX.check[view][n].plan;',
        'for (var g = 0; g < 6; g++) { render(g); }',
        'wrap.querySelectorAll("[data-gidx]").forEach(fill);',
    ]
    bad = [
        'var SEGS = ["1a_t3","1a_t2","1b","B1","B2","C"];',
        "var order = ['1a_t3', '1a_t2', '1b', 'B1', 'B2', 'C'];",
        'var ids = [ "1a_t3", "1a_t2" ];',
        'foo(["1a_t3","1b"])',
    ]
    for s in good:
        print("    quiet on OK code   : %-5s %s" % (not rx.search(s), s[:62]))
    for s in bad:
        print("    fires on hardcode  : %-5s %s" % (bool(rx.search(s)), s[:62]))
    print("    -> combined with the existing plain-string blacklist, F23 now catches")
    print("       both 'a stray segment key' and 'the whole order array'.")

    # ------------------------------------------------------------ B9-residual
    print("\n[B9-residual] hero / stack (view=all) vs what view=new actually shows")
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)
    st = __import__("dashboard").read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    for n in (3,):
        kept = [r for r in win_rows(rows, anchor, n) if id(r) not in S]
        a = Counter(R.segment(r) for r in kept)
        nw = Counter(R.segment(r) for r in kept if (r.get("_recorded") or "") > pc)
        print("    N=%d, anchor %s, prev_cutoff %s" % (n, anchor, pc))
        print("      %-6s %8s %8s %8s" % ("seg", "all", "new", "ratio"))
        for s in SEGS:
            ratio = (a[s] / float(nw[s])) if nw[s] else float("inf")
            print("      %-6s %8d %8d %8s"
                  % (s, a[s], nw[s], ("%.0fx" % ratio) if nw[s] else "n/a"))
    print("    -> the hero number and the stacked bar keep showing the 'all' column")
    print("       while the segment tables show the 'new' column. That gap is why the")
    print("       qualifier belongs in the hero card TITLE, not only next to the switch.")


if __name__ == "__main__":
    main()
