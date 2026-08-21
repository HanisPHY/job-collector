# -*- coding: utf-8 -*-
import os, sys; os.chdir(os.path.dirname(os.path.abspath(__file__)))
"""Adjudicate A4 attribution: batch composition vs model capability vs knowledge cutoff."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich_v4 as E
from base import norm
S4o=json.load(open('stage2_gpt-4o.json',encoding='utf-8'))
Smini=json.load(open('stage2_gpt-4o-mini.json',encoding='utf-8'))
rec=[v['name'] for v in S4o.values() if v.get('tier',0)>=2]
print("EXP-1  gpt-4o recovered these", len(rec), "from the residue.")
print("       gpt-4o-mini on the SAME dense residue batches recovered:",
      sum(1 for v in Smini.values() if v.get('tier',0)>=2))
print("\nEXP-2  maximum-density batch: ask gpt-4o-mini ONLY these", len(rec), "recoverable names.")
print("       If batch composition were the mechanism, 4o-mini should now recognise them.")
E.MODEL="gpt-4o-mini"
arr,u=E.ask(sorted(rec), seed=11)
got={norm(x.get('name','')):x for x in arr}
ok=sum(1 for n in rec if got.get(norm(n),{}).get('tier',0)>=2)
print(f"       -> gpt-4o-mini recognises {ok}/{len(rec)} as tier>=2   (cost ~${u.prompt_tokens*0.15/1e6+u.completion_tokens*0.6/1e6:.4f})")
fail=[n for n in rec if got.get(norm(n),{}).get('tier',0)<2]
print("       still unknown/low to 4o-mini:", fail[:25])
E.MODEL="gpt-4o"
arr2,u2=E.ask(sorted(rec), seed=11)
got2={norm(x.get('name','')):x for x in arr2}
ok2=sum(1 for n in rec if got2.get(norm(n),{}).get('tier',0)>=2)
print(f"       -> gpt-4o   on the identical batch: {ok2}/{len(rec)} tier>=2  (cost ~${u2.prompt_tokens*2.5/1e6+u2.completion_tokens*10/1e6:.4f})")
