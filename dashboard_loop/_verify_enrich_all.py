# -*- coding: utf-8 -*-
import os, json, time, sys, re
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
from llm_probe3 import ask, client

rows = load()
names = {}
for r in rows:
    n = (r.get("company_name") or "").strip()
    if not n: continue
    names.setdefault(norm(n), n)
allnames = sorted(names.values(), key=str.lower)
print("companies to enrich:", len(allnames))

B = 40
batches = [allnames[i:i+B] for i in range(0, len(allnames), B)]
MODEL = "gpt-4o-mini"

def run(b):
    for attempt in range(3):
        try:
            txt, u, dt = ask(b, MODEL)
            data = json.loads(txt)
            arr = data.get("companies") or data.get("results") or next(v for v in data.values() if isinstance(v, list))
            return b, arr, u.prompt_tokens, u.completion_tokens, dt, None
        except Exception as e:
            err = repr(e); time.sleep(2)
    return b, [], 0, 0, 0.0, err

t0 = time.time()
with ThreadPoolExecutor(max_workers=5) as ex:
    out = list(ex.map(run, batches))
wall = time.time() - t0

profiles, tin, tout, miss, errs = {}, 0, 0, 0, []
for b, arr, pi, po, dt, err in out:
    tin += pi; tout += po
    if err: errs.append(err)
    got = {}
    for x in arr:
        nm = (x.get("name") or "").strip()
        if nm: got[norm(nm)] = x
    for nm in b:
        k = norm(nm)
        if k in got:
            profiles[k] = got[k]
        else:
            miss += 1
            profiles[k] = {"name": nm, "kind": "unknown", "tier": 0, "conf": 0.0, "why": "LLM_NO_ROW"}

cost = tin*0.15/1e6 + tout*0.60/1e6
print(f"batches={len(batches)} wall={wall:.1f}s in={tin} out={tout} cost=${cost:.4f} missing_rows={miss} errors={len(errs)}")
if errs: print("ERR", errs[:3])
json.dump(profiles, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
