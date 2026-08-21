# -*- coding: utf-8 -*-
"""Q2: what does switching stage-2 to gpt-4o-mini b20 cost on the CHOICE that matters (lane)?"""
import sys, re, json, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load, norm
import _evalA3_r3 as r3
from _evalA3_r3 import R3, build, day_rows
from collections import Counter, defaultdict
r3.REL_INC=re.compile(r3.REL_INC.pattern, re.I)
rows=load()
P4o=build("stage2_gpt-4o.json"); Pmini=build("stage2_gpt-4o-mini.json")
for DAY in ["2026-08-19","2026-08-20"]:
    print(f"\n=== {DAY} ===")
    for lab,P in [("stage2=gpt-4o  ",P4o),("stage2=4o-mini ",Pmini)]:
        R=R3(rows,P,DAY); dr=day_rows(rows,DAY)
        raw=Counter(); g=defaultdict(lambda: defaultdict(list))
        for r in dr:
            s=R.segment(r); raw[s]+=1; g[s][norm(r['company_name'])].append(r)
        cap2={s:sum(min(2,len(v)) for v in g[s].values()) for s in g}
        C=raw.get('C',0)
        print(f"  {lab} 段①={cap2.get('1a_t3',0):3d} 段②={cap2.get('1a_t2',0):3d} "
              f"④={cap2.get('B1',0):3d} | Lane C raw={C:4d} ({100*C/len(dr):.1f}%) "
              f"公司数={len(g['C'])}")
# who leaves / enters Lane C
DAY="2026-08-20"; dr=day_rows(rows,DAY)
Ra=R3(rows,P4o,DAY); Rb=R3(rows,Pmini,DAY)
ca={norm(r['company_name']) for r in dr if Ra.segment(r)=='C'}
cb={norm(r['company_name']) for r in dr if Rb.segment(r)=='C'}
print("\n  换成 mini 后逃出 Lane C 的公司:", len(ca-cb))
print("   ", ", ".join(sorted(P4o[c]['name'] for c in ca-cb)))
print("  换成 mini 后新进 Lane C 的公司:", len(cb-ca))
print("   ", ", ".join(sorted(Pmini.get(c,{}).get('name',c) for c in cb-ca)))
# my 50 long-tail suspects
FN=json.load(open('fn50.json',encoding='utf-8'))
INTER={'staffing','outsourcing','training','job_board'}
for lab,P in [("gpt-4o ",P4o),("4o-mini",Pmini)]:
    n=sum(1 for x in FN if P.get(norm(x),{}).get('kind') in INTER)
    print(f"  我 50 家长尾中介，被 {lab} 的 kind 抓到: {n}/50")
