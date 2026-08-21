# Round 3 施工规格 —— 给工程师的补丁清单

> 收口轮。**不引入新机制，只做减法和参数固化。**
> round1/round2 的设计推理不再重复；本文只写「改哪个文件、加多少行、怎么断言做对了」。
> 本轮新增实测约 **$0.014**（stage-2 换模型换批次的生产规模复跑）。
> 语料口径：**1391 行 / 767 家**（8/19 287 + 8/20 1104），当日去重后 8/20 = **931 行**。

---

## 1. 对 7 条修正的处置

| # | 来源 | 决定 | 一句话改法 |
|---|---|---|---|
| 1 | A-阻断1 | ✅ **接受，删相对项** | `r2.py` 删掉 `n_win/win_total >= 0.004`，只留 `n_7d >= 5`；验收 gate 换成「背景流量压测」 |
| 2 | A-阻断2 | ✅ **接受** | S5 前置 `v.get("stage",0) >= 1`；未富化公司永不进 Lane C |
| 3 | BB1 | ✅ 同第 1 条 | 直接删，不修分母 |
| 4 | BB2 | ✅ 接受 | `run_daily_report.bat` 加 1 行 `python -u dashboard.py` |
| 5 | BB3 阅后即焚 | ✅ 接受 | 加「上一期未处理」段 + 7 天日期条 + 口径说明 |
| 6 | BB4 Lane B1 | ✅ 接受 (b)+(c) | B1 **默认展开**（稳态仅 10 行）；那 23 家写进 `company_overrides.json` |
| 7 | BB5 配额 | ✅ **接受，整段删除** | 换成 gpt-4o-mini 后日成本 $0.07，配额机制没有存在理由 |

**另外 6 条零散修正一并处理**：A 的 EXP-2/EXP-3（删「stage-2 必须全残差」规则、BATCH 50→20）、
配额成本算错（$0.13 → 该机制整体删除）、Yara AI 的 FP 措辞、验收 gate 第 3 条的盲测、
`gpt-4o` 已在 `MODEL_PRICING`（只缺 `gpt-4o-mini`）、`r2.py:has_board` 死代码删除。

### 1.1 我部分反驳编排者 steer 1 的**理由**，但接受它的**结论**

steer 1 说「分段要用离散且稳定的量（tier），prom 只排序」。**「tier 比 prom 稳」这个前提不成立**，
我用 `passes_v4.json` 离线复算（不花钱）：

```
3 遍之间「分段会变」的公司：
   用 prom 阈值 (85/60) 分段 : 30/680 = 4.4%   （与 A 实测同值）
   用 tier 阈值 (3/2)   分段 : 33/680 = 4.9%   ← 不比 prom 稳
```

**但结论仍然正确，理由要换成更强的那个**：新分段的主判据是**应届相关性正则**，
它是纯字符串匹配，**采样噪声为 0**。tier 只在「已相关」的集合内部做粗切，
被切低一档的代价是「多点一次展开」。prom 退化为段**内**排序，对噪声不敏感
（Amazon 92 还是 88 都排前面）。
所以最终分段判据里**不含任何 prom 阈值**（steer 1 的要求满足），
B 建议的 `prom>=60` 那道门也一并消掉。

### 1.2 A 的 EXP-4（知识截止）—— 不再争，写进已知缺口

接受 A 的裁决：**批次效应与知识截止两者都真实存在**，我用 `GE Vernova` 证伪是选错了样本
（名字可分解成 "GE spinoff"）。2023 年后成立/分拆的公司（Anysphere/Cursor、Sierra AI、
Harvey、Figure、Decagon、Solventum…）任何模型任何批次都拿不到 tier，**永久落折叠区**。
这是 LLM 路线的结构性上限，兜底手段只有 `company_overrides.json`，不是再问一遍 LLM。

---

## 2. stage-2 的重新裁决：**留在 P0，但换成 gpt-4o-mini + batch 20**

B 判「不值」的两个前提，我实测**两个都被推翻**。

### 前提一「产出 100% 落在折叠区」—— 在新分段下不成立

B 自己的分段建议（相关性 ∩ tier≥2）推翻了它自己的成本论证。实测段①+②（cap2）：

| profile | 8/19 | 8/20 |
|---|---|---|
| 无 stage-2 | 43 | 69 |
| stage-2 = gpt-4o-mini b20 | 45 (**+2**) | 71 (**+2**) |
| stage-2 = gpt-4o b50 | 53 (**+10**) | 71 (**+2**) |

进入首屏的 stage-2 公司实名：8/20 = `GE Vernova`、`Mintegral`；
8/19 = `Handshake`、`Five Rings`、`IMC`、`WeRide.ai`、`STR`、`Crb`。
**不是 0 行，是每天 2-10 行。**

### 前提二「贵」—— A 的 EXP-3 在生产规模复现，便宜 12.4 倍

按 A 的建议把 stage-2 换成 `gpt-4o-mini` + `BATCH=20`，跑同一份 347 家残差：

```
gpt-4o      batch 50 : 回收 tier>=2 44 家   in  9018 / out 14939   $0.1719   41s
gpt-4o-mini batch 20 : 回收 tier>=2 30 家   in 19843 / out 18072   $0.0138   73s
                       = 68% 的回收量，12.4 倍便宜
```

`gpt-4o-mini b20` 拿到的关键公司：`GE Vernova` t3、`Handshake` t2、`ClickHouse` t2、
`Fubo` t2、`ECS` t2、`DataBank` t2。丢掉的：`Five Rings`、`IMC`、`Ramp`、`Waystar`、
`Superhuman`、`Enigma`、`Amplify`、`Mintegral`（全部 t0）。

### 最终决定

- **初始缓存保持 gpt-4o 版本**（`company_profiles.round2.json` 里那 105 条已经付过钱，
  含 Five Rings / IMC / Ramp / Waystar 等 gpt-4o-mini 拿不到的）。**用户从最好的表起步。**
- **增量富化用 `gpt-4o-mini` + `BATCH=20`**，日成本 $0.02 级别。
- 保留一个 `--deep` 开关（`gpt-4o`、batch 20）供人工一次性补跑，**不进定时任务**。
- **每日配额机制整段删除**（BB5 随之消失，-25 行）。`gpt-4o` 不进日常路径。

---

## 3. 最终分段定义

判据里**不含 prom 阈值**；prom 只决定段**内**顺序。

| 段 | 判据 | 8/19 cap2 | 8/20 cap2 | 默认 |
|---|---|---|---|---|
| ⓪ hero | 「今日必看 N 条（上一期 M 条）」 | — | — | — |
| **① 今日必看** | `lane≠C ∧ tier==3 ∧ 应届相关` | 13 | **28** | **展开** |
| ② 大中公司应届岗 | `lane≠C ∧ tier==2 ∧ 应届相关` | 40 | 43 | 折叠（标题带条数） |
| ③ 大中公司其他岗位 | `lane≠C ∧ tier>=2 ∧ 非应届相关` | 36 | 232 | 折叠 |
| ④ 有自有 ATS board 的小公司 | `lane≠C ∧ tier<=1 ∧ 公司出现在 ats/ddg CSV` | 70※ | **10** | **展开**（BB4-b） |
| ⑤ 长尾 | 其余 `lane≠C` | 21 | 347 | 折叠 |
| ⑥ 中介 / 刷屏 | `lane==C` | 13 | 113 | 折叠 |
| ⑦ 上一期未处理 | 上一个 cutoff 区间内的 ①②④ 行 | — | — | 折叠（BB3） |

※ 8/19 的 ④ 段 70 行是 `ats_direct` 首日全量收割的一次性效应；稳态 = 10 行（B 已核实）。

**默认可见 = ① + ④ = 8/20 的 38 行**（对比用户当前在看的 md 日报 3076 行 / 938 链接，
81 倍压缩），落在编排者要求的 30-50 区间。一键展开 ② 到 81 行。

**段① 实测内容（8/20 前 12 行，prom 排序）** —— 前 30 行 30/30 全是明确应届岗：

```
[T3 p100] Intel                 | AI Software Engineering Intern
[T3 p 95] NVIDIA                | Software QA Engineer - 2026 New College Grad
[T3 p 85] Palantir Technologies | Software Engineer, New Grad
[T3 p 85] Palantir Technologies | Software Engineer, New Grad - Production Infrastructure
[T3 p 85] Intuit                | Software Engineer 1
[T3 p 75] Bank of America       | Global Technology Summer Analyst 2027 - Software Engineer
[T3 p 75] BlackRock             | 2027 Full-Time Analyst Program - AMRS
[T3 p 75] Gartner               | Associate Data Scientist
[T3 p 70] L3Harris Technologies | Associate, Software Engineer            x2
[T3 p 60] Micron Technology     | New College Grad - EDA/CAD Engineer     x2
[T3 p 60] BAE Systems, Inc.     | Entry Level Software Engineer
[T3 p 60] GE Vernova            | Graduate Field Service Engineer Electrical
```

**零丢弃算术校验（统一 cap2 口径，修 A 的 NB-A）**：

```
段  raw   cap2  藏在 +N more
1a   74    71      3
1b  270   232     38
B1   11    10      1
B2  359   347     12
C   217   113    104
raw 合计 931 == 当日去重后 931  OK
```

表格里**只登记 raw 与 cap2 两列**，禁止混用口径。「+N more」必须是真 `<details>`。

### 3.1 应届相关性正则（写死在 `dashboard.py`，约 6 行）

```python
REL_BODY = re.compile(r"new\s*grad|new college|entry[ -.]level|university|campus|graduat|"
                      r"intern(?!ational)|202[6-8]|junior|associate|apprentic|"
                      r"early career|rotational", re.I)     # 正文：大小写不敏感
REL_SUF  = re.compile(r"\b(?:I|1)$")                        # 后缀标级：大小写敏感
REL_EXC  = re.compile(r"senior|principal|staff engineer|manager|director|architect|"
                      r"\bsr\b|\bII\b|\bIII\b|\blead\b|years of experience", re.I)
def is_entry(title):
    t = (title or "").strip()
    return bool(REL_BODY.search(t) or REL_SUF.search(t)) and not REL_EXC.search(t)
```

**正文必须带 `re.I`，只有后缀标级 `\b(?:I|1)$` 保持大小写敏感**（要区分 `Engineer I`
与小写单词 `i`）。⚠️ round3 初稿写成「`REL_INC` 整体大小写敏感」是**错的**：按字面实现会让
`New Grad` / `Entry Level` / `Associate` / `Graduate` / `Intern` 五个分支全部哑火，
只剩年份分支在干活，段① 从 28 掉到 **9**、默认可见从 38 掉到 **20**，直接违反 F10 / F11。
两位评估者独立撞到同一处；上面这一版是能复现 §3 表全部六个分段数字的那一版。
**它是分段依据，不是过滤器 —— 任何行都不许因为不匹配而被删除**，只是落到段③。

抽检说明：段① 里有 20/74 行不含 "grad/intern/entry" 字样，全部是 `Engineer I` /
`Software Engineer 1` / `ENGINEER TEST OPERATIONS 1` 这类**后缀标级**的入门岗，
是真阳性，不是误匹配。

---

## 4. 最终信号与决议顺序（可直接翻译成代码）

```python
HARD_INTER = {"staffing", "outsourcing", "training"}
S5_MIN, WINDOW_DAYS = 5, 7

def profile(c):                       # 全函数，永不抛异常
    v = PROFILES.get(c) or {"kind": "unknown", "tier": 0, "prom": 0, "stage": 0,
                            "why": "not enriched"}
    o = OVERRIDES.get(c)
    if o:
        v = {**v, **{k: o[k] for k in ("kind", "tier", "prom") if k in o},
             "why": "manual override", "stage": max(v.get("stage", 0), 1)}
    return v

def company_lane(c, day):             # -> ("inter" | "ok", signals)
    v = profile(c)
    if c in OVERRIDES:                                        # O1 人工，最高
        return ("inter" if v["kind"] in HARD_INTER | {"job_board"} else "ok"), ["override"]
    if v["kind"] in HARD_INTER:                               # S1a 硬中介
        return "inter", ["LLM:" + v["kind"]]
    if v["kind"] == "job_board":                              # S1b 招聘板
        return "inter", ["LLM:job_board"]
    if v.get("stage", 0) < 1:                                 # A-阻断2：未富化，永不进 C
        return "ok", ["not enriched"]
    n = window_count(c, day, WINDOW_DAYS)
    if v["kind"] == "unknown" and v["tier"] == 0 and n >= S5_MIN:   # A-阻断1：无相对项
        if c in BOARD_COMPANIES:                              # V1 公司级否决
            return "ok", ["VETO: own ATS board"]
        return "inter", ["unknown+vol %d/7d" % n]
    return "ok", []

def row_lane(row, day):               # 按行求值（KAYAK / Jobgether）
    c = norm(row["company_name"])
    verdict, sig = company_lane(c, day)
    if verdict == "inter" and row["_source"] != "newgrad":
        return "ok", sig + ["own-board row"]                  # 这条岗位来自它自己的 board
    return verdict, sig

def segment(row, day):
    if row_lane(row, day)[0] == "inter":
        return "C"
    v = profile(norm(row["company_name"]))
    if v["tier"] >= 2:
        if is_entry(row["job_title"]):
            return "1a_t3" if v["tier"] == 3 else "1a_t2"
        return "1b"
    return "B1" if norm(row["company_name"]) in BOARD_COMPANIES else "B2"

# 段内排序（prom 只在这里出现）
def sort_key(c, day):
    v = profile(c)
    return (0 if c in PRIORITY else 1, -v["prom"], -v["tier"],
            -window_count(c, day, 7), v["name"].lower())
```

`BOARD_COMPANIES` = `ats_jobs.csv` ∪ `ddg_jobs.csv` 里出现过的公司（94 家）。
**不要用 `ats_registry.json`** —— B 实测只多 2 家 3 行。
删除 `r2.py` 里的死代码 `self.has_board`（等于全体公司，从未生效，真正用的是 `board_cos`）。

**删除的信号**：S2（` at X` 转贴）、S3（标题以 Jobs 结尾）、S4（技术栈发散度）。
S2 保留为 Panel ③ 的**展示列**，不参与判定。

---

## 5. 最终成本表

| 项 | 单价 | 680 家一次性 | 稳态/天（悲观 1200 家新公司，51% 落残差） |
|---|---|---|---|
| stage 1 `gpt-4o-mini` batch 20 + 5 锚点 | $0.000016/家 | $0.0109 | $0.019 |
| stage 2 `gpt-4o-mini` batch 20（残差） | $0.0000398/家 | $0.0138 | $0.024 |
| newgrad 现有 LLM | — | — | $0.027 |
| **合计** | | **$0.025** | **约 $0.07/天（年 $26）** |

对比 round2 的 $0.244/天。**占 `LLM_DAILY_COST_ALERT_USD = 0.50` 的 14%**，
保持 SCHEDULING.md 原有语义（「只有调用量或模型变了才会触发」），
**不需要调阈值，不需要配额，不需要 `gpt-4o` 进日常路径**。
md 日报第 1 节的 LLM 花费从 $0.027 变成约 $0.07，不是 10 倍跳变，
但 N-9（富化 summary 用独立 `script` 名、按脚本分行）仍然要做。

**`--deep`（gpt-4o）= $0.17，建议每月手动跑一次，不是纯可选项。**
§2 说的「mini b20 拿到 68% 的回收量」**只比了 `tier`，没比 `kind`，坐标轴是窄的**：
实测换成 mini b20 之后 **16 家长尾中介逃出 Lane C**，A 那 50 家样本的召回从 16/50 掉到 **5/50**，
Lane C 从 222 行 / 82 家缩到 204 行 / 67 家。逃出去的落在折叠的 ⑤ 段、不污染首屏，所以不阻断 ——
但这是省 12.4 倍的**真实代价**，`--deep` 就是用来周期性把中介召回补回来的。
`MODEL_PRICING` **只需加 `gpt-4o-mini`**（`gpt-4o` 已在表里，A 的 NB-D）：

```python
"gpt-4o-mini": {"input": 0.00015, "output": 0.0006},   # $0.15 / $0.60 per 1M
```

---

## 6. P0 任务清单

| # | 文件 | 动作 | 新增/改动 | 验收 |
|---|---|---|---|---|
| P0-1 | `enrich_companies.py`（新） | 两段式：stage1 `gpt-4o-mini` batch 20+5 锚点；stage2 `gpt-4o-mini` batch 20 跑残差；`--deep` 用 gpt-4o；只问 `company_profiles.json` 里没有的键；按 `name` 回填；原子写；整体墙钟 300 s；**无配额**。<br>⚠️ **漏返兜底字典必须带 `"stage": 0`**：`{"name": nm, "kind": "unknown", "tier": 0, "prom": 0, "why": "LLM_NO_ROW", "stage": 0}` —— 否则「API 没返回这家」会被记成「LLM 说不认识」，正好是 S5 的触发态（阻断-2 的第三扇门，round2 §7.5 记录过这种漏返真实发生过） | ~170 新增 | F1, F2, F9, **F18** |
| P0-2 | `company_profiles.json` | 由 `dashboard_loop/company_profiles.round2.json` 改名而来（680 家，含 105 条 gpt-4o 结果） | 0 | F3 |
| P0-3 | `company_lane.py`（新） | §4 的伪代码原样落地，**含 stage 门控与无相对项的 S5** | ~90 新增 | F4-F8 |
| P0-4 | `company_overrides.json`（新）<br>`priority_companies.txt`（新，默认空） | override 读取；把 A4 剩余 23 家里用户在意的写进 override（BB4-c） | ~25 + 数据 | F8 |
| P0-5 | `dashboard.py`（新） | hero + 7 段 `<details>` + Panel ②′ + Panel ③；相关性正则；水位线；`a:visited`；「上一期」段；7 天日期条；`latest.html` | ~330 新增 | F10-F14 |
| P0-6 | `job_collector/tracking/cost_tracker.py` | 加 `gpt-4o-mini` 价格 | 4 改动 | F15 |
| P0-7 | `run_daily_report.bat` | 在 `python -u daily_report.py` 之后加 `python -u dashboard.py`（BB2） | 1 改动 | F16 |
| P0-8 | Task Scheduler | 新增 `run_logged.bat run_enrich_companies`，07:30（不需提权） | 3 行 PS | F17 |
| P0-9 | `tests/test_lane.py`（新） | §7 的 18 条 fixture（F1-F12、F14-F19） | ~170 新增 | 全绿 |
| | **合计** | | **约 765 新增 + 5 行改动** | |

**零行改在 `daily_report.py` 的分析/渲染路径上**（B3/B6 从机制上不可能回归）。

### P1（按价值排序）

1. 名字正则 → Panel ③「疑似待确认」子表（覆盖 A 剩余 34 家长尾中介）
2. `mark_applied.py` 已投写入路径
3. Panel ④ 趋势折线（≥7 天后）
4. Panel ② 漏斗 / ⑤ 采集器健康 / ⑥ 告警与花费
5. `override.py add "..." --kind staffing` 一行命令
6. `JOB_PROFILE_PATH` + 90 天未出现的 tier0 清理
7. prom 跨模型可比性一次性核对（A 的 NB-C）
8. **删掉 req1 里「实现前跑 `scripts/validate_palette.js`」这条悬空约定**（脚本不存在，
   且顺序色阶不需要配对校验）。配色：A0-B2 用单一色相 5 级顺序色阶，
   **C 段单独用中性灰/警示色 + 图标 + 文字**（它不是「更弱的 A」）。

---

## 7. 验收 fixture 清单

工程师写完逐条跑，全绿才算做对。**F19 和 F10 要最先写** —— 正则一错，其余分段断言全部连带失真。

| # | 断言 | 期望值（当前语料） |
|---|---|---|
| F1 | 全量富化 dropped rows | 0 |
| F2 | 全量富化墙钟 / 花费 | < 300 s / < $0.05 |
| F3 | 初始缓存条目数 | 680 |
| F4 | 60 家真实雇主 fixture 落 Lane C 的数量（断言**缓存值**，不调模型） | **0** |
| F5 | **背景流量压测**：8/20 之前 6 天各注入 N 条来自**独立新公司**的行（不改动任何真实公司的 `n_7d`），S5 命中公司数 | N=0/300/700/1100/1500/3000/6000 时**恒定 8**。<br>旧的「复制同一天」gate **作废** —— 它在构造上看不见相对项失效 |
| F6 | **空档案表**下 Lane C 行数，以及 Deloitte/Amazon/Booz Allen 是否在 C | **0 行 / 全部不在** |
| F7 | **过期档案表**（只含 8/19 见过的公司）下 Lane C 里的真实雇主数 | 0（Capgemini/Infosys/TCS 是正确的 outsourcing，不计入） |
| F8 | 档案表缺失该公司时 `profile()` 不抛异常且 `stage==0` | 通过 |
| F9 | 富化超时后 dashboard 仍生成，且顶部显示「N 家未分层」 | 通过 |
| F10 | 段① cap2 行数 | **稳态日 [20, 45]**（8/20 实测 28）；**收割日 [10, 45]**（8/19 实测 13） |
| F11 | 默认可见行数（①+④） | **稳态日 [30, 55]**（8/20 实测 38）；**收割日 [30, 95]**（8/19 实测 **83** —— ④ 段 70 行是 `ats_direct` 首日全量收割的一次性效应，不是回归。两类日子必须分开断言） |
| F12 | **不变式**：各段 raw 相加 == 当日去重后行数 | 恒等成立。**实现成不变式，不要写死数字** —— 语料每天在涨，规格初稿写的 `931 == 931` 两小时内就过期了（1391→1464 行，8/20 去重后 931→1006） |
| ~~F13~~ | ~~段① 前 30 行里明确应届岗的比例~~ | **删除**。段① 的定义就是 `is_entry()`，比例必然 100%，这条恒真、等于什么都没测。改为人工签核：抽查段① 20 行，确认读起来确实是应届岗 |
| **F18** | 一条 `why=="LLM_NO_ROW"` / `stage==0` 的档案，在 `n_7d=40` 时是否进 Lane C | **不得进**。守阻断-2 的第三扇门 —— F8 只盖「档案表里根本没有这家」，盖不到「有这家、但内容是漏返兜底」 |
| **F19** | `is_entry()` 表驱动逐条断言 | **True**：`Software Engineer, New Grad` / `Entry Level Software Engineer` / `Graduate Field Service Engineer` / `AI Software Engineering Intern` / `Associate Data Scientist` / `Software Engineer I` / `2027 Analyst Program`<br>**False**：`Senior Software Engineer` / `Staff Engineer` / `Engineering Manager` / `Software Engineer II` / `Principal Architect` / `International Sales Engineer`<br>比 F10 值钱：F10 红了只给出「9 ≠ 28」这个谜，F19 直接指出哪一条分支炸了 |
| F14 | KAYAK 的 2 条 ats_direct 岗位所在段；Jobgether 的 newgrad 行 / ats_direct 行 | A 段 / C 段 / 非 C 段 |
| F15 | `LLMCostTracker` 对 `gpt-4o-mini` 返回非 None 成本 | 通过 |
| F16 | `daily_report.py` 失败时 `dashboard.py` 仍执行 | 通过 |
| F17 | `daily_report.py --date 2026-08-19 --no-prune` 与归档 md | **逐字节相同** |

另需一次**人工签核**（不是自动断言）：8/19 与 8/20 的 Lane C **全量成员**逐家过一遍。
当前基线 = 8/19 九家、8/20 八十二家，**其中 1 家存疑：`Yara AI`**（8 条，招聘爆发期的
早期 AI 创业公司被量判据误伤；round1 §5.3 的 override 示例里我自己就写过它）。
round2 §3.4「Lane C 零真实雇主」的措辞**作废**，改为「**1 家存疑，已放进 override 示例**」。

---

## 8. 已知缺口（写进 dashboard 脚注，不是 bug）

1. **2023 年后成立/分拆的公司永远拿不到 tier**（Anysphere/Cursor、Sierra AI、Harvey、
   Figure、Decagon、Solventum…），落 ⑤ 段折叠。唯一兜底是 `company_overrides.json`。
2. **`prom` 是一次 LLM 采样、永久缓存**；约 4.4% 的公司其段内位置由那次调用决定。
   override 支持覆盖 `prom`（代码已支持，文档补上）。
3. **中介占比是下界，而且日常路径的下界更低**：A 手工找出的长尾中介仍未被识别。
   gpt-4o 版档案实测 23.0%（真实下界 27.7%）；**日常增量改用 mini b20 之后召回进一步下降**
   （A 的 50 家样本 16/50 → 5/50，Lane C 82 家 → 67 家）。
   Panel ②′ 必须标注「这是下界」，并靠 `--deep` 月度补跑把它拉回来。
4. **只追踪新增侧**：`date_recorded` 是首次收录时间，岗位下架不反映。
5. **两个「今天」口径不同**：Panel ① 用水位线区间，Panel ②′ 用自然日。两处都要标注，
   否则用户会以为数字对不上是 bug。
6. **两套「已读」记忆的分工**：水位线（`logs/last_report.json`，文件状态，唯一权威，
   决定「这个文件里有什么」，可复现）；`a:visited`（浏览器状态，best-effort，
   只决定「看起来点过没有」，清缓存/换浏览器即失效，丢了最多重看一眼）。
   实施时**先在用户自己的浏览器里用 `file://` 验证 `:visited` 是否生效**
   （Chrome 正在做 visited-link 分区），2 分钟的事；哑了不致命，但要知道。

---

## 9. 工程师必读的坑（我和两位评估者都真实踩过）

| 坑 | 现象 | 规避 |
|---|---|---|
| **`queue.py` 遮蔽 stdlib** | 脚本目录里有 `queue.py` → `openai` → `httpcore` → `trio` 导入链炸在 `AttributeError: module 'queue' has no attribute 'SimpleQueue'` | 任何新文件都不要叫 `queue.py`；A 和我各踩一次 |
| **`json_object` 400** | prompt 里没有字面的 "JSON" 一词 → `400 'messages' must contain the word 'json'` | prompt 里保留字面 "JSON" |
| **重试循环吞异常** | 上面那个 400 被 `except Exception` 吃掉，跑完 117 秒才发现 3 遍全空 | 重试耗尽必须打印异常；整批为空要让进程非零退出 |
| **OneDrive 原子写** | profiles.json 在同步树里，半截写坏会让**之后每天**的 dashboard 都失败 | 写临时文件 + `os.replace`；读取解析失败降级为空表（配合 stage 门控，空表不会造成误判） |
| **`PYTHONIOENCODING`** | 中文列值输出 `UnicodeEncodeError` | 跑任何脚本前 `export PYTHONIOENCODING=utf-8` |
| **LLM 少返回行 / 省略 `name`** | 40 家输入只回 32 个对象且无 `name` → 按位置对齐**整体错位**，`Yara AI` 被贴上 "Big-4 consulting firm" | 强制 `response_format={"type":"json_object"}` + 要求回显 `name` + **按 name 回填，绝不按位置** |
| **批次组成/尺寸效应** | 同一模型同一 prompt，`BATCH=50` 回收 1/150，`BATCH=20` 回收 13-14/150 | stage-2 用 `BATCH=20`；**删掉 round2 §5.3「批次必须全部由残差组成」这条规则，方向是反的** |

---

## 10. 复现

```bash
export PYTHONIOENCODING=utf-8
cd D:/OneDrive/work/school/project/Job
py=D:/Apps/Miniconda/envs/job-classifier/python.exe

$py dashboard_loop/enrich_v4.py 1                       # stage 1
$py dashboard_loop/stage2.py gpt-4o-mini                # stage 2（把 BATCH 常量改成 20）
```

产物：`dashboard_loop/company_profiles.round2.json`（P0-2 的初始缓存，gpt-4o 版）、
`stage2_gpt-4o.json`、`stage2_gpt-4o-mini.json`（本轮新增，batch 20）、
`passes_v4.json`、`r2.py`（参考实现，落地时按 §4 修两处并删死代码）。

本轮 LLM 花费 $0.0138。累计三轮：round1 $0.024 + round2 $0.324 + round3 $0.014 ≈ **$0.36**。

---

## 11. round3 补丁记录

本节记录 round3 初稿发布后、依据 `round3_eval_A.md` / `round3_eval_B.md` 做的原地修改。
**只改错，未改变任何设计决策。**

| # | 改动位置 | 改了什么 | 为什么 |
|---|---|---|---|
| 1 | §3.1 正则 | `REL_INC`（整体大小写敏感）拆成 `REL_BODY`（`re.I`）+ `REL_SUF`（`后缀标级项`，保持敏感）；`REL_EXC` 的行内 `(?i)` 改成 `re.I` flag；删掉「REL_INC 大小写敏感」那句，换成正确说明 | **必修**。两位评估者独立撞到：按初稿字面实现，`New Grad`/`Entry Level`/`Associate`/`Graduate`/`Intern` 五个分支全部哑火，段① 28→**9**、默认可见 38→**20**，直接违反本文自己的 F10/F11。现写法能精确复现 §3 表六个分段数字 |
| 2 | §6 P0-1 行 | 明确要求漏返兜底字典带 `"stage": 0` | **必修**。`enrich_v4.run_pass` 的兜底字典不带 `stage`，而 `build_profiles` 给全部 stage-1 条目统一盖 `stage=1` → 「API 漏返这家」被编码成「LLM 说不认识」= S5 触发态 = 真实雇主进中介面板。这是阻断-2 的第三扇门，round2 §7.5 记录过漏返真实发生过，却一直没有 fixture 守它 |
| 3 | §7 新增 **F18** | 漏返兜底档案在 `n_7d=40` 时不得进 Lane C | 守上面第 2 条。F8 只覆盖「档案表里没有这家」，覆盖不到「有这家但内容是兜底」 |
| 4 | §7 新增 **F19** | `is_entry()` 表驱动断言，正反各 6-7 条 | 守第 1 条。正则是本轮唯一的分段主判据却零测试覆盖；F10 红了只给一个数字谜，F19 直接定位到分支 |
| 5 | §7 F12 | `931 == 931` 改成不变式，删掉写死的数字 | 语料每天在涨（1391→1464 行，8/20 去重后 931→1006），点值型期望上线即过期 |
| 6 | §7 F13 | 删除，降级为人工签核项 | 恒真。段① 的定义就是 `is_entry()`，「段① 里应届岗占比」必然 100%，测了等于没测 |
| 7 | §7 F10 / F11 | 区间按「稳态日 / `ats_direct` 收割日」分开给 | 8/19 默认可见 83 行（④ 段 70 行是 ATS 首日全量收割），会撑爆原来的 [30,55] 上界，属误报 |
| 8 | §5 成本表 + §8 已知缺口 3 | 写清 mini b20 的代价：中介召回 16/50 → 5/50，Lane C 82→67 家；`--deep` 改成「建议每月手动跑一次」 | 「回收量 68%」只比了 `tier` 没比 `kind`，坐标轴是窄的。省 12.4 倍不是免费的，必须在成本表里对账 |
| 9 | §6 P0-9 | 17 条 fixture → 18 条（F1-F12、F14-F19），行数 150→170 | 随 F13 删除、F18/F19 新增 |

**未改动的部分**：§1 的 7 条处置、§2 的 stage-2 裁决、§3 的分段表与实测行数、§4 的决议顺序伪代码、
§9 的坑表、§10 的复现方式。A 已确认阻断-1 主路径修死（背景压测 0→6000 行/天恒定 8 家）、
F6/F7 复现（空表 Lane C = 0 行）、mini b20 未使段① 退化（仍为 28）。
