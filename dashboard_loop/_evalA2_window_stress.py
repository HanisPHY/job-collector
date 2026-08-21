# -*- coding: utf-8 -*-
import os, sys; os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm
from r2 import build_profiles
from collections import defaultdict
from datetime import datetime, timedelta
rows=load(); P=build_profiles(); DAY="2026-08-20"
d0=datetime.strptime(DAY,"%Y-%m-%d")
def run(bg_per_day, rule):
    rr=list(rows); i=0
    for k in range(1,7):
        d=(d0-timedelta(days=k)).strftime("%Y-%m-%d")
        for j in range(bg_per_day):
            i+=1
            # UNIQUE company per row: fillers never accumulate volume
            rr.append({"unique_id":"bg%d"%i,"company_name":"BGCo%06d"%i,
                       "job_title":"Engineer","_source":"newgrad","_day":d})
    lo=(d0-timedelta(days=6)).strftime("%Y-%m-%d")
    win=[r for r in rr if lo<=r["_day"]<=DAY]; wt=len(win) or 1
    bywin=defaultdict(int); bycum=defaultdict(int); board=set()
    for r in win: bywin[norm(r["company_name"])]+=1
    for r in rr:
        bycum[norm(r["company_name"])]+=1
        if r["_source"]!="newgrad": board.add(norm(r["company_name"]))
    hits=[]
    for c in bywin:
        v=P.get(c) or {"kind":"unknown","tier":0}
        if not (v["kind"]=="unknown" and v["tier"]==0): continue
        if c in board: continue
        if rule=="r1" and bycum[c]>=5: hits.append(c)
        if rule=="r2" and bywin[c]>=5 and bywin[c]/wt>=0.004: hits.append(c)
        if rule=="win" and bywin[c]>=5: hits.append(c)
    return hits, wt
print(f"{'背景(唯一公司)/天':>16} {'win_total':>9} | {'r1 累计>=5':>10} {'r2 窗口+0.4%':>13} {'仅7天窗口>=5':>13}")
for bg in [0,300,700,1100,1500,3000,6000]:
    a,_=run(bg,"r1"); b,wt=run(bg,"r2"); c,_=run(bg,"win")
    print(f"{bg:16d} {wt:9d} | {len(a):10d} {len(b):13d} {len(c):13d}")
b,_=run(1100,"r2"); c,_=run(1100,"win")
print("\n稳态 1100/天：r2 漏掉、但『仅窗口>=5』仍抓到的刷屏方：")
for x in sorted(set(c)-set(b)): print("   ", P.get(x,{}).get("name",x), )
