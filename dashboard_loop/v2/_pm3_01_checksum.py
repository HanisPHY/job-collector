# -*- coding: utf-8 -*-
"""ROUND-3 PROBE 1 - close A6: an order-sensitive checksum over the FULL rendered
row sequence of every segment, provably identical in Python and in JS.

Evaluator A: `check[f][N].anchors` samples only 3 coordinates per segment, so on the
big folded segments it covers 1.3%-12% of the rows. Everything else could be
reordered / dropped / duplicated by JS and no reconciliation layer would notice.

This probe:
  A. re-measures the anchors coverage on today's corpus
  B. defines the checksum (integer-only, 32-bit, no floats, no strings)
  C. proves three implementations agree on all 3 views x 5 N x 6 segments:
       A1  the spec pseudocode, transliterated
       A2  an INDEPENDENT Python implementation written a different way
       JS  the JS implementation, executed in headless Chrome under file://
  D. proves the checksum is order sensitive: random swaps, adjacent swaps,
     single-row drops and duplications must ALL change it
  E. measures the byte cost
"""
import io
import json
import os
import random
import re
import shutil
import struct
import subprocess
import tempfile
from collections import defaultdict
from functools import reduce

from _pm2_base import (CAP, CL, N_CHOICES, SEGS, banner, days_back, load,
                       superseded, win_rows)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
VIEWS = ("all", "new", "wm")
MASK = 0xFFFFFFFF
FNV_OFF = 2166136261        # 0x811C9DC5
FNV_PRIME = 16777619        # 0x01000193


# --------------------------------------------------------------- B. the checksum
def mix(h, v):
    """One step. Integer only; every intermediate is masked to 32 bits."""
    h = (h ^ (v & MASK)) & MASK
    return (h * FNV_PRIME) & MASK


def seq_hash_A1(pairs):
    """Implementation A1 - the pseudocode in the design, transliterated."""
    h = FNV_OFF
    for d, i in pairs:
        h = mix(h, d)
        h = mix(h, i)
    return mix(h, len(pairs))


def seq_hash_A2(pairs):
    """Implementation A2 - written independently: flatten first, fold with reduce,
    do the 32-bit multiply through struct so it cannot accidentally share code with
    A1's masking. Must agree with A1 bit for bit."""
    flat = []
    for p in pairs:
        flat.append(p[0])
        flat.append(p[1])
    flat.append(len(pairs))

    def step(acc, v):
        x = struct.unpack("<I", struct.pack("<I", (acc ^ v) % 4294967296))[0]
        prod = x * FNV_PRIME
        return struct.unpack("<I", struct.pack("<I", prod % 4294967296))[0]

    return reduce(step, flat, FNV_OFF)


JS_IMPL = """
function mix(h, v){ h = (h ^ (v >>> 0)) >>> 0; return Math.imul(h, 16777619) >>> 0; }
function seqHash(pairs){
  var h = 2166136261 >>> 0;
  for (var k = 0; k < pairs.length; k++){
    h = mix(h, pairs[k][0]);
    h = mix(h, pairs[k][1]);
  }
  return mix(h, pairs.length);
}
"""


# ------------------------------------------------------- the rendered sequences
def build_sequences(rows, profiles, overrides, priority):
    """-> {(view, n, seg): {"head": [[d,i],...], "over": [[d,i],...]}}

    The order is exactly what the design tells JS to render:
      groups ordered by o[company]; inside a group by the CANONICAL key
      (day index desc, r desc, title desc, row index desc) - r alone is HH*100+MM and
      carries no day, so the day index MUST come first (issue A9); head = first CAP of
      each group concatenated in group order; over = the rest.
    """
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)

    all_days = days_back(anchor, 30)
    didx = {d: i for i, d in enumerate(all_days)}
    ridx = {}
    hhmm = {}
    for d in days:
        for i, r in enumerate([x for x in rows if x["_day"] == d]):
            ridx[id(r)] = (didx[d], i)
    for r in rows:
        rec = r.get("_recorded") or ""
        hhmm[id(r)] = int(rec[11:13] + rec[14:16]) if len(rec) >= 16 else 0

    def canon(r):
        """A9: day index first, THEN r. Descending. Identical to sorting by the
        full _recorded string - proved in _pm3_04_a9.py section B."""
        return (ridx[id(r)][0], hhmm[id(r)], (r.get("job_title") or ""),
                ridx[id(r)][1])

    cos = sorted({CL.norm(r["company_name"]) for r in rows})
    rank = {c: k for k, c in enumerate(sorted(cos, key=R.sort_key))}

    st = __import__("dashboard").read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""

    out = {}
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, anchor, n) if id(r) not in S]
        for f in VIEWS:
            if f == "all":
                sel = kept
            elif f == "new":
                sel = [r for r in kept if (r.get("_recorded") or "") > pc]
            else:
                sel = [r for r in kept if pp < (r.get("_recorded") or "") <= pc]
            by = defaultdict(lambda: defaultdict(list))
            for r in sel:
                by[R.segment(r)][CL.norm(r["company_name"])].append(r)
            for s in SEGS:
                groups = sorted(by[s].items(), key=lambda kv: rank[kv[0]])
                head, over = [], []
                for c, rs in groups:
                    rs = sorted(rs, key=canon, reverse=True)
                    head.extend(list(ridx[id(r)]) for r in rs[:CAP])
                    over.extend(list(ridx[id(r)]) for r in rs[CAP:])
                out[(f, n, s)] = {"head": head, "over": over}
    return out


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    banner("ROUND-3 PROBE 1  A6: full-sequence checksum for every segment")
    print("corpus %d rows, days %s, anchor %s" % (len(rows), ",".join(days), days[-1]))

    seqs = build_sequences(rows, profiles, overrides, priority)

    # ------------------------------------------------- A. anchors coverage today
    print("\n[A] what 3 sampled anchors actually cover (view=all)")
    print("    %-6s %8s %8s %10s" % ("seg", "N=3", "N=30", "cover@N=30"))
    for s in SEGS:
        n3 = len(seqs[("all", 3, s)]["head"])
        n30 = len(seqs[("all", 30, s)]["head"])
        cov = 100.0 * min(3, n30) / n30 if n30 else 0.0
        print("    %-6s %8d %8d %9.1f%%" % (s, n3, n30, cov))
    tot = sum(len(seqs[("all", 30, s)]["head"]) for s in SEGS)
    print("    total cap2-head rows at N=30: %d ; sampled by anchors: %d (%.1f%%)"
          % (tot, sum(min(3, len(seqs[("all", 30, s)]["head"])) for s in SEGS),
             100.0 * sum(min(3, len(seqs[("all", 30, s)]["head"])) for s in SEGS)
             / max(1, tot)))

    # ------------------------------------- C. three implementations must agree
    print("\n[C] Python A1 vs independent Python A2 vs JS (headless Chrome, file://)")
    keys = sorted(seqs, key=lambda k: (VIEWS.index(k[0]), k[1], SEGS.index(k[2])))
    hs_a1, hs_a2 = {}, {}
    for k in keys:
        for part in ("head", "over"):
            hs_a1[(k, part)] = seq_hash_A1(seqs[k][part])
            hs_a2[(k, part)] = seq_hash_A2(seqs[k][part])
    dis = [k for k in hs_a1 if hs_a1[k] != hs_a2[k]]
    print("    cells: %d (3 views x %d N x %d segments x {head,over})"
          % (len(hs_a1), len(N_CHOICES), len(SEGS)))
    print("    A1 vs A2 disagreements: %d" % len(dis))

    tmp = tempfile.mkdtemp(prefix="pm3_")
    payload = {"%s|%d|%s|%s" % (k[0], k[1], k[2], part): seqs[k][part]
               for k in keys for part in ("head", "over")}
    io.open(os.path.join(tmp, "seq.js"), "w", encoding="utf-8").write(
        "window.SEQ=" + json.dumps(payload, separators=(",", ":")) + ";")
    io.open(os.path.join(tmp, "h.html"), "w", encoding="utf-8").write(
        '<!doctype html><html><head><meta charset="utf-8"></head><body>'
        '<pre id="out">PENDING</pre><script src="seq.js"></script><script>'
        + JS_IMPL +
        'var R={};for(var k in window.SEQ){R[k]=seqHash(window.SEQ[k]);}'
        'document.getElementById("out").textContent=JSON.stringify(R);'
        '</script></body></html>')
    js = None
    if os.path.exists(CHROME):
        prof = tempfile.mkdtemp(prefix="pm3prof_")
        try:
            p = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                 "--user-data-dir=" + prof, "--virtual-time-budget=20000",
                 "--dump-dom",
                 "file:///" + os.path.join(tmp, "h.html").replace("\\", "/")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
            m = re.search(r'<pre id="out">(.*?)</pre>',
                          p.stdout.decode("utf-8", "replace"), re.S)
            js = json.loads(m.group(1)) if m else None
        finally:
            shutil.rmtree(prof, ignore_errors=True)
    if js is None:
        print("    JS: chrome unavailable / no output -- CANNOT CONFIRM")
    else:
        bad = [k for k in payload
               if js.get(k) != hs_a1[((k.split("|")[0], int(k.split("|")[1]),
                                       k.split("|")[2]), k.split("|")[3])]]
        print("    JS cells returned: %d ; Python-vs-JS disagreements: %d"
              % (len(js), len(bad)))
        if bad:
            for k in bad[:5]:
                print("       %s js=%s py=%s" % (k, js[k], hs_a1[k]))
    sample = keys[len(keys) // 2]
    print("    sample cell %s head len=%d  checksum=%d (0x%08X)"
          % (str(sample), len(seqs[sample]["head"]),
             hs_a1[(sample, "head")], hs_a1[(sample, "head")]))

    # ------------------------------------------------- D. order sensitivity
    print("\n[D] does the checksum actually move when the sequence is disturbed?")
    random.seed(20260821)
    stats = {"random_swap": [0, 0], "adjacent_swap": [0, 0],
             "drop_one": [0, 0], "duplicate_one": [0, 0]}
    for k in keys:
        seq = seqs[k]["head"]
        if len(seq) < 2:
            continue
        base = seq_hash_A1(seq)
        for _ in range(40):
            a, b = random.sample(range(len(seq)), 2)
            if seq[a] == seq[b]:
                continue
            q = list(seq)
            q[a], q[b] = q[b], q[a]
            stats["random_swap"][0] += 1
            if seq_hash_A1(q) == base:
                stats["random_swap"][1] += 1
        for a in range(len(seq) - 1):
            if seq[a] == seq[a + 1]:
                continue
            q = list(seq)
            q[a], q[a + 1] = q[a + 1], q[a]
            stats["adjacent_swap"][0] += 1
            if seq_hash_A1(q) == base:
                stats["adjacent_swap"][1] += 1
        for a in random.sample(range(len(seq)), min(20, len(seq))):
            q = seq[:a] + seq[a + 1:]
            stats["drop_one"][0] += 1
            if seq_hash_A1(q) == base:
                stats["drop_one"][1] += 1
            q2 = seq[:a] + [seq[a]] + seq[a:]
            stats["duplicate_one"][0] += 1
            if seq_hash_A1(q2) == base:
                stats["duplicate_one"][1] += 1
    for name, (n, miss) in stats.items():
        print("    %-14s trials %7d   checksum UNCHANGED (missed) %d" % (name, n, miss))
    print("    every adjacent swap is included, which is the hardest case for an")
    print("    order-sensitive hash and the exact shape a stale rAF batch produces.")

    # ------------------------------------------------------------ E. byte cost
    print("\n[E] byte cost")
    hsum = {"%s|%d" % (f, n): {str(SEGS.index(s)): hs_a1[((f, n, s), "head")]
                               for s in SEGS}
            for f in VIEWS for n in N_CHOICES}
    osum = {"%s|%d" % (f, n): {str(SEGS.index(s)): hs_a1[((f, n, s), "over")]
                               for s in SEGS}
            for f in VIEWS for n in N_CHOICES}
    anch = {"%s|%d" % (f, n): {str(SEGS.index(s)):
                               [seqs[(f, n, s)]["head"][0],
                                seqs[(f, n, s)]["head"][len(seqs[(f, n, s)]["head"]) // 2],
                                seqs[(f, n, s)]["head"][-1]]
                               for s in SEGS if seqs[(f, n, s)]["head"]}
            for f in VIEWS for n in N_CHOICES}
    b = lambda o: len(json.dumps(o, separators=(",", ":")).encode("utf-8"))
    print("    hsum (head checksums, 3 views x %d N x %d segs) : %5d B"
          % (len(N_CHOICES), len(SEGS), b(hsum)))
    print("    osum ('+N more' checksums, same shape)           : %5d B" % b(osum))
    print("    anchors already in v2 (kept for localisation)    : %5d B" % b(anch))
    print("    rows now covered by a checksum: %d of %d cap2-head rows at N=30 (100%%)"
          % (tot, tot))
    print("\ntemp dir %s" % tmp)


if __name__ == "__main__":
    main()
