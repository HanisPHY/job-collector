# -*- coding: utf-8 -*-
"""Q1a-2: the window FILLING UP (the case my background-filler test held fixed).
Model: the same daily traffic shape repeats for D days; evaluate on the last day."""
import sys, re, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load, norm
import _evalA3_r3 as r3
from _evalA3_r3 import R3, build
from datetime import datetime, timedelta
r3.REL_INC=re.compile(r3.REL_INC.pattern, re.I)
rows=load(); P=build(); DAY="2026-08-20"
d0=datetime.strptime(DAY,"%Y-%m-%d")
today=[r for r in rows if r['_day']==DAY]
NOTABLE={norm(x) for x in """muon space|hadrian|astroforge|traba|baseten|flock|nscale|overland ai|
xaira therapeutics|circana|openlane|red cat holdings|core4ce|vantor|rhombus power inc|oklo inc|
character.ai|warp|wonderschool|atticus|otter|doppel|happyrobot|nooks|radiant|11x|squint|confido|
netic|gradial|freeform|general matter|ellipsis labs|northwoodspace|lightfield|crusoe|weride.ai
""".replace("\n","").split("|")}
print(f"{'窗口内天数':>8} {'win_total':>9} {'S5命中':>7} {'其中真实早期公司':>16}")
for D in [1,2,3,4,5,6,7]:
    rr=[]
    for k in range(D):
        d=(d0-timedelta(days=k)).strftime("%Y-%m-%d")
        for i,r in enumerate(today):
            x=dict(r); x["_day"]=d; x["unique_id"]=r["unique_id"]+"_d%d"%k; rr.append(x)
    R=R3(rr,P,DAY)
    hits=[(c,len(R.win_by[c])) for c in R.win_by
          if R.company_lane(c)[0]=='inter' and 'unknown+vol' in ''.join(R.company_lane(c)[1])]
    fp=[c for c,_ in hits if c in NOTABLE]
    print(f"{D:8d} {len(R.win):9d} {len(hits):7d} {len(fp):16d}   {[P.get(c,{}).get('name',c) for c in fp][:7]}")
print("\n窗口填满(7天同样流量)时被判中介的真实早期公司全名单：")
rr=[]
for k in range(7):
    d=(d0-timedelta(days=k)).strftime("%Y-%m-%d")
    for r in today:
        x=dict(r); x["_day"]=d; x["unique_id"]=r["unique_id"]+"_d%d"%k; rr.append(x)
R=R3(rr,P,DAY)
hits=sorted(((len(R.win_by[c]),c) for c in R.win_by
    if R.company_lane(c)[0]=='inter' and 'unknown+vol' in ''.join(R.company_lane(c)[1])), reverse=True)
print("  总命中", len(hits), "家；其中我判为值得看的真实公司：")
for n,c in hits:
    if c in NOTABLE: print(f"     {n:4d}  {P.get(c,{}).get('name',c)}")
print("\n  对比：窗口只有 2 天（今天的真实状态）命中 8 家")
