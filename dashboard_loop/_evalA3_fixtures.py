# -*- coding: utf-8 -*-
"""Verify the fixtures that guard my two blocking items, plus F13 vacuity."""
import sys, re, json, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load, norm
import _evalA3_r3 as r3
from _evalA3_r3 import R3, build, day_rows, is_entry
r3.REL_INC=re.compile(r3.REL_INC.pattern, re.I)
rows=load(); P=build(); DAY="2026-08-20"; dr=day_rows(rows,DAY)
co819={norm(r['company_name']) for r in rows if r['_day']<="2026-08-19"}
Pstale={k:v for k,v in P.items() if k in co819}
print("### F6 空档案表")
R=R3(rows,{},DAY)
C=[r for r in dr if R.segment(r)=='C']
print("   Lane C 行数 =", len(C), "(F6 期望 0)")
for q in ['deloitte','amazon','booz allen hamilton']:
    print(f"   {q} in C:", any(norm(r['company_name'])==q for r in C))
print("\n### F7 过期档案表（只含 8/19 见过的公司）")
R=R3(rows,Pstale,DAY)
Cc={norm(r['company_name']) for r in dr if R.segment(r)=='C'}
fp=[c for c in Cc if P.get(c,{}).get('tier',0)>=2 and P.get(c,{}).get('kind')=='employer']
print("   Lane C 公司数 =", len(Cc), " 其中真实雇主(employer且tier>=2) =", len(fp), fp)
print("\n### F13 是否可自动断言")
R=R3(rows,P,DAY)
seg1=[r for r in dr if R.segment(r)=='1a_t3']
g={}
for r in seg1: g.setdefault(norm(r['company_name']),[]).append(r)
q=[]
for c in sorted(g, key=R.sort_key):
    for r in g[c][:2]: q.append(r)
print("   段① cap2 行数 =", len(q))
print("   前 30 行里 is_entry()==True 的比例 =",
      f"{sum(1 for r in q[:30] if is_entry(r['job_title']))}/30",
      "<- 段①的定义就是 is_entry，所以这条断言恒真，等于什么都没测")
print("   前 12 行实际内容：")
for r in q[:12]:
    v=R.profile(norm(r['company_name']))
    print(f"     [T{v['tier']} p{v['prom']:3d}] {v['name'][:24]:26s} | {(r['job_title'] or '')[:56]}")
print("\n### 现在 Lane C 与中介占比（gpt-4o 缓存，8/20）")
Cn=[r for r in dr if R.segment(r)=='C']
print(f"   {len(Cn)} 行 / {len({norm(r['company_name']) for r in Cn})} 家 = {100*len(Cn)/len(dr):.1f}%  (spec: 113cap2 / 82家 / 23.0%)")
