# -*- coding: utf-8 -*-
"""Round3 resolver, transcribed literally from round3_spec.md section 4."""
import os, json, re
from datetime import datetime, timedelta
from collections import defaultdict
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import load, norm

HARD_INTER = {"staffing", "outsourcing", "training"}
S5_MIN, WINDOW_DAYS = 5, 7

REL_INC = re.compile(r"new\s*grad|new college|entry[ -.]level|university|campus|graduat|"
                     r"intern(?!ational)|202[6-8]|junior|associate|apprentic|"
                     r"early career|rotational|\bI\b$|\b1\b$")
REL_EXC = re.compile(r"(?i)senior|principal|staff engineer|manager|director|architect|"
                     r"\bsr\b|\bII\b|\bIII\b|\blead\b|years of experience")
def is_entry(title):
    t = (title or "").strip()
    return bool(REL_INC.search(t)) and not REL_EXC.search(t)

def build(stage2_file="stage2_gpt-4o.json"):
    HERE=os.path.dirname(os.path.abspath(__file__))
    s1=json.load(open(os.path.join(HERE,"passes_v4.json"),encoding="utf-8"))[0]
    s2=json.load(open(os.path.join(HERE,stage2_file),encoding="utf-8"))
    P={}
    for k,v in s1.items():
        w=dict(v); w["stage"]=1; P[k]=w
    for k,v in s2.items():
        if v.get("tier",0)>0 or v.get("kind")!="unknown":
            w=dict(v); w["stage"]=2; P[k]=w
    for v in P.values():
        try: v["prom"]=int(v.get("prom",0) or 0)
        except Exception: v["prom"]=0
    return P

class R3:
    def __init__(self, rows, P, day, overrides=None, priority=None, window=WINDOW_DAYS):
        self.P=P; self.ov=overrides or {}; self.prio=priority or set(); self.day=day
        lo=(datetime.strptime(day,"%Y-%m-%d")-timedelta(days=window-1)).strftime("%Y-%m-%d")
        self.win=[r for r in rows if lo<=r["_day"]<=day]
        self.win_by=defaultdict(list)
        for r in self.win: self.win_by[norm(r["company_name"])].append(r)
        self.board={norm(r["company_name"]) for r in rows if r["_source"]!="newgrad"}
    def profile(self,c):
        v=self.P.get(c) or {"name":c,"kind":"unknown","tier":0,"prom":0,"stage":0,"why":"not enriched"}
        o=self.ov.get(c)
        if o:
            v={**v, **{k:o[k] for k in ("kind","tier","prom") if k in o},
               "why":"manual override","stage":max(v.get("stage",0),1)}
        return v
    def company_lane(self,c):
        v=self.profile(c)
        if c in self.ov:
            return ("inter" if v["kind"] in HARD_INTER|{"job_board"} else "ok"), ["override"]
        if v["kind"] in HARD_INTER: return "inter", ["LLM:"+v["kind"]]
        if v["kind"]=="job_board":  return "inter", ["LLM:job_board"]
        if v.get("stage",0)<1:      return "ok", ["not enriched"]
        n=len(self.win_by.get(c,[]))
        if v["kind"]=="unknown" and v["tier"]==0 and n>=S5_MIN:
            if c in self.board: return "ok", ["VETO: own ATS board"]
            return "inter", ["unknown+vol %d/7d"%n]
        return "ok", []
    def row_lane(self,r):
        c=norm(r["company_name"]); verdict,sig=self.company_lane(c)
        if verdict=="inter" and r["_source"]!="newgrad": return "ok", sig+["own-board row"]
        return verdict, sig
    def segment(self,r):
        if self.row_lane(r)[0]=="inter": return "C"
        v=self.profile(norm(r["company_name"]))
        if v["tier"]>=2:
            if is_entry(r["job_title"]): return "1a_t3" if v["tier"]==3 else "1a_t2"
            return "1b"
        return "B1" if norm(r["company_name"]) in self.board else "B2"
    def sort_key(self,c):
        v=self.profile(c)
        return (0 if c in self.prio else 1, -v["prom"], -v["tier"], -len(self.win_by.get(c,[])), v.get("name",c).lower())

def tnorm(t): return re.sub(r"\W+"," ",(t or "").lower()).strip()
def day_rows(rows, day):
    seen=set(); out=[]
    for r in rows:
        if r["_day"]!=day: continue
        k=(norm(r["company_name"]), tnorm(r["job_title"]))
        if k in seen: continue
        seen.add(k); out.append(r)
    return out
