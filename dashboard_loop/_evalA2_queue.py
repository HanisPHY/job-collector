# -*- coding: utf-8 -*-
import os, sys; os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
from r2 import Resolver, build_profiles, day_rows
from collections import Counter, defaultdict
rows=load(); P=build_profiles()
DAY="2026-08-20"
R=Resolver(rows,P,DAY); dr,_=day_rows(rows,DAY)
A=[r for r in dr if R.bucket(r)[0] in ("A0","A1","A2")]
g=defaultdict(list)
for r in A: g[norm(r['company_name'])].append(r)
order=sorted(g, key=R.sortkey)
q=[]
for c in order:
    for r in g[c][:2]: q.append((c,r))
print("Lane A cap2 total rows:", len(q))
print("\n--- TOP 30 (design §4.1) ---")
for i,(c,r) in enumerate(q[:30],1):
    v=R.prof(c)
    print(f"{i:3d}. [T{v['tier']} p{v['prom']:3d}] {v['name'][:26]:28s} | {(r['job_title'] or '')[:52]}")
print("\n--- prom band cap2 row counts (design §4.2 table) ---")
for th in [95,85,75,70,60,40,0]:
    sel=[x for x in q if R.prof(x[0])['prom']>=th]
    print(f"  prom>={th:3d}: rows(cap2)={len(sel):4d}  companies={len({c for c,_ in sel}):4d}")
# is the >=85 segment a contiguous prefix of the sorted queue?
proms=[R.prof(c)['prom'] for c,_ in q]
first_below=next((i for i,p in enumerate(proms) if p<85), None)
after=[ (R.prof(c)['name'],R.prof(c)['prom'],R.prof(c)['tier']) for c,_ in q[first_below:] if R.prof(c)['prom']>=85]
print(f"\nfirst row with prom<85 is at position {first_below+1}")
print(f"rows with prom>=85 that appear AFTER it (segment is NOT a prefix): {len(after)}")
print("  e.g.", after[:12])
