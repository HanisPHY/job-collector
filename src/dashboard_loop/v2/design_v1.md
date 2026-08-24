# Dashboard v2 设计 v1（pm-design）

> 对应需求：`docs/req/req2-dashboard-v2.md`（全文读过，497 行）
> 框架约束：`docs/multiagent_design_build_loop.md` §0
> 共享状态：`dashboard_loop/v2/state.json`
> 探查脚本：`dashboard_loop/v2/_pm_*.py`（10 个，可复现，见 §9）
>
> **本文所有数字都带测量时间与配置。语料在写这份文档的 18 分钟里从 2491 涨到 2581 行
> （02:14 → 02:32），所以下游任何断言都不许写点值。**

---

## 0. 我理解的问题（复述）

用户要一个**挑岗位的工作台**：看过去 N 天（N ∈ {1,3,7,14,30}）的分段结果，
一条条看过去、挑出来投。四条需求：趋势图天数可调（R1）、分段支持 N 天窗口（R2，核心）、
点堆叠条跳到对应分段（R3）、把 583 行 Python 拼 HTML 拆成真 `.html/.css/.js`（R4）。

**这一轮不重做判定层。** `company_lane.py` 一行不动。段的判据、tier/prom/中介判定、
应届正则、7 天滑动判定窗口、I1-I9 九条不变量、六段判据、N 的 5 个档位、
「判定留 Python / 取景交 JS」这条分工线、`daily_report.py` 不改 —— 全部是**约束**，不是待议项。
已投 / 已忽略**不做**（用户 2026-08-21 否掉）。

对照 §0 的失败源，我这一轮特别防的四件事：

| §0 坑 | 本设计里对应的动作 |
|---|---|
| A 缺范围边界 | §2「明确不做」+ 每条 orchestrator 建议给同意/反对，不静默重设计判定层 |
| B 缺证据标准 | §3 每条反对都先跑脚本，脚本名和输出都贴出来 |
| C 在便利环境里验证 | **§1 的 [T2] 是这份文档最重要的一张表**：所有人一直在「一天结束时」量首屏，而页面是 **08:00** 生成的。08:00 量出来是 21 / 26 / 7 行，从来没进过 30-50。另外 file:// 能力表我真的在浏览器里跑了（§3 S7） |
| D 把约束写成目标 | §4.10 一张表，每个「不能超过 X」写清是哪一行代码在保证它，以及对应 fixture |

---

## 1. 实测快照

**配置（所有 [T*] 表共用）**：`_pm_10_snapshot.py`，2026-08-21 02:32:18 本地时间，
Python 3.10.19，解释器 `D:\Apps\Miniconda\envs\job-classifier\python.exe`，
Windows-10-10.0.26200，Git Bash，`PYTHONIOENCODING=utf-8`。
语料 2581 行 / 3 天 / 1312 家公司；`company_profiles.json` 1266 条；overrides 24 条。

```
2026-08-19 raw   287  按日去重   230
2026-08-20 raw  2072  按日去重  1674
2026-08-21 raw   222  按日去重   169     (当天还在涨)
```

基线：`python tests/test_lane.py` → `Ran 36 tests ... OK (skipped=2)`（02:28 实测）。

### [T1] 5 档 N 的窗口视图（anchor = 2026-08-21）

| N | 窗口原始行 | 窗口去重后 | 去重丢弃 | ① | ② | ③ | ④ | ⑤ | ⑥ | cap2 合计 | 首屏展开 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 222 | 169 | 53 | 5 | 4 | 48 | 3 | 79 | 30 | 144 | 11 |
| 3 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 |
| 7 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 |
| 14 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 |
| 30 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 |

N ≥ 3 全同，因为语料只有 3 天。脚本在每个 N 上断言了三件事并全部通过：
`Σ raw == 窗口去重行数`（**I1 窗口版**）、`窗口去重行数 == 窗口内 distinct (公司,归一化标题) 数`、
`min(FLOOR, supply) <= 首屏 <= 47`。

**不同 N 下同公司同标题重复 = 0**（`_pm_01_window.py`，5 档各查一次，全 0）。

### [T2] ★ 首屏行数，在**页面真正生成的那个小时（08:00）**测

| anchor | N | v1 现行规则 `min(cap2,OPEN_CAP)` | 本设计的 open_plan | 可供展开的总量 |
|---|---|---|---|---|
| 08-19 | 1 / 3 / 7 / 14 / 30 | 21 | **30** | 101 |
| 08-20 | 1 | 26 | **30** | 59 |
| 08-20 | 3 / 7 / 14 / 30 | 46 | 46 | 175 |
| 08-21 | 1 | 7 | **11** | 11 |
| 08-21 | 3 / 7 / 14 / 30 | 47 | 47 | 290 |

到货曲线（`_pm_09_default_n.py`）：8/20 全天 2072 行，其中 **08:00 之前只到 790 行（38%）**，
12:00 前 1202，18:00 前 1760。也就是说过去所有「首屏 47 行」的结论都是拿**一天结束时**的语料算的，
而 `run_daily_report.bat` 在 **07:30 富化 → 08:00 生成**。**在真实生成时刻，现行 OPEN_CAP 给出 21/26/7 行，
一次都没进过 30-50 这个用户认过的量级。** 这是 §0.3-C 那类错误的第三次重演。

### [T3] 载荷大小（编码 E4，见 §4.2）

```
data-2026-08-19.js    287 行   28,164 B   98.1 B/行
data-2026-08-20.js   2072 行  156,197 B   75.4 B/行
data-2026-08-21.js    222 行   16,623 B   74.9 B/行
index（co / o / days）        42,430 B   （1312 家公司）
今天全部                     243,414 B  = 0.23 MB
按 req2 §5.5 的 2000 行/天外推：155,741 B/天，30 天 = 4.46 MB
```

**req2 §5.2 写的「每行 152 字节」是错的。** 按 §5.2 逐字段实测（`_pm_03_payload.py`）：
**261.2 B/行**，30 天 = **14.95 MB**，不是 9 MB。逐级优化：

| 编码 | B/行 | 相对 E0 |
|---|---|---|
| E0 = req2 §5.2 逐字（含 `k`、完整 `r`、`sig`） | 261.2 | 100% |
| E1 = 去掉 `k`，换成 1 bit 的 `x` | 210.8 | 80.7% |
| E2 = E1 + `r` 存 HHMM 整数 + `sig` 移到公司表 | 167.3 | 64.0% |
| E3 = E2 改列式数组 | 129.3 | 49.5% |
| **E4 = E3 去掉 unique_id + 日期/段/链接前缀内插** | **80.0** | **30.6%** |

`unique_id` 一列单独占 13.5 B/行，而 **92.4% 的行里它就是 `job_link` 的最后一段路径**
（`_pm_03_payload.py` E 节，2324/2514）—— 纯冗余。

### [T4] 第 ⑦ 段（水位线区间）

水位线 `logs/last_report.json`：`cutoff=2026-08-21 00:24`，`prev_cutoff=2026-08-20 12:24`。
区间内去重后 739 行，落在 ①②④ 的 **86 行**。这 86 行有多少在 N 天窗口**外面**：

| N | 在窗口外（⑦ 段必须自己显示） | 在窗口内（筛选开关就够） |
|---|---|---|
| 1 | **83** | 3 |
| 3 / 7 / 14 / 30 | **0** | 86 |

### [T5] 浏览器实测（file://，无 localhost）

`_pm_05_fileproto.py` / `_pm_07_perf.py` / `_pm_08_chunks.py`，
**Chrome 151.0.7922.172，`--headless=new --dump-dom`，页面在 `file:///C:/Users/.../probe.html`**：

| req2 §6 的断言 | 实测结果 |
|---|---|
| 同目录 `<link rel=stylesheet>` | ✅ `getComputedStyle` 拿到 `rgb(1, 2, 3)` |
| 同目录经典 `<script src>` | ✅ |
| 动态注入 `<script src>` | ✅ `onload` 触发且数据可见 |
| 并发注入多块 | ✅ 3 块全部 onload，累加值正确；30 块也全部成功（见下） |
| `<script type="module">` | ✅ 断言成立：**onerror，被拦** |
| `fetch()` | ✅ 断言成立：`REJECT: TypeError` |
| `XMLHttpRequest` | ✅ 断言成立：`THROW: NetworkError` |
| `localStorage` | **能用**（写入后读回 `"v"`）；`location.origin` 报 `"file://"` 而不是 req2 写的 `null`。仍然按 req2 的要求 try/catch 且拿不到值要能正常渲染 |

性能（Chrome 同上，合成 30 天 × 2000 行 = 60000 行，5.05 MB，跨天重复率按实测的 6.1% 造）：

```
整个 5 MB 文件 parse + eval           48.0 ms
N=30 纯数据一趟（筛选+去重+分组+cap2）  3.2 ms（冷）/ 3.5 ms（热），去重后 59,954 行
段① 按 rank 排序（3252 行）            1.1 ms
```

**结论：数据层不是瓶颈，DOM 才是。** req2 §5.5「30 天一次性建几万个 `<tr>` 会卡死」成立，
「所以必须分块才能跑得动」不成立 —— 分块的理由是别的（见 §3 S3）。

分块方案对比（同一次 Chrome 运行，`_pm_08_chunks.py`）：

| 方案 | 文件数 | 注入耗时 | 每天早上要重写的字节 |
|---|---|---|---|
| 按自然日一天一块（N=1） | 1 | 12.9 ms | — |
| 按自然日（N=7） | 7 | 5.9 ms | — |
| **按自然日（N=30）** | **30** | **17.9 ms** | 0.15 MB（若冻结）/ 4.46 MB（若每天重算判定） |
| req2 §5.5 的 5 个偏移块（N=30） | 5 | 20.2 ms | **4.48 MB，且五块每天全变** |
| 一个 30 天大文件 | 1 | 37.3 ms | 4.50 MB |

30 个文件比 5 个块**更快**（并行加载），错误数 0。

---

## 2. 目标与明确不做

**目标**：`dashboard.py` 只算数据，输出真 `.html/.css/.js` + 按天的数据块；
浏览器里切 N 不重载；点堆叠条跳段；首屏行数由机制锁住；I1 在窗口上继续有 fixture 守着。

**明确不做**：已投 / 已忽略（用户 2026-08-21 否掉）；任意 N 输入；重设计判定层；
改 `daily_report.py`；改 `company_lane.py`；build step / npm / CDN / ES module / fetch。

---

## 3. 对 orchestrator 七条建议的逐条回应（同意也给实测）

### S1 去重键 `k` 由 Python 预生成；保留「先出现的天」还是「最新天」

**部分反对：不要发 `k`，发一个布尔位。同时明确选「最新天」，理由不是审美，是它可以被冻结。**

实测（`_pm_03_payload.py` A 节，02:19）：5 档窗口都是「以今天结尾的后缀」，因此互相嵌套
（W1 ⊂ W3 ⊂ W7 ⊂ W14 ⊂ W30）。在这个结构下：

```
keep-NEWEST : 某组在窗口内的幸存者与「该组全局最新那条」不同的 (组,N) 情形 = 0 次
keep-OLDEST : 同上 = 20 次
```

因为窗口是按日期的后缀，一个组只要有成员落在窗口里，最新那条**必定**也在窗口里。
所以 **keep-NEWEST 的幸存者与 N 无关**，可以在 Python 侧固化成每行一个 `x`（1 = 被更新的同键行取代）；
**keep-OLDEST 做不到**，它的幸存者随 N 变，JS 必须自己跑一遍去重。

这条比 §5.3 的原方案更强：JS 连去重键的字符串都看不到，只是 `if (x[i]) continue`，
**「两边归一化规则漂移」这个 R2 最容易犯的错在结构上被消灭了**，而不是靠约定。
脚本对 5 档 N 都断言了 `flag 去重结果 == 真实去重结果` 且无重复键残留，全部通过。

代价实测为零：keep-FIRST 与 keep-LAST 下**段① 的日期分布完全一致**（`_pm_01_window.py`，
5 档全同：`08-19:22, 08-20:70, 08-21:1`），**同一去重组里出现两个不同段的组数 = 0**
（tnorm 会把 `Software Engineer I` 和 `... i` 折成一个键，而 `\b(?:I|1)$` 是大小写敏感的，
理论上能造出跨段的组；实测语料里 0 个）。所以换成 keep-NEWEST 不改变任何可见结果。

**⚠ 一条必须写进规格的陷阱**：`x` 必须在「`_day <= 生成日`」的行集合上算，不能在整个语料上算。
实测（02:30）：用全局 `x` 去渲染 8/19 的窗口会**静默丢 10 行**，8/20 丢 28 行 —— 直接破 I1。
按「`_day <= anchor`」算，3 个 anchor × 5 档 N 全部 `flag == real`。

**顺带**：跨天重复的量级很小但真实 —— 1971 个键里 29 个跨天（1.47%），涉及 151 行（6.06%）；
「按天各自去重再拼」比窗口去重多出 29 行（2000 vs 1971）。req2 §4.2 决策 1 成立。

### S2 首屏 30-50 的机制：OPEN_CAP 对 ①④ 固定上限，沿用 35/12

**同意机制，反对数值够用这个判断。35/12 只是天花板，没有地板，而实测坏在地板上。**

现行规则 `visible = min(cap2①,35) + min(cap2④,12)`，**结构上必然 ≤ 47**，
对 N=30、对任何采集量都成立（cap2 关于 N 单调不减，`_pm_02_anchor.py` C 节断言过）。
所以 S2 要的「5 档 N 各算一遍证明 N=30 也在 30-50」，上界部分不需要算也成立。

**但 [T2] 显示，在 08:00 这个真正的生成时刻，三天的 N=1 首屏是 21 / 26 / 7 行，一次都没到 30。**
8/19 那天全天算也只有 25 行。把 35/12 原样搬进 v2，等于把「首屏 30-50」写成了「首屏 ≤ 47」。

**提出的机制**（纯函数，不看数据只看计数）：

```python
OPEN_ORDER   = ["1a_t3", "B1", "1a_t2"]      # ① → ④ → ②(仅补位)
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
ALWAYS_OPEN  = ("1a_t3", "B1")
FLOOR        = 30
CEIL         = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)   # 47，派生，不许第二次手写

def open_plan(cap2):
    plan, used = {}, 0
    for s in ALWAYS_OPEN:                       # 天花板
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s]); used += plan[s]
    for s in OPEN_ORDER:                        # 地板：只补到 FLOOR，不补到 CEIL
        if s in ALWAYS_OPEN or used >= FLOOR:
            continue
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s], FLOOR - used); used += plan[s]
    return plan, used
```

两条**不变量**（不是点值，永远不会过期）：

- `open_plan` 的和 `<= CEIL`。因为补位段最多补到 `FLOOR - used`，总和不可能超过 `max(CEIL, FLOOR)` = CEIL。
- `open_plan` 的和 `>= min(FLOOR, supply)`，其中 `supply = Σ cap2[s] for s in OPEN_ORDER`。
  语料确实只有 4 行可看的时候（8/21 02:14），首屏就是 4 行，这是**诚实**，不是失败。

实测结果见 [T2]「proposed」列：08:00 三天分别 30 / 30 / 11 —— 除了「今天真的只有 11 行」那次，
全部进 30-50。② 段只在 ①④ 喂不饱时才展开，8/20、8/21 的 N≥3 视图里 `plan` 是 `①=35 ④=12`，
**和今天一模一样，行为零变化**。

**另一个由 [T2] 直接推出的结论：默认 N 应该是 3，不是 1。**
08:00 时 N=1 的可供量是 11~101 行，N=3 是 175~290 行；N=3 在两个完整天上都给出 46/47 行首屏。
默认 N=3 只多加载 2 个数据块（实测 7 块并行 5.9 ms）。

### S3 五块 d0/d1_2/d3_6/d7_13/d14_29 是否仍是最优

**反对。改成一天一个块，按绝对日期命名。**

实测理由，不是风格：

1. **偏移命名每天全变。** `d3_6` 今天指 8/15-8/18，明天指 8/16-8/19。五块**每天早上全部重写**
   （4.48 MB/天，`_pm_08_chunks.py`）。按自然日命名，只有今天那块是新的。
2. **历史 `<day>.html` 在偏移方案下无法复用任何数据块** —— 每保留一天的快照就要多存 5 个私有块，
   无上界增长。按绝对日期命名，`2026-08-20.html` 直接引用大家共用的 `data-2026-08-20.js`。
3. **30 次注入并不慢**：17.9 ms，比 5 块的 20.2 ms 还快，比单文件 37.3 ms 快一倍，错误 0。
4. **过量加载两种方案一样**：N=7 时按天是 7 × 0.15 = 1.05 MB，五块方案是 d0+d1_2+d3_6 = 1.04 MB。
   偏移分块并没有省流量，它只是让文件名依赖「今天是哪天」。
5. **req2 §5.1 自己就不自洽**：文件树写 `data-<day>-d0.js`，紧接着的 HTML 片段写 `data-latest-d0.js`。
   绝对日期命名把这个歧义直接消掉。

**分块边界怎么跟「今天」对齐**：不用对齐。块名就是自然日 `data-2026-08-20.js`，
`JOB_INDEX.days` 给出从旧到新的 30 天列表（含空天），`JOB_INDEX.chunk[i]` 给出第 i 天的文件名
（空天为 `""`，不写文件也不注入）。选 N = 取 `days` 的最后 N 项。

**空块问题不存在**：语料只有 3 天时，只写 3 个文件；30 天视图注入 3 个文件加 27 个空天占位，
趋势图仍按 R1 的要求画出 27 根空柱子。

**历史 `<day>.html` 怎么处置**：保留，但从 439 KB 降到约 2 KB。
它变成一份**骨架**，只是把 `PIN_DAY` 钉在那一天，数据仍来自共用的 `data-*.js`。
现状实测：`logs/dashboard/2026-08-20.html` = 439,438 B，每天一份。
保留策略：数据块和骨架都只保留 30 天，超期一起删（`--retain` 参数，默认 30）。

**判定漂移的处置（req2 完全没提，但绕不开）**：
段 `g` 是拿**生成日**的 resolver 算的，而 `LaneResolver` 的 7 天判定窗口跟着生成日滑动。
实测（`_pm_02_anchor.py` A 节）：同一行在「生成日 resolver」和「本行自己那天的 resolver」下
段不同的比例是 **12/2491 = 0.48%**，方向全是 `B2 → C`；公司层面 13/1284 家的 lane 会变。
本设计选**统一用生成日的 resolver**（理由：`companies[]` 只有一份 tier/prom/w，
两者必须同源；页面语义是「今天怎么看过去 N 天」），因此**保留的 30 天数据块每天早上全部重算重写**
（4.46 MB/天）。冻结方案见 §7 rejected_alternatives R5 —— 它能把日写入量降到 0.25 MB，
但要引入按位置对齐的补丁文件，我认为第一版不值得。

### S4 `companies[].w` 是固定 7 天判定窗口，不随 N 变

**同意，并加三道机械保险**（S4 说「防止混淆」，但没写机制）：

1. **字段就叫 `w7`**，不叫 `w`。名字里带死数字，改 N 的人不会以为它跟着变。
2. `JOB_INDEX` 里带一个常量 `w7_days: 7`，表头文案由它拼：`「近 7 天」`。
   **数字和文案同源**，不会出现表头写 7 天而数据是别的窗口。
3. **对账**：`check[N].w7_days == 7` 对每个 N 都成立；JS 渲染表头前断言 `JOB_INDEX.w7_days === 7`，
   否则红条。fixture 侧断言 `payload["w7_days"] == CL.WINDOW_DAYS`（读常量，不写字面量）。

### S5 ⑦ 段在 N>1 时降级成筛选开关

**同意结论，但反对「按 N 切换形态」这个做法 —— 用一条不看 N 的规则，让它自己退化。**

规则：**⑦ 段永远存在，内容是「上一期水位线区间内、落在 ①②④、且不在当前 N 天窗口里的行」。**

实测 [T4]：N=1 时这条规则给出 83 行（占 86 行的 97%，正是窗口看不见的那些），
N≥3 时给出 0 行 —— 段自动变空，页面显示「上一期的行都在当前窗口内，用上面的『只看上一期未处理』开关」。
一条规则，没有模式切换，没有「N=1 时是段 / N>1 时是开关」这种要写在两处的分支。

窗口内那部分由**筛选开关**覆盖：勾上后六个段各自只保留 `prev_prev < 收录时刻 <= prev_cutoff` 的行。
开关是纯过滤（比两个时间戳），不产生判断。

**⚠ 一个必须写进加载策略的后果**：N=1 时 ⑦ 段的内容来自**窗口外**的天（实测跨 2 天）。
所以加载器必须永远把 `JOB_INDEX.wm_days`（水位线区间覆盖到的那些天的下标）
并到要加载的天集合里，否则 ⑦ 段会安静地少行。这是 req2 里没有的一条。

### S6 双实现 vs 只在 JS 实现

**同意「Python 留一份纯数据逻辑」，但反对把它描述成「双实现」。**

设计成**一份参考实现 + 三层对账**，Python 是唯一定义处：

| 层 | 谁断言 | 抓什么 |
|---|---|---|
| L1 | fixture 断言 `view.window_view(payload, N)` | I1 窗口版、cap2、open_plan 上下界。**注意它吃的是 payload，不是 CSV** —— 序列化丢行也会被抓到 |
| L2 | 运行时 JS 用自己算的计数对 `JOB_INDEX.check[N]` | JS 的过滤/去重/分组跟 Python 不一致 → 页面顶部红条 |
| L3 | fixture 用无头 Chrome 跑真页面，读 `#selfcheck` | L2 本身没被接上、或某个块没加载 |

「只在 JS 实现、Python 只给 check」的盲区是：**check 的数字没有任何 fixture 能断言**，
`check` 自己错了就永远发现不了 —— I1 的守卫直接归零。
漂移风险的另一头（两份实现慢慢分家）被 L2 每次打开页面都抓一次，
而且 L1 和 check 是**同一个函数的返回值**，不存在「Python 的两份实现」。

**再加一条把首屏钉死的机制**：`check[N].head` 直接给出首屏那 ≤47 行的
`[天下标, 行下标]` 有序列表（≤ 47 × 5 档 ≈ 1.9 KB）。
JS 渲染完首屏后逐项比对，不一致就红条。**用户真正会读的那几十行是 Python 逐行指定的，
JS 在首屏上只剩下拼 DOM。** 折叠段仍然只靠计数对账。

### S7 没有测试框架的情况下怎么保护 JS 不变量

**同意要做，并且反对「只能写个极小断言」这个前提 —— 无头浏览器在这台机器上是现成的，我跑通了。**

三条，都不引入 npm：

1. **`--selfcheck` 模式**（`latest.html#selfcheck`）：JS 依次对 5 档 N 跑一遍计数，
   跟 `check` 对账，把结果 JSON 写进 `<pre id="selfcheck">`。既是调试工具也是测试钩子。
2. **fixture F24（新增）**：找到 Chrome/Edge 可执行文件就跑
   `--headless=new --dump-dom file:///.../latest.html#selfcheck`，正则取出 `<pre id="selfcheck">`，
   断言 5 档全 `ok`。找不到浏览器就 `skipTest`（跟现有 F1/F2 一个模式）。
   **实测可行**：`_pm_05/07/08` 三个脚本都是用这个办法拿到结果的，Chrome 151.0.7922.172 正常。
   **⚠ Edge（本机 `.html` 的默认打开程序，实测注册表 `MSEdgeHTM`）的无头模式在这台机器上
   `--dump-dom` 和 `--screenshot` 都产出 0 字节**，三种 headless 参数都试过。
   所以 F24 只能覆盖 Chrome；**「双击 latest.html」这条验收必须由人在 Edge 里真做一次**，
   不能只看 F24 绿。
3. **fixture F23（新增，静态）**：把判定层词汇列成黑名单，在去掉注释后的 `dashboard.js` 里 grep，
   出现即失败。这是把 §5.3 那条分工线从「约定」变成「机制」的唯一办法。

---

## 4. 设计

### 4.1 文件布局

```
web/                                  ← 新目录，源文件，进版本库
    shell.html                        真 HTML 模板，含 <!--SLOT:*--> 占位
    dashboard.css                     真 CSS（从 dashboard.py 的 CSS 常量逐字搬过来）
    dashboard.js                      真 JS（经典脚本，非模块）
dashboard.py                          只算数据 + 填模板 + 原子写，不再拼 CSS/表格字符串
view.py                               新增：纯数据参考实现（无 HTML、无 I/O）
logs/dashboard/
    latest.html                       ← 双击这个
    2026-08-21.html                   按日骨架（约 2 KB，钉住 PIN_DAY）
    dashboard.css                     每次运行从 web/ 复制（原子写）
    dashboard.js                      同上
    data-index-2026-08-21.js          每次运行重写
    data-2026-08-19.js                按自然日，绝对命名
    data-2026-08-20.js
    data-2026-08-21.js
```

`latest.html` 的关键几行（默认 N=3，所以静态引 3 天 + 水位线覆盖到的天）：

```html
<link rel="stylesheet" href="dashboard.css">
<script src="data-index-2026-08-21.js"></script>
<script src="data-2026-08-19.js"></script>
<script src="data-2026-08-20.js"></script>
<script src="data-2026-08-21.js"></script>
<script src="dashboard.js"></script>          <!-- 经典脚本，绝不能 type="module" -->
```

CSS 从 Python 字符串常量变成真文件，是 R4 的实质内容；`web/` 里的两个文件由 `dashboard.py`
**原样复制**到输出目录（OneDrive 下用 `tmp + os.replace`），不做任何拼接，也不做 build。

**骨架里放什么（重要）**：Python 把自己算出来的**事实**直接渲染成静态 HTML —— hero 四块、
「N 家未分层」健康横幅、趋势 SVG、堆叠条 SVG + 图例（含 `<a href="#seg-...">`）、
六个 `<details id="seg-...">` 的**空壳与 summary 计数**、⑦ 段空壳、面板 ②′ 和 ③、footer。
JS 只负责往 `<details>` 的 body 里塞表格，以及在切 N 时更新上述数字。

这样做的三个好处：R3 的第 1-3 步真的零 JS（锚点和 SVG 链接是静态 HTML）；
JS 整个挂掉时页面仍然显示所有 Python 算出来的数字（I9 的精神延伸到前端）；
`F9` 现有断言（`page` 以 `<!doctype html>` 开头、含 `家未分层`、含 `<details`）**一个字都不用改**。

### 4.2 数据结构

**`data-index-<day>.js`**（每次运行重写，实测 42 KB / 1312 家公司）：

```js
window.JOB_INDEX = {
  v: 2,                              // schema 版本，JS 不匹配就红条并停止渲染
  day: "2026-08-21",                 // 生成日 = 所有窗口的右端点
  generated: "2026-08-21 08:00",
  cutoff: "2026-08-21 08:00",        // 水位线，驱动「● 新」
  prev_cutoff: "2026-08-20 08:00",
  prev_prev:  "2026-08-19 08:00",
  w7_days: 7,                        // 判定窗口，见 S4；表头文案由它拼
  n_choices: [1,3,7,14,30],
  n_default: 3,
  days:  ["2026-07-23", ... , "2026-08-21"],   // 30 项，旧→新，含空天
  chunk: ["", ... , "data-2026-08-21.js"],     // 空天为 ""，不写文件也不注入
  nrows: [0, ... , 2072, 222],                 // 每天期望的原始行数，用于「块没加载」检测
  wm_days: [28, 29],                           // 水位线区间覆盖到的天下标，永远要加载
  co: [ ["Palantir Technologies", 3, 85, 18, 1, 12, 12], ... ],
  //     0 显示名                  1t 2p 3w7 4b 5sig 6sig_own
  o:    [ 417, ... ],              // 每家公司的排序名次 = CL.sort_key 的名次（见 4.6）
  sigs: [ "", "LLM:job_board", "unknown+vol 7/7d", ... ],
  lpre: ["https://www.linkedin.com", "https://jobs.ashbyhq.com", ...],
  check:  { "1": {...}, "3": {...}, ... },     // 见 4.3
  panels: { "1": {...}, "3": {...}, ... },     // 面板 ②′/③ 的表，Python 算好
  health: { unenriched: 7, examples: ["...", ...] }
}
```

`co` 用**定长数组而不是对象**，一是省字节，二是**让 `tier` / `prom` / `stage` 这些词根本不出现在 JS 里**
（F23 靠这个）。`sig` 每家两个下标：`5` 是普通信号，`6` 是「自有 board 那条行」的信号
（实测 1312 家里只有 1 家两者不同）；JS 取 `sigs[co[s === 0 ? 5 : 6]]`，是查表不是判断。

**`data-<day>.js`**（一天一个，实测 75-98 B/行）：

```js
(window.JOB_DAY = window.JOB_DAY || {})["2026-08-20"] = {
  d: 28,                       // days[] 下标
  n: 2072,                     // 原始行数，必须等于 JOB_INDEX.nrows[28]
  c:  [42, 17, ...],           // 公司下标
  g:  [0, 3, 5, ...],          // 段下标，顺序 = CL.SEGMENT_ORDER
  t:  ["Software Engineer, New Grad", ...],
  lp: [0, -1, ...],            // 链接前缀下标，-1 = l 里是完整 URL
  l:  ["/jobs/view/4456201304", ...],
  s:  [0, 1, 2, ...],          // 0 newgrad / 1 ats_direct / 2 ddg
  r:  [1224, 806, ...],        // 收录时刻的 HH*100+MM
  x:  [0, 1, 0, ...]           // 1 = 被更新的同键行取代（见 S1）
};
```

九个数组等长，长度 = `n`；不等长 → 红条。**没有 `k`，没有 `unique_id`，没有完整时间戳。**
`unique_id` 92.4% 情况下就是 `job_link` 的尾段，纯冗余（[T3]）。

**编码规则**：`json.dumps(obj, ensure_ascii=False, separators=(",", ":"))`，UTF-8 无 BOM，
文件以 `;` 结尾。不做任何压缩（`file://` 下浏览器不会解 gzip）。

### 4.3 `check` —— I1 在窗口上怎么继续守住

```js
check["7"] = {
  dedup: 2035,                     // 窗口去重后行数
  raw:   [97,151,634,90,692,371],  // 各段，顺序 = SEGMENT_ORDER
  cap2:  [75,136,502,74,641,198],
  plan:  [35,0,0,12,0,0],          // open_plan 的分配
  open:  47,                       // Σ plan
  per_day: [0,...,230,1674,169],   // 按日去重后的行数（趋势柱）
  sum_per_day: 2073,               // Σ per_day，跟 dedup 差的就是跨天合并掉的
  w7_days: 7,
  head: [[28,17],[28,203],[29,4], ...]   // 首屏 ≤47 行的 [天下标, 行下标]，有序
}
```

JS 渲染完做四件对账，任一不过就在页面顶部显示红条（而不是安静少几行）：

1. `Σ raw == dedup` —— **I1 窗口版**
2. 自己数出来的 `raw` / `cap2` 逐段等于 `check[N]`
3. 首屏渲染出来的 `[天下标,行下标]` 序列逐项等于 `check[N].head`
4. 每个应加载的天，`JOB_DAY[day].n == JOB_INDEX.nrows[i]`（块没加载 / 加载了旧块会在这里现形）

页面上继续显示 `raw 97 · cap2 75`（现在就是这么显示的），
再加一行 `按日去重相加 2073 · 窗口合并 38 条`（实测跨天重复 1.85%，
不写这一行的话两个数字并排出现会像 bug）。

### 4.4 分块与加载

- 首屏：`latest.html` 里静态引 index + `days` 最后 `n_default` 天 + `wm_days`，去重后 3-4 个文件，
  实测 0.23 MB / 约 13 ms。
- 切 N：算出需要的天集合 = `days` 最后 N 天 ∪ `wm_days`，减去已加载的，
  对每个还没加载且 `chunk[i] !== ""` 的天动态注入 `<script src>`；全部 `onload` 后重渲染。
  加载期间 N 选择器置 `aria-busy="true"` 并显示「载入 N 天…」。
- **`onerror` 不许静默**：某块加载失败 → 该天标记为「未加载」，红条列出天名，
  并且 §4.3 的第 4 条对账必然失败。空天（`chunk[i] === ""`）根本不注入，不算失败。
- 保留 30 天：`data-*.js` 与 `<day>.html` 超过 `--retain`(默认 30) 天一起删。
- 每天早上重写：index + 保留窗口内**全部**天块（实测外推 4.46 MB/天，理由见 S3 末段）。
- 所有写盘走 `tmp + os.replace`（OneDrive，req2 §7.3）。

### 4.5 首屏机制

见 S2。`CAP = 2` 的含义按 req2 §4.2 决策 2：**整个窗口内每家公司每段最多先看 2 条**，
不是每天 2 条（实测 8/20 单日 Deloitte 同名岗位 13 条，按天算 7 天视图会变 91 条）。
`OPEN_ORDER / SEG_OPEN_CAP / FLOOR` 三个常量定义在 `view.py`，
`CEIL` **派生**自 `SEG_OPEN_CAP`，任何地方都不许再手写 47。

### 4.6 排序键

**JS 不实现排序键，只按 Python 给的名次 `o` 排。**

`CL.sort_key(c)` 是**与段无关的公司全序**，所以一个全局名次数组对所有段、所有 N 都成立。
段内行序 = 先按 `o[c]` 升序，同公司内按 `(r 降序, 标题)`（沿用 `group_segment` 现在的规则）。

**这条不只是省字节，是修一个已经埋好的雷**：
`company_lane.sort_key` 实际是 `(不在priority, -prom, -tier, -窗口内岗位数, 公司名)`，
而 **req2 §4.2 决策 4 的正文把它写成了 `(不在priority, -tier, -prom, ...)` —— tier 和 prom 是反的**。
实测（`_pm_06_sort_trend.py`）：在当前语料上**两种排序结果完全一致**
（5 档 N 下「第一个位置不同的下标」都是 `None`，top-20 集合重合 20/20），
所以照着正文实现，**所有测试都会绿，等 prom/tier 相关性变化时才慢慢歪掉**。
发一个 `o` 数组，这个雷就不存在了。

「窗口内岗位数」这个 tiebreaker 用的是 `w7`（固定 7 天），不是 N 天 —— 见 S4。
行上显示的那一列表头写「近 7 天」。

### 4.7 ⑦ 段、水位线与「● 新」

- **「● 新」**：`(days[d], r) > cutoff`，纯比较。水位线驱动，跟 N 无关（req2 §4.2 决策 5）。
- **筛选开关**「只看上一期未处理」：勾上后六段各自只留 `prev_prev < (days[d], r) <= prev_cutoff` 的行；
  段计数、cap2、open_plan 都在过滤后重算，`check` 里另存一份 `check_wm[N]` 供对账。
- **⑦ 段**：见 S5 的单一规则。空的时候显示「上一期的行都在当前窗口内 → 用上面的开关」。
- 水位线本身仍然只在真实定时运行时推进（`dashboard.py` 现有逻辑，不动）。

### 4.8 JS 渲染与交互

**渲染策略**
- 页面加载：只渲染 `open_plan` 指定的那 ≤47 行（外加各段 summary 的计数，来自 `check`，不需要遍历行）。
- 折叠段：监听 `toggle`，**首次打开时**才建表；建完标记 `dataset.rendered = "1"`。
- 切 N / 切筛选开关：所有段 body 清空并标记 dirty；当前是 `open` 的段立即重渲染，
  折叠的等下次打开。实测纯数据一趟 N=30 / 60000 行 = 3.2 ms，所以每次切 N 全量重算计数没问题。
- 大段用 `documentFragment` 一次性 append；单段超过 2000 行时分片（`requestAnimationFrame` 每帧 500 行），
  避免 30 天视图打开 ⑤ 段时长时间掉帧。

**切 N 不重载 + 保持展开与滚动**
1. 记录每个 `<details id>` 的 `open`；
2. 记录当前视口最靠上的那个 `<details id>` 及其 `getBoundingClientRect().top`；
3. 注入缺的块 → 重算 → 重渲染 → 恢复 `open`；
4. `window.scrollTo(0, el.offsetTop - savedTop)`。
   （N 变了高度必然变，绝对 `scrollY` 恢复没有意义；锚在同一个段上才是用户预期。）

**锚点跳转（R3）**
- `<details id="seg-1a_t3">` 静态存在；堆叠条每个 `<rect>` 外包 SVG 原生 `<a href="#seg-1a_t3">`，
  图例同样。这三步零 JS。
- JS 只做一件事：`hashchange` + 首屏读 `location.hash` → `el.open = true`；若该段 dirty 则先渲染，
  再 `el.setAttribute("tabindex","-1"); el.focus({preventScroll:true})`，
  最后 `el.scrollIntoView({block:"start"})`。
- CSS：`details[id]{scroll-margin-top:64px}`（顶部有 sticky 的 N 选择器）、
  `:focus-visible{outline:2px solid var(--link);outline-offset:2px}`。
- **hash 只用于锚点，不放 N**。否则点一次堆叠条就把 N 冲掉了。
  N 记在 `localStorage["dash.n"]`（实测 Chrome file:// 可用），
  读写都 try/catch，取不到或不在 `n_choices` 里就用 `n_default`。
  另外接受一次性覆盖 `#n=7`：解析后立刻把 hash 改回段锚点，不长期占用。

**N 选择器**：`<div role="radiogroup">` + 5 个 `<button role="radio" aria-checked>`，
键盘左右箭头切换；不是 `<select>`（5 个档位平铺一眼可见，且不需要展开动作）。

**`--selfcheck`**：`location.hash === "#selfcheck"` 时，对 5 档 N 依次跑计数并对账，
把 `{"1":{"ok":true,...},...}` 写进 `<pre id="selfcheck">`，不渲染表格。

### 4.9 Python 侧改动清单（函数签名级）

**`company_lane.py`：不动。**
**`daily_report.py`：不动（I8 / F17）。**

**新增 `view.py`**（纯数据，零 HTML，零 I/O，可被 fixture 直接调）：

```python
CAP = 2
OPEN_ORDER   = ["1a_t3", "B1", "1a_t2"]
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
ALWAYS_OPEN  = ("1a_t3", "B1")
FLOOR        = 30
CEIL         = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)
N_CHOICES    = (1, 3, 7, 14, 30)
N_DEFAULT    = 3
RETAIN_DAYS  = 30

def superseded_flags(rows, day) -> dict          # id(row) -> 0/1，作用域 _day <= day
def build_payload(day, rows, profiles, overrides, priority, state,
                  retain=RETAIN_DAYS) -> dict    # {"index": {...}, "days": {d: {...}}}
def window_view(payload, n, wm_only=False) -> dict
        # -> {"dedup","raw","cap2","plan","open","per_day","sum_per_day","head","w7_days"}
        # 这是 check 的唯一来源，也是 fixture 断言的对象
def open_plan(cap2) -> (dict, int)
def encode_index(index) -> str                   # "window.JOB_INDEX={...};"
def encode_day(day, cols) -> str                 # "(window.JOB_DAY=...)[...]={...};"
```

**`dashboard.py`**：删掉 `CSS` 常量、`row_html`、`table_html`、`details`、`build()` 里 39 次
`P.append` 中拼表格的部分；`svg_trend` / `svg_stack` 保留（骨架里仍是 Python 渲染的内联 SVG）。

```python
OPEN_CAP = view.SEG_OPEN_CAP     # 保留这个名字，tests/test_lane.py 现在 import 它
CAP      = view.CAP

def build_bundle(day, rows, profiles, overrides, priority, state,
                 retain=view.RETAIN_DAYS) -> (files, new_state, stats)
        # files: {"latest.html": str, "<day>.html": str, "dashboard.css": str,
        #         "dashboard.js": str, "data-index-<day>.js": str,
        #         "data-<d>.js": str, ...}
        # stats: 保持现有键 raw/cap2/total/visible/unenriched/carry（按 N_DEFAULT 算）
        #        新增 by_n = {n: window_view(...)}

def build(day, rows, profiles, overrides, priority, state):
        """兼容壳：返回 (files["latest.html"], new_state, stats)，签名一个字不改。"""

def render_shell(tpl, ctx) -> str        # 只做 <!--SLOT:*--> 字符串替换，无模板引擎
def main(argv=None)                      # 新增 --retain N；--out 时把整个 bundle 写进该目录
```

`group_segment` / `split_cap` 保留（`tests/test_lane.py` 直接 import 它们），
但 `split_cap` 的输入改成「窗口去重后的行」而不是「当日行」——函数本身不用改。

**`web/shell.html`**：新文件，`<!--SLOT:HEAD--> <!--SLOT:HERO--> <!--SLOT:BANNER-->
<!--SLOT:TREND--> <!--SLOT:SEGMENTS--> <!--SLOT:PANELS--> <!--SLOT:FOOTER-->`。
**`web/dashboard.css`**：`dashboard.py` 里 95 行 CSS 常量逐字搬过来，加上
`scroll-margin-top` / `:focus-visible` / N 选择器 / 红条 / `[aria-busy]` 几条新样式。
**`web/dashboard.js`**：新文件，经典脚本。

### 4.10 每个「不能超过 X」背后的机制

| 要求 | 机制（哪一行代码在保证） | fixture |
|---|---|---|
| 首屏 ≤ 47 行 | `open_plan` 里 `min(cap2, SEG_OPEN_CAP[s])`，补位段只补到 `FLOOR - used` | F11a：`vis <= sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)`（派生，不写 47） |
| 首屏 ≥ 30 行（有货就给够） | `open_plan` 的补位循环 | F11b：`vis >= min(FLOOR, supply)` |
| 每家公司每段 ≤ 2 条 | `split_cap(groups, cap=CAP)`，作用域是窗口不是天 | F11c：`len(window_head(day,n,s)) == cap2[s]` |
| 窗口内无重复岗位 | Python 预生成 `x` 位；JS 只会 `if (x[i]) continue` | F21：5 档 N 下 `{键}` 无重复且基数等于真实去重 |
| 零丢弃（I1 窗口版） | `window_view` 的 `Σ raw == dedup`，JS 运行时对账 `check[N]` | F12（推广到 5 档 N × 2 anchor）+ L2 红条 |
| 首屏行本身不许错 | `check[N].head` 逐项比对 | F22 + F24（浏览器 selfcheck） |
| 判定不许漏到 JS | `co` 用定长数组，判定词汇不出现在 JS | F23（去注释后 grep 黑名单） |
| 数据块没加载不许静默 | `nrows[i]` vs `JOB_DAY[d].n` 对账 + `onerror` 记账 | F24 |
| 判定窗口永远 7 天 | 字段名 `w7` + `JOB_INDEX.w7_days` 拼表头文案 | F25：`payload["w7_days"] == CL.WINDOW_DAYS` |
| 磁盘不无限涨 | `--retain 30`，数据块与 `<day>.html` 同步删 | F26：跑两次不同 day 后目录里天数 ≤ retain |

---

## 5. 测试推广方案（逐条）

作用域只放宽，不放宽任何不变量。辅助函数改造：

```python
# 旧: segment_counts(day, profiles=None, overrides=None, rows=None)
def window_counts(day, n, profiles=None, overrides=None, rows=None):
    """-> (raw, cap2, dedup_total)，来自 view.window_view(payload, n)。
    payload 由 view.build_payload 生成 —— 断言的是浏览器真正拿到的那份数据。"""

def segment_counts(day, **kw):        # 保留旧名，等价于 window_counts(day, 1, **kw)
    return window_counts(day, 1, **kw)

def window_head(day, n, seg)          # 旧 segment_head(day, seg) = window_head(day, 1, seg)
def expanded_rows(day, n=view.N_DEFAULT)   # = view.open_plan(cap2)[1]
```

`segment_counts(day) == window_counts(day, 1)` 是安全的：实测（02:30）3 天全部
`CL.day_rows(rows,d)` 行数 == `N=1` 窗口去重行数（230/1674/169，三天全相等），
所以 **F6 / F7 / F19 一个断言都不用改**，只是函数体换了实现。

| fixture | 现在 | 改成 |
|---|---|---|
| F10 | 单日，段① head 全是 `is_entry` | `for n in N_CHOICES: for day in (HARVEST_DAY, STEADY_DAY)` 同样断言。段① 非空的断言保留 |
| F11 `default_visible_is_bounded` | `1 <= vis <= 50` | 5 档 N × 2 天：`vis <= sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)` **且** `vis >= min(FLOOR, supply)`。上下界都从常量派生，**50 这个字面量删掉** |
| F11 `truncated_rows_are_folded_not_dropped` | 单日 | 5 档 N；断言 `len(window_head(day,n,s)) == cap2[s]`，对 `SEG_OPEN_CAP` 里每个段 |
| F12 `zero_loss` | 单日 `Σraw == total` | 5 档 N × 2 天，且 payload 版：`Σ window_view(payload,n).raw == .dedup` |
| F12 `every_row_gets_exactly_one_segment` | 单日 | 对 payload 的 `g` 列断言 `0 <= g < len(SEGMENT_ORDER)` |
| F19 `is_a_criterion_not_a_filter` | 单日 | 不动（`segment_counts` 别名保底），另加一条 5 档 N 版 |
| F9（三条） | `DASH.build(...) -> page` | 改成 `files = DASH.build_bundle(...)[0]; page = files["latest.html"]`。`家未分层`、`<!doctype html>`、`<details`、`stats` 三键的断言**逐字保留**（骨架里就有这些） |
| `test_dashboard_has_no_external_dependency` | 断言 `"<script" not in page` | **方法名保留，body 换成 `assert_offline(files)`**（见下）。R4 必然要有 `<script`，但「离线双击可开」这个真不变量一条不放 |
| F17 / F16 / F15 / F14 / F8 / F5 / F4 / F3 | — | 一个字不改 |

**`assert_offline(files)` 的内容**（`_pm_06_sort_trend.py` §3 已经写好并对 6 种攻击各试了一遍）：

1. 任何文件里不出现 `type="module"` / `import x` / `export`；
2. `latest.html` 里每个 `src=` / `href=` 要么以 `#` 开头，要么**不含 `://`、不以 `/` 开头、不含 `..`**；
3. 任何 `.js` 里不出现 `fetch(` / `XMLHttpRequest` / `WebSocket` / `importScripts` /
   `EventSource` / `navigator.sendBeacon`；
4. `.js` 里所有 `X.src = ...` 的右值不含 `://`（动态注入只能是相对路径）；
5. `dashboard.css` 里仍有 `prefers-color-scheme` 与 `a:visited`；`<details` 仍在。

实测拦截效果：CDN `<script>` ✓、Google Fonts `<link>` ✓、`type="module"` ✓、
JS 里的 `fetch` ✓、注入绝对 URL 的块 ✓、`../` 越级引用 ✓ —— 六种全部抓到，
预期的 v2 骨架通过。**不是空断言。**

**新增 fixture**

| # | 断言 | 为什么必须有 |
|---|---|---|
| F20 | `Σ 各天 payload 行数 == 保留窗口内 CSV 原始行数`，且逐天相等 | 序列化丢行 fixture 现在完全看不见 |
| F21 | 5 档 N：payload 去重后无重复键，且基数 == 真实 distinct 键数；另断言 `x` 是在 `_day <= day` 上算的（用 8/19、8/20 两个 anchor 各验一次） | **实测全局作用域的 `x` 会让 8/19 丢 10 行、8/20 丢 28 行** |
| F22 | `payload["index"]["check"][n] == view.window_view(payload, n)`，5 档全对 | check 是 JS 唯一的真相来源，它自己必须被断言 |
| F23 | 去注释后的 `web/dashboard.js` 不含 `tier|prom|stage|kind|staffing|outsourcing|job_board|new\s*grad|entry.level|tnorm`（大小写不敏感） | 把 §5.3 的分工线从约定变成机制 |
| F24 | 找到 Chromium 可执行文件则 `--headless=new --dump-dom latest.html#selfcheck`，断言 5 档全 ok；找不到 `skipTest` | JS 侧唯一的端到端断言。实测可行 |
| F25 | `payload["index"]["w7_days"] == CL.WINDOW_DAYS`，且 `"近 %d 天" % CL.WINDOW_DAYS` 出现在骨架里 | S4 的机械保险 |
| F26 | 连跑两个不同 `--date` 后，输出目录里 `data-*.js` 的天数 ≤ retain | 保留策略没机制就会无限涨 |

**断言纪律**：以上没有一条写具体行数。凡是要比较数值的，右边都是**从常量或另一次计算派生**的
（`sum(SEG_OPEN_CAP...)`、`CL.WINDOW_DAYS`、`len(CL.day_rows(...))`），不是抄下来的数字。

---

## 6. 验收

在 `D:\OneDrive\work\school\project\Job`，Git Bash，`export PYTHONIOENCODING=utf-8`，
解释器 `D:/Apps/Miniconda/envs/job-classifier/python.exe`。

1. `python tests/test_lane.py` **全绿**（基线 36 个：34 过 2 跳；新增 7 条后是 43 个，
   F24 在无 Chromium 时跳过）。
2. **必须用 `.bat` 真跑一次**，不能只在已经设好 UTF-8 的 shell 里跑：
   `cmd /c run_daily_report.bat`（req2 §7.1 那个 `UnicodeEncodeError` 就是这么漏掉的）。
3. `python -u dashboard.py --date 2026-08-20 --no-watermark --out <临时目录>`
   → 目录里有 `latest.html` / `dashboard.css` / `dashboard.js` / `data-index-*.js` / `data-*.js`。
4. **人真的双击 `logs/dashboard/latest.html`**（Edge，本机 `.html` 的默认程序，
   实测注册表 `MSEdgeHTM`）。**这条不能只看代码，也不能只看 F24（F24 只覆盖 Chrome，
   本机 Edge 无头实测产出 0 字节）。** 双击后逐项：
   - 5 档 N 各切一次：不重载页面、去重正确、`check` 对账无红条；
   - 切 N 前展开 ③ 段、滚到页面中部，切完 ③ 仍展开、位置仍在那一段；
   - 点堆叠条每一段和图例每一项 → 跳到对应段并自动展开，段顶不被 sticky 挡住；
   - 键盘 Tab 到 N 选择器，左右键切换，`:focus-visible` 可见；
   - 断网（拔网线/飞行模式）重新双击 → 一切正常。
5. `latest.html#selfcheck` 双击 → `<pre id="selfcheck">` 5 档全 `ok`。
6. **首屏行数**：在 08:00 那次真实定时产物上量，`stats["visible"]` 落在
   `[min(30, supply), 47]`；语料翻倍后重跑仍然落在同一区间（把 `newgrad_classifications.csv`
   复制一份改 `unique_id` 前缀灌进去测，就像 F5 那样）。
7. **降级三连**（I9）：断网 / 删掉 `company_profiles.json` / 档案表是空 `{}` —— 三种情况下
   页面都能生成，`家未分层` 横幅出现，且没有任何真实雇主进 ⑥ 段。
8. `daily_report.py` 逐字节未改（F17）；`git diff --stat daily_report.py company_lane.py` 为空。
9. `logs/dashboard/` 里天数 ≤ 30，`<day>.html` 每份约 2 KB（对照：现在 8/20 那份 439,438 B）。

---

## 7. 放弃的方案（rejected_alternatives）

| # | 方案 | 为什么放弃（实测） |
|---|---|---|
| R1 | 按 req2 §5.2 原样发 `k` 字符串，JS 自己按 `k` 去重 | 261 B/行里 `k` 占约 45 B；而且幸存者随 N 变，JS 必须实现去重循环。换成 `x` 位后 JS 连键都看不到，**归一化漂移这个失败模式被结构消灭**（S1） |
| R2 | 保留 `unique_id` 字段 | 13.5 B/行，且 92.4% 的行里它就是 `job_link` 的尾段（实测 2324/2514）。真要排查时从链接里取 |
| R3 | req2 §5.5 的五个偏移块 | 五块每天全部重写（4.48 MB），历史 `<day>.html` 无法复用任何块，块名依赖「今天是哪天」；30 个按日块注入实测 17.9 ms **比五块的 20.2 ms 还快**（S3） |
| R4 | 一个 30 天大文件，不分块 | 5 MB 单文件 parse 37.3 ms 其实也能接受，但 OneDrive 每天重写一个 5 MB 文件、且没法只保留 30 天里的一部分；按日分块是同样的钱换更细的粒度 |
| R5 | **冻结按日块 + 每天只发一个「判定补丁」文件** | 能把日写入量从 4.46 MB 降到约 0.25 MB（补丁只含 0.48% 的 `g` 变更和 1.47% 的 `x` 变更）。放弃理由：补丁按「块内位置」对齐，一旦错位就是**安静的错分段**；第一版不值得。**如果 OneDrive 同步真的开始烦人，这是第一个该做的优化**，数字都在这里 |
| R6 | 每行发 `g`（段）由 JS 用 tier/is_entry 现算 | 直接违反 §5.3 分工线，把 I2/I3/I5/I6/I7 五条不变量搬进没有 fixture 的地方 |
| R7 | 按公司发一张 4 项段查找表（`(是否应届, 是否自有board) -> 段`），行上只发 2 bit | 能再省约 5 B/行，但要把 `is_entry` 的结果发给 JS，等于把「应届相关性」这个判据的一半暴露在 JS 语汇里，F23 那条黑名单就守不住了。省的钱不值 |
| R8 | N 放进 URL hash（`#n=7&seg=1a_t3`） | R3 要求堆叠条用 SVG 原生 `<a href="#seg-...">`，点一下就会把 N 冲掉。改成 localStorage（实测 Chrome file:// 可用）+ 一次性 `#n=7` 覆盖 |
| R9 | ⑦ 段按 N 切换形态（N=1 是段，N>1 是开关） | 要在两个地方各写一套。改成一条不看 N 的规则「区间内 ①②④ 且不在窗口里」，实测 N=1 给 83 行、N≥3 给 0 行，自己就退化了（S5） |
| R10 | 趋势柱改成「窗口去重后按天归属」，让柱子加起来等于窗口总数 | 那样 8/19 这根柱子会随 N 变高变矮（keep-newest 会把重复归到后面的天）。改成柱子永远是**按日去重**（跟 v1 一致、与 N 无关），差额 38 行（1.85%）在页面上写一行说明 |
| R11 | 把 CSS/JS 内联进 HTML（避免多文件） | 直接违反 R4「真 `.css` / `.js` 文件」；而且 `<link>`/`<script src>` 在 file:// 下实测可用，没有理由内联 |
| R12 | 用 `<select>` 做 N 选择器 | 5 个档位，平铺一眼可见且一次点击到位；`<select>` 要两次交互 |
| R13 | 首屏也做成懒渲染（连 ①④ 都等打开） | 首屏 ≤47 行，实测排序 1.1 ms、建 DOM 可忽略。懒渲染首屏只会让页面打开时是空的 |
| R14 | 用 `ats_registry.json` 当 `BOARD_COMPANIES` | req2 §7.5 已实测：只多 2 家 3 行。不动 |
| R15 | 加「已投 / 已忽略」 | 用户 2026-08-21 明确否掉 |

---

## 8. 自检清单

> `docs/multiagent_design_build_loop.md` 在我写这份设计的过程中被改过：原来的 §0.4
> 单张清单已经拆成 **§0.5 交接文档自检清单** 和 **§0.6 Prompt 自检清单**（我在 02:35
> 重新读过）。这份设计是要交给 evaluator 和 engineer 反复读的**交接文档**，所以按 §0.5 过。

- [x] **哪些已定、哪些待议切开了吗（单列两节）**：§0 复述 + §2「明确不做」。判定层、
      九条不变量 I1-I9、六段判据、N 的 5 个档位、§5.3 分工线、`daily_report.py` 不改 ——
      全部当约束处理，本文一条都没重新设计。开放的六项（数据结构 / 分块 / 渲染策略 /
      CAP-OPEN_CAP-排序键数值 / fixture 推广 / 跳转交互）逐项在 §4 给了方案。
- [x] **有「明确不做」一节，写清谁在什么时候否掉的**：§2 —— 已投/已忽略，用户 2026-08-21 否掉。
- [x] **规定了推翻既有结论的证据标准，并指出现成脚本在哪**：§3 每条反对都先跑脚本，
      脚本名和输出都贴在正文里；§9 是脚本索引；`_pm_base.py` 提供 `load()/win_rows()/dkey()`，
      跟上一轮 `_verify_base.py` 一个角色。
- [x] **每条约束都写了为什么**：§4.10 的每一行都有「机制」列（哪一行代码在保证它）；
      §7 的每一条 rejected 都有实测数字而不是「风格上更好」。
      特别是 `x` 必须按 `_day <= 生成日` 算这条，理由写成了实测后果（8/19 丢 10 行、8/20 丢 28 行），
      不是「这样比较干净」。
- [x] **每个数字标注了配置和时间**：§1 顶部一次性给出配置（解释器、Python 3.10.19、
      Windows-10-10.0.26200、Git Bash、`PYTHONIOENCODING=utf-8`），每张表标 `[T*]` 与脚本名；
      §3 里零散的数字各自标了 02:14 / 02:19 / 02:21 / 02:30 / 02:32；
      浏览器数字标了 Chrome 151.0.7922.172 / `--headless=new` / `file://`。
- [x] **会过期的数字写清了怎么重测**：§9 给了完整命令行；[T1]-[T4] 全部来自
      `_pm_10_snapshot.py` 一次运行，重跑即可刷新。文里点名了语料在 18 分钟内
      2491 → 2581 这件事，作为「为什么下游一个点值都不许写」的现场证据。
- [x] **环境信息完整**：§1 顶部 + §6 验收里给了解释器路径、环境变量、
      `python tests/test_lane.py`、`cmd /c run_daily_report.bat`、
      `python -u dashboard.py --date ... --no-watermark --out ...` 全部命令。
- [x] **每个「不能超过 X」背后有机制**：§4.10 一整张表。**并且补了原来没有的地板**：
      现行 35/12 只是天花板，[T2] 显示它在真实生成时刻（08:00）给出 21/26/7 行，
      从来没进过用户认过的 30-50。
- [x] **有没有哪条约束把两件不同的事压成了一件**：找到四处并拆开 ——
      ① 「7 天」判定窗口 vs N 取景窗口（字段改名 `w7`，表头文案由 `w7_days` 拼，F25 守）；
      ② 「零外部依赖」被 `test_dashboard_has_no_external_dependency` 压成「零 `<script>` 标签」
      （§5 拆成 5 条真断言，6 种攻击各试过一遍）；
      ③ 「窗口去重」与「按日去重」在趋势柱上被当成一件事（差 1.85%，R10 决定柱子按日、
      页面上写明差额）；
      ④ **`x` 去重标记的作用域**（全局 vs `_day <= 生成日`）—— 这一处压扁会直接破 I1，
      实测丢 10/28 行。

**§0.6（Prompt 自检）不适用于本文**，它是给 orchestrator 写 evaluator prompt 用的。
但有一条与我有关：**「明确授权它反对我」**—— 本轮 prompt 写了，我用了：
S1 部分反对、S2 反对「数值沿用就够」、S3 反对五个偏移块、S5 反对「按 N 切换形态」、
S7 反对「只能写极小断言」这个前提。五处都带脚本输出。

**已知的、我没能自己验证的一条**：Edge（真正的双击目标，实测注册表 `.html` 关联
`MSEdgeHTM`）的无头模式在本机产出 0 字节 —— `--headless=new` / `--headless` /
`--headless=old` 三种参数、`--dump-dom` 与 `--screenshot` 两种输出方式全试过。
所以 file:// 能力表在 Edge 上**没有实测**，只有间接证据（Edge 151.0.4129 与
Chrome 151.0.7922 同属 Chromium 151；`HKLM\SOFTWARE\Policies\Microsoft\Edge`
无任何策略键）。**这就是 §6 第 4 条必须由人真双击一次的原因，F24 绿不能代替它。**

---

## 9. 复现脚本

全部在 `dashboard_loop/v2/`，用
`export PYTHONIOENCODING=utf-8; D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/<脚本>` 跑。

| 脚本 | 回答什么 |
|---|---|
| `_pm_base.py` | 共用 loader（`load` / `win_rows` / `dedup_keep` / `dkey`） |
| `_pm_01_window.py` | 5 档 N 的窗口行数、各段 raw/cap2、I1 窗口版、重复=0、keep-first vs keep-last |
| `_pm_02_anchor.py` | 生成日 resolver vs 本日 resolver 的段漂移、跨天重复率、首屏地板、cap2 对 N 单调 |
| `_pm_03_payload.py` | 后缀嵌套证明（keep-NEWEST 可冻结）、E0-E4 五种编码的 B/行、每列字节、按天块大小 |
| `_pm_04_openplan.py` | open_plan 的上下界、⑦ 段与窗口的重叠、check 表大小、渲染量 |
| `_pm_05_fileproto.py` | **file:// 能力表实跑**（Chrome/Edge） |
| `_pm_06_sort_trend.py` | sort_key 的 tier/prom 倒置影响、趋势柱对账、`assert_offline` 的 6 种攻击测试 |
| `_pm_07_perf.py` | 60000 行 / 5 MB 载荷在 Chrome file:// 下的 parse 与纯数据一趟耗时 |
| `_pm_08_chunks.py` | 按日 30 块 vs 五个偏移块 vs 单文件：注入耗时与每日重写量 |
| `_pm_09_default_n.py` | **08:00 到货曲线与首屏行数**、⑦ 段细化规则、按日 HTML 快照成本 |
| `_pm_10_snapshot.py` | 合并快照，本文 [T1]-[T4] 的唯一来源 |
