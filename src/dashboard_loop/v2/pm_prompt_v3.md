# 第 3 轮(最后一轮,MAX_DESIGN_ITERS=3):定向修订,不是重做
Evaluator B 对 v2 判 **pass**(0 must_fix)。Evaluator A 判 conditional_pass,A1-A5 全部 closed,剩 **1 条 must_fix:A6**。
这一轮**只允许改 A6 涉及的段落和采纳下面的 nice-to-have**,其余内容逐字保留。不要引入任何新机制。

# Must-fix A6(`dashboard_loop/v2/evalA_v2.json`)
`check[f][N].anchors` 每段只取首/中/末 3 个坐标,实测 ③ 506 行、⑤ 673 行、⑥ 198 行下覆盖率 1.8% / 1.3% / 4.6%;且 §5.10 故意破坏回归没有一项破坏大折叠段中间的行序。
评审建议:(a) 每段发一个对 head 完整 [天下标,行下标] 序列的廉价顺序校验和(滚动哈希/异或),JS 渲染后比对 → 覆盖率 100%,字节几乎不增;(b) §5.10 加第 4 项:互换 ⑤ 段中间任意两行坐标,确认红条。
**要求**:两者都做。校验和算法要在 Python 与 JS 两边逐字等价、只依赖整数运算(避免浮点/字符串编码差异),在文档里写出伪代码,并用脚本证明:Python 对 5 档 N × 3 视图 × 6 段算出的校验和,与一个用同样伪代码独立实现的函数结果一致;互换任意两行必改变校验和(跑若干随机互换证实)。字节成本实测。

# Nice-to-have(采纳即可,均为文档级)
- A7 / B2-2(两位评审独立撞到同一处):验收第 12 条加上 `dashboard.py` 模块 docstring 第 9 行,并给出 grep 判定标准。
- A8:B4 的措辞改成「●新 第一次有了可对账的计数」,不要暗示两条独立机制互证。
- B2-1:F23 加一条针对「段序字符串字面量数组」形状的正则(如 `\["1a_t3"` / `'1a_t3'`)。
- B9-residual:hero 卡片标题自带「全部窗口」限定词,不只靠开关旁一行小字;把 B 量出的 99 vs 7 写进文档作为理由。

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


# 输出
把 v2 复制为 `dashboard_loop/v2/design_v3.md`,只做上述改动(开头「对评审的逐条回应」加一节 v2→v3),脚本放 `_pm3_*.py`。
最终回复:文档路径 + 改了哪些节 + 校验和实测结果 3 行。不改任何已有仓库文件。
环境同前:D:/OneDrive/work/school/project/Job,`export PYTHONIOENCODING=utf-8`,D:/Apps/Miniconda/envs/job-classifier/python.exe。
