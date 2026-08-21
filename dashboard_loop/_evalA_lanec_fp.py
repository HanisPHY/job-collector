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
print("=== companies that reach Lane C DESPITE having their own ATS board (S1 beats V1) ===")
for c in allg:
    if CL[c][0]=='inter' and any(r['_source']!='newgrad' for r in allg[c]):
        srcs=Counter(r['_source'] for r in allg[c])
        print(f"  {P[c]['name'][:36]:38s} n={len(allg[c])} {dict(srcs)} kind={P[c]['kind']} tier={P[c]['tier']}")
for DAY in ["2026-08-19","2026-08-20"]:
    today=[r for r in rows if r['_day']==DAY]; seen=set(); dr=[]
    for r in today:
        k=(norm(r['company_name']), tnorm(r['job_title']))
        if k in seen: continue
        seen.add(k); dr.append(r)
    C=defaultdict(int)
    for r in dr:
        if CL[norm(r['company_name'])][0]=='inter': C[norm(r['company_name'])]+=1
    print(f"\n=== {DAY} Lane C : {len(C)} companies / {sum(C.values())} jobs ===")
    for c,n in sorted(C.items(), key=lambda kv:-kv[1]):
        src=set(r['_source'] for r in allg[c])
        flag = "  <-- HAS OWN ATS BOARD" if src-{'newgrad'} else ""
        print(f"  {n:3d}  {P[c]['name'][:36]:38s} {'|'.join(CL[c][1])}{flag}")
