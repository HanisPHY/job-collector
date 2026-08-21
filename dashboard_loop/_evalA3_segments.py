# -*- coding: utf-8 -*-
import sys, re, json, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load, norm
import _evalA3_r3 as r3
from _evalA3_r3 import R3, build, day_rows
from collections import Counter, defaultdict
rows=load(); P=build()
def measure(label):
    for DAY in ["2026-08-19","2026-08-20"]:
        R=R3(rows,P,DAY); dr=day_rows(rows,DAY)
        raw=Counter(); g=defaultdict(lambda: defaultdict(list))
        for r in dr:
            s=R.segment(r); raw[s]+=1; g[s][norm(r['company_name'])].append(r)
        cap2={s:sum(min(2,len(v)) for v in g[s].values()) for s in g}
        print(f"  {label} {DAY}: 段①={cap2.get('1a_t3',0):3d} 段②={cap2.get('1a_t2',0):3d} "
              f"段③={cap2.get('1b',0):4d} ④B1={cap2.get('B1',0):3d} ⑤B2={cap2.get('B2',0):4d} "
              f"⑥C={cap2.get('C',0):4d} | 默认可见①+④={cap2.get('1a_t3',0)+cap2.get('B1',0):3d} | raw总={sum(raw.values())}")
print("spec 声称:            8/19: 段①=13 段②=40 段③=36 ④=70 ⑤=21 ⑥=13")
print("spec 声称:            8/20: 段①=28 段②=43 段③=232 ④=10 ⑤=347 ⑥=113  默认可见=38  raw总=931")
print()
measure("regex 按 §3.1 字面 :")
r3.REL_INC = re.compile(r3.REL_INC.pattern, re.I)
measure("regex 加 re.I     :")
# titles ending in ' I' or ' 1'
t=[x['job_title'] or '' for x in rows]
print("\n corpus 里以 ' I' 结尾的标题:", sum(1 for x in t if re.search(r'\bI$',x.strip())),
      " 以 ' 1' 结尾:", sum(1 for x in t if re.search(r'\b1$',x.strip())))
print(" 例:", [x for x in t if re.search(r'\b(I|1)$',x.strip())][:6])
