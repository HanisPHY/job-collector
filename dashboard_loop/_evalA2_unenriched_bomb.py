# -*- coding: utf-8 -*-
import os, sys; os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
from r2 import Resolver, build_profiles, day_rows
from collections import Counter, defaultdict
rows=load(); P=build_profiles()
DAY="2026-08-20"
# simulate: enrichment ran through 8/19 only, then failed on 8/20 (stale-by-one-day table)
co819={norm(r['company_name']) for r in rows if r['_day']<="2026-08-19"}
Pstale={k:v for k,v in P.items() if k in co819}
print("stale table (as of 8/19):", len(Pstale), "companies; new-on-8/20 companies unenriched:",
      len({norm(r['company_name']) for r in rows if r['_day']=='2026-08-20'} - co819))
for label,prof in [("FULL profile", P), ("STALE (enrich failed on 8/20)", Pstale), ("EMPTY (json parse failed)", {})]:
    R=Resolver(rows,prof,DAY); dr,_=day_rows(rows,DAY)
    b=defaultdict(int)
    for r in dr: b[R.bucket(r)[0]]+=1
    cond=[c for c in R.win_by_co if R.company_lane(c)[0]=='inter' and 'unknown+rate' in ''.join(R.company_lane(c)[1])]
    fp=[c for c in cond if P.get(c,{}).get('tier',0)>=2]
    print(f"\n{label:32s} C={b['C']:4d} rows | S5-condemned companies={len(cond):3d} | of them real employers(tier>=2)={len(fp)}")
    if fp: print("    FALSE POSITIVES ->", [(P[c]['name'], P[c]['tier']) for c in fp][:14])
