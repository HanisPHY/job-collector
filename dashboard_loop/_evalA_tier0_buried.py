# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_base import *
P=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"company_profiles.sample.json"),encoding="utf-8"))
INTER={'staffing','outsourcing','training','aggregator'}
STACK=['java','python','.net','c#','react','angular','vue','flutter','php','ruby','node','salesforce','sap','android','ios','swift','kotlin','desktop','electron','maui','sharepoint','oracle','tableau']
rows=load(); allg=defaultdict(list)
for r in rows: allg[norm(r['company_name'])].append(r)
def tnorm(t): return re.sub(r'\W+',' ',(t or '').lower()).strip()
def cls(c):
    rs=allg[c]; v=P[c]; n=len(rs); ats=any(r['_source']!='newgrad' for r in rs); t=[]
    if v['kind'] in INTER: t.append('llm')
    if sum(1 for r in rs if re.search(r'\s+at\s+[A-Z0-9]',r['job_title'] or ''))/n>=0.5: t.append('rep')
    if sum(1 for r in rs if (r['job_title'] or '').rstrip().lower().endswith('jobs'))/n>=0.5: t.append('jobs')
    st={k for r in rs for k in STACK if k in (r['job_title'] or '').lower()}
    if len(st)>=3 and len(st)/n>=0.25: t.append('stack')
    if v['kind']=='unknown' and v['tier']==0 and n>=5: t.append('unkvol')
    if not t: return 'ok'
    if ats and v['kind'] not in INTER: return 'veto'
    return 'inter'
CL={c:cls(c) for c in allg}
NOTABLE = """GE Vernova|Crusoe|ClickHouse|WHOOP|IMC|Traba|Nooks|Hadrian|Freeform|Ellipsis Labs|General Matter|
WeRide.ai|Muon Space|Confido|Netic|Gradial|Lightfield|Ramp|Warp|Character.AI|Baseten|Vultr|Motive|Waystar|
Fubo|Circana|OPENLANE|Abridge|ThreatLocker|Flock|Superhuman|Otter|Composio|Doppel|Mach Industries|
Reflect Orbital|AstroForge|Overland AI|Nscale|Xaira Therapeutics|Zelis|Tebra|Harbinger|Radiant|Squint|
Xendit|Mintegral|Red Cat Holdings|Vantor|Core4ce|ECS|Kikoff|Amplify|Enigma|DataBank|Pylon|11x|Rhombus Power Inc.|
Wonderschool|Atticus|Fonzi AI|HappyRobot|Oklo Inc|True Anomaly|Anthropic|Anduril|Anduril Industries|Five Rings"""
NOT=[norm(x.strip()) for x in NOTABLE.replace("\n","").split("|") if x.strip()]
DAY="2026-08-20"
today=[r for r in rows if r['_day']==DAY]; seen=set(); dr=[]
for r in today:
    k=(norm(r['company_name']), tnorm(r['job_title']))
    if k in seen: continue
    seen.add(k); dr.append(r)
B=[r for r in dr if CL[norm(r['company_name'])]!='inter' and P[norm(r['company_name'])]['tier']<2]
gb=defaultdict(int)
for r in B: gb[norm(r['company_name'])]+=1
hit=[(P[c]['name'],n,P[c]['tier']) for c,n in gb.items() if c in NOT]
print(f"8/20 Lane B (folded by default): {len(B)} jobs / {len(gb)} companies")
print(f"of these, companies I judge notable (unicorn / public co / well-funded hot startup): {len(hit)} companies / {sum(n for _,n,_ in hit)} jobs")
for nm,n,t in sorted(hit,key=lambda x:-x[1]): print(f"   t{t} {nm[:32]:34s} {n} job(s)")
missing=[x for x in NOT if x not in gb]
print("\n(listed but no 8/20 Lane-B job:", len(missing),")")
# where do they sit overall
print("\nLifetime view of the same notable set:")
tot=sum(len(allg[c]) for c in NOT if c in allg)
print("  lifetime jobs from notable-but-tier0/1 companies:", tot)
