# -*- coding: utf-8 -*-
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.dirname(os.path.abspath(__file__)))
"""EXP-3: batch SIZE vs recognizable-DENSITY, model fixed at gpt-4o-mini."""
import sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich_v4 as E
from base import norm
from concurrent.futures import ThreadPoolExecutor
S4o=json.load(open('stage2_gpt-4o.json',encoding='utf-8'))
passes=json.load(open('passes_v4.json',encoding='utf-8')); s1=passes[0]
residue=sorted([v['name'] for v in s1.values() if v['tier']==0 and v['kind']=='unknown'], key=str.lower)
sub=residue[:150]
E.MODEL="gpt-4o-mini"
def run(names,size,seed):
    bs=[names[i:i+size] for i in range(0,len(names),size)]
    out={}; ti=to=0
    def one(b):
        for _ in range(3):
            try: return E.ask(b,seed=seed)
            except Exception: pass
        return [],None
    with ThreadPoolExecutor(max_workers=8) as ex:
        for arr,u in ex.map(one,bs):
            if u: ti+=u.prompt_tokens; to+=u.completion_tokens
            for x in arr:
                nm=(x.get('name') or '').strip()
                if nm: out[norm(nm)]=x
    return out,ti,to
ref=sum(1 for n in sub if S4o.get(norm(n),{}).get('tier',0)>=2)
print(f"reference on the same 150 names: gpt-4o batch50 -> tier>=2 = {ref}")
for size in [50,20,10]:
    got,ti,to=run(sub,size,seed=21)
    n=sum(1 for x in sub if got.get(norm(x),{}).get('tier',0)>=2)
    print(f"gpt-4o-mini batch{size:<3d} -> tier>=2 = {n:3d}/150   cost ${ti*0.15/1e6+to*0.6/1e6:.4f}")
