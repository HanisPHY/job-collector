# -*- coding: utf-8 -*-
"""
Pure-data reference implementation behind the v2 dashboard.

No HTML, no I/O, no printing. `dashboard.py` turns what this module returns into
files; `web/dashboard.js` re-derives the same numbers in the browser and is forced
to agree with them (`JOB_INDEX.check`); `tests/test_lane.py` asserts them.

Everything here is a TOTAL function in the sense `company_lane.profile()` is: an
empty profile table, an empty row list, a `cap2` dict with missing keys or a state
dict with no watermark all produce a degenerate result, never an exception. The
daily unattended job must not be able to die here.

Two things in this file are load bearing and are spelled out where they live:

  * `superseded_flags()` is the ONE dedup rule in the whole design (keep-NEWEST,
    scoped to `_day <= generation day`).  There is no second one.
  * `seq_hash()` must stay bit-for-bit identical to `seqHash` in
    `web/dashboard.js`; fixture F29 holds the two together.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import company_lane as CL          # noqa: E402

# ------------------------------------------------------------------- constants
SCHEMA = 2                      # JOB_INDEX.v; the JS refuses to render on a mismatch

CAP = 2                         # rows per company PER SEGMENT, over the whole window
OPEN_ORDER = ("1a_t3", "B1", "1a_t2")        # (1) -> (4) -> (2), (2) as filler only
ALWAYS_OPEN = ("1a_t3", "B1")
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
FLOOR = 30
CEIL = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)      # derived, never written as 47

N_CHOICES = (1, 3, 7, 14, 30)
N_DEFAULT = 3
VIEWS = ("all", "new", "wm")
RETAIN_DAYS = 30

SOURCE_KEYS = ("newgrad", "ats_direct", "ddg")
SOURCE_LABEL = ("LinkedIn", "ATS 直连", "DDG")

MASK = 0xFFFFFFFF
FNV_OFF = 2166136261            # 0x811C9DC5
FNV_PRIME = 16777619            # 0x01000193


# ------------------------------------------------------------ first screen plan
def open_plan(cap2):
    """-> (plan, total). The ceiling comes first, the floor only tops up to FLOOR."""
    cap2 = cap2 if isinstance(cap2, dict) else {}
    plan, used = {}, 0
    for s in ALWAYS_OPEN:
        plan[s] = min(_int(cap2.get(s, 0)), SEG_OPEN_CAP[s])
        used += plan[s]
    for s in OPEN_ORDER:
        if s in ALWAYS_OPEN or used >= FLOOR:
            continue
        plan[s] = min(_int(cap2.get(s, 0)), SEG_OPEN_CAP[s], FLOOR - used)
        used += plan[s]
    return plan, used


def openable(cap2):
    """What the three openable segments can ACTUALLY contribute, each under its own
    ceiling. The untruncated sum is what made the published lower bound false."""
    cap2 = cap2 if isinstance(cap2, dict) else {}
    return sum(min(_int(cap2.get(s, 0)), SEG_OPEN_CAP[s]) for s in OPEN_ORDER)


def open_expected(cap2):
    """Closed form of open_plan()'s total, so the fixture asserts an equality and
    there is no hand-written bound left to get wrong."""
    cap2 = cap2 if isinstance(cap2, dict) else {}
    base = sum(min(_int(cap2.get(s, 0)), SEG_OPEN_CAP[s]) for s in ALWAYS_OPEN)
    filler = sum(min(_int(cap2.get(s, 0)), SEG_OPEN_CAP[s])
                 for s in OPEN_ORDER if s not in ALWAYS_OPEN)
    return max(base, min(base + filler, FLOOR))


def _int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


# --------------------------------------------------------------- order checksum
def mix(h, v):
    """One FNV-1a step. Integer only - no floats, no strings, no encoding."""
    h = (h ^ (v & MASK)) & MASK
    return (h * FNV_PRIME) & MASK


def seq_hash(pairs):
    """Order-sensitive 32-bit checksum over a [[day, row], ...] sequence.

    Must stay bit-identical to seqHash() in web/dashboard.js - F29 asserts it.
    The length is folded in at the end so an empty sequence and a truncated one
    cannot collide with a shorter prefix.
    """
    h = FNV_OFF
    for p in pairs:
        h = mix(h, _int(p[0]))
        h = mix(h, _int(p[1]))
    return mix(h, len(pairs))


# ------------------------------------------------------------------- time keys
def days_back(day, n):
    """[oldest, ..., day], n entries, empty days included."""
    d0 = datetime.strptime(day, "%Y-%m-%d")
    return [(d0 - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]


def tkey(stamp):
    """'YYYY-MM-DD HH:MM[...]' -> ('YYYY-MM-DD', HH*100+MM). '' -> ('', -1).

    The payload never ships a full timestamp string: (day index, r) IS the
    timestamp, and this is the one place the two representations meet.
    """
    s = (stamp or "").strip()
    if len(s) < 16:
        return ("", -1)
    try:
        return (s[:10], int(s[11:13]) * 100 + int(s[14:16]))
    except Exception:
        return ("", -1)


def hhmm(stamp):
    return tkey(stamp)[1] if tkey(stamp)[1] >= 0 else 0


# ------------------------------------------------------------- THE dedup rule
def superseded_flags(rows, day):
    """-> {id(row): 0|1}. 1 = a newer row with the same (company, normalised title)
    exists, so this one is not rendered.

    THE dedup rule of the whole design; there is no second one. Two properties are
    load bearing:

      * keep-NEWEST, so the survivor of a group is the same row for every N (the
        five windows are nested suffixes of the same corpus);
      * scope `_day <= day`. Computing it globally lets a row recorded AFTER the
        generation day supersede a row inside the window, and the window then
        silently loses that row - measured at 10 rows on 8/19 and 28 on 8/20.
    """
    groups = defaultdict(list)
    out = {}
    for r in rows:
        if (r.get("_day") or "") <= day:
            groups[_dkey(r)].append(r)
        else:
            out[id(r)] = 1
    for v in groups.values():
        v.sort(key=lambda z: ((z.get("_recorded") or ""), str(z.get("unique_id") or "")))
        for z in v[:-1]:
            out[id(z)] = 1
        out[id(v[-1])] = 0
    return out


def _dkey(r):
    return CL.norm(r.get("company_name")) + "\x00" + CL.tnorm(r.get("job_title"))


# ------------------------------------------------------------------- payload
def build_payload(day, rows, profiles, overrides, priority, state, retain=RETAIN_DAYS):
    """-> {"index": {...}, "days": {"YYYY-MM-DD": {columns}}}

    This is exactly what the browser gets. Every fixture that matters asserts
    against THIS, not against the CSVs, so a serialisation that loses rows is
    visible to the tests.
    """
    rows = list(rows or [])
    state = state if isinstance(state, dict) else {}
    retain = _int(retain) or RETAIN_DAYS
    if retain < 1:
        retain = 1

    days = days_back(day, retain)
    didx = {d: i for i, d in enumerate(days)}

    R = CL.LaneResolver(rows, profiles or {}, day,
                        overrides=overrides or {}, priority=priority or set())
    sup = superseded_flags(rows, day)

    by_day = defaultdict(list)
    for r in rows:
        d = r.get("_day") or ""
        if d in didx:
            by_day[d].append(r)

    # ---- company table (fixed-length arrays: the words tier/prom/stage never
    #      have to travel to the JS side at all)
    cidx, colist = {}, []
    for d in days:
        for r in by_day.get(d, ()):
            c = CL.norm(r.get("company_name"))
            if c not in cidx:
                cidx[c] = len(colist)
                colist.append(c)

    sigs, sigi = [""], {"": 0}

    def sig_id(txt):
        txt = txt or ""
        if txt not in sigi:
            sigi[txt] = len(sigs)
            sigs.append(txt)
        return sigi[txt]

    co = []
    for c in colist:
        v = R.profile(c)
        verdict, sg = R.company_lane(c)
        normal = ", ".join(sg) or (v.get("why") or "")
        own = ", ".join(list(sg) + ["own-board row"]) if verdict == "inter" else normal
        co.append([str(v.get("name") or c), _int(v.get("tier")), _int(v.get("prom")),
                   R.window_count(c), 1 if c in R.board else 0,
                   sig_id(normal), sig_id(own)])

    # the company ordering is the ONLY ordering the JS is given; it never sees the
    # sort key itself, so the tier/prom transposition in the prose spec cannot
    # reach the browser
    order = sorted(range(len(colist)), key=lambda k: R.sort_key(colist[k]))
    o = [0] * len(colist)
    for rank, k in enumerate(order):
        o[k] = rank

    # ---- link prefixes
    pre_count = defaultdict(int)
    for d in days:
        for r in by_day.get(d, ()):
            p = _link_prefix((r.get("job_link") or "").strip())
            if p:
                pre_count[p] += 1
    lpre = [p for p, n in sorted(pre_count.items(), key=lambda kv: (-kv[1], kv[0]))
            if n >= 2]
    pmap = {p: i for i, p in enumerate(lpre)}

    src_id = {k: i for i, k in enumerate(SOURCE_KEYS)}
    seg_id = {s: i for i, s in enumerate(CL.SEGMENT_ORDER)}

    # ---- one column block per natural day
    dayblocks = {}
    nrows = [0] * len(days)
    chunk = [""] * len(days)
    for i, d in enumerate(days):
        rs = by_day.get(d, ())
        nrows[i] = len(rs)
        if not rs:
            continue
        chunk[i] = "data-%s.js" % d
        cols = {"d": i, "n": len(rs), "c": [], "g": [], "t": [], "lp": [], "l": [],
                "s": [], "r": [], "x": []}
        for r in rs:
            c = CL.norm(r.get("company_name"))
            lp, tail = _split_link((r.get("job_link") or "").strip(), pmap)
            cols["c"].append(cidx[c])
            cols["g"].append(seg_id.get(R.segment(r), 0))
            cols["t"].append((r.get("job_title") or "").strip() or "(no title)")
            cols["lp"].append(lp)
            cols["l"].append(tail)
            cols["s"].append(src_id.get(r.get("_source"), 0))
            cols["r"].append(hhmm(r.get("_recorded")))
            cols["x"].append(1 if sup.get(id(r), 0) else 0)
        dayblocks[d] = cols

    # ---- watermark
    cutoff_now = max((r.get("_recorded") or "") for r in rows) if rows else ""
    prev_cutoff = state.get("cutoff") or ""
    prev_prev = state.get("prev_cutoff") or ""

    wm_days = []
    if prev_cutoff:
        lo, hi = tkey(prev_prev), tkey(prev_cutoff)
        for i, d in enumerate(days):
            cols = dayblocks.get(d)
            if not cols:
                continue
            for r in cols["r"]:
                if lo < (d, r) <= hi:
                    wm_days.append(i)
                    break

    # ---- health (the "N companies not yet classified" banner)
    win_default = set(days[-min(N_DEFAULT, len(days)):])
    seen = {}
    for d in win_default:
        for r in by_day.get(d, ()):
            seen.setdefault(CL.norm(r.get("company_name")),
                            (r.get("company_name") or "").strip())
    unenriched = sorted((v or k) for k, v in seen.items()
                        if R.profile(k).get("stage", 0) < 1)

    index = {
        "v": SCHEMA,
        "day": day,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cutoff": cutoff_now,
        "prev_cutoff": prev_cutoff,
        "prev_prev": prev_prev,
        "w7_days": CL.WINDOW_DAYS,
        "n_choices": list(N_CHOICES),
        "n_default": N_DEFAULT,
        "views": list(VIEWS),
        "cap": CAP,
        "days": days,
        "chunk": chunk,
        "nrows": nrows,
        "wm_days": wm_days,
        "co": co,
        "o": o,
        "sigs": sigs,
        "lpre": lpre,
        "srcs": list(SOURCE_LABEL),
        "health": {"unenriched": len(unenriched), "examples": unenriched[:6]},
        "check": {},
    }
    payload = {"index": index, "days": dayblocks}

    # `check` is the single source of truth the browser reconciles against, and it
    # is nothing but window_view()'s own return value - F22 re-runs it and compares.
    for f in VIEWS:
        index["check"][f] = {str(n): window_view(payload, n, f) for n in N_CHOICES}
    return payload


def _link_prefix(url):
    i = url.find("://")
    if i < 0:
        return ""
    j = url.find("/", i + 3)
    return url if j < 0 else url[:j]


def _split_link(url, pmap):
    """-> (prefix index, remainder). -1 means the remainder is the whole URL."""
    if not url:
        return (-1, "")
    i = url.find("://")
    if i < 0:
        return (-1, url)
    j = url.find("/", i + 3)
    if j < 0:
        return (-1, url)
    pre = url[:j]
    if pre in pmap:
        return (pmap[pre], url[j:])
    return (-1, url)


# ---------------------------------------------------------------- window view
def segment_rows(payload, n, view="all"):
    """-> (raw, bars, heads, overs).

    heads[g] / overs[g] are [[day index, row index], ...] in exactly the order the
    browser has to render them; `window_view` and every fixture that needs one
    segment's rows read this, so there is only one place the ordering lives.
    """
    payload = payload if isinstance(payload, dict) else {}
    index = payload.get("index") or {}
    blocks = payload.get("days") or {}
    days = index.get("days") or []
    o = index.get("o") or []
    segs = list(CL.SEGMENT_ORDER)
    segn = len(segs)

    n = _int(n) or 1
    nd = len(days)
    lo = max(0, nd - n)

    pcut = tkey(index.get("prev_cutoff"))
    ppcut = tkey(index.get("prev_prev"))
    has_wm = bool((index.get("prev_cutoff") or "").strip())

    raw = [0] * segn
    bars = [0] * nd
    groups = [defaultdict(list) for _ in range(segn)]

    for di in range(lo, nd):
        cols = blocks.get(days[di])
        if not cols:
            continue
        xs, gs, cs, rs, ts = cols["x"], cols["g"], cols["c"], cols["r"], cols["t"]
        d = days[di]
        for i in range(len(xs)):
            if xs[i]:
                continue
            key = (d, rs[i])
            if view == "new":
                if not has_wm or not (key > pcut):
                    continue
            elif view == "wm":
                if not has_wm or not (ppcut < key <= pcut):
                    continue
            g = gs[i]
            if g < 0 or g >= segn:
                g = 0
            raw[g] += 1
            bars[di] += 1
            groups[g][cs[i]].append((di, rs[i], ts[i], i))

    heads, overs = [], []
    for g in range(segn):
        keys = sorted(groups[g].keys(),
                      key=lambda c: (o[c] if 0 <= c < len(o) else c, c))
        h, ov = [], []
        for c in keys:
            rs = groups[g][c]
            # (day index desc, r desc, title desc, row index desc). The day index
            # MUST come first: r is HH*100+MM and carries no day, so comparing r
            # first puts "yesterday 03:22" above "today 02:22".
            rs.sort(reverse=True)
            for z in rs[:CAP]:
                h.append([z[0], z[3]])
            for z in rs[CAP:]:
                ov.append([z[0], z[3]])
        heads.append(h)
        overs.append(ov)

    return raw, bars, heads, overs


def segment_head(payload, n, seg, view="all"):
    """One segment's cap-2 head as [[day index, row index], ...]."""
    segs = list(CL.SEGMENT_ORDER)
    if seg not in segs:
        return []
    return segment_rows(payload, n, view)[2][segs.index(seg)]


def window_view(payload, n, view="all"):
    """The whole browser-visible truth for one (N, view) cell, computed from the
    PAYLOAD - not from the CSVs, so a serialisation bug is inside the assertion.

    -> {"dedup","raw","cap2","plan","open","bars","head","anchors","hsum","osum",
        "w7_days"}   (all JSON-native types, so `check[f][n] == window_view(...)`
                      is a plain equality)
    """
    index = (payload if isinstance(payload, dict) else {}).get("index") or {}
    segs = list(CL.SEGMENT_ORDER)
    segn = len(segs)
    raw, bars, heads, overs = segment_rows(payload, n, view)
    cap2 = [len(h) for h in heads]

    planmap, opened = open_plan({s: cap2[i] for i, s in enumerate(segs)})
    plan = [_int(planmap.get(s, 0)) for s in segs]

    head = []
    for g in range(segn):                    # DOM order, which is what the JS walks
        k = plan[g]
        if k:
            head.extend(heads[g][:k])

    anchors, hsum, osum = {}, {}, {}
    for g in range(segn):
        h = heads[g]
        if h:
            anchors[str(g)] = [h[0], h[len(h) // 2], h[-1]]
        hsum[str(g)] = seq_hash(h)
        osum[str(g)] = seq_hash(overs[g])

    return {"dedup": sum(raw), "raw": raw, "cap2": cap2, "plan": plan,
            "open": opened, "bars": bars, "head": head, "anchors": anchors,
            "hsum": hsum, "osum": osum, "w7_days": _int(index.get("w7_days"))}


def carry_seq(payload, n):
    """Section 7: rows the LAST issue put in front of the reader (segments 1/2/4)
    that the current N-day window does NOT cover. One rule, no branch on N - at
    N=1 it fills up, at N>=3 it empties itself out.

    -> (head, over) as [[day index, row index], ...] in render order.
    """
    payload = payload if isinstance(payload, dict) else {}
    index = payload.get("index") or {}
    blocks = payload.get("days") or {}
    days = index.get("days") or []
    o = index.get("o") or []
    segs = list(CL.SEGMENT_ORDER)
    want = {segs.index(s) for s in ("1a_t3", "1a_t2", "B1") if s in segs}

    prev_cutoff = (index.get("prev_cutoff") or "").strip()
    if not prev_cutoff:
        return [], []
    pcut, ppcut = tkey(prev_cutoff), tkey(index.get("prev_prev"))

    nd = len(days)
    lo = max(0, nd - (_int(n) or 1))
    groups = defaultdict(list)
    for di in range(nd):
        if di >= lo:                         # inside the window: not "carry over"
            continue
        cols = blocks.get(days[di])
        if not cols:
            continue
        d = days[di]
        for i in range(len(cols["x"])):
            if cols["x"][i] or cols["g"][i] not in want:
                continue
            key = (d, cols["r"][i])
            if not (ppcut < key <= pcut):
                continue
            groups[cols["c"][i]].append((di, cols["r"][i], cols["t"][i], i))

    head, over = [], []
    for c in sorted(groups.keys(), key=lambda k: (o[k] if 0 <= k < len(o) else k, k)):
        rs = groups[c]
        rs.sort(reverse=True)
        for z in rs[:CAP]:
            head.append([z[0], z[3]])
        for z in rs[CAP:]:
            over.append([z[0], z[3]])
    return head, over


# ----------------------------------------------------------------- encoding
def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def encode_index(index):
    return "window.JOB_INDEX=" + _dumps(index) + ";\n"


def encode_day(day, cols):
    return ("(window.JOB_DAY=window.JOB_DAY||{})[%s]=%s;\n"
            % (_dumps(day), _dumps(cols)))
