# -*- coding: utf-8 -*-
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.dirname(os.path.abspath(__file__)))
"""Verify the design's rebuttal of the coordinator's 3-pass proposal."""
import json
from collections import Counter
P=json.load(open('passes_v4.json',encoding='utf-8'))
R1=json.load(open('company_profiles.sample.json',encoding='utf-8'))   # round1 profiles
S2=json.load(open('stage2_gpt-4o.json',encoding='utf-8'))
keys=sorted(P[0])
r1_t0=[k for k in keys if R1.get(k,{}).get('tier',0)==0 and R1.get(k,{}).get('kind')=='unknown']
print("round1 tier0/unknown companies:", len(r1_t0), "(design says 300)")
mx =sum(1 for k in r1_t0 if max(P[i][k]['tier'] for i in range(3))>=2)
def maj(vals):
    c=Counter(vals); return c.most_common(1)[0][0]
mj =sum(1 for k in r1_t0 if maj([P[i][k]['tier'] for i in range(3)])>=2)
print(f"  3-pass agg=max      -> tier>=2: {mx}  (design says 5)")
print(f"  3-pass agg=majority -> tier>=2: {mj}  (design says 4)")
# damage: companies round1 called tier>=2 that 3-pass majority demotes
r1_big=[k for k in keys if R1.get(k,{}).get('tier',0)>=2]
dem=[k for k in r1_big if maj([P[i][k]['tier'] for i in range(3)])<2]
print(f"\nround1 tier>=2 companies: {len(r1_big)};  3-pass majority demotes {len(dem)} (design says 37)")
print("  e.g.", [R1[k]['name'] for k in dem][:20])
for nm in ['five rings','flextrade','fluence','draper','q2','bigbear.ai','bigbearai','drata']:
    if nm in keys:
        print(f"   {nm:14s} round1 t{R1.get(nm,{}).get('tier')} -> 3pass {[P[i][nm]['tier'] for i in range(3)]} maj={maj([P[i][nm]['tier'] for i in range(3)])}")
# A4's 44 buried names
A44="""muon space|confido|gradial|clickhouse|ge vernova|hadrian|ecs|core4ce|vantor|superhuman|
rhombus power|astroforge|oklo|character.ai|fonzi ai|warp|flock|netic|wonderschool|atticus|otter|ramp|
overland ai|fubo|doppel|happyrobot|nooks|traba|nscale|radiant|red cat holdings|11x|amplify|circana|
openlane|zelis|enigma|waystar|xendit|databank|xaira therapeutics|mintegral|baseten|squint"""
import re
def n(s):
    s=s.strip().lower(); s=re.sub(r'[.,]','',s); return s
A=[n(x) for x in A44.replace("\n","").split("|") if x.strip()]
A=[a for a in A if a in keys]
print(f"\nA4's buried list present in corpus: {len(A)}")
print("  3-pass max recovers tier>=2:", sum(1 for k in A if max(P[i][k]['tier'] for i in range(3))>=2),
      "(design says 2)", [R1[k]['name'] for k in A if max(P[i][k]['tier'] for i in range(3))>=2])
s2rec=[k for k in A if S2.get(k,{}).get('tier',0)>=2]
s2t1 =[k for k in A if S2.get(k,{}).get('tier',0)==1]
print("  stage2(gpt-4o) recovers tier>=2:", len(s2rec), "(design says 13)")
print("      ", [S2[k]['name'] for k in s2rec])
print("  stage2 -> tier1:", len(s2t1), "(design says 8)", [S2[k]['name'] for k in s2t1])
print("\nstage2 overall: residue", len(S2), " recovered tier>=2:", sum(1 for v in S2.values() if v.get('tier',0)>=2),
      " tier1:", sum(1 for v in S2.values() if v.get('tier',0)==1),
      " still t0:", sum(1 for v in S2.values() if v.get('tier',0)==0), "(design: 44 / 61 / 242)")
# hallucination guards in stage2
for g in ['thomas to','sundayy','onyx chambers','stellar alpina','fionics','forcepull','フジアルテ株式会社']:
    if g in S2: print(f"   guard {g:18s} -> {S2[g]['kind']}/t{S2[g]['tier']}/p{S2[g].get('prom')}")
