# -*- coding: utf-8 -*-
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.dirname(os.path.abspath(__file__)))
import json, statistics
from collections import Counter
P=json.load(open('passes_v4.json',encoding='utf-8'))
keys=sorted(set(P[0])|set(P[1])|set(P[2]))
print("companies:", len(keys))
tsame=sum(1 for k in keys if len({P[i][k]['tier'] for i in range(3)})==1)
ksame=sum(1 for k in keys if len({P[i][k]['kind'] for i in range(3)})==1)
psame=sum(1 for k in keys if len({P[i][k].get('prom',0) for i in range(3)})==1)
print(f"tier identical across 3 passes: {tsame}/{len(keys)} = {100*tsame/len(keys):.1f}%   (design claims 93.2%)")
print(f"kind identical across 3 passes: {ksame}/{len(keys)} = {100*ksame/len(keys):.1f}%   (design claims 96.8%)")
print(f"prom identical across 3 passes: {psame}/{len(keys)} = {100*psame/len(keys):.1f}%   <-- NOT CLAIMED ANYWHERE")
# prom spread
spread=[]
for k in keys:
    v=[P[i][k].get('prom',0) or 0 for i in range(3)]
    spread.append((max(v)-min(v), k, v))
spread.sort(reverse=True)
nz=[s for s in spread if s[0]>0]
print(f"\ncompanies whose prom varies at all: {len(nz)}/{len(keys)} = {100*len(nz)/len(keys):.1f}%")
print(f"mean prom range over all 680: {sum(s[0] for s in spread)/len(spread):.2f}")
print(f"mean prom range over the varying ones: {sum(s[0] for s in nz)/max(1,len(nz)):.2f}")
print(f"max prom range: {spread[0][0]}")
print("\ntop-40 most unstable prom (range, name, three values):")
for d,k,v in spread[:40]:
    print(f"  {d:3d}  {P[0][k]['name'][:34]:36s} {v}  tiers={[P[i][k]['tier'] for i in range(3)]}")
# restricted to companies that matter: any pass gives tier>=2
print("\n--- restricted to companies with tier>=2 in ANY pass (these drive the queue) ---")
big=[k for k in keys if max(P[i][k]['tier'] for i in range(3))>=2]
sb=[(max(P[i][k].get('prom',0) or 0 for i in range(3))-min(P[i][k].get('prom',0) or 0 for i in range(3)),k) for k in big]
sb.sort(reverse=True)
print(f"n={len(big)}  prom identical: {sum(1 for d,_ in sb if d==0)}/{len(big)} = {100*sum(1 for d,_ in sb if d==0)/len(big):.1f}%")
print(f"mean range {sum(d for d,_ in sb)/len(sb):.2f}  |  range>=10: {sum(1 for d,_ in sb if d>=10)}  range>=20: {sum(1 for d,_ in sb if d>=20)}")
