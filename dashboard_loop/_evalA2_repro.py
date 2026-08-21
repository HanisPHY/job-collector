# -*- coding: utf-8 -*-
import os, sys; os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
from r2 import Resolver, build_profiles, day_rows
from collections import Counter, defaultdict
rows=load()
print("corpus rows:", len(rows), " companies:", len({norm(r['company_name']) for r in rows}))
print("by day:", Counter(r['_day'] for r in rows))
P=build_profiles()
print("profiles:", len(P), " stage split:", Counter(v.get('stage') for v in P.values()))
missing={norm(r['company_name']) for r in rows} - set(P)
print("companies NOT in profiles (total-function test):", len(missing))
for DAY in ["2026-08-19","2026-08-20"]:
    R=Resolver(rows,P,DAY)
    dr,_=day_rows(rows,DAY)
    b=defaultdict(list)
    for r in dr: b[R.bucket(r)[0]].append(r)
    print(f"\n=== {DAY} ===  day rows after (co,title) dedup: {len(dr)}")
    for L in ["A0","A1","A2","B1","B2","C"]:
        rs=b[L]; print(f"  {L}: {len(rs):4d} jobs / {len({norm(x['company_name']) for x in rs}):3d} companies")
    print(f"  中介占比 {100*len(b['C'])/len(dr):.1f}%")
