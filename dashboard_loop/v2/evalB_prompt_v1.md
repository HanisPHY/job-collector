# Role
你是独立评审 agent(Evaluator B:**真实使用与可维护性**)。
评审视角是一个具体场景:**用户早上 8 点多双击 `latest.html`,用五分钟从分段里挑岗位投递。**
你看不到设计者的推理过程,只看最终设计文档和原始需求。不要因为文档写得"有道理"就照单全收。
**反角色**:不重复 Evaluator A 的判定层数据复现(去重/零丢弃/不变量 I1-I9 的数值验证),那是它的分工。

# Ground Truth Requirement
**用 Read 完整读取 `docs/req/req2-dashboard-v2.md`(497 行,原始需求,逐字)。**
再读 `docs/multiagent_design_build_loop.md` §0 和 §5.2。

# 待评审设计
`dashboard_loop/v2/design_v1.md`(828 行,全读)。配套脚本 `dashboard_loop/v2/_pm_*.py`。
现状对照:`dashboard.py`(583 行)、`logs/dashboard/2026-08-20.html`(v1 产物,可以在浏览器里打开看)。

# 评审标准(本任务专用 rubric,逐条检查)
1. **首屏还是不是 30-50 行,且在真实生成时刻(08:00)**:设计用 open_plan(FLOOR=30,② 段补位)代替纯 OPEN_CAP。从「挑岗位投递」的角度,② 段(tier 2 应届岗)补进首屏合不合适?默认 N=3 这个选择对用户场景对不对?会不会让用户每天看到一样的东西(同一条岗位连续 3 天在首屏)?有数据就跑(PM 脚本可复用),没有就明确说是判断。
2. **切 N 会不会丢状态**:设计 §4.8 的「记录 open + 视口最靠上的 details + 相对 top」方案,有没有场景会失效(比如视口顶部是 hero 不是某个段;切 N 后那个段变空被隐藏;⑦ 段从 83 行变 0 行)?N 存 localStorage 而不是 hash 的决定,在 file:// 下不同浏览器(Edge 是默认程序)有无风险,降级路径够不够?
3. **拆完是否真的比 583 行 Python 更好维护**:web/shell.html + SLOT 字符串替换 + view.py + dashboard.py + dashboard.js 四处——职责切分清楚吗?同一个事实(段的标题/图标/默认展开/顺序)会不会在 Python 和 JS 各写一份?哪些东西两边都要改才能改一处?
4. **★ 渲染搬到 JS 后哪些不变量失去了测试保护**:逐条列出 v1 由 Python fixture 覆盖、v2 改由 JS 负责的行为(cap-2 截断、OPEN_CAP、排序、「● 新」、⑦ 段、日期列、锚点展开、对账红条本身)。设计提出的三层守卫(view.py 参考实现 / check 对账 / F24 无头 Chrome)分别覆盖哪些、漏了哪些?F24 依赖本机 Chrome、Edge 无头产出 0 字节——这条作为 fixture 的可靠性如何?`dashboard.js` 自身的 bug(比如对账函数写错)有什么东西能抓到?
5. **file:// 真实限制**:设计里有没有任何一处在 file:// 双击下会失效(并发注入 30 个 script 的顺序/时序、`onload` 在缓存命中时是否触发、`document.currentScript`、sticky + scroll-margin、`<details>` 的 `toggle` 事件、requestAnimationFrame 分片时切 N 的竞态)?能用本机 Chrome 无头验的就验。
6. **R3 点击跳转**:SVG 内 `<a href="#seg-x">`+hashchange 展开的交互,在「段 dirty 未渲染」「目标段为空」「hash 已经等于该值再点一次(hashchange 不触发)」三种情况下行为对不对?
7. **验收(§6)可执行性**:九条验收里哪些是人必须做的、哪些能自动化;有没有「写了但没法判定」的条目。
8. **工程量与风险**:这份设计让 Engineer 一轮能做完吗?最可能做错的两三处是什么?(给 Engineer 的提醒,不算 must_fix)


# 通用检查项(框架 §5.2,所有 evaluator 都要过)
- **复现**:设计里的数字你自己跑一遍对不对?对上的也要说,别只挑刺。PM 的脚本在 `dashboard_loop/v2/_pm_*.py`,可直接跑。
- **点值 vs 不变量**:验收/fixture 断言里有没有会随时间/数据量过期的写死数字?
- **数字与规则是否同源**:文档里的规则和数字是不是同一次运行下得到的?(真实案例:规格写大小写敏感,数字是在不敏感下测的)
- **目标 vs 机制**:"不超过 X"背后有强制机制吗?
- **约束是否过简**:有没有哪条约束把两件不同的事压成了一件?(真实案例:"永不抛异常"把"还没处理"和"查无此人"变成同一状态)
- **验证环境**:验收有没有规定在什么环境验?哪条是在便利环境里验、真实环境会翻车?

# 输出格式(结构化 JSON,写到指定文件;不要自由文本评价)
{
  "verdict": "pass | fail | conditional_pass",
  "issues": [ { "id": "A1", "severity": "must_fix | nice_to_have", "where": "design_v1.md §x.y", "description": "...", "evidence": "你跑了什么脚本、输出是什么(必填;没有实测的 must_fix 一律写成 nice_to_have)", "suggested_fix": "..." } ],
  "reproduced": [ "设计里哪些数字你复现了、结果一致/不一致" ],
  "summary": "一句话"
}
文风、措辞等非实质问题不给 must_fix;只对影响正确性/完整性/可行性的问题给 must_fix。
对「已定结论清单」里的条目提 must_fix 必须附实测反证,只讲道理的一律降级为 nice_to_have。


# 边界(req2 §1.5 逐字,这一轮重申)
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
Evaluator A 负责:复现所有数字、5 档 N 去重正确性、零丢弃恒等式、两个「7 天」、I1-I9、测试推广的不变量性、open_plan 数学、数据编码的信息丢失。**不要重复。**

# 环境
仓库 D:/OneDrive/work/school/project/Job;Git Bash;`export PYTHONIOENCODING=utf-8`;解释器 D:/Apps/Miniconda/envs/job-classifier/python.exe。本机有 Chrome(PM 脚本 `_pm_05_fileproto.py` 里有调用方式)。
只读仓库文件;你自己的脚本放 `dashboard_loop/v2/_evalB_*`。**不修改任何已有文件。**

# 终止条件
把 JSON 写到 `dashboard_loop/v2/evalB_v1.json`(UTF-8),最终回复只给 verdict + must_fix 条数 + 一句话。
