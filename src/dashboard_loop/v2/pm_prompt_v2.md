# Role
你是产品设计 agent(pm-design),这是**第 2 轮修订**。不写生产代码。
**这一轮只做减法和收口:不要再引入新机制,除非某条 must-fix 没有新机制就无法关闭。** 每条 must-fix 逐条回应(接受→改什么;反对→跑脚本给反证)。

# Ground Truth Requirement(逐字)
重新 Read `docs/req/req2-dashboard-v2.md` 全文(不要依赖上一轮的记忆)。

# 上一版设计与评审
- 你的 v1:`dashboard_loop/v2/design_v1.md`
- Evaluator A(数据与不变量):`dashboard_loop/v2/evalA_v1.json`,脚本 `_evalA_*.py`
- Evaluator B(真实使用与可维护性):`dashboard_loop/v2/evalB_v1.json`,脚本 `_evalB_*`
两位 evaluator 互相看不到对方;以下是 orchestrator 的交叉比对结果。

# Must-fix(必须逐条回应)
1. **A1 — PIN_DAY 历史页共享可变块会漂移(已用数据证实)**:`2026-08-20.html` 钉 08-20,但共用的 `data-2026-08-20.js` 每天按新生成日重写 x/g,28 行被错标为已取代、12 行 B2→C 静默改判,而 08-20 的 index/check 不再更新。这正是你自己量出的「x 必须按 `_day<=anchor` 算」同一机制。二选一并写清机制:(a) 每天的运行给自己的 `<day>.html` 留私有冻结拷贝;(b) 明确承认历史页「尽力而为」并给出过期处理(或干脆不再保留历史 `<day>.html`,只留 `latest.html`——这是减法,请量化代价)。
2. **A2 — open_plan 下界不变量为假**:`open >= min(FLOOR, supply)` 在 supply=Σ原始 cap2 的定义下不成立(反例 cap2={①:0,④:1000,②:0} → open=12;随机 50 万组 0.39% 违例)。上界 ≤CEIL 成立。要么把 supply 重定义为「各段截断后能贡献的量」(评审已验证恒等成立),要么改 open_plan;注意后者会和 ④≤12 天花板冲突,你要二选一并说明 F11b 的断言写成什么。
3. **A3 — `segment_counts(day)==window_counts(day,1)` 的等价是巧合不是机制**:`dedup_rows`(source 顺序先到先得)与 keep-NEWEST 在 3 天里选出 45 组不同的物理行,只是目前恰好同段。F6/F7/F19「一字不改」不能建立在这上面。加 canary 断言(每天两种策略幸存行集合相同,不同则明确失败)或改为让单日视图也走同一条去重规则,说明取舍。
4. **B7 — 同 hash 再点不触发 `hashchange`(Chrome 实测)**:用户手动折叠后再点同一堆叠条/图例 = 静默无效。改成 click 处理器直接调用展开逻辑,`hashchange` 只兜底地址栏/前进后退。
5. **B1 — FLOOR 买到的是数量不是新鲜度**:默认 N=3 下 8/20→8/21 首屏 42/47 相同,15 条岗位连续三个早晨都在首屏。**边界提醒(orchestrator)**:req2 §1 已记录「窗口视图下同一条岗位会连续 N 天出现」是已知后果,且用户仍在 2026-08-21 否掉了已投/已忽略——所以**不许引入任何需要持久化用户状态的机制**。你可以:把这个权衡写进设计并维持默认 N=3;或用数据重新论证默认 N;或用纯水位线/纯派生的方式(不存用户行为)做轻量区分——三者任选,给实测。

# Nice-to-have(选择性采纳,说明理由)
A4 数字非同一快照(29/151/20 vs 评审复测 38/177/29);A5 view.py 函数应声明为全函数并纳入降级三连;B2 SEGMENT_ORDER 未发给 JS(建议 `data-gidx` 或 `seg_ids`,并把段 key 纳入 F23);B3 折叠段内部无 identity 对账(建议每段抽样锚点进 check);B4 「● 新」无任何测试/人工检查点;B5 `check_wm`/⑦ 段/筛选开关无 fixture;B6 视口无 `<details>` 时滚动恢复的 fallback;B8 rAF 分片切 N 需要世代号;B9 `panels[N]` 算了但 §4.8 没说 JS 怎么用;B10 `.bat` 验收判定标准;B11 Engineer 提醒——验收前做一次「故意破坏」回归(改错 cap2/翻 x 位/打乱 head)确认红条真会亮。
B3/B8 叠加成同一盲区,优先考虑。

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


# 环境
仓库 D:/OneDrive/work/school/project/Job;Git Bash;`export PYTHONIOENCODING=utf-8`;解释器 D:/Apps/Miniconda/envs/job-classifier/python.exe。不改任何已有仓库文件,新脚本放 `dashboard_loop/v2/_pm2_*.py`。

# 输出
写 `dashboard_loop/v2/design_v2.md`:**完整的、可独立交给 Engineer 的设计文档**(不是增量 diff——Engineer 只会读 v2),开头加一节「对 v1 评审的逐条回应」(must-fix 5 条 + nice-to-have 采纳/不采纳及理由),并更新 rejected_alternatives。
最终回复只给:文档路径 + ≤10 行摘要 + 你反对评审/orchestrator 的地方。
