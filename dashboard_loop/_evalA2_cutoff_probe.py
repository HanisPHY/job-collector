# -*- coding: utf-8 -*-
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.dirname(os.path.abspath(__file__)))
import sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich_v4 as E
from base import norm
POST=["Anysphere","Sierra AI","Physical Intelligence","Thinking Machines Lab",
      "Safe Superintelligence Inc","World Labs","Skild AI","Decagon","Harvey AI","Figure AI",
      "Perplexity AI","Glean","Cognition AI","Mistral AI",
      "GE Vernova","Veralto","Solventum","Kenvue",
      "ClickHouse","Ramp","Waystar","Stripe","Anthropic","Databricks"]
for m,(pi,po) in [("gpt-4o",(2.5,10.0)),("gpt-4o-mini",(0.15,0.60))]:
    E.MODEL=m
    arr,u=E.ask(POST, seed=31)
    g={norm(x.get('name','')):x for x in arr}
    print(f"\n=== {m}  (dense batch of 24, mostly recognisable) cost ${u.prompt_tokens*pi/1e6+u.completion_tokens*po/1e6:.4f}")
    for n in POST:
        x=g.get(norm(n),{})
        print(f"   {n:26s} {str(x.get('kind','MISSING')):9s} t{x.get('tier','?')} p{str(x.get('prom','?')):>4}  {str(x.get('why',''))[:32]}")
