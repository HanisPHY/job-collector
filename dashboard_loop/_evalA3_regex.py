# -*- coding: utf-8 -*-
"""Test the §3.1 relevance regex EXACTLY as written vs a case-insensitive variant."""
import sys, re, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load
rows=load()
SPEC_INC = re.compile(r"new\s*grad|new college|entry[ -.]level|university|campus|graduat|"
                      r"intern(?!ational)|202[6-8]|junior|associate|apprentic|"
                      r"early career|rotational|\bI\b$|\b1\b$")
EXC = re.compile(r"(?i)senior|principal|staff engineer|manager|director|architect|"
                 r"\bsr\b|\bII\b|\bIII\b|\blead\b|years of experience")
CI_INC = re.compile(SPEC_INC.pattern, re.I)
def spec(t):
    t=(t or "").strip(); return bool(SPEC_INC.search(t)) and not EXC.search(t)
def ci(t):
    t=(t or "").strip(); return bool(CI_INC.search(t)) and not EXC.search(t)
titles=[(r['job_title'] or '') for r in rows]
print(f"corpus titles: {len(titles)}")
print(f"  §3.1 as written (case-SENSITIVE INC): {sum(1 for t in titles if spec(t))}")
print(f"  same regex with re.I            : {sum(1 for t in titles if ci(t))}")
print("\n--- the spec's own 段① sample rows, run through the regex as written ---")
SAMPLE=["AI Software Engineering Intern","Software Quality Assurance Engineer - 2026 New College Grad",
 "Software Engineer, New Grad","Software Engineer, New Grad - Production Infrastructure",
 "Software Engineer 1","Global Technology Summer Analyst 2027 - Software Engineer",
 "2027 Full-Time Analyst Program - AMRS","Associate Data Scientist","Associate, Software Engineer",
 "New College Grad - EDA/CAD Engineer","Entry Level Software Engineer",
 "Graduate Field Service Engineer Electrical"]
for t in SAMPLE:
    print(f"   spec={str(spec(t)):5s} ci={str(ci(t)):5s}  {t}")
print("\n--- which alternative fires, for the case-sensitive version ---")
alts=["new\s*grad","new college","entry[ -.]level","university","campus","graduat",
      "intern(?!ational)","202[6-8]","junior","associate","apprentic","early career",
      "rotational","\bI\b$","\b1\b$"]
import collections
cnt=collections.Counter(); cnt_ci=collections.Counter()
for t in titles:
    for a in alts:
        if re.search(a,t): cnt[a]+=1
        if re.search(a,t,re.I): cnt_ci[a]+=1
print(f"{'alternative':22s} {'case-sensitive':>15s} {'case-insensitive':>17s}")
for a in alts: print(f"  {a:22s} {cnt[a]:15d} {cnt_ci[a]:17d}")
