# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import *
HERE=r"D:/OneDrive/work/school/project/Job"
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"profiles.json"),encoding="utf-8"))
INTER={'staffing','outsourcing','training','aggregator'}
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
DAY = sys.argv[1] if len(sys.argv)>1 else "2026-08-20"
CAP = int(sys.argv[2]) if len(sys.argv)>2 else 3

rows=load()
allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)

def tnorm(t): return re.sub(r'\W+',' ',(t or '').lower()).strip()

# stage 1: cross-source unique_id dedup already done in load(); stage 2: (company,title)
today=[r for r in rows if r['_day']==DAY]
seen=set(); day_rows=[]
for r in today:
    k=(norm(r['company_name']), tnorm(r['job_title']))
    if k in seen: continue
    seen.add(k); day_rows.append(r)

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
    if ats and v['kind'] not in INTER: return 'veto', trig     # ATS board -> real employer
    return 'inter', trig

lane={}
for c in allg: lane[c]=classify(c)[0]

A=[];B=[];C=[]
for r in day_rows:
    c=norm(r['company_name']); v=P[c]; L=lane[c]
    if L=='inter': C.append(r)
    elif v['tier']>=2: A.append(r)
    else: B.append(r)

def emit(bucket, label, cap):
    g=defaultdict(list)
    for r in bucket: g[norm(r['company_name'])].append(r)
    order=sorted(g.items(), key=lambda kv:(-P[kv[0]]['tier'], -P[kv[0]]['conf'], P[kv[0]]['name'].lower()))
    out=[]
    for c,rs in order:
        for r in rs[:cap]: out.append((c,r,len(rs)))
        if len(rs)>cap: out.append((c,None,len(rs)-cap))
    return out

qa=emit(A,'A',CAP)
print(f"=== {DAY} ===")
print(f"raw rows(day, uid-deduped) {len(today)} -> (company,title) dedup {len(day_rows)}")
print(f"Lane A 大中公司 tier>=2 : {len(A)} jobs / {len({norm(r['company_name']) for r in A})} companies")
print(f"Lane B 其他真实雇主      : {len(B)} jobs / {len({norm(r['company_name']) for r in B})} companies")
print(f"Lane C 中介/刷屏         : {len(C)} jobs / {len({norm(r['company_name']) for r in C})} companies")
print(f"Lane A with per-company cap {CAP}: {sum(1 for x in qa if x[1] is not None)} rows on the first screen")
print()
print("--- TOP 30 of the Lane A reading queue ---")
i=0
for c,r,extra in qa:
    if i>=30: break
    v=P[c]
    if r is None:
        print(f"     ... {v['name']} 还有 {extra} 条（折叠）")
        continue
    i+=1
    print(f"{i:3d}. [T{v['tier']}] {v['name'][:28]:30s} | {(r['job_title'] or '')[:52]:54s} | {r['_source']}")
