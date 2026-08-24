# 第 2 轮评审(Evaluator A)
你上一轮的 prompt(`dashboard_loop/v2/evalA_prompt_v1.md`)里的角色、反角色、rubric、通用检查项、输出格式**全部继续有效**,这里不重复;但请重新 Read 一遍它,以及重新 Read `docs/req/req2-dashboard-v2.md` 全文(不要依赖记忆)。

# 待评审
`dashboard_loop/v2/design_v2.md`(766 行,**完整规格,Engineer 只读这份**)。开头有「对 v1 评审的逐条回应」。新脚本 `dashboard_loop/v2/_pm2_*.py`。

# 这一轮重点
1. 你上一轮每条 must_fix:是否真的关闭?关闭方式是否引入新问题?逐条给 closed / not_closed / closed_with_new_issue。
2. 你上一轮的 nice_to_have:PM 声称全部采纳,抽查核实。
3. **v2 的新改动要当新设计审**(orchestrator 标出的疑点,请用脚本证实或证伪):
   - 趋势柱改为「窗口幸存者按天归属」—— v1 自己在 R10 里以「8/19 柱子会随 N 变」为由否掉过它,v2 又说柱高与 N 无关且 Σ柱高==dedup。哪个对?为什么 keep-NEWEST 下按天归属能与 N 无关(提示:嵌套窗口 + 幸存者是全局最新)?构造/实测验证,包括 anchor 不是今天的情况。
   - **不再写历史 `<day>.html`**:这是减法,但 req2 §5.1 文件布局没有明确要求历史页,v1 现状每天写一份。有没有任何地方(run_daily_report.bat、tests、SCHEDULING.md、用户习惯)依赖 `logs/dashboard/<day>.html`?grep 一下。
   - 三选一筛选(全部/新增/上一期未处理)全部由水位线派生——确认零持久化用户状态,确认与「明确不做已投/已忽略」不冲突;`check[f][N]` 三档 × 5 档 N 的对账是否每格都有 Σraw==dedup。
   - `anchors` 字段(折叠段行 identity 抽样)覆盖面与成本。
   - Python 预渲染每档 N 一份非行表 HTML(5 份)—— 切 N 时怎么换、切筛选时不换(R21),用户会不会误读。
4. 仍然按通用检查项过一遍:点值 vs 不变量(特别是新 F11 两条、F27 canary)、数字同源(v2 说统一为 03:07:49 快照,抽查)、目标 vs 机制、约束过简、验证环境。

# 范围边界与证据标准(req2 §1.5 逐字,这一轮重申)
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

# 另一位 evaluator 的分工
Evaluator B 负责真实使用/状态保持/可维护性/JS 侧测试保护/file:// 行为。你负责数据与不变量、复现数字、去重/零丢弃/两个 7 天/I1-I9/fixture 的不变量性。

# 环境 / 输出
仓库 D:/OneDrive/work/school/project/Job;Git Bash;`export PYTHONIOENCODING=utf-8`;解释器 D:/Apps/Miniconda/envs/job-classifier/python.exe。不改已有文件;脚本放 `dashboard_loop/v2/_evalA2_*`。
JSON 写到 `dashboard_loop/v2/evalA_v2.json`(同 v1 格式,另加 `"v1_followup": [{"id":"..","status":"closed|not_closed|closed_with_new_issue","note":".."}]`)。最终回复只给 verdict + must_fix 条数 + 一句话。
