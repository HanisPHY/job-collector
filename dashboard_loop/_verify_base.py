# -*- coding: utf-8 -*-
import csv, os, json, re
from collections import Counter, defaultdict
HERE = r"D:/OneDrive/work/school/project/Job"
SOURCES = [("newgrad_classifications.csv","newgrad"),("ats_jobs.csv","ats_direct"),("ddg_jobs.csv","ddg")]

def load():
    seen=set(); rows=[]
    for fn,label in SOURCES:
        p=os.path.join(HERE,fn)
        with open(p,"r",newline="",encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                uid=r.get("unique_id")
                if uid and uid in seen: continue
                if uid: seen.add(uid)
                r["_source"]=label
                r["_day"]=(r.get("date_recorded") or "")[:10]
                rows.append(r)
    return rows

def norm(name):
    s=(name or "").strip().lower()
    s=re.sub(r"[.,]", "", s)
    s=re.sub(r"\s+"," ",s)
    for suf in [" inc"," llc"," ltd"," corp"," corporation"," co"," company"," limited"," plc"," lp"," llp"," group"," gmbh"," pvt"," private limited"]:
        if s.endswith(suf): s=s[:-len(suf)].strip()
    return s
