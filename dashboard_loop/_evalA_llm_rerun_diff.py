# -*- coding: utf-8 -*-
import json,sys,os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_base import norm
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"company_profiles.sample.json"),encoding="utf-8"))
INTER={'staffing','outsourcing','training','aggregator'}
def rd(p):
    t=open(p,encoding="utf-8").read(); t=t[t.index("{"):]
    d=json.loads(t); a=d.get("companies") or next(v for v in d.values() if isinstance(v,list))
    return {norm(x.get("name","")):x for x in a}
tot=0; flips=0; lane_flips=0; miss=0
for i in [0,5,10]:
    r=rd(f"pb{i}_out.txt"); names=json.load(open(f"pb{i}.json",encoding="utf-8"))
    for n in names:
        k=norm(n); b=r.get(k); o=P[k]; tot+=1
        if not b: miss+=1; print(f"  MISSING ROW: {n}"); continue
        if b['kind']!=o['kind'] or b['tier']!=o['tier']:
            flips+=1
            oi = o['kind'] in INTER; bi = b['kind'] in INTER
            olane = 'C' if oi else ('A' if o['tier']>=2 else 'B')
            blane = 'C' if bi else ('A' if b['tier']>=2 else 'B')
            mark = ""
            if olane!=blane: lane_flips+=1; mark=f"  ***LANE {olane}->{blane}***"
            print(f"  {n[:38]:40s} cached={o['kind']}/t{o['tier']:<2} rerun={b['kind']}/t{b['tier']:<2}{mark}")
print(f"\nre-ran 3 of the 17 production batches ({tot} companies)")
print(f"  label changed (kind or tier): {flips}/{tot} = {100*flips/tot:.1f}%")
print(f"  of which LANE changed        : {lane_flips}/{tot} = {100*lane_flips/tot:.1f}%")
print(f"  rows the model failed to return: {miss}")
