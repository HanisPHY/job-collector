# -*- coding: utf-8 -*-
"""PROBE 3 - how big is the payload really, per encoding and per chunk.

Encodings compared (all UTF-8, no whitespace, json.dumps(separators=(',',':'))):
  E0  req2 5.2 literal  : array of objects, short keys, k = norm(co)+NUL+tnorm(title)
  E1  E0 minus k        : dedup key replaced by a precomputed 'superseded' flag x
  E2  E1 + r as HHMM int + sig moved to companies[] + link prefix table
  E3  E2 as column arrays (struct of arrays)

Also measures:
  * per-day chunk bytes -> the real d0/d1_2/... table, and the per-day-file table
  * the suffix-nesting property that makes the 'x' flag legal for every N
  * how much of a row is the job link
"""
import json
from collections import Counter, defaultdict

from _pm_base import CL, DB, N_CHOICES, banner, days_back, dkey, load, win_rows

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
B = lambda o: len(J(o).encode("utf-8"))


def main():
    rows, profiles, overrides, priority = load()
    day = max(r["_day"] for r in rows)
    banner("PROBE 3  payload encoding + chunk sizes, anchor %s" % day)
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)

    # ---- suffix nesting: keep-NEWEST survivor is N-independent -------------
    print("A. is the keep-NEWEST survivor the same row for every N?")
    grp = defaultdict(list)
    for r in rows:
        grp[dkey(r)].append(r)
    for k in grp:
        grp[k].sort(key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""))
    bad_new = bad_old = 0
    for n in N_CHOICES:
        ds = days_back(day, n)
        lo, hi = ds[0], ds[-1]
        for k, g in grp.items():
            ing = [r for r in g if lo <= r["_day"] <= hi]
            if not ing:
                continue
            if ing[-1] is not g[-1]:
                bad_new += 1              # newest-in-window != newest overall
            if ing[0] is not g[0]:
                bad_old += 1              # oldest-in-window != oldest overall
    print("   keep-NEWEST : survivor differs from the global newest in %d (group,N) cases"
          % bad_new)
    print("   keep-OLDEST : survivor differs from the global oldest in %d (group,N) cases"
          % bad_old)
    print("   => keep-NEWEST can be frozen into a per-row flag; keep-OLDEST cannot.")

    superseded = set()
    for k, g in grp.items():
        for r in g[:-1]:
            superseded.add(id(r))
    print("   rows carrying x=1 (superseded): %d / %d" % (len(superseded), len(rows)))

    # verify against the real dedup for every N
    for n in N_CHOICES:
        w = win_rows(rows, day, n)
        kept = [r for r in w if id(r) not in superseded]
        keys = Counter(dkey(r) for r in kept)
        assert not [1 for v in keys.values() if v > 1], "flag dedup left duplicates"
        # cardinality must equal a real dedup of the window
        real = len({dkey(r) for r in w})
        assert len(kept) == real, "N=%d flag dedup %d != real %d" % (n, len(kept), real)
    print("   flag-based dedup == real dedup for all 5 N: OK")

    # ---- company table -----------------------------------------------------
    cos = {}
    for r in rows:
        c = CL.norm(r["company_name"])
        if c not in cos:
            v = R.profile(c)
            cos[c] = {"n": (v.get("name") or c), "t": v["tier"], "p": v["prom"],
                      "w": R.window_count(c), "b": 1 if c in R.board else 0}
    cidx = {c: i for i, c in enumerate(sorted(cos))}
    comp_list = [cos[c] for c in sorted(cos)]
    print("\nB. companies[] : %d entries, %d bytes (%.1f B/company)"
          % (len(comp_list), B(comp_list), B(comp_list) / float(len(comp_list))))

    # signal string: is it company-level or row-level?
    sig_row = {}
    for r in rows:
        sig_row[id(r)] = ", ".join(R.row_lane(r)[1]) or (R.profile(
            CL.norm(r["company_name"])).get("why") or "")
    per_co = defaultdict(set)
    for r in rows:
        per_co[CL.norm(r["company_name"])].add(sig_row[id(r)])
    multi = sum(1 for v in per_co.values() if len(v) > 1)
    print("   sig distinct values: %d ; companies with >1 distinct sig: %d / %d"
          % (len(set(sig_row.values())), multi, len(per_co)))

    # ---- link prefix stats -------------------------------------------------
    links = [(r.get("job_link") or "") for r in rows]
    pre = Counter()
    for l in links:
        pre["/".join(l.split("/")[:3])] += 1
    print("\nC. job_link: %d rows, mean %.1f chars ; top prefixes:"
          % (len(links), sum(len(l) for l in links) / float(len(links))))
    for p, n in pre.most_common(5):
        print("      %-45s %5d  (%d chars)" % (p, n, len(p)))

    # ---- encodings ---------------------------------------------------------
    def enc(r, mode):
        c = CL.norm(r["company_name"])
        i = cidx[c]
        seg = R.segment(r)
        src = {"newgrad": 0, "ats_direct": 1, "ddg": 2}[r["_source"]]
        rec = (r.get("_recorded") or "")
        hhmm = int(rec[11:13] + rec[14:16]) if len(rec) >= 16 else 0
        d = {"i": r.get("unique_id") or "", "c": i, "g": seg,
             "t": (r.get("job_title") or "").strip(),
             "l": (r.get("job_link") or "").strip(), "s": src, "d": r["_day"]}
        if mode == 0:
            d["r"] = rec
            d["k"] = c + chr(0) + CL.tnorm(r.get("job_title"))
            d["sig"] = sig_row[id(r)]
        elif mode == 1:
            d["r"] = rec
            d["x"] = 1 if id(r) in superseded else 0
            d["sig"] = sig_row[id(r)]
        else:
            d["r"] = hhmm
            d["x"] = 1 if id(r) in superseded else 0
        return d

    print("\nD. whole-corpus payload size by encoding (%d rows)" % len(rows))
    base = None
    for mode, name in ((0, "E0 req2 5.2 literal (with k, full r, sig)"),
                       (1, "E1 k -> x flag"),
                       (2, "E2 E1 + r as HHMM + sig off-row")):
        payload = [enc(r, mode) for r in rows]
        b = B(payload)
        if base is None:
            base = b
        print("   %-42s %9d B   %6.1f B/row   %5.1f%% of E0"
              % (name, b, b / float(len(rows)), 100.0 * b / base))

    # E3: column arrays over E2
    p2 = [enc(r, 2) for r in rows]
    cols = {k: [d[k] for d in p2] for k in ("i", "c", "g", "t", "l", "s", "d", "r", "x")}
    b3 = B(cols)
    print("   %-42s %9d B   %6.1f B/row   %5.1f%% of E0"
          % ("E3 E2 as column arrays", b3, b3 / float(len(rows)), 100.0 * b3 / base))
    for k in ("i", "c", "g", "t", "l", "s", "d", "r", "x"):
        print("        col %-3s %8d B  (%.1f B/row)" % (k, B(cols[k]),
                                                        B(cols[k]) / float(len(rows))))

    # E4: drop i, intern d as index into days[], g as int, link prefix table
    days_u = sorted({r["_day"] for r in rows})
    dmap = {d: i for i, d in enumerate(days_u)}
    segi = {s: i for i, s in enumerate(SEGS)}
    prefs = [p for p, n in pre.most_common() if n >= 20]
    pmap = {p: i for i, p in enumerate(prefs)}
    lt, lp = [], []
    for r in rows:
        l = (r.get("job_link") or "").strip()
        p = "/".join(l.split("/")[:3])
        if p in pmap:
            lp.append(pmap[p])
            lt.append(l[len(p):])
        else:
            lp.append(-1)
            lt.append(l)
    cols4 = {"c": cols["c"], "g": [segi[g] for g in cols["g"]], "t": cols["t"],
             "lp": lp, "l": lt, "s": cols["s"], "d": [dmap[d] for d in cols["d"]],
             "r": cols["r"], "x": cols["x"]}
    b4 = B(cols4) + B(prefs) + B(days_u)
    print("   %-42s %9d B   %6.1f B/row   %5.1f%% of E0"
          % ("E4 E3 - unique_id + interned d/g/link-prefix", b4,
             b4 / float(len(rows)), 100.0 * b4 / base))
    print("        (unique_id column alone was %d B = %.1f B/row)"
          % (B(cols["i"]), B(cols["i"]) / float(len(rows))))

    # ---- chunking ----------------------------------------------------------
    print("\nE. per-natural-day chunk size in encoding E4 (what a data-<day>.js costs)")
    for d in days_u:
        idx = [i for i, r in enumerate(rows) if r["_day"] == d]
        sub = {k: [v[i] for i in idx] for k, v in cols4.items()}
        print("      %s  %5d rows  %8d B  (%.1f KB)"
              % (d, len(idx), B(sub), B(sub) / 1024.0))
    bpr = b4 / float(len(rows))
    print("\nF. projection at the steady-state rate req2 5.5 assumes (2000 rows/day)")
    print("      per day               %8.0f B  (%.2f MB)" % (2000 * bpr, 2000 * bpr / 2**20))
    for label, ndays in (("d0 (1 day)", 1), ("d1_2 (2)", 2), ("d3_6 (4)", 4),
                         ("d7_13 (7)", 7), ("d14_29 (16)", 16), ("all 30 days", 30)):
        print("      %-22s %8.0f B  (%.2f MB)"
              % (label, 2000 * bpr * ndays, 2000 * bpr * ndays / 2**20))
    print("\n      req2 5.2 (E0, 152 B/row) for the same 30 days: %.2f MB"
          % (2000 * (base / float(len(rows))) * 30 / 2**20))


if __name__ == "__main__":
    main()
