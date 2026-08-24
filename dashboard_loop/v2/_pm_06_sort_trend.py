# -*- coding: utf-8 -*-
"""PROBE 6 - three small things that would silently go wrong.

1. req2 4.2 decision 4 prints the sort key as
       (not in priority, -tier, -prom, -window rows, company)
   but company_lane.sort_key is
       (not in priority, -prom, -tier, -window rows, company)
   tier and prom are SWAPPED. Measure how much of segment (1)'s first screen moves
   if an engineer implements the documented tuple instead of the shipped one.

2. trend bars: per-day dedup (today's behaviour) does NOT sum to the window dedup
   total. Measure the gap, because the page shows both numbers next to each other.

3. the replacement for test_dashboard_has_no_external_dependency: run the proposed
   assertion against pages that SHOULD pass and pages that MUST fail, so the new
   form is not vacuous.
"""
import re
from collections import defaultdict

from _pm_base import CL, N_CHOICES, banner, days_back, dkey, load, win_rows

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")


def main():
    rows, profiles, overrides, priority = load()
    day = max(r["_day"] for r in rows)
    banner("PROBE 6  sort key / trend reconciliation / dependency assertion")
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)

    # ---------------------------------------------------------------- 1. sort
    def shipped(c):
        return R.sort_key(c)

    def documented(c):
        v = R.profile(c)
        return (0 if c in R.prio else 1, -v["tier"], -v["prom"],
                -R.window_count(c), str(v.get("name") or c).lower())

    grp = defaultdict(list)
    for r in rows:
        grp[dkey(r)].append(r)
    sup = set()
    for k, g in grp.items():
        g.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
        sup.update(id(z) for z in g[:-1])

    print("1. sort key: shipped (-prom,-tier) vs req2 4.2 text (-tier,-prom)")
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, day, n) if id(r) not in sup]
        s1 = [r for r in kept if R.segment(r) == "1a_t3"]
        cos = sorted({CL.norm(r["company_name"]) for r in s1})
        a = sorted(cos, key=shipped)
        b = sorted(cos, key=documented)
        first_diff = next((i for i in range(len(a)) if a[i] != b[i]), None)
        top35a, top35b = a[:20], b[:20]
        print("   N=%-3d segment(1) companies %3d ; first position that differs: %s ; "
              "top-20 set overlap %d/20"
              % (n, len(cos), first_diff, len(set(top35a) & set(top35b))))
    cos = sorted({CL.norm(r["company_name"]) for r in rows
                  if R.segment(r) == "1a_t3" and id(r) not in sup})
    print("   shipped  top 8: %s" % [c[:18] for c in sorted(cos, key=shipped)[:8]])
    print("   document top 8: %s" % [c[:18] for c in sorted(cos, key=documented)[:8]])

    # --------------------------------------------------------------- 2. trend
    print("\n2. trend bars: per-day dedup vs window dedup grouped by day")
    for n in N_CHOICES:
        ds = days_back(day, n)
        kept = [r for r in win_rows(rows, day, n) if id(r) not in sup]
        by_day = defaultdict(int)
        for r in kept:
            by_day[r["_day"]] += 1
        per_day_dedup = {d: len(CL.day_rows(rows, d)) for d in ds}
        a, b = sum(per_day_dedup.values()), sum(by_day.values())
        print("   N=%-3d sum(per-day dedup)=%-6d  window dedup=%-6d  gap %d (%.2f%%)  "
              "empty days in the axis: %d"
              % (n, a, b, a - b, 100.0 * (a - b) / max(1, a),
                 sum(1 for d in ds if not per_day_dedup.get(d))))

    # --------------------------------------------- 3. dependency assertion
    print("\n3. proposed replacement for test_dashboard_has_no_external_dependency")

    def assert_offline(files):
        """files: {name: text}. Raises AssertionError on anything that needs a network
        or a build step. Keeps the ORIGINAL invariant (offline double-click) while
        allowing local classic <script src> and local <link href>."""
        page = files["latest.html"]
        # a) no ES modules anywhere (file:// blocks them - measured, PROBE 5)
        assert 'type="module"' not in page and "type='module'" not in page
        for name, txt in files.items():
            assert not re.search(r"\bimport\s+[\w{*]", txt) or name.endswith(".html"), name
            assert "export " not in txt or name.endswith(".html"), name
        # b) every src=/href= is either a job link (https, inside a data file or an
        #    <a>) or a same-directory relative path - never a scheme, never absolute
        for m in re.finditer(r'\b(?:src|href)\s*=\s*"([^"]*)"', page):
            u = m.group(1)
            if u.startswith("#"):
                continue
            assert "://" not in u, "external reference in the shell: %r" % u
            assert not u.startswith("/") and ".." not in u, "not same-dir: %r" % u
        # c) no network API anywhere in the shipped JS
        for name, txt in files.items():
            if not name.endswith(".js"):
                continue
            for bad in ("fetch(", "XMLHttpRequest", "WebSocket", "importScripts",
                        "EventSource", "navigator.sendBeacon"):
                assert bad not in txt, "%s uses %s" % (name, bad)
        # d) the dynamically injected chunk names must be relative literals
        for name, txt in files.items():
            if name.endswith(".js"):
                for m in re.finditer(r"\.src\s*=\s*([^;\n]+)", txt):
                    assert "://" not in m.group(1), "%s injects an absolute URL" % name
        # e) the things v1 promised the reader
        assert "prefers-color-scheme" in files.get("dashboard.css", "")
        assert "a:visited" in files.get("dashboard.css", "")
        assert "<details" in page or "details" in files.get("dashboard.js", "")
        return True

    good = {
        "latest.html": '<!doctype html><html><head><link rel="stylesheet" href="dashboard.css">'
                       '<script src="data-2026-08-21.js"></script><script src="dashboard.js">'
                       '</script></head><body><div id="app"></div></body></html>',
        "dashboard.css": "@media (prefers-color-scheme: dark){} a:visited{color:red}",
        "dashboard.js": 'var s=document.createElement("script");s.src="data-"+d+".js";'
                        'document.head.appendChild(s);var x="<details open>";',
    }
    bad_cases = {
        "cdn <script>": dict(good, **{"latest.html": good["latest.html"].replace(
            'src="dashboard.js"', 'src="https://cdn.example.com/x.js"')}),
        "google fonts <link>": dict(good, **{"latest.html": good["latest.html"].replace(
            'href="dashboard.css"', 'href="https://fonts.googleapis.com/css"')}),
        "ES module": dict(good, **{"latest.html": good["latest.html"].replace(
            '<script src="dashboard.js">', '<script type="module" src="dashboard.js">')}),
        "fetch in js": dict(good, **{"dashboard.js": good["dashboard.js"] + "fetch('x')"}),
        "absolute injected chunk": dict(good, **{"dashboard.js":
            'var s=document.createElement("script");s.src="https://x/"+d+".js";'}),
        "parent dir": dict(good, **{"latest.html": good["latest.html"].replace(
            'href="dashboard.css"', 'href="../shared/dashboard.css"')}),
    }
    print("   PASS on the intended v2 shell: %s" % assert_offline(good))
    for label, files in bad_cases.items():
        try:
            assert_offline(files)
            print("   !! NOT CAUGHT: %s" % label)
        except AssertionError as e:
            print("   caught %-26s (%s)" % (label, str(e)[:52] or "assert"))


if __name__ == "__main__":
    main()
