# -*- coding: utf-8 -*-
import sys, re, json, os; os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,'.')
from base import load, norm
import _evalA3_r3 as r3
from _evalA3_r3 import R3, build, day_rows
from collections import Counter, defaultdict
r3.REL_INC=re.compile(r3.REL_INC.pattern, re.I)
rows=load(); P=build(); DAY="2026-08-20"; R=R3(rows,P,DAY)
print("### A. S5 今天的安全边际（unknown/t0/stage>=1/非自有board 的 n_7d 排名）")
cand=sorted(((len(R.win_by[c]),c) for c in R.win_by
   if R.profile(c)['kind']=='unknown' and R.profile(c)['tier']==0
   and R.profile(c).get('stage',0)>=1 and c not in R.board), reverse=True)
for n,c in cand[:16]:
    mark=" <= 阈值 5" if n==5 else ("  ★命中" if n>=5 else "")
    print(f"   {n:3d}  {P.get(c,{}).get('name',c)[:40]:42s}{mark}")
print(f"   命中 {sum(1 for n,_ in cand if n>=5)} 家；紧挨阈值下方(n=4)的有 {sum(1 for n,_ in cand if n==4)} 家、n=3 的 {sum(1 for n,_ in cand if n==3)} 家")

print("\n### B. 第三种状态：LLM_NO_ROW / 富化返回残缺")
s1=json.load(open('passes_v4.json',encoding='utf-8'))[0]
nr=[k for k,v in s1.items() if v.get('why')=='LLM_NO_ROW']
print("   passes_v4 pass1 里 why=='LLM_NO_ROW' 的公司数:", len(nr), nr[:6])
print("   -> build_profiles 给所有 stage1 条目统一 stage=1，所以 LLM_NO_ROW 也被当成『已富化』")
print("   -> 这类条目 kind=unknown tier=0，量大时会被 S5 判中介，而它其实是 API 没回来")
print("   spec §4 的 profile() 也没有区分 why=='LLM_NO_ROW'")
# also: does enrich_v4 even write a 'stage' key? 
import inspect, enrich_v4
src=inspect.getsource(enrich_v4.run_pass)
print("   enrich_v4.run_pass 的兜底字典是否含 'stage':", "'stage'" in src or '"stage"' in src)

print("\n### C. 第三种状态：override 只覆盖 prom 会把未富化公司变成『已富化』")
ov={"hadrian":{"prom":40}}
R2=R3(rows,{},DAY,overrides=ov)   # empty profile table -> everyone stage 0
v=R2.profile("hadrian")
print("   空档案表 + override 只给 prom:", {k:v[k] for k in ('kind','tier','prom','stage')})
print("   company_lane('hadrian') =", R2.company_lane("hadrian"))
print("   -> spec 的 profile() 写死 stage=max(stage,1)，所以只覆盖 prom 的公司会解锁 S5")
print("   -> 但 spec 的 company_lane 第一步 `if c in OVERRIDES: return ...` 会先返回，实测:", R2.company_lane("hadrian")[0])

print("\n### D. 公司改名 / 别名")
print("   改名 = 新 norm 键 = 不在档案表 = stage 0 = 永不进 C（安全方向）")
print("   反向风险：一个中介改名后会逃出 Lane C，直到下次富化。属于已知长尾，不新增。")
