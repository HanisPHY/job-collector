# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_base import *
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"company_profiles.sample.json"),encoding="utf-8"))
INTER={'staffing','outsourcing','training','aggregator'}
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
rows=load()
print("total rows after cross-source uid dedup:", len(rows))
allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)
print("total companies:", len(allg))
print("profiles entries:", len(P))
print("companies missing from profiles:", [c for c in allg if c not in P][:20])
def tnorm(t): return re.sub(r'\W+',' ',(t or '').lower()).strip()
def classify(c):
    rs=allg[c]; v=P[c]; n=len(rs)
    ats=any(r['_source']!='newgrad' for r in rs)
    trig=[]
    if v['kind'] in INTER: trig.append('llm:'+v['kind'])
    atx=sum(1 for r in rs if re.search(r'\s+at\s+[A-Z0-9]',r['job_title'] or ''))
    if atx/n>=0.5: trig.append('repost@%d%%'%(atx/n*100))
    if sum(1 for r in rs if (r['job_title'] or '').rstrip().lower().endswith('jobs'))/n>=0.5: trig.append('title=Jobs')
    st={k for r in rs for k in STACK if k in (r['job_title'] or '').lower()}
    if len(st)>=3 and len(st)/n>=0.25: trig.append('stack%d'%len(st))
    susp = v['kind']=='unknown' and v['tier']==0 and n>=5
    if susp: trig.append('unknown_vol%d'%n)
    if not trig: return 'ok', []
    if ats and v['kind'] not in INTER: return 'veto', trig
    return 'inter', trig
CL={c:classify(c) for c in allg}
for DAY in ["2026-08-19","2026-08-20"]:
    today=[r for r in rows if r['_day']==DAY]
    seen=set(); day_rows=[]
    for r in today:
        k=(norm(r['company_name']), tnorm(r['job_title']))
        if k in seen: continue
        seen.add(k); day_rows.append(r)
    lanes=defaultdict(list)
    for r in day_rows:
        c=norm(r['company_name']); v=P[c]
        if CL[c][0]=='inter': lanes['C'].append(r)
        elif v['tier']==3: lanes['A1'].append(r)
        elif v['tier']==2: lanes['A2'].append(r)
        else: lanes['B'].append(r)
    print(f"\n=== {DAY} === uid-dedup {len(today)} -> (co,title) dedup {len(day_rows)}")
    for L in ['A1','A2','B','C']:
        b=lanes[L]; g=defaultdict(list)
        for r in b: g[norm(r['company_name'])].append(r)
        cap2=sum(min(2,len(v)) for v in g.values())
        print(f"  {L}: {len(b)} jobs / {len(g)} companies | cap2 -> {cap2} rows")
    print("  中介占比 %.1f%%" % (100*len(lanes['C'])/len(day_rows)))
# tier dist over 8/20 non-C
DAY="2026-08-20"
today=[r for r in rows if r['_day']==DAY]
seen=set(); day_rows=[]
for r in today:
    k=(norm(r['company_name']), tnorm(r['job_title']))
    if k in seen: continue
    seen.add(k); day_rows.append(r)
nonC=[r for r in day_rows if CL[norm(r['company_name'])][0]!='inter']
print("\n8/20 non-C rows:", len(nonC))
print("tier dist:", Counter(P[norm(r['company_name'])]['tier'] for r in nonC))
print("\nglobal tier dist (companies):", Counter(v['tier'] for v in P.values()))
print("global kind dist (companies):", Counter(v['kind'] for v in P.values()))
