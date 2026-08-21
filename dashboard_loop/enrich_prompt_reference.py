# -*- coding: utf-8 -*-
import os, json, time, sys
HERE = r"D:/OneDrive/work/school/project/Job"
key=None
for line in open(os.path.join(HERE,".env"), encoding="utf-8-sig"):
    if line.strip().startswith("OPENAI_API_KEY="): key=line.split("=",1)[1].strip()
from openai import OpenAI
client=OpenAI(api_key=key)

SYSTEM = ("You label employers for a job-search triage tool. Answer only from knowledge you are "
          "confident about. \"unknown\" is a correct and valued answer; guessing from the company "
          "name is a serious error.")

INSTR = """Label each company below. Output a JSON array, one object per input, same order, no prose.

Field "kind" - what the company does with the person it hires:
  "employer"    - you become an employee working on that company's own products, projects or
                  client engagements under its own brand. This INCLUDES management consultancies
                  (Deloitte, EY, Accenture Federal, Booz Allen, Slalom, Gartner), defense primes
                  and federal integrators (Leidos, L3Harris, SAIC, ManTech, Parsons, GDIT),
                  banks, hospitals, universities and government labs.
  "outsourcing" - global IT-services / offshore delivery firm whose model is staffing client
                  projects with rotating engineers (Tata Consultancy Services, Infosys, Wipro,
                  HCL, Cognizant, Capgemini, Synechron, NTT DATA, and small US-registered
                  Indian-owned body shops).
  "staffing"    - recruiting agency, headhunter or contract-placement firm; the job is at an
                  unnamed client, not at them (TEKsystems, Insight Global, Randstad, Robert Half,
                  Jobot, Aerotek).
  "training"    - trains or bootcamps candidates and then places them on client projects,
                  often with a training bond (Revature, SynergisticIT, Per Scholas).
  "aggregator"  - job board, job aggregator, or marketplace that reposts other companies'
                  openings under its own name (Jobright.ai, Jobgether, Hired, Jack & Jill).
  "unknown"     - you do not actually recognise this company.

Field "tier" - how big / well-known the company itself is, INDEPENDENT of "kind":
  3 - household name or sector giant: mega-cap tech, Fortune 500, top defense prime, Big-4,
      bulge-bracket bank, famous AI lab, national laboratory.
  2 - large or well-known: public mid-cap, unicorn, well-known late-stage private, a major
      player inside its industry or region, elite quant/trading firm.
  1 - small but real: a startup or small firm that you genuinely recognise.
  0 - you do not recognise it at all, or the name is too generic to identify.

Field "conf" - 0.0-1.0, your probability that BOTH kind and tier are correct.
Field "why"  - at most 8 words, or "no knowledge".
Field "name" - the input name copied EXACTLY, character for character.

Hard rules:
- If you do not recognise the company, you MUST output tier 0, kind "unknown", conf <= 0.3.
  Never infer kind or tier from words in the name such as Inc, LLC, Solutions, Technologies,
  Systems, Group or Consulting. A name is not evidence.
- "kind" and "tier" are independent: Tata Consultancy Services is outsourcing AND tier 3.
- Big-4 / strategy consultancies and defense primes are "employer", never "staffing".
- Output exactly one object for EVERY numbered input, including the ones you know nothing
  about. Do not skip, merge or reorder. The array length must equal the number of inputs.
- Return {"companies": [ ... ]}."""

def ask(names, model):
    listing = "\n".join(f"{i}. {n}" for i,n in enumerate(names,1))
    msgs=[{"role":"system","content":SYSTEM},
          {"role":"user","content":INSTR+"\n\nCompanies:\n"+listing}]
    t0=time.time()
    r=client.chat.completions.create(model=model, messages=msgs, temperature=0, response_format={"type":"json_object"})
    return r.choices[0].message.content, r.usage, time.time()-t0

if __name__=="__main__":
    names=json.load(open(sys.argv[1],encoding="utf-8")); model=sys.argv[2]
    txt,u,dt=ask(names,model)
    print("MODEL",model,"N",len(names),"IN",u.prompt_tokens,"OUT",u.completion_tokens,"SEC",round(dt,2))
    print(txt)
