# -*- coding: utf-8 -*-
import os, sys; os.chdir(os.path.dirname(os.path.abspath(__file__)))
"""Q4: after deleting S2/S3/S4, did the long-tail miss get worse? + Lane C FP review."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
from r2 import Resolver, build_profiles, day_rows
from collections import defaultdict, Counter
rows=load(); P=build_profiles()
allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
def s2(c):
    rs=allg[c]; return sum(1 for r in rs if re.search(r'\s+at\s+[A-Z0-9]',r['job_title'] or ''))/len(rs)>=0.5
def s3(c):
    rs=allg[c]; return sum(1 for r in rs if (r['job_title'] or '').rstrip().lower().endswith('jobs'))/len(rs)>=0.5
def s4(c):
    rs=allg[c]; st={k for r in rs for k in STACK if k in (r['job_title'] or '').lower()}
    return len(st)>=3 and len(st)/len(rs)>=0.25
for DAY in ["2026-08-19","2026-08-20"]:
    R=Resolver(rows,P,DAY); dr,_=day_rows(rows,DAY)
    inC={norm(r['company_name']) for r in dr if R.bucket(r)[0]=='C'}
    extra=[c for c in {norm(r['company_name']) for r in dr} if c not in inC and (s2(c) or s3(c) or s4(c))]
    nrows=sum(1 for r in dr if norm(r['company_name']) in extra)
    print(f"{DAY}: S2/S3/S4 would additionally catch {len(extra)} companies / {nrows} rows -> "
          + ", ".join(f"{P.get(c,{}).get('name',c)}" for c in extra))
# my 50 suspected long-tail names from round1
FN=json.load(open('fn50.json',encoding='utf-8')) if os.path.exists('fn50.json') else None
FN=json.load(open('fn50.json',encoding='utf-8'))
INTER={'staffing','outsourcing','training','job_board'}
R=Resolver(rows,P,"2026-08-20")
caught=[n for n in FN if P.get(norm(n),{}).get('kind') in INTER]
print(f"\nmy 50 long-tail suspects now caught by LLM kind: {len(caught)}/50  (design says 16)")
print("  ", [P[norm(n)]['name'] for n in caught])
lane=[(n, R.company_lane(norm(n))[0]) for n in FN]
print(f"  of the 50, now in Lane C by any rule: {sum(1 for _,l in lane if l=='inter')}")
still=[n for n,l in lane if l!='inter']
d20=sum(1 for r in day_rows(rows,'2026-08-20')[0] if norm(r['company_name']) in {norm(x) for x in still})
print(f"  still escaping: {len(still)}, carrying {d20} rows on 8/20")
dr,_=day_rows(rows,'2026-08-20')
C=sum(1 for r in dr if R.bucket(r)[0]=='C')
print(f"  measured 中介占比 {100*C/len(dr):.1f}%  ->  lower bound incl. my remaining suspects {100*(C+d20)/len(dr):.1f}%")
print("\n### Lane C full roster 8/20 (FP review) ###")
g=defaultdict(int)
for r in dr:
    if R.bucket(r)[0]=='C': g[norm(r['company_name'])]+=1
for c,n in sorted(g.items(), key=lambda kv:-kv[1]):
    v=P.get(c,{}); print(f"  {n:3d}  {v.get('name',c)[:38]:40s} {v.get('kind','?'):11s} t{v.get('tier','?')} | {'|'.join(R.company_lane(c)[1])}")
