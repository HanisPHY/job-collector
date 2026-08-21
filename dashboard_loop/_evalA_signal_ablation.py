# -*- coding: utf-8 -*-
import sys, json, os, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_base import *
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"company_profiles.sample.json"),encoding="utf-8"))
INTER={'staffing','outsourcing','training','aggregator'}
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
rows=load(); allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)
def sigs(c):
    rs=allg[c]; v=P[c]; n=len(rs); s=set()
    if v['kind'] in INTER: s.add('S1')
    if sum(1 for r in rs if re.search(r'\s+at\s+[A-Z0-9]',r['job_title'] or ''))/n>=0.5: s.add('S2')
    if sum(1 for r in rs if (r['job_title'] or '').rstrip().lower().endswith('jobs'))/n>=0.5: s.add('S3')
    st={k for r in rs for k in STACK if k in (r['job_title'] or '').lower()}
    if len(st)>=3 and len(st)/n>=0.25: s.add('S4')
    if v['kind']=='unknown' and v['tier']==0 and n>=5: s.add('S5')
    return s
def lane(c, off=()):
    s=sigs(c)-set(off); rs=allg[c]; v=P[c]
    if not s: return 'ok'
    if any(r['_source']!='newgrad' for r in rs) and v['kind'] not in INTER: return 'veto'
    return 'inter'
base={c:lane(c) for c in allg}
for off in [('S2',),('S3',),('S4',),('S5',),('S2','S3'),('S2','S3','S4')]:
    d=[c for c in allg if lane(c,off)!=base[c]]
    print(f"ablate {str(off):20s}: {len(d)} companies change lane  {[P[c]['name'] for c in d]}")
