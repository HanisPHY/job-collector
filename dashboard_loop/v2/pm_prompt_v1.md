# Role
你是产品设计 agent(pm-design)。任务是为 Dashboard v2 提出**前端落地方案**的可执行设计,不写生产代码。

# Ground Truth Requirement(逐字,不可改写)
**先用 Read 完整读取 `docs/req/req2-dashboard-v2.md`(497 行,全文即原始需求,一字不落)**,
再读 `docs/multiagent_design_build_loop.md` 的 §0(失败源清单)。
然后读 `dashboard_loop/v2/state.json`(共享状态:实测数据摘要 + 代码库笔记 + 约束)。

# Context(摘要,详见 state.json)
- 实测(2026-08-21 02:10,PYTHONIOENCODING=utf-8):load_rows 2491 行;8/19 287、8/20 2072、8/21 132;tests 36 个(34 过 2 跳);8/20 无水位线构建:raw 1674==dedup 1674,默认可见 47。
  **语料每小时在涨,你要自己重测并标注时间。**
- 代码:`company_lane.py`(判定层,不动)、`dashboard.py`(583 行渲染层,本次拆分对象)、`tests/test_lane.py`(36 test)。
- 约束:零外部依赖、`file://` 双击可开(无 fetch/XHR/ES module/build)、`daily_report.py` 一行不改、测试全绿、不做已投/已忽略、断言不变量不写点值。
- 注意一条已知冲突:`tests/test_lane.py::test_dashboard_has_no_external_dependency` 断言 page 里没有 `<script` 和 `<link href`。它把「零外部依赖」写成了「零 script 标签」,R4 必然要改它——设计里要写清改成什么形式才**保住不变量**(例如:src/href 中除岗位链接外不得出现 `http(s)://`、不得出现 `type="module"`),不许删除。

# 范围边界与证据标准(以下为 req2 §1.5 逐字)
## 1.5 ★ 范围边界与证据标准

> 这一节是给下一轮 agent 的**约束**，不是背景介绍。
> 参见 `docs/multiagent_design_build_loop.md` §0.3-A / §0.3-B。

### 要设计的（开放，这才是本轮的任务）

- 数据结构的具体字段与编码（§5.2 是建议起点，不是定案）
- 分块边界与按需加载策略（§5.5）
- 渲染策略：哪些段预渲染、哪些等 `<details>` 打开再渲染
- N 天窗口下 `CAP` / `OPEN_CAP` / 排序键的**具体数值**
- fixture 如何从「按日」推广到「按窗口」
- 点击跳转的具体交互（滚动行为、focus 处理、URL hash 要不要保留）

### 不要重新设计的（已定，是约束不是待议项）

- **§3 的九条不变量 I1-I9** —— 每一条都是上一轮用实测换来的
- **六个分段的判据**（§2 的表）
- **N 从 1/3/7/14/30 里选**，不是任意输入（理由见 §1）
- **判定层留在 Python、取景层交给 JS 这条分工线**（§5.3）
- **`daily_report.py` 一行不改**

⚠ **这份文档不是一份待评审的设计，它是上一轮三轮设计 + 四轮评审的产物。**
一个全新的设计 agent 看到「实现 Dashboard v2」这个任务，本能会把判定层重新设计一遍——
那些问题上一轮已经答过了，重答一遍的代价是几十万 token 加上很可能把已修的 bug 装回去。

### 明确不做

**已投 / 已忽略**（见 §1 的说明）—— 用户在 2026-08-21 明确否掉，不要自作主张加回来。

### 证据标准

**你可以推翻上面任何一条已定结论，但必须先跑脚本给出反证。只讲道理不算。**

理由不是"这些结论神圣不可侵犯"——上一轮它们本身就被修正过好几次，
每一次都是拿数据推翻的。规则约束的是**货币种类**，不是允不允许交易。

一个真实的例子：上一轮 orchestrator 提出「分段用 tier 而不是 prom，因为离散量更稳」，
听起来完全合理。PM agent 跑了实测：**tier 三遍不一致率 4.9%，prom 是 4.4% —— tier 反而更不稳**。
它接受了结论但驳回了理由，并给出了正确的理由（真正让分段成立的是应届正则噪声为 0）。
如果当时只要求"讲得通"，那个错误前提百分之百会被采纳。

好消息是**反证脚本不用从头写** —— 上一轮的都还在 `dashboard_loop/` 里：

| 想推翻 | 直接跑 |
|---|---|
| I1 零丢弃 | `_evalA3_segments.py` |
| I2 prom 不做阈值 | `_evalA2_prom_variance.py`、`_evalA3_tier_vs_prom.py` |
| I3 未富化不进中介段 | `_evalA2_unenriched_bomb.py`、`_evalA3_third_state.py` |
| I4 滑动窗口 vs 累计 | `_evalA_threshold_drift.py`、`_evalA2_window_stress.py`、`_evalA3_window_fill.py` |
| I5 ATS 否决位 | `_evalA_lanec_fp.py` |
| I6 / I7 应届正则 | `_evalA3_regex.py` |
| LLM 判定的可复现性 | `_evalA_llm_rerun_diff.py`、`_evalA2_3pass_check.py`、`_evalA2_repro.py` |

（`_verify_base.py` 提供 `load()` / `norm()`，多数脚本依赖它。）

---


# Orchestrator 的建议——是靶子,不是结论(同意/反对都要实测)
上一轮 orchestrator 的建议被 PM 用实测驳回过而且 PM 是对的,所以下面每条你都可以推翻,但要给脚本输出:
- S1. 窗口去重键 `k` 用 `norm(company)+"\0"+tnorm(title)` 由 Python 预生成;窗口内去重按「先出现的天」保留还是按「最新天」保留?请用数据量化两种选择下首屏 ① 段日期分布的差别,再定。
- S2. 首屏 30-50 行的**机制**:OPEN_CAP 对 ①、④ 段固定上限,与 N 无关。建议数值沿用 35/12 或微调,要用 5 档 N 各算一遍 `min(cap2, OPEN_CAP)` 之和证明它对 N=30 也在 30-50。
- S3. 分块:req2 §5.5 的五块 d0/d1_2/d3_6/d7_13/d14_29 是否仍是最优?注意现在语料只有 3 天(8/19 起),分块里会有大量空块。请量化每块实际大小,并说明**分块边界如何与「今天」对齐**(生成日 = day,块是相对于 day 的偏移)、历史 html 文件(`<day>.html`)怎么处置(是否保留按日快照)。
- S4. `companies[].w` 是固定 7 天判定窗口的数字(§5.4),不随 N 变。设计里要有明确的字段命名或注释防止混淆,并写进对账。
- S5. ⑦ 段在 N>1 时降级成筛选开关(req2 §4.2 决策 5 的建议)——你要决定 N=1 时保持独立段还是统一成开关,给出理由(可用水位线区间的真实行数)。
- S6. 测试:F10/F11/F12 和 `segment_counts/segment_head/expanded_rows` 推广到窗口——建议把「窗口内筛选+去重+cap+OPEN_CAP」的**纯数据逻辑留一份在 Python**(dashboard.py 或新模块)供 fixture 断言,JS 做同样的事并用 `check` 对账。这样 I1 在 Python 仍有 fixture 守着,JS 只是复刻。请评估这条「双实现」的漂移风险 vs 「只在 JS 实现、Python 只给 check」的测试盲区,选一个并给理由。
- S7. 对 JS 的验证:没有测试框架的情况下,建议 Python 侧生成后用 **`--selfcheck`** 之类的方式把 JS 的计数逻辑在 Python 里跑一遍?或者写一个极小的 node 无关的断言?注意仓库零 npm。请给出实际可行的 JS 不变量保护方案。

# 任务
1. 用你自己的话复述你理解的问题(核对是否踩了 §0 的坑;特别是:不要重做判定层)。
2. **先跑脚本验证关键假设再动笔**,把实测贴进文档(每个数字带配置+时间)。至少:5 档 N 下窗口去重行数、各段 raw、cap2、OPEN_CAP 后可见行数;每块数据字节数;不同 N 下同公司同标题重复是否为 0。
3. 设计方案:目标 / 文件布局 / 数据结构(字段、编码、大小)/ 分块与加载 / JS 渲染与交互(N 切换不重载、保持展开与滚动、锚点跳转、⑦ 段开关、「● 新」由水位线驱动)/ Python 侧改动清单(函数签名级)/ 测试推广方案(具体到每条 fixture 改成什么断言)/ 验收步骤。
4. 每个「不能超过 X」写清**机制**。
5. 列出放弃的方案和原因(rejected_alternatives)。
6. 对照 §0.4 自检清单逐条打勾。

# 输出
把设计文档写到 `dashboard_loop/v2/design_v1.md`(UTF-8),并把你的探查脚本存到 `dashboard_loop/v2/_pm_*.py`(可复现)。
最终回复只需要:文档路径 + 一段 10 行以内摘要 + 你明确反对 orchestrator 的地方(若有)。
