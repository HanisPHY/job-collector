# Dashboard v2 设计 v2（pm-design 第 2 轮，收口版）

> **Engineer 只需要读这一份。** 它是完整规格，不是对 v1 的增量 diff。
> 需求原文：`docs/req/req2-dashboard-v2.md`（本轮已重新逐字读过）。
> 框架：`docs/multiagent_design_build_loop.md` §0。
> 复现脚本：`dashboard_loop/v2/_pm_*.py`（第 1 轮）、`_pm2_*.py`（本轮），见 §8。
>
> **本轮方针：只做减法和收口。** 新机制只在某条 must-fix 没有它就关不掉时才引入 —— 全文只有一处（§3.6 的三视图开关），而它是把 v1 已有的「⑦ 段筛选开关」改成三选一，不是新增第二套机制。
>
> **口径**：§2 的所有语料数字来自 `_pm2_10_snapshot.py` 的**同一次运行**（2026-08-21 03:07:49）。浏览器数字单独标注（浏览器行为与语料增长无关）。语料每小时在涨，任何断言都不许写点值。

---

## 0. 对 v1 评审的逐条回应

### 0.1 Must-fix（5 条，全部接受，全部已复现）

#### A1 — PIN_DAY 历史页共享可变块会漂移 → **接受，用减法关闭：不再写历史 `<day>.html`**

复现（`_evalA_pinday_drift.py`，03:02）：`2026-08-20.html` 钉在 08-20，但它引用的 `data-2026-08-20.js` 每天被按新生成日重写 —— 28 行 `x` 被改成「已被取代」、12 行 `g` 从 B2 静默滑进 C，而 `data-index-2026-08-20.js` 里的 `check` 再也不更新。评审说得对，而且更糟：v1 的 L2 对账会让这一页在漂移发生的第二天**永久变成红条**，且 v1 没写任何修复路径。

我不选评审给的 (a)「每天存一份私有冻结拷贝」，也不选 (b)「承认尽力而为」，**选 orchestrator 提示的第三条：干脆不再保留历史 `<day>.html`**。

量化代价（`_pm2_03_size.py`，03:06）：一个钉住的历史页与「今天的窗口视图」相比，只在这些行上会显示得不一样 ——

```
pin=2026-08-19 : 287 行中 g 差 0、x 差 10、并集 10  (3.48%)
pin=2026-08-20 : 2072 行中 g 差 12、x 差 28、并集 39  (1.88%)
```

也就是说，放弃历史页丢掉的是「这 1.9%-3.5% 的行按当天判定该长什么样」。**这些行本身一条都没丢** —— N 天窗口仍然逐条显示它们，带日期，只是用今天的判定。换来的是：删掉 `PIN_DAY` 代码路径、删掉 HTML 的保留/清理规则、删掉「冻结索引指向可变数据块」这一整类 bug、每天少写一份文件（v1 实测 `2026-08-20.html` = 439,438 B）。

**真要一份冻结快照时**：`python -u dashboard.py --date 2026-08-20 --out <目录>` 把**整套自包含 bundle**（骨架 + css + js + 该 anchor 下重算的 index 与全部日块）写进那个目录。它是按需产生的、内部自洽的、不与 `logs/dashboard/` 共享任何可变文件。这条本来就是验收步骤，现在同时也是历史快照的正式办法。

> Engineer 注意：`SCHEDULING.md` 第 204 行写着「Output: `logs/dashboard/<day>.html` plus `logs/dashboard/latest.html`」，实现后需要改这一行。

#### A2 — `open >= min(FLOOR, supply)` 下界不成立 → **接受，改的是「公布的合同」，不是 `open_plan`**

复现（`_evalA_openplan_math.py` 与 `_pm2_01_fixes.py`，03:05）：v1 把 `supply` 定义成**未截断**的 cap2 之和，50 万组随机 cap2 里 **1931 次（0.39%）** 违反下界，最紧的一次少 18 行；`cap2={①:0, ④:1000, ②:0}` 时 `open=12` 而声称下界是 30。上界 `<= CEIL` 一次都没被打破。

orchestrator 要我二选一。**我选「重定义 supply」，不改 `open_plan`**，理由是实测而不是口味：把 ④ 的首屏天花板从 12 放开去补地板，等于让「有自有 ATS board 的小公司」在 ①② 都空的那天独占 30 行首屏 —— 那正是 `OPEN_CAP` 当初被加进来要防的事（req2 §3.3）。而且本轮方针是减法，A2 用定义就能关掉。

新合同（`_pm2_base.py`，50 万随机 + 7 组人工对抗形状，**违例 0、与闭式不符 0**）：

```python
openable(cap2)   = Σ min(cap2[s], SEG_OPEN_CAP[s])  for s in OPEN_ORDER   # 截断后能贡献的量
open_expected(c) = max(base, min(base + filler, FLOOR))
                   base   = Σ min(c[s], SEG_OPEN_CAP[s]) for s in ALWAYS_OPEN
                   filler = Σ min(c[s], SEG_OPEN_CAP[s]) for s in OPEN_ORDER - ALWAYS_OPEN
```

fixture 断言的是**等式**而不是区间，所以没有手写边界可以写错：

- F11a：`open_plan(cap2)[1] == view.open_expected(cap2)`，另跑 2000 组随机 cap2 的属性测试
- F11b：`min(FLOOR, openable(cap2)) <= open <= CEIL`，`CEIL` 由 `sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)` 派生

页面上的说法也跟着改成能兑现的那句：**「首屏在 ①④② 三段各自的上限之内补到 30 行，最多 47 行」**，而不是「首屏永远 30-50」。当 `open < FLOOR` 且未截断的 cap2 之和 ≥ FLOOR 时，hero 那块直接写明「①② 的量不够，④ 按设计封顶 12 行」——这是一句文案，不是新机制。

#### A3 — 单日/窗口两套去重规则的等价是巧合 → **接受，用减法关闭：v2 数据路径只留一条去重规则**

复现（`_evalA_daykeep_equiv.py` / `_pm2_01_fixes.py`，03:05）：`CL.dedup_rows`（三个 CSV 按 source 顺序先到先得）与 keep-NEWEST（按 `_recorded` 取最新）在三天里对 **45 组**选出了不同的物理行，目前**恰好 0 组跨段**。评审是对的：那是语料的偶然性质。

v1 之所以要同时活着两条规则，是因为**趋势柱**用的是「按日去重」（`CL.day_rows`），而窗口视图用 keep-NEWEST —— v1 还为此写了一行页面脚注解释 2073 与 2035 的差。**这一条整个删掉**：

> **趋势柱 bar(d) := 窗口去重后仍然存活、且落在自然日 d 的行数。**

实测（`_pm2_01_fixes.py` / `_pm2_10_snapshot.py`）：`x` 的作用域与 N 无关，所以 **bar(d) 与 N 无关**，且 **Σ bar(窗口内各天) == dedup(N) 对 5 档 N 全部精确成立**。两个数字变成同一个数字，脚注删除。代价是柱高与 v1 相比略低（8/19 220 vs 230，8/20 1646 vs 1674，8/21 169 vs 169），页面上用一行图注说清口径：「柱高 = 该日仍是同公司同标题最新一条的行数」。

再加评审要的 canary（F27）：`CL.day_rows(rows, d)` 选出的幸存行集合必须等于 keep-NEWEST 在该日选出的集合，**每天各断言一次**。它红了就说明两条规则开始分家，需要人介入 —— 而不是让两套测试静默各测各的。同时把 F6/F7/F19 依赖的 `segment_counts(day)` 换成 `window_counts(day, 1)`，让**测试里也只剩一条规则**。

#### B7 — 同 hash 再点不触发 `hashchange` → **接受**

复现（`_evalB_hashclick.py`，Chrome 151.0.7922.172，`--headless=new`，file://，03:02）：
`["after_click_1 hash=#seg-1a_t3 events=1", "after_click_2_same_hash hash=#seg-1a_t3 events=1"]` —— 第二次点击同一个锚点，`hashchange` 计数仍是 1。

改法见 §3.9：堆叠条 `<a>`、图例 `<a>` 上挂一个**委托 click 处理器**，直接调用幂等的 `openSegment(id)`（展开 + 渲染 + 滚动 + focus），不 `preventDefault()`（hash 照常更新，前进/后退仍然可用）；`hashchange` 只留给地址栏输入和前进后退。

#### B1 — FLOOR 买到的是数量不是新鲜度 → **接受，用「已有开关三选一」关闭，零持久化用户状态**

评审用整天语料测出 8/20→8/21 首屏 89% 重复。我在**页面真正生成的 08:00** 重测（`_pm2_10_snapshot.py` [T2]）是 39%/42%（`repeat` 列 18/46 与 20/47）—— 两个数都真实，评审量的是「白天再打开看」的情形，我量的是生成时刻。**结论方向完全一致：默认 N=3 下首屏确实大面积重复。**

先回答「要不要改默认 N」。[T2] 的 `new` 列是决定性的：

| anchor | N=1 首屏 / 其中新增 | N=3 首屏 / 其中新增 |
|---|---|---|
| 08-19 | 30 / **30** | 30 / **30** |
| 08-20 | 30 / **30** | 46 / **29** |
| 08-21 | 11 / **11** | 47 / **27** |

N=3 的首屏在**绝对新增行数**上与 N=1 基本持平（29 vs 30、27 vs 11），却多给出 16-36 行可挑的存量。**所以不改默认 N（仍是 3）**，这是数据结论不是惯性。

真正的修法是让「新鲜」变成一个**一键可选的取景**，而不是改排序或存用户状态。v1 里本来就有一个「只看上一期未处理」的布尔开关；**把它改成三选一**（同一套过滤代码、同一个 `r` 字段、同一套对账）：

```
显示：  ● 全部          窗口内全部行（默认）
        ● 新            _recorded > 上一期 cutoff          —— 就是「● 新」那批
        ● 上一期未处理   prev_prev < _recorded <= prev_cutoff
```

实测效果（[T3]，N=3）：

```
                 全部    只看新增
8/20 首屏行数     46       38        日复一日重复  18/46 (39%)  ->  1/38  (2.6%)
8/21 首屏行数     47       44        日复一日重复  20/47 (42%)  ->  1/44  (2.3%)
```

**一次点击把重复率从 39-42% 压到 2%，首屏仍然是 38-44 行（在 30-47 区间内）。** 三个视图全部由水位线派生，不存任何用户行为，符合 orchestrator 的边界提醒和 req2「明确不做已投/已忽略」。

另外补上 v1 漏掉的一条 req2 硬要求：**req2 §4.2 决策 4 明确「日期列在窗口视图下是必需的」，v1 从头到尾没有写行表有哪些列。** 实测（`_pm2_02_freshness.py` [E]）N≥3 时首屏横跨 3 个自然日（8/19 15 行、8/20 27 行、8/21 5 行），日期列确实是承重的。列定义写进 §3.9。

**权衡照写不藏**：默认视图（全部）下，首屏在 08:00 有 39-42% 是昨天见过的。缓解手段是三件已有的东西 —— 日期列、`● 新` 标记、一键切「只看新增」；不做任何需要记住「你处理过什么」的机制（用户 2026-08-21 否掉）。

### 0.2 Nice-to-have（11 条）

| # | 采纳 | 做法 / 不采纳的理由 |
|---|---|---|
| A4 数字来自不同快照 | **采纳** | §2 全部来自 `_pm2_10_snapshot.py` 一次运行（03:07:49）。v1 里 `29/151/20` 这几个点值直接删掉，只留结构性结论 |
| A5 view.py 应声明为全函数 | **采纳** | §3.11 写进签名约定；§5 降级三连点名 `build_payload` / `window_view` |
| B2 SEGMENT_ORDER 没发给 JS | **采纳（用 b 方案，更省）** | 骨架六个 `<details>` 带 `data-gidx="0".."5"`，JS 用 `[data-gidx]` 定位，**不发 `seg_ids` 数组、JS 里不出现任何段 key 字符串**；F23 黑名单加入 `1a_t3` / `1a_t2` 两个不可能误撞的字符串 |
| B3 折叠段内部无 identity 对账 | **采纳** | `check[f][N].anchors[seg]` = 该段 cap2 head 的**首 / 中 / 末**三个 `[天下标, 行下标]`。实测 6 段 × 3 坐标 × 5 档 = **973 B** |
| B4 「● 新」无任何检查点 | **采纳** | B1 的修法让「● 新」升级成一个正式视图，`check["new"][N]` 的 `head`/`anchors` 直接把它纳入对账；§5 人工清单加一条 |
| B5 `check_wm`/⑦/开关无 fixture | **采纳** | `check` 改成 `check[f][N]`，f ∈ {all,new,wm}；F28 对三个 f × 5 档 N 断言 I1；`#selfcheck` 跑满 15 组 |
| B6 视口无 `<details>` 时的滚动 fallback | **采纳** | §3.9 写死：找不到锚点就退回绝对 `scrollTop`；**并且对账在滚动恢复之前跑**，滚动出错绝不可能连累红条 |
| B8 rAF 分片需要世代号 | **采纳** | §3.9 写死 `gen` 自增，每帧校验 |
| B9 `panels[N]` 算了没说怎么用 | **采纳，并顺手做成减法** | 所有非行表区块（趋势 SVG、堆叠条、图例、面板②′、面板③、hero）由 **Python 预渲染成 HTML 字符串，每档 N 一份**，JS 只做 `el.innerHTML = chrome[n][slot]`。实测 5 档合计 **29.9 KB**，换来 dashboard.js 里**没有 SVG 渲染器、没有面板渲染器**。切 N 时这些块跟着换；三视图开关**不影响**它们（它们描述整个窗口），页面上明说 |
| B10 `.bat` 验收判定标准 | **采纳** | §5 第 2 条写清：退出码 0、stdout/stderr 无 `Traceback`、`latest.html` 与今天的数据块 mtime 是本次运行 |
| B11 故意破坏回归 | **采纳，列为必做** | §5 第 10 条 |

---

## 1. 范围与边界（本轮重申）

**目标**：`dashboard.py` 只算数据；输出真 `.html` / `.css` / `.js` + 按自然日的数据块；浏览器里切 N 不重载；点堆叠条跳段；首屏行数由机制锁住；I1 在窗口上继续有 fixture 守着。

**不要重新设计（约束，不是待议项）**：I1-I9 九条不变量、六段判据、N 只能从 1/3/7/14/30 里选、判定层留 Python 取景层交 JS 这条分工线、`daily_report.py` 一行不改、`company_lane.py` 一行不改。

**明确不做**：已投 / 已忽略（用户 2026-08-21 否掉）。任何需要持久化「用户处理过什么」的机制都在此列内。

**技术硬约束**：零外部依赖、离线 `file://` 双击可开、无 build step、无 npm/CDN/Google Fonts、`<script type="module">` 与 `fetch`/`XHR` 在 file:// 下不可用（§2 [T6] 实测）。

---

## 2. 实测快照

**配置（[T1]-[T5] 共用）**：`_pm2_10_snapshot.py`，**2026-08-21 03:07:49 本地时间**，Python 3.10.19，解释器 `D:\Apps\Miniconda\envs\job-classifier\python.exe`，Windows-10-10.0.26200，Git Bash，`PYTHONIOENCODING=utf-8`。
语料 2581 行 / 3 天 / 1312 家公司；`company_profiles.json` 1266 条；overrides 24 条。
常量：`CAP=2  FLOOR=30  CEIL=47  SEG_OPEN_CAP={1a_t3:35, B1:12, 1a_t2:30}  N_DEFAULT=3`。
测试基线：`python tests/test_lane.py` → `Ran 36 tests ... OK (skipped=2)`（03:08 实测）。

```
2026-08-19 raw   287   趋势柱（唯一规则）  220
2026-08-20 raw  2072   趋势柱             1646
2026-08-21 raw   222   趋势柱              169     (当天还在涨)
```

### [T1] 5 档 N 的窗口视图（anchor 2026-08-21，唯一去重规则）

| N | 窗口原始 | 去重后 | 丢弃 | ① | ② | ③ | ④ | ⑤ | ⑥ | cap2 合计 | 首屏 | Σ柱高 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 222 | 169 | 53 | 5 | 4 | 48 | 3 | 79 | 30 | 144 | 11 | 169 |
| 3 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 | 2035 |
| 7 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 | 2035 |
| 14 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 | 2035 |
| 30 | 2581 | 2035 | 546 | 97 | 151 | 634 | 90 | 692 | 371 | 1655 | 47 | 2035 |

脚本对每个 N 断言并全部通过：`Σraw == 去重后行数 == 窗口内 distinct(公司,归一化标题) == Σ柱高`（**I1 窗口版**）、`open == open_expected(cap2)`、`min(FLOOR, openable) <= open <= CEIL`。N≥3 全同是因为语料只有 3 天。

### [T2] ★ 首屏，在页面真正生成的那个小时（08:00）

| anchor | N | 首屏 | openable | 其中新增 | 新增占比 | 与前一天重复 |
|---|---|---|---|---|---|---|
| 08-19 | 1 / 3 / 7 / 14 / 30 | 30 | 51 | 30 | 100% | 0 |
| 08-20 | 1 | 30 | 56 | 30 | 100% | 0 |
| 08-20 | 3 / 7 / 14 / 30 | 46 | 76 | 29 | 63% | 18 |
| 08-21 | 1 | 11 | 11 | 11 | 100% | 0 |
| 08-21 | 3 / 7 / 14 / 30 | 47 | 77 | 27 | 57% | 20 |

到货曲线：8/20 全天 2072 行，**08:00 之前只到 790 行（38%）**。所有「首屏 47 行」的旧结论都是拿一天结束时的语料算的。

### [T3] 三个水位线派生视图（零持久化用户状态）

| anchor | N | 全部 | 新增 | 上一期 | 首屏(全部) | 首屏(新增) | 首屏(上一期) | 新增视图的日重复 |
|---|---|---|---|---|---|---|---|---|
| 08-19 | 任意 | 143 | 143 | 0 | 30 | 30 | 0 | 0/30 |
| 08-20 | 1 | 560 | 560 | 0 | 30 | 30 | 0 | 0/30 |
| 08-20 | 3+ | 782 | 645 | 137 | 46 | 38 | 30 | **1/38** |
| 08-21 | 1 | 169 | 169 | 0 | 11 | 11 | 0 | 0/11 |
| 08-21 | 3+ | 2035 | 1310 | 588 | 47 | 44 | 38 | **1/44** |

### [T4] ⑦ 段（上一期摆在眼前、而当前窗口盖不到的行）

水位线 `logs/last_report.json`：`prev_prev=2026-08-20 12:24`，`prev_cutoff=2026-08-21 00:24`。
区间内去重后 739 行，落在 ①②④ 的 86 行。

| N | ⑦ 段显示（窗口外） | 窗口内（视图开关覆盖） |
|---|---|---|
| 1 | **83** | 3 |
| 3 / 7 / 14 / 30 | **0** | 86 |

### [T5] 载荷大小（编码 E4，见 §3.2）

```
data-2026-08-19.js    287 行    28,164 B   98.1 B/行
data-2026-08-20.js   2072 行   156,197 B   75.4 B/行
data-2026-08-21.js    222 行    16,623 B   74.9 B/行
index（co / o / days）           42,430 B   （1312 家公司）
预渲染 chrome（5 档 N）          29,896 B   （_pm2_03_size.py，03:06）
今天写盘合计                    273,414 B  = 0.26 MB
按 2000 行/天外推：155,741 B/天，保留 30 天 = 4.46 MB
```

req2 §5.2 写的「每行 152 字节」实测是 **261.2 B/行**（`_pm_03_payload.py`，02:19）。逐级优化到 E4 = **80 B/行**（30.6%）：去掉 `k`（换成 1 bit 的 `x`）、`r` 存 HHMM 整数、`sig` 移到公司表、改列式数组、去掉 `unique_id`（92.4% 的行里它就是 `job_link` 的尾段）、日期/段/链接前缀内插。

### [T6] 浏览器实测

`_pm_05_fileproto.py` / `_pm_07_perf.py` / `_pm_08_chunks.py` / `_evalB_hashclick.py`，
**Chrome 151.0.7922.172，`--headless=new --dump-dom`，页面在 `file:///C:/Users/...`**（02:22-02:26 与 03:02）：

| 断言 | 实测 |
|---|---|
| 同目录 `<link rel=stylesheet>` | ✅ `getComputedStyle` = `rgb(1, 2, 3)` |
| 同目录经典 `<script src>` | ✅ |
| 动态注入 `<script src>` | ✅ `onload` 触发且数据可见 |
| 并发注入 3 块 / 30 块 | ✅ 全部 onload，累加值正确，错误 0 |
| `<script type="module">` | **onerror，被拦** |
| `fetch()` / `XMLHttpRequest` | **REJECT: TypeError / THROW: NetworkError** |
| `localStorage` | **能用**（写入读回 `"v"`）；`location.origin` 是 `"file://"` 而不是 req2 §6 写的 `null` |
| 同 hash 再次点击 | **不触发 `hashchange`**（events 停在 1）→ B7 |

性能（合成 30 天 × 2000 行 = 60000 行，5.05 MB）：整文件 parse+eval **48.0 ms**；N=30 纯数据一趟（筛选+去重+分组+cap2）**3.2 ms 冷 / 3.5 ms 热**；段① 按 rank 排序 3252 行 **1.1 ms**。**数据层不是瓶颈，DOM 才是。**

分块方案（同一次运行）：按自然日 30 块并行注入 **17.9 ms**（错误 0），req2 §5.5 的 5 个偏移块 **20.2 ms**，单个 30 天大文件 **37.3 ms**。

**Edge 的限制（必须写在这里）**：本机 `.html` 的默认打开程序是 Edge（注册表 `MSEdgeHTM`），但 **Edge 无头在本机 `--dump-dom` 与 `--screenshot` 都产出 0 字节**（`--headless=new` / `--headless` / `--headless=old` 三种都试过），`HKLM` 下的 Edge 策略键不存在。所以上表在 Edge 上**没有实测**，只有「Edge 151.0.4129 与 Chrome 151.0.7922 同属 Chromium 151」这个间接证据。**§5 第 5 条的人工双击因此是硬性验收项。**

---

## 3. 设计

### 3.1 文件布局

```
web/                              ← 新目录，源文件，进版本库
    shell.html                    真 HTML 模板，含 <!--SLOT:*--> 占位
    dashboard.css                 真 CSS（dashboard.py 的 95 行 CSS 常量逐字搬来 + 新增几条）
    dashboard.js                  真 JS（经典脚本，非模块）
view.py                           新增：纯数据参考实现（无 HTML、无 I/O）
dashboard.py                      算数据 + 填模板 + 原子写；不再拼 CSS、不再拼行表
logs/dashboard/
    latest.html                   ← 双击这个（唯一的 HTML 产物）
    dashboard.css                 每次运行从 web/ 原样复制
    dashboard.js                  同上
    data-index.js                 每次运行重写（固定文件名）
    data-2026-08-19.js            按自然日，绝对命名
    data-2026-08-20.js
    data-2026-08-21.js
```

**没有 `<day>.html`**（A1）。`--date X --out DIR` 会把上面整套（`latest.html` + css + js + index + 该 anchor 下的全部日块）写进 `DIR`，那是按需的、自包含的冻结快照。

`latest.html` 里的脚本引用（默认 N=3，静态引今天 + 前 2 天 + 水位线覆盖到的天，去重后 3-4 个文件）：

```html
<link rel="stylesheet" href="dashboard.css">
<script src="data-index.js"></script>
<script src="data-2026-08-19.js"></script>
<script src="data-2026-08-20.js"></script>
<script src="data-2026-08-21.js"></script>
<script src="dashboard.js"></script>          <!-- 经典脚本，绝不能 type="module" -->
```

CSS 从 Python 字符串常量变成真文件，是 R4 的实质内容。`web/` 里的两个文件由 `dashboard.py` **原样复制**（不拼接、不模板化）到输出目录，OneDrive 下一律 `tmp + os.replace`。

### 3.2 数据结构

**`data-index.js`**（每次运行重写；实测 42 KB 公司表 + 30 KB chrome）：

```js
window.JOB_INDEX = {
  v: 2,                            // schema 版本；JS 不匹配就红条并停止渲染
  day: "2026-08-21",               // 生成日 = 所有窗口的右端点
  generated: "2026-08-21 08:00",
  cutoff: "2026-08-21 08:00",      // 水位线，驱动「● 新」与「新增」视图
  prev_cutoff: "2026-08-20 08:00",
  prev_prev:  "2026-08-19 08:00",
  w7_days: 7,                      // 判定窗口，固定 7 天，见 §3.5
  n_choices: [1,3,7,14,30],
  n_default: 3,
  views: ["all","new","wm"],
  days:  ["2026-07-23", ... , "2026-08-21"],   // 30 项，旧→新，含空天
  chunk: ["", ... , "data-2026-08-21.js"],     // 空天为 ""，不写文件也不注入
  nrows: [0, ... , 2072, 222],                 // 每天期望的原始行数（含被 x 标记的）
  wm_days: [28, 29],                           // 水位线区间覆盖到的天下标，永远要加载
  co: [ ["Palantir Technologies", 3, 85, 18, 1, 12, 12], ... ],
  //     0 显示名                  1t 2p 3w7 4b 5sig 6sig_own
  o:    [ 417, ... ],              // 每家公司的排序名次（= CL.sort_key 的名次），见 §3.5
  sigs: [ "", "LLM:job_board", "unknown+vol 7/7d", ... ],
  lpre: ["https://www.linkedin.com", "https://jobs.ashbyhq.com", ...],
  chrome: { "1": {...}, "3": {...}, "7": {...}, "14": {...}, "30": {...} },  // 见 §3.8
  check:  { "all": {"1":{...},...}, "new": {...}, "wm": {...} },             // 见 §3.10
  health: { unenriched: 7, examples: ["...", ...] }
}
```

`co` 用**定长数组而不是对象**：一是省字节，二是让 `tier` / `prom` / `stage` 这些词根本不出现在 JS 里（F23 靠这个）。每家两个 `sig` 下标：`[5]` 是普通信号，`[6]` 是「自有 board 那条行」的信号（实测 1312 家里只有 1 家两者不同）；JS 取 `sigs[co[c][s === 0 ? 5 : 6]]`，是查表不是判断。

**`data-<day>.js`**（一天一个；实测 75-98 B/行）：

```js
(window.JOB_DAY = window.JOB_DAY || {})["2026-08-20"] = {
  d: 28,                       // days[] 下标
  n: 2072,                     // 原始行数，必须等于 JOB_INDEX.nrows[28]
  c:  [42, 17, ...],           // 公司下标
  g:  [0, 3, 5, ...],          // 段下标 0..5，顺序 = CL.SEGMENT_ORDER
  t:  ["Software Engineer, New Grad", ...],
  lp: [0, -1, ...],            // 链接前缀下标，-1 = l 里是完整 URL
  l:  ["/jobs/view/4456201304", ...],
  s:  [0, 1, 2, ...],          // 0 newgrad / 1 ats_direct / 2 ddg
  r:  [1224, 806, ...],        // 收录时刻的 HH*100+MM（配合 d 就是完整时间戳）
  x:  [0, 1, 0, ...]           // 1 = 被更新的同键行取代，见 §3.3
};
```

九个数组等长，长度必须 = `n`；不等长 → 红条。**没有 `k`，没有 `unique_id`，没有完整时间戳字符串。**

编码：`json.dumps(obj, ensure_ascii=False, separators=(",", ":"))`，UTF-8 无 BOM，文件以 `;` 结尾。不压缩（file:// 下浏览器不解 gzip）。

### 3.3 ★ 唯一的去重规则

> **keep-NEWEST，作用域 `_day <= 生成日`。整份设计里没有第二条去重规则。**

Python 对每一行预生成一个布尔位 `x`：同一个 `(CL.norm(公司), CL.tnorm(标题))` 组里，除了 `_recorded` 最新的那条，其余全部 `x=1`。JS 的去重就是一行 `if (x[i]) continue` —— **它连去重键的字符串都看不到，归一化规则漂移这个 R2 最容易犯的错在结构上不存在**。

为什么 keep-NEWEST 可以被冻结成一个与 N 无关的位：5 档窗口都是「以生成日结尾的后缀」，互相嵌套（W1 ⊂ W3 ⊂ W7 ⊂ W14 ⊂ W30）；一个组只要有成员落在窗口里，最新那条必定也在。实测（`_pm_03_payload.py`）：keep-NEWEST 幸存者与全局最新不同的 (组,N) 情形 **0 次**；keep-OLDEST **20 次**。

**作用域是承重的**：`x` 必须在 `_day <= 生成日` 的行集合上算。实测（02:30）用全局作用域去渲染 8/19 的窗口会**静默丢 10 行**，8/20 丢 28 行 —— 直接破 I1。按 `_day <= anchor` 算，3 个 anchor × 5 档 N 全部 `flag 去重 == 真实去重`。

**趋势柱也用这条规则**（A3）：`bar(d) = |{r : r._day == d 且 x=0}|`。它与 N 无关，且 `Σ bar(窗口内各天) == dedup(N)` 对 5 档 N 精确成立（[T1] 的 `Σ柱高` 列）。页面图注：「柱高 = 该日仍是同公司同标题最新一条的行数」。

`CL.dedup_rows` / `CL.day_rows` 在 v2 的数据路径里**不再被使用**（`daily_report.py` 不 import `company_lane`，已核对），只剩 F27 canary 在看着它们与新规则是否还一致。

### 3.4 首屏机制（A2 修正后的合同）

```python
CAP          = 2                                     # 每家公司每段，在整个窗口内
OPEN_ORDER   = ("1a_t3", "B1", "1a_t2")              # ① → ④ → ②(仅补位)
ALWAYS_OPEN  = ("1a_t3", "B1")
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
FLOOR        = 30
CEIL         = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)   # 47，派生，全仓库只算这一次

def open_plan(cap2):
    plan, used = {}, 0
    for s in ALWAYS_OPEN:                            # 天花板
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s]); used += plan[s]
    for s in OPEN_ORDER:                             # 地板：只补到 FLOOR，不补到 CEIL
        if s in ALWAYS_OPEN or used >= FLOOR: continue
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s], FLOOR - used); used += plan[s]
    return plan, used

def openable(cap2):        # 三段各自封顶后「能贡献的量」——A2 的关键修正
    return sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s]) for s in OPEN_ORDER)

def open_expected(cap2):   # open_plan 总数的闭式；fixture 断言等式，不断言区间
    base   = sum(min(cap2.get(s,0), SEG_OPEN_CAP[s]) for s in ALWAYS_OPEN)
    filler = sum(min(cap2.get(s,0), SEG_OPEN_CAP[s]) for s in OPEN_ORDER
                 if s not in ALWAYS_OPEN)
    return max(base, min(base + filler, FLOOR))
```

**合同**：`open_plan(cap2)[1] == open_expected(cap2)`，因此 `min(FLOOR, openable(cap2)) <= open <= CEIL`。
50 万组随机 cap2 + 7 组人工对抗形状：**违例 0、与闭式不符 0**（v1 的旧说法违例 1931 次）。

`CAP=2` 的含义按 req2 §4.2 决策 2：**整个窗口内每家公司每段最多先看 2 条**，不是每天 2 条。

② 只在 ①④ 喂不饱时才展开：8/20、8/21 的 N≥3 视图里 `plan` 就是 `①=35 ④=12`，与今天的 v1 行为完全一致。

### 3.5 排序键

**JS 不实现排序键，只按 Python 给的名次 `o` 排。**

`CL.sort_key(c)` 是与段无关的公司全序，所以一个全局名次数组对所有段、所有 N、所有视图都成立。段内行序 = 先按 `o[c]` 升序，同公司内按 `(_recorded 降序, 标题)`。

**这条同时拆掉一颗雷**：`company_lane.sort_key` 实际是 `(不在priority, -prom, -tier, -窗口内岗位数, 公司名)`，而 **req2 §4.2 决策 4 的正文把它写成 `(不在priority, -tier, -prom, ...)` —— tier 和 prom 反了**。实测（`_pm_06_sort_trend.py`）当前语料上两种排序结果完全一致（5 档 N 下「第一个不同的位置」都是 `None`，top-20 重合 20/20），所以照正文实现**所有测试都会绿，等相关性变化时才慢慢歪掉**。发一个 `o` 数组，这个雷就不存在了。

**两个「7 天」不许混**（req2 §5.4）：`co[c][3]` 叫 `w7`，永远是固定 7 天判定窗口内的岗位数，不随 N 变。`JOB_INDEX.w7_days = 7`，表头文案由它拼成「近 7 天」，**数字与文案同源**。F25 断言 `payload["w7_days"] == CL.WINDOW_DAYS` 且 `"近 %d 天" % CL.WINDOW_DAYS` 出现在骨架里。

### 3.6 水位线：`● 新`、三视图、⑦ 段

窗口（N）与水位线正交，不合并（req2 §4.2 决策 5）。

- **`● 新`**：`(days[d], r) > cutoff`，纯比较。
- **三视图开关**（B1 的修法，替换 v1 的布尔开关，不是新增第二套机制）：

  | 值 | 谓词 | 语义 |
  |---|---|---|
  | `all`（默认） | 无 | 窗口内全部行 |
  | `new` | `(days[d], r) > prev_cutoff` | 上一期报告之后新增的 —— 就是带 `● 新` 的那批 |
  | `wm` | `prev_prev < (days[d], r) <= prev_cutoff` | 上一期摆在眼前的那批 |

  切换只影响**六个分段的行表与它们的计数**；趋势图、堆叠条、图例、面板②′/③、hero **始终描述整个窗口**（它们是窗口统计），开关旁边写明这一点。
  三个视图各自有完整的 `check[f][N]`（§3.10），`#selfcheck` 跑满 3 × 5 = 15 组。

- **⑦ 段**：一条与 N 无关的规则 —— **「上一期水位线区间内、落在 ①②④、且不在当前 N 天窗口里的行」**。实测 [T4]：N=1 给 83 行（正是窗口看不见的那些），N≥3 给 0 行，段自动变空并显示「上一期的行都在当前窗口内，用上面的『上一期未处理』视图」。一条规则，没有按 N 切换形态的分支。

  **由此产生一条必须写进加载策略的约束**：N=1 时 ⑦ 段的内容来自窗口外的天（实测跨 2 天）。加载器必须永远把 `JOB_INDEX.wm_days` 并进要加载的天集合，否则 ⑦ 段会安静地少行。

- 水位线本身仍然只在真实定时运行时推进（`dashboard.py` 现有逻辑，不动）。

### 3.7 分块与加载

- **一天一个块，按绝对日期命名。** 不用 req2 §5.5 的五个偏移块：偏移名每天全变、历史快照无法复用、且实测 30 块并行注入 **17.9 ms** 比五块的 20.2 ms 还快、比单文件 37.3 ms 快一倍。req2 §5.1 自身也不自洽（文件树写 `data-<day>-d0.js`，HTML 片段写 `data-latest-d0.js`），绝对命名消掉这个歧义。
- **首屏**：`latest.html` 静态引 `data-index.js` + `days` 最后 `n_default` 天 + `wm_days`，去重后 3-4 个文件，实测 0.26 MB。
- **切 N**：需要的天集合 = `days` 最后 N 天 ∪ `wm_days`，减去已加载的；对每个 `chunk[i] !== ""` 的天动态注入 `<script src>`；全部 `onload` 后重渲染。加载期间 N 选择器 `aria-busy="true"`。
- **`onerror` 不许静默**：某块失败 → 该天标记未加载、红条列出天名，且 §3.10 的第 4 条对账必然失败。空天（`chunk[i] === ""`）不注入，不算失败。
- **保留 30 天**：`--retain`（默认 30），`data-<day>.js` 超期即删。
- **每天早上重写**：`data-index.js` + 保留窗口内**全部**天块（外推 4.46 MB/天）。理由：段 `g` 与 `x` 都是拿生成日的 resolver 算的（实测漂移 12/2581 行，方向全是 B2→C；公司层面 13/1312 家），只有全部重算才自洽。冻结 + 补丁的方案见 §6 R5。
- 所有写盘 `tmp + os.replace`（OneDrive，req2 §7.3）。

### 3.8 骨架与预渲染 chrome（JS 只做行表）

Python 把自己算出来的**事实**渲染成静态 HTML 放进骨架：hero 四块、「N 家未分层」健康横幅、趋势 SVG、堆叠条 SVG + 图例（含 `<a href="#seg-...">`）、六个 `<details id="seg-..." data-gidx="0..5">` 的空壳与 summary 计数、⑦ 段空壳、面板②′、面板③、footer。

**JS 只负责往 `<details>` 的 body 里塞行表**，以及在切 N 时把上述区块整块换掉：

```js
JOB_INDEX.chrome["7"] = { trend:"<svg…>", stack:"<svg…>", legend:"…",
                          p2:"<tr>…", p3:"<tr>…", summ:"…", hero:"…" }
```

实测（`_pm2_03_size.py`，03:06）：5 档 N 合计 **29,896 B**（N=1 3.0 KB … N=30 10.2 KB）。这 30 KB 换来 `dashboard.js` 里**没有 SVG 渲染器、没有面板渲染器、没有 hero 渲染器**，`svg_trend` / `svg_stack` 直接复用 `dashboard.py` 现有代码（`TREND_DAYS` 改成参数）。

三个好处：R3 的第 1-3 步真的零 JS（锚点与 SVG 链接是静态 HTML）；JS 整个挂掉时页面仍显示所有 Python 算出来的数字（I9 的精神延伸到前端）；**F9 现有断言（`page` 以 `<!doctype html>` 开头、含 `家未分层`、含 `<details`）一个字都不用改**。

段容器定位（B2）：JS 用 `document.querySelector('[data-gidx="' + g + '"]')`，**不发 `seg_ids` 数组，JS 里不出现任何段 key 字符串**，段顺序保持 `CL.SEGMENT_ORDER` 单一事实来源。

### 3.9 JS 渲染与交互

**行表的列**（req2 §4.2 决策 4，v1 漏写）：

| 列 | 内容 | 备注 |
|---|---|---|
| 公司 | `T<tier>` 徽章 + `co[c][0]` | 徽章配数字，颜色不单独承载语义 |
| 岗位 | `<a href>` 标题 + `● 新` | 链接 = `lpre[lp] + l`（`lp < 0` 时直接用 `l`） |
| **日期** | `days[d]`（窗口视图必需） | N=1 时这一列隐藏；实测 N≥3 首屏横跨 3 天 |
| 来源 | LinkedIn / ATS 直连 / DDG | 由 `s` 查表 |
| 近 7 天 | `co[c][3]`，表头文案由 `w7_days` 拼 | **不是 N 天** |
| 信号 | `sigs[co[c][ s===0 ? 5 : 6 ]]` | 查表，不是判断 |

**渲染策略**
- 加载时只渲染 `open_plan` 指定的那 ≤47 行；折叠段的 summary 计数直接来自 `check`，不需要遍历行。
- 折叠段监听 `toggle`，**首次打开**才建表，建完标记 `dataset.rendered="1"`。
- 切 N / 切视图：所有段 body 清空并标记 dirty；当前 `open` 的段立即重渲染，折叠的等下次打开。实测 N=30 / 60000 行纯数据一趟 3.2 ms，全量重算计数没问题。
- 大段用 `documentFragment` 一次性 append；单段超过 2000 行时按 `requestAnimationFrame` 每帧 500 行分片。
- **分片必须带世代号（B8）**：每次 dirty 让 `gen++`；rAF 回调第一行 `if (myGen !== gen) return;`，直接丢弃剩余分片。否则切 N 时上一轮遗留的帧会往新容器里继续 append，产生重复行或乱序 —— 而这恰好落在 B3 指出的「没有对账层能看见」的区域。

**切 N / 切视图不重载，保持展开与滚动**
1. 记录每个 `<details id>` 的 `open`；
2. 记录当前视口最靠上的那个 `<details id>` 及其 `getBoundingClientRect().top`；**找不到就记 `document.scrollingElement.scrollTop` 的绝对值**（B6）；
3. 注入缺的块 → 重算 → 重渲染 → **先跑 §3.10 的五件对账** → 再恢复 `open` 与滚动；
4. 有锚点：`window.scrollTo(0, el.offsetTop - savedTop)`；无锚点：`window.scrollTo(0, savedTop)`。整个恢复过程包在 `try/catch` 里。
   **顺序是承重的**：对账在滚动恢复之前跑，任何滚动异常都不可能连累红条。

**锚点跳转（R3）**
- `<details id="seg-1a_t3" data-gidx="0">` 静态存在；堆叠条每个 `<rect>` 外包 SVG 原生 `<a href="#seg-1a_t3">`，图例同样。这三步零 JS。
- **点击走 click 处理器，不依赖 `hashchange`（B7）**：在容器上挂一个委托 `click` 监听，命中 `a[href^="#seg-"]` 就直接调 `openSegment(id)`；**不 `preventDefault()`**，hash 照常更新，前进/后退仍可用。`openSegment` 幂等：展开 → 若 dirty 则渲染 → `el.setAttribute("tabindex","-1"); el.focus({preventScroll:true})` → `el.scrollIntoView({block:"start"})`。
- `hashchange` 监听保留，只兜底「用户手改地址栏 / 前进后退」，调的是同一个 `openSegment`。
- CSS：`details[id]{scroll-margin-top:64px}`（顶部有 sticky 的选择器）、`:focus-visible{outline:2px solid var(--link);outline-offset:2px}`。

**N 与视图的持久化**
- **hash 只用于锚点，不放 N**（否则点一次堆叠条就把 N 冲掉）。
- N 与视图记在 `localStorage["dash.n"]` / `["dash.view"]`（实测 Chrome file:// 可用），读写 `try/catch`，取不到或不在 `n_choices` / `views` 里就用 `n_default` / `"all"`。
- 接受一次性覆盖 `#n=7`：解析后立刻把 hash 改回段锚点，不长期占用。

**控件**：N 选择器与视图选择器都是 `<div role="radiogroup">` + `<button role="radio" aria-checked>`，键盘左右箭头切换。不用 `<select>`（档位少，平铺一眼可见、一次点击到位）。

**`#selfcheck`**：`location.hash === "#selfcheck"` 时，对 3 视图 × 5 档 N 依次跑计数并对账，把 `{"all":{"1":{"ok":true,…},…},…}` 写进 `<pre id="selfcheck">`，不渲染表格。

### 3.10 `check` 与三层守卫

```js
check["all"]["7"] = {
  dedup: 2035,
  raw:   [97,151,634,90,692,371],      // 顺序 = CL.SEGMENT_ORDER
  cap2:  [75,136,502,74,641,198],
  plan:  [35,0,0,12,0,0],
  open:  47,
  bars:  [0,…,220,1646,169],           // 每天一根柱；Σ(窗口内) 必须 == dedup
  w7_days: 7,
  head:  [[28,17],[28,203],[29,4], …], // 首屏 ≤47 行的 [天下标, 行下标]，有序
  anchors: { "0": [[1,690],[0,107],[1,444]], … }   // 每段 cap2 head 的首/中/末（B3）
}
```

大小实测：`anchors` 6 段 × 3 坐标 × 5 档 = 973 B；`head` ≤47 × 15 组约 7 KB；计数部分约 3 KB。

**JS 渲染完做五件对账**，任一不过就在页面顶部显示红条（而不是安静少几行）：

1. `Σ raw == dedup` —— **I1 窗口版**
2. 自己数出来的 `raw` / `cap2` / `bars` 逐项等于 `check[f][N]`
3. 首屏渲染出的 `[天下标, 行下标]` 序列逐项等于 `check[f][N].head`
4. 每个应加载的天，`JOB_DAY[day].n == JOB_INDEX.nrows[i]`（块没加载 / 加载了旧块在这里现形）
5. **每段展开后**，该段 cap2 head 的首/中/末三行坐标等于 `check[f][N].anchors[gidx]`（B3：折叠段内部的行 identity 与顺序）

三层守卫：

| 层 | 谁断言 | 抓什么 |
|---|---|---|
| L1 | fixture 断言 `view.window_view(payload, n, f)` | I1 窗口版、cap2、open 闭式。**它吃的是 payload，不是 CSV** —— 序列化丢行也会被抓到 |
| L2 | 运行时 JS 的五件对账 | JS 的过滤/去重/分组/选行跟 Python 不一致 → 红条 |
| L3 | fixture F24 用无头 Chrome 跑真页面读 `#selfcheck` | L2 本身没接上、或某块没加载 |

这不是「双实现」：`check` 与 L1 断言的是**同一个函数的返回值**，Python 是唯一定义处，JS 复刻并被 L2/L3 逼着一致。「只在 JS 实现、Python 只给 check」的盲区是 `check` 自己没有任何 fixture 能断言，I1 的守卫直接归零。

**L3 有一个结构性局限（B11）**：F24 复用的正是 JS 里那份对账代码，对账函数自己写反时会和生产环境一起「自我印证」为 ok。唯一的解法是人工的故意破坏回归，列为 §5 第 10 条必做项。

### 3.11 Python 侧改动清单（函数签名级）

**`company_lane.py`：一行不动。`daily_report.py`：一行不动（I8 / F17）。**

**新增 `view.py`**（纯数据，零 HTML，零 I/O）。**这些函数与 `profile()` 同样是全函数：退化输入（空 `profiles`、空 `rows`、缺键的 `cap2`）下返回退化结果，不抛异常**（A5）：

```python
CAP = 2
OPEN_ORDER   = ("1a_t3", "B1", "1a_t2")
ALWAYS_OPEN  = ("1a_t3", "B1")
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
FLOOR        = 30
CEIL         = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)
N_CHOICES    = (1, 3, 7, 14, 30)
N_DEFAULT    = 3
VIEWS        = ("all", "new", "wm")
RETAIN_DAYS  = 30

def superseded_flags(rows, day) -> dict            # id(row) -> 0/1，作用域 _day <= day
def build_payload(day, rows, profiles, overrides, priority, state,
                  retain=RETAIN_DAYS) -> dict      # {"index": {...}, "days": {d: {...}}}
def window_view(payload, n, view="all") -> dict
        # -> {"dedup","raw","cap2","plan","open","bars","head","anchors","w7_days"}
        # check 的唯一来源，也是 fixture 断言的对象
def open_plan(cap2) -> (dict, int)
def openable(cap2) -> int
def open_expected(cap2) -> int
def encode_index(index) -> str                     # "window.JOB_INDEX={...};"
def encode_day(day, cols) -> str                   # "(window.JOB_DAY=...)[...]={...};"
```

**`dashboard.py`**：删掉 `CSS` 常量、`row_html`、`table_html`、`details`、`build()` 里拼行表的那部分；`svg_trend` / `svg_stack` 保留并把 `TREND_DAYS` 改成参数（chrome 预渲染要按 N 调用）。

```python
OPEN_CAP = view.SEG_OPEN_CAP     # 保留这个名字：tests/test_lane.py 现在 import 它
CAP      = view.CAP

def build_bundle(day, rows, profiles, overrides, priority, state,
                 retain=view.RETAIN_DAYS) -> (files, new_state, stats)
        # files: {"latest.html", "dashboard.css", "dashboard.js",
        #         "data-index.js", "data-<d>.js", ...}
        # stats: 保持现有键 raw/cap2/total/visible/unenriched/carry（按 N_DEFAULT、view=all）
        #        新增 by_n = {(view, n): window_view(...)}

def build(day, rows, profiles, overrides, priority, state):
        """兼容壳：返回 (files["latest.html"], new_state, stats)，签名一个字不改。"""

def render_shell(tpl, ctx) -> str      # 只做 <!--SLOT:*--> 字符串替换，无模板引擎
def main(argv=None)                    # 新增 --retain N；--out DIR 写整套 bundle 到该目录
                                       # 不再写 <day>.html
```

`group_segment` / `split_cap` 保留（`tests/test_lane.py` 直接 import），输入改成「窗口去重后的行」，函数本身不用改。

**`web/shell.html`**：新文件，`<!--SLOT:HERO--> <!--SLOT:BANNER--> <!--SLOT:TREND--> <!--SLOT:SEGMENTS--> <!--SLOT:PANELS--> <!--SLOT:FOOTER-->`。
**`web/dashboard.css`**：`dashboard.py` 的 95 行 CSS 常量逐字搬来，加 `scroll-margin-top` / `:focus-visible` / 两个 radiogroup / 红条 / `[aria-busy]`。
**`web/dashboard.js`**：新文件，经典脚本。

### 3.12 每个「不能超过 X」背后的机制

| 要求 | 机制（哪一行代码在保证） | fixture |
|---|---|---|
| 首屏 ≤ 47 行 | `open_plan` 里 `min(cap2, SEG_OPEN_CAP[s])`，补位段只补到 `FLOOR - used` | F11b：`open <= sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)`（派生，不写 47） |
| 首屏补到 30 行（有货就给够） | `open_plan` 的补位循环 | F11a：`open == view.open_expected(cap2)`（等式 + 属性测试）；F11b：`open >= min(FLOOR, openable(cap2))` |
| 每家公司每段 ≤ 2 条 | `split_cap(groups, cap=CAP)`，作用域是窗口不是天 | F11c：`len(window_head(day,n,s)) == cap2[s]` |
| 窗口内无重复岗位 | Python 预生成 `x`；JS 只会 `if (x[i]) continue` | F21：5 档 N 下无重复键且基数 == 真实去重 |
| 零丢弃（I1 窗口版） | `window_view` 的 `Σraw == dedup == Σbars` | F12（3 视图 × 5 档 N × 2 anchor）+ L2 第 1 条 |
| 首屏行本身不许错 | `check[f][N].head` 逐项比对 | F22 + F24 |
| 折叠段内部行不许错 | `check[f][N].anchors[gidx]` 首/中/末比对 | F22 + F24 + L2 第 5 条 |
| 判定不许漏到 JS | `co` 定长数组 + `data-gidx` 定位，判定词汇与段 key 都不出现在 JS | F23（去注释后 grep 黑名单） |
| 数据块没加载不许静默 | `nrows[i]` vs `JOB_DAY[d].n` + `onerror` 记账 | F24 |
| 判定窗口永远 7 天 | 字段名 `w7` + `JOB_INDEX.w7_days` 拼表头文案 | F25：`payload["w7_days"] == CL.WINDOW_DAYS` |
| 只存在一条去重规则 | 数据路径只用 `superseded_flags`；`CL.day_rows` 不再被使用 | F27 canary：两条规则每天选出的幸存行集合必须相同 |
| 磁盘不无限涨 | `--retain 30`，超期删 `data-<day>.js` | F26：跑两次不同 day 后目录里天数 ≤ retain |
| 切 N 时旧帧不许污染新容器 | rAF 世代号 `gen` | 人工验收第 6 条（30 天视图下连点 N） |

---

## 4. 测试推广方案

作用域只放宽，不放宽任何不变量。辅助函数改造：

```python
def window_counts(day, n, view="all", profiles=None, overrides=None, rows=None):
    """-> (raw, cap2, dedup_total)，来自 view.window_view(payload, n, view)。
    payload 由 view.build_payload 生成 —— 断言的是浏览器真正拿到的那份数据。"""

def segment_counts(day, **kw):          # 旧名保留，等价于 window_counts(day, 1)
    return window_counts(day, 1, **kw)

def window_head(day, n, seg, view="all")    # 旧 segment_head(day, seg) = window_head(day, 1, seg)
def expanded_rows(day, n=view.N_DEFAULT, v="all")   # = view.open_plan(cap2)[1]
```

**A3 的处理**：`segment_counts` 现在走 keep-NEWEST（与窗口视图同一条规则），所以 F6/F7/F19 与窗口 fixture 测的是同一件事，不再依赖「两条规则恰好同段」这个巧合。旧规则由 F27 canary 单独看着。

| fixture | 现在 | 改成 |
|---|---|---|
| F10 | 单日，段① head 全是 `is_entry` | 5 档 N × 2 天，同样断言；段① 非空的断言保留 |
| F11 `default_visible_is_bounded` | `1 <= vis <= 50` | **拆成三条**：F11a `open == view.open_expected(cap2)`（另加 2000 组随机 cap2 的属性测试）；F11b `min(FLOOR, openable) <= open <= sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)`；**字面量 50 删掉** |
| F11 `truncated_rows_are_folded_not_dropped` | 单日 | 5 档 N；`len(window_head(day,n,s)) == cap2[s]`，对 `SEG_OPEN_CAP` 里每段 |
| F12 `zero_loss` | 单日 `Σraw == total` | 3 视图 × 5 档 N × 2 天，且 payload 版：`Σ window_view(...).raw == .dedup == Σ .bars` |
| F12 `every_row_gets_exactly_one_segment` | 单日 | 对 payload 的 `g` 列断言 `0 <= g < len(CL.SEGMENT_ORDER)` |
| F19 `is_a_criterion_not_a_filter` | 单日 | 不动（`segment_counts` 别名保底），另加一条 5 档 N 版 |
| F9（三条） | `DASH.build(...) -> page` | `files = DASH.build_bundle(...)[0]; page = files["latest.html"]`。`家未分层`、`<!doctype html>`、`<details`、`stats` 三键断言**逐字保留**（骨架里就有这些） |
| `test_dashboard_has_no_external_dependency` | 断言 `"<script" not in page` | **方法名保留，body 换成 `assert_offline(files)`**（见下）。R4 必然要有 `<script`，但「离线双击可开」这个真不变量一条不放 |
| F17 / F16 / F15 / F14 / F8 / F5 / F4 / F3 | — | 一个字不改 |

**`assert_offline(files)`**（`_pm_06_sort_trend.py` §3 已写好并对 6 种攻击各试一遍，全部拦下）：

1. 任何文件里不出现 `type="module"` / `import x` / `export`；
2. `latest.html` 里每个 `src=` / `href=` 要么以 `#` 开头，要么**不含 `://`、不以 `/` 开头、不含 `..`**；
3. 任何 `.js` 里不出现 `fetch(` / `XMLHttpRequest` / `WebSocket` / `importScripts` / `EventSource` / `navigator.sendBeacon`；
4. `.js` 里所有 `X.src = ...` 的右值不含 `://`；
5. `dashboard.css` 里仍有 `prefers-color-scheme` 与 `a:visited`；`<details` 仍在。

实测拦截：CDN `<script>` ✓、Google Fonts `<link>` ✓、`type="module"` ✓、JS 里的 `fetch` ✓、注入绝对 URL ✓、`../` 越级 ✓。**不是空断言。**

**新增 fixture**

| # | 断言 | 为什么必须有 |
|---|---|---|
| F20 | `Σ 各天 payload 行数 == 保留窗口内 CSV 原始行数`，且逐天相等 | 序列化丢行现在完全没人看得见 |
| F21 | 5 档 N：payload 去重后无重复键且基数 == 真实 distinct 键数；另断言 `x` 是在 `_day <= day` 上算的（8/19、8/20 两个 anchor 各验一次） | **实测全局作用域会让 8/19 丢 10 行、8/20 丢 28 行** |
| F22 | `payload["index"]["check"][f][n] == view.window_view(payload, n, f)`，3 视图 × 5 档全对（含 `head` 与 `anchors`） | `check` 是 JS 唯一的真相来源，它自己必须被断言 |
| F23 | 去注释后的 `web/dashboard.js` 不含 `tier`、`prom`、`stage`、`kind`、`staffing`、`outsourcing`、`job_board`、`new grad`、`entry level`、`tnorm`（大小写不敏感），**也不含 `1a_t3` / `1a_t2`** | 把分工线从约定变成机制；后半段防 `SEGMENT_ORDER` 的硬编码副本（B2） |
| F24 | 找到 Chromium 可执行文件则 `--headless=new --dump-dom latest.html#selfcheck`，断言 3 视图 × 5 档全 ok；找不到 `skipTest` | JS 侧唯一的端到端断言。实测可行 |
| F25 | `payload["index"]["w7_days"] == CL.WINDOW_DAYS`，且 `"近 %d 天" % CL.WINDOW_DAYS` 出现在骨架里 | 两个「7 天」不许混 |
| F26 | 连跑两个不同 `--date` 后，输出目录里 `data-*.js` 的天数 ≤ retain | 保留策略没机制就会无限涨 |
| **F27** | **canary**：对每一天，`CL.day_rows(rows,d)` 选出的幸存行集合 == keep-NEWEST 在该日选出的集合 | **A3**：两条规则一旦分家要立刻知道，而不是让两套测试静默各测各的 |
| **F28** | 3 视图 × 5 档 N：`Σ check[f][n].raw == check[f][n].dedup`，且 `view="all"` 的 dedup ≥ 另两个 | **B5**：⑦ 段 / 视图开关这块新行为的 I1 |

**断言纪律**：没有一条写具体行数。要比较数值时右边一律从常量或另一次计算派生（`sum(SEG_OPEN_CAP…)`、`CL.WINDOW_DAYS`、`view.open_expected(...)`、`len(CL.day_rows(...))`），不是抄下来的数字。

---

## 5. 验收

在 `D:\OneDrive\work\school\project\Job`，Git Bash，`export PYTHONIOENCODING=utf-8`，解释器 `D:/Apps/Miniconda/envs/job-classifier/python.exe`。

1. `python tests/test_lane.py` **全绿**（基线 36 个：34 过 2 跳；新增 9 条后 45 个，F24 在无 Chromium 时跳过）。
2. **必须用 `.bat` 真跑一次**，不能只在已设好 UTF-8 的 shell 里跑：`cmd /c run_daily_report.bat`。
   **判定标准（B10）**：退出码 0；stdout/stderr 都不含 `Traceback`；`logs/dashboard/latest.html`、`data-index.js`、`data-<今天>.js` 的 mtime 是本次运行产生的。
3. `python -u dashboard.py --date 2026-08-20 --no-watermark --out <临时目录>` → 该目录是**自包含**的：`latest.html` / `dashboard.css` / `dashboard.js` / `data-index.js` / `data-*.js`，双击能开。
4. `logs/dashboard/` 里**没有 `<day>.html`**；`data-*.js` 的天数 ≤ 30。
5. **人真的双击 `logs/dashboard/latest.html`**（Edge，本机 `.html` 默认程序，注册表实测 `MSEdgeHTM`）。
   **这条不能只看代码，也不能只看 F24 绿 —— F24 只覆盖 Chrome，本机 Edge 无头实测产出 0 字节。** 双击后逐项：
   - 5 档 N 各切一次：不重载页面、去重正确、无红条；
   - 三个视图各切一次（全部 / 新增 / 上一期未处理）：计数变、无红条；面板②′③ 与趋势图**不随视图变**（它们描述整个窗口）；
   - **核对 `● 新`（B4）**：`新增` 视图里每一行都带 `● 新`；`全部` 视图里带 `● 新` 的行数等于 `新增` 视图的行数；
   - 切 N 前展开 ③ 段、滚到页面中部，切完 ③ 仍展开、位置仍在那一段；
   - **滚到面板②′（非 `<details>` 区域）再切 N**：不报错、不跳回顶部（B6）；
   - 点堆叠条每一段和图例每一项 → 跳到对应段并自动展开；**手动折叠后再点同一个 → 仍然展开**（B7）；
   - 键盘 Tab 到两个 radiogroup，左右键切换，`:focus-visible` 可见；
   - 断网（飞行模式）重新双击 → 一切正常。
6. **30 天视图下连续快速切 N 三次**：⑤ 段展开后行数等于 summary 里的 cap2，无重复行、无乱序（B8 的世代号）。
7. `latest.html#selfcheck` 双击 → `<pre id="selfcheck">` 3 视图 × 5 档全 `ok`。
8. **首屏行数**：在 08:00 那次真实定时产物上量，`open` 落在 `[min(30, openable), 47]`；把 `newgrad_classifications.csv` 复制一份改 `unique_id` 前缀灌进去（像 F5 那样）翻倍后重跑，仍落在同一区间。
9. **降级三连**（I9）：断网 / 删掉 `company_profiles.json` / 档案表是空 `{}` —— 三种情况下页面都能生成，`家未分层` 横幅出现，没有任何真实雇主进 ⑥ 段，**且 `view.build_payload` 与 `view.window_view` 都不抛异常**（A5）。
10. **故意破坏回归（B11，必做）**：手工改坏三处再打开页面，确认红条真的会亮 ——
    (a) 把 `check["all"]["3"].cap2` 里某个数字改错 1；
    (b) 把某个 `data-<day>.js` 里几个 `x` 位取反；
    (c) 把 `check["all"]["3"].head` 的坐标顺序打乱。
    三次都必须出现红条并指出是哪一条对账失败。**这是唯一能验证「对账代码本身没写反」的办法**（L3 会与生产代码一起自我印证）。
11. `daily_report.py` 逐字节未改（F17）；`git diff --stat daily_report.py company_lane.py` 为空。
12. `SCHEDULING.md` 第 204 行关于输出文件的描述已更新（不再有 `<day>.html`）。

---

## 6. 放弃的方案（rejected_alternatives）

| # | 方案 | 为什么放弃（实测） |
|---|---|---|
| R1 | 按 req2 §5.2 发 `k` 字符串，JS 自己去重 | 261 B/行里 `k` 约占 45 B；且幸存者随 N 变，JS 必须实现去重循环。换 `x` 位后 JS 连键都看不到，归一化漂移这个失败模式被结构消灭 |
| R2 | 保留 `unique_id` 字段 | 13.5 B/行，且 92.4% 的行里它就是 `job_link` 的尾段 |
| R3 | req2 §5.5 的五个偏移块 | 五块每天全重写、历史快照无法复用、块名依赖「今天是哪天」；30 个按日块注入实测 17.9 ms **比五块的 20.2 ms 还快** |
| R4 | 一个 30 天大文件 | parse 37.3 ms 也能接受，但没法按天保留/清理，OneDrive 每天重写一个 5 MB 文件 |
| R5 | 冻结按日块 + 每天发一个「判定补丁」文件 | 能把日写入量从 4.46 MB 降到约 0.25 MB（补丁只含约 0.5% 的 `g` 变更与 1.5% 的 `x` 变更）。放弃：补丁按块内位置对齐，错位就是**安静的错分段**。**若 OneDrive 同步真的开始烦人，这是第一个该做的优化** |
| R6 | 每行 `g` 由 JS 用 tier/is_entry 现算 | 直接违反分工线，把 I2/I3/I5/I6/I7 搬进没有 fixture 的地方 |
| R7 | 按公司发 4 项段查找表，行上只发 2 bit | 再省约 5 B/行，但要把 `is_entry` 的结果暴露给 JS，F23 黑名单就守不住了 |
| R8 | N 放进 URL hash | R3 要求堆叠条用 SVG 原生 `<a href="#seg-...">`，点一下就把 N 冲掉。改 localStorage + 一次性 `#n=7` |
| R9 | ⑦ 段按 N 切换形态 | 要在两处各写一套。改成不看 N 的规则，实测 N=1 给 83 行、N≥3 给 0 行，自己退化 |
| **R10** | **趋势柱用「按日去重」(`CL.day_rows`)** | **本轮删除。** 那会让两条去重规则同时活着（A3：45 组选出不同物理行，0 组跨段纯属巧合），还要一行脚注解释 2073 vs 2035。改成「窗口幸存者按天归属」后两个数字**是同一个数字**，且实测柱高与 N 无关 |
| R11 | 把 CSS/JS 内联进 HTML | 违反 R4「真 `.css` / `.js` 文件」；`<link>` / `<script src>` 在 file:// 下实测可用 |
| R12 | 用 `<select>` 做 N / 视图选择器 | 档位少，平铺一眼可见且一次点击到位 |
| R13 | 首屏也懒渲染 | 首屏 ≤47 行，排序实测 1.1 ms；懒渲染只会让页面打开时是空的 |
| R14 | 用 `ats_registry.json` 当 `BOARD_COMPANIES` | req2 §7.5 已实测只多 2 家 3 行 |
| R15 | 加「已投 / 已忽略」 | 用户 2026-08-21 明确否掉 |
| **R16** | **保留历史 `<day>.html`（不管冻结还是共享块）** | **A1。** 共享可变块方案实测 8/20 有 39/2072 行（1.88%）会被静默改判，而且 v1 的 L2 对账会让该页在漂移当天起**永久红条**；私有冻结拷贝方案要为每个保留日多存一份日块。改成不写历史页 —— 那 1.88% 的行一条没丢，只是用今天的判定显示；真要冻结快照用 `--out` |
| **R17** | **放开 ④ 的首屏天花板去补 FLOOR** | **A2 的另一半。** 那等于让「有自有 ATS board 的小公司」在 ①② 都空的那天独占 30 行首屏，正是 `OPEN_CAP` 当初要防的（req2 §3.3）。改成修正公布的下界定义 |
| **R18** | **为 B1 改默认 N（3 → 1）** | 实测 [T2]：N=1 首屏的**绝对新增行数**并不比 N=3 多（8/20 30 vs 29，8/21 11 vs 27），却少给 16-36 行存量。改成保留 N=3 + 一键「只看新增」，实测把日重复从 39-42% 压到 2.3-2.6% |
| **R19** | **为 B1 把排序键改成「新的排前面」** | 违反 req2 §4.2 决策 4「prom 主序不变」这条已定结论；而 req2 自己给的解法（日期列 + `● 新`）v1 漏实现，本轮补上就够 |
| **R20** | **为 B1 记住「这条上过首屏几次」** | 需要持久化用户/报告行为状态；用户 2026-08-21 否掉已投/已忽略，orchestrator 本轮明确重申 |
| **R21** | **面板②′/③ 与趋势图跟着三视图开关变** | 它们是**窗口统计**，跟着筛选变会让「中介占比」这类数字失去可比性；且 chrome 要从 5 份涨到 15 份。改成只跟 N 变、不跟视图变，并在开关旁写明 |

---

## 7. 自检清单（`docs/multiagent_design_build_loop.md` §0.5，交接文档版）

- [x] **哪些已定、哪些待议切开了**：§1 单列。判定层、I1-I9、六段判据、N 档位、分工线、`daily_report.py` 全部当约束，本轮一条都没重新设计。
- [x] **有「明确不做」一节，写清谁在什么时候否掉的**：§1 —— 已投/已忽略，用户 2026-08-21 否掉；R20 再次点名。
- [x] **规定了推翻既有结论的证据标准，并指出现成脚本在哪**：§0 每条 must-fix 都先跑评审的脚本复现再给修法；§8 是脚本索引。
- [x] **每条约束都写了为什么**：§3.12 每行有「机制」列；§6 每条 rejected 都有实测数字。
- [x] **每个数字标注了配置与时间**：§2 顶部一次性给出配置，[T1]-[T5] 全部来自 **03:07:49 的同一次运行**（A4 已修）；浏览器数字单列 [T6] 并标 Chrome 版本与参数。
- [x] **会过期的数字写清了怎么重测**：§8 给完整命令行；重跑 `_pm2_10_snapshot.py` 即可刷新。语料在第 1 轮的 18 分钟里从 2491 涨到 2581 —— 这就是没有一条断言可以写点值的现场证据。
- [x] **环境信息完整**：§2 顶部 + §5 给了解释器路径、环境变量与全部命令。
- [x] **每个「不能超过 X」背后有机制**：§3.12 一整张表；本轮把首屏的**下界**从一个假命题改成了可兑现的闭式（A2）。
- [x] **有没有把两件不同的事压成一件**：本轮找到并拆开五处 ——
  ① 两个「7 天」（判定窗口 vs 取景窗口）→ 字段 `w7` + `w7_days` 拼文案，F25；
  ② 「零外部依赖」被写成「零 `<script>` 标签」→ `assert_offline` 五条真断言，6 种攻击各试过；
  ③ **两条去重规则**（按日 vs 窗口）→ 本轮删到只剩一条，F27 canary 看着旧规则（A3）；
  ④ **「窗口」与「新鲜」**→ 拆成正交的 N 选择器与三视图开关（B1）；
  ⑤ **「首屏上界」与「首屏下界」**→ 上界是结构保证，下界是 `openable` 的函数，两者用不同的式子表述（A2）。

**我没能自己验证的一条**：Edge（真正的双击目标）无头在本机产出 0 字节，三种参数 × 两种输出方式全试过。所以 [T6] 在 Edge 上没有实测，只有「同属 Chromium 151、无 Edge 策略键」这个间接证据。**§5 第 5 条因此必须由人真双击一次。**

---

## 8. 复现脚本

全部在 `dashboard_loop/v2/`，用
`export PYTHONIOENCODING=utf-8; D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/<脚本>` 跑。

**本轮（第 2 轮）**

| 脚本 | 回答什么 |
|---|---|
| `_pm2_base.py` | 共用 loader + 修正后的 `open_plan` / `openable` / `open_expected` / 唯一去重规则 |
| `_pm2_01_fixes.py` | **A2**（50 万随机 cap2：旧下界违例 1931、新合同违例 0、闭式不符 0）；**A3**（两条规则差 45 组、0 跨段；一条规则下柱高与 N 无关且 Σ柱高 == dedup） |
| `_pm2_02_freshness.py` | **B1**（日重复率、首屏新增行数、三视图行数、开「新增」后重复率、首屏跨几天） |
| `_pm2_03_size.py` | 预渲染 chrome 5 档共 29.9 KB；**A1** 丢弃历史页的代价（10/287、39/2072）；**B3** anchors 973 B |
| `_pm2_10_snapshot.py` | **[T1]-[T5] 的唯一来源**，一次运行一个时间戳 |

**第 1 轮（仍然有效，本轮引用了它们的浏览器与编码结论）**

| 脚本 | 回答什么 |
|---|---|
| `_pm_base.py` / `_pm_01_window.py` / `_pm_02_anchor.py` | 窗口行数、I1、判定漂移、跨天重复、cap2 对 N 单调 |
| `_pm_03_payload.py` | 后缀嵌套证明（keep-NEWEST 可冻结）、E0-E4 编码 B/行、每列字节 |
| `_pm_05_fileproto.py` | **file:// 能力表实跑** |
| `_pm_06_sort_trend.py` | sort_key 的 tier/prom 倒置影响、`assert_offline` 的 6 种攻击测试 |
| `_pm_07_perf.py` | 60000 行 / 5 MB 在 Chrome file:// 下的 parse 与纯数据一趟耗时 |
| `_pm_08_chunks.py` | 按日 30 块 vs 五偏移块 vs 单文件 |
| `_pm_09_default_n.py` | 08:00 到货曲线 |

**评审的脚本（本轮全部亲自复现过）**

`_evalA_pinday_drift.py`（A1）、`_evalA_openplan_math.py`（A2）、`_evalA_daykeep_equiv.py`（A3）、`_evalB_hashclick.py`（B7）、`_evalB_repeat.py`（B1）。
