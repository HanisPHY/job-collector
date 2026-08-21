# -*- coding: utf-8 -*-
"""Q4: is the spec's rebuttal of steer-1 correct, and does tier noise move companies
between 段① and 段②?"""
import sys, re, json, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load, norm
import _evalA3_r3 as r3
from _evalA3_r3 import R3, build, day_rows, is_entry
r3.REL_INC=re.compile(r3.REL_INC.pattern, re.I)
import _evalA3_r3 as R3M
from collections import Counter, defaultdict
PS=json.load(open('passes_v4.json',encoding='utf-8'))
keys=sorted(PS[0])
def band_prom(p): return 1 if p>=85 else (2 if p>=60 else 3)
def band_tier(t): return 1 if t==3 else (2 if t==2 else 3)
cp=sum(1 for k in keys if len({band_prom(PS[i][k].get('prom',0) or 0) for i in range(3)})>1)
ct=sum(1 for k in keys if len({band_tier(PS[i][k]['tier']) for i in range(3)})>1)
print(f"3 遍之间分段会变的公司： prom 阈值(85/60) {cp}/680 = {100*cp/680:.1f}%   "
      f"tier 阈值(3/2) {ct}/680 = {100*ct/680:.1f}%   (spec 说 4.4% / 4.9%)")
# tier3<->tier2 flips specifically (段① vs 段②)
flip32=[k for k in keys if {PS[i][k]['tier'] for i in range(3)} & {3} and {PS[i][k]['tier'] for i in range(3)} & {2}]
print(f"\ntier 在 3 和 2 之间抖动的公司: {len(flip32)}")
# which of them actually carry an entry-relevant job on 8/20 -> would jump 段①<->段②
rows=load(); P=build(); DAY="2026-08-20"; R=R3(rows,P,DAY); dr=day_rows(rows,DAY)
ent=defaultdict(int)
for r in dr:
    if is_entry(r['job_title']): ent[norm(r['company_name'])]+=1
jump=[(k,ent[k],[PS[i][k]['tier'] for i in range(3)]) for k in flip32 if ent.get(k)]
print(f"其中在 8/20 有『应届相关』岗位、因此会在段①/段②之间跳的公司: {len(jump)}")
for k,n,t in sorted(jump,key=lambda x:-x[1]):
    print(f"    {PS[0][k]['name'][:34]:36s} 应届岗 {n} 条  三遍 tier={t}")
tot1=sum(1 for r in dr if R.segment(r)=='1a_t3')
print(f"\n段① raw 行数 {tot1}；会因 tier 抖动而进出段①的行数 {sum(n for _,n,_ in jump)} "
      f"= {100*sum(n for _,n,_ in jump)/max(1,tot1):.0f}%")
# and prom, under the round3 design, only orders WITHIN a segment
print("\nprom 在 round3 只做段内排序；检查 prom 抖动是否会改变段内相对顺序：")
big=[k for k in keys if max(PS[i][k]['tier'] for i in range(3))>=2]
sw=0
for k in big:
    ps=[PS[i][k].get('prom',0) or 0 for i in range(3)]
    if max(ps)-min(ps)>=20: sw+=1
print(f"   tier>=2 的 {len(big)} 家里，prom 三遍振幅 >=20 的有 {sw} 家 —— 只影响段内位次，不影响可见性")
