# -*- coding: utf-8 -*-
"""Stage 2: re-ask ONLY the stage-1 unknown residue, with a stronger model, in dense
batches made entirely of residue names. Measured in round 2: the batch-composition
effect (eval A blocking-4) is what buries known companies, and a dense residue batch
plus gpt-4o reverses most of it."""
import os, json, time, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
import enrich_v4 as E

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL2 = "gpt-4o"
PRICE = {"gpt-4o": (2.5, 10.0), "gpt-4o-mini": (0.15, 0.60), "gpt-4.1-mini": (0.40, 1.60)}
BATCH = 50

if __name__ == "__main__":
    model2 = sys.argv[1] if len(sys.argv) > 1 else MODEL2
    passes = json.load(open(os.path.join(HERE, "passes_v4.json"), encoding="utf-8"))
    stage1 = passes[0]
    residue = sorted([v["name"] for v in stage1.values()
                      if v["tier"] == 0 and v["kind"] == "unknown"], key=str.lower)
    print("stage1 companies=%d  residue(unknown/t0)=%d  model2=%s"
          % (len(stage1), len(residue), model2))

    batches = [residue[i:i + BATCH] for i in range(0, len(residue), BATCH)]
    E.MODEL = model2

    def one(b):
        last = None
        for _ in range(3):
            try:
                arr, u = E.ask(b, seed=7)
                return b, arr, u.prompt_tokens, u.completion_tokens
            except Exception as e:
                last = e; time.sleep(3)
        print("  BATCH FAILED:", repr(last)[:160])
        return b, [], 0, 0

    t0 = time.time()
    got, tin, tout, miss = {}, 0, 0, 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for b, arr, pi, po in ex.map(one, batches):
            tin += pi; tout += po
            by = {}
            for x in arr:
                nm = (x.get("name") or "").strip()
                if nm:
                    by[norm(nm)] = x
            for nm in b:
                k = norm(nm)
                if k in by:
                    got[k] = by[k]
                else:
                    miss += 1
    wall = time.time() - t0
    pi_, po_ = PRICE[model2]
    cost = tin * pi_ / 1e6 + tout * po_ / 1e6
    up = sum(1 for v in got.values() if v.get("tier", 0) >= 2)
    up1 = sum(1 for v in got.values() if v.get("tier", 0) == 1)
    print("batches=%d wall=%.1fs in=%d out=%d cost=$%.4f missing=%d"
          % (len(batches), wall, tin, tout, cost, miss))
    print("recovered tier>=2: %d   tier1: %d   still tier0: %d"
          % (up, up1, len(residue) - up - up1 - miss))
    json.dump(got, open(os.path.join(HERE, "stage2_%s.json" % model2), "w",
                        encoding="utf-8"), ensure_ascii=False)
