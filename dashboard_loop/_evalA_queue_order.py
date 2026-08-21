# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_base import *
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"company_profiles.sample.json"),encoding="utf-8"))
INTER={'staffing','outsourcing','training','aggregator'}
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
rows=load(); allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)
def tnorm(t): return re.sub(r'\W+',' ',(t or '').lower()).strip()
def classify(c):
    rs=allg[c]; v=P[c]; n=len(rs); ats=any(r['_source']!='newgrad' for r in rs); trig=[]
    if v['kind'] in INTER: trig.append('llm:'+v['kind'])
    atx=sum(1 for r in rs if re.search(r'\s+at\s+[A-Z0-9]',r['job_title'] or ''))
    if atx/n>=0.5: trig.append('repost')
    if sum(1 for r in rs if (r['job_title'] or '').rstrip().lower().endswith('jobs'))/n>=0.5: trig.append('titleJobs')
    st={k for r in rs for k in STACK if k in (r['job_title'] or '').lower()}
    if len(st)>=3 and len(st)/n>=0.25: trig.append('stack%d'%len(st))
    if v['kind']=='unknown' and v['tier']==0 and n>=5: trig.append('unkvol%d'%n)
    if not trig: return 'ok', []
    if ats and v['kind'] not in INTER: return 'veto', trig
    return 'inter', trig
CL={c:classify(c) for c in allg}
# KAYAK days
print("KAYAK rows:", [(r['_day'], r['job_title'][:40], r['_source']) for r in allg['kayak']])
# signal singleton check
rep=[c for c in allg if sum(1 for r in allg[c] if re.search(r'\s+at\s+[A-Z0-9]',r['job_title'] or ''))/len(allg[c])>=0.5]
jb=[c for c in allg if sum(1 for r in allg[c] if (r['job_title'] or '').rstrip().lower().endswith('jobs'))/len(allg[c])>=0.5]
print("S2 repost>=50% companies:", [(P[c]['name'],len(allg[c])) for c in rep])
print("S3 title endswith Jobs >=50%:", [(P[c]['name'],len(allg[c])) for c in jb])
# Lane A1 queue position of famous companies
DAY="2026-08-20"
today=[r for r in rows if r['_day']==DAY]; seen=set(); day_rows=[]
for r in today:
    k=(norm(r['company_name']), tnorm(r['job_title']))
    if k in seen: continue
    seen.add(k); day_rows.append(r)
A1=[r for r in day_rows if CL[norm(r['company_name'])][0]!='inter' and P[norm(r['company_name'])]['tier']==3]
g=defaultdict(list)
for r in A1: g[norm(r['company_name'])].append(r)
order=sorted(g.items(), key=lambda kv: P[kv[0]]['name'].lower())
pos=[];i=0
for c,rs in order:
    for r in rs[:2]:
        i+=1; pos.append((i,P[c]['name'],r['job_title'][:45]))
print(f"\nA1 cap2 rows = {len(pos)}  (alphabetical, as the design doc claims)")
want=['google','meta','microsoft','nvidia','palantir','spacex','amazon','openai','apple','stripe','deloitte','city of houston','bridgestone americas','hermès','quora','florida international university']
for w in want:
    hits=[p for p in pos if norm(p[1])==w]
    print(f"  {w:34s} -> rows {[h[0] for h in hits]}")
print("\nrows 1-12 and 100-140 of the alphabetical A1 queue:")
for p in pos[:12]+pos[99:]: print(f"  {p[0]:4d}. {p[1][:32]:34s} {p[2]}")
# cap loss
print("\ncap2 cost: jobs hidden behind '+N more' in A1:")
for c,rs in sorted(g.items(), key=lambda kv:-len(kv[1]))[:12]:
    print(f"  {P[c]['name'][:30]:32s} today={len(rs):3d} shown=2 hidden={len(rs)-2}")
