# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_base import *
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"company_profiles.sample.json"),encoding="utf-8"))
rows=load(); allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)
unk=[(c,len(allg[c])) for c in allg if P[c]['kind']=='unknown' and P[c]['tier']==0]
print("tier0+unknown companies:", len(unk), " total jobs:", sum(n for _,n in unk))
from collections import Counter
d=Counter(n for _,n in unk)
print("their lifetime-n histogram:", dict(sorted(d.items())))
for th in range(2,9):
    hit=[(c,n) for c,n in unk if n>=th]
    print(f"  threshold n>={th}: {len(hit)} companies, {sum(n for _,n in hit)} lifetime jobs")
# what happens if corpus grows k-fold (companies keep posting at same rate)
print("\nsimulated corpus growth (multiply every company's n by k), threshold stays 5:")
for k in [1,2,3,5,7,10,14,30]:
    hit=[(c,n) for c,n in unk if n*k>=5]
    print(f"  k={k:2d} (~{k*2} days of data): {len(hit)} of {len(unk)} unknown companies flagged as 中介 ({100*len(hit)/len(unk):.0f}%)")
# S4 stack ratio drift
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
print("\nS4 stack signal, current hits:")
for c in allg:
    rs=allg[c]; n=len(rs)
    st={k for r in rs for k in STACK if k in (r['job_title'] or '').lower()}
    if len(st)>=3 and len(st)/n>=0.25:
        print(f"  {P[c]['name'][:35]:37s} stacks={len(st)} n={n} ratio={len(st)/n:.2f}  -> ratio at 10x data = {len(st)/(n*10):.3f} (dies)")
