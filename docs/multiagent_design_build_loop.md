# Multi-Agent Design–Build Loop 架构规范

> 通用编排框架:不限于 dashboard,适用于任何"理解问题 → 设计方案 → 评审 → 实现 → 验证 → 交付"的 AI 编码任务(数据管道、API 功能、重构、ML 特征、报表等)。

---

## 0. 先读这一节:prompt 里"没写的东西"才是主要失败源

### 0.1 这是一类什么问题

多 agent 编排跑砸的时候,**很少是因为某个 prompt 写错了,几乎总是因为某个东西没写**。
Prompt 里每一处留白,agent 都会用一个默认值填上——而那个默认值通常是
"通用场景下最合理的做法",不是你这个项目实际需要的。

这类问题的共同特征:

- 每个 agent 单独看都表现良好,产出也像模像样
- 问题在**交界处**或**上线后**才暴露,而不是在评审里
- 事后看原因都很"显然",但当时没人问那个问题——因为**没人被要求去问**

### 0.2 为什么 LLM 特别容易踩这一类

| 机制 | 后果 |
|---|---|
| **不会留白** | 没规定的地方一定会被填上一个默认值,而且填得很自信 |
| **论证能力接近无限** | 能为几乎任何立场生成读起来很顺的理由,所以"讲得通"这件事**几乎不携带信息量** |
| **默认顺从** | 不明确授权它反对你,它倾向于接受你给的前提 |
| **在便利环境里验证** | 会在手边最容易跑通的环境里验,而不是目标环境 |
| **优化它看得见的指标** | 你写"目标 35 行",它会在设计时凑到 35 行,但不会去建立一个**让它永远不超过**的机制 |

### 0.3 五类缺失 × 本项目的真实案例

下面每一条都是这个项目真实发生过的,不是假想。

#### A. 缺范围边界:没说"什么已经定了"

- **案例**:第 3 轮设计时,orchestrator 必须在 prompt 里显式写
  「**不要再引入新机制,这一轮只做减法和收口**」。不写的话 PM agent 每一轮都在加东西——
  这不是它的错,是"设计 agent"这个角色的默认行为就是提出方案。
- **案例**:交接文档里有一个功能被用户明确否掉了。如果只是把它删掉而不写明"**明确不做**",
  下一轮 agent 看到相关证据(某个字段全空、某个痛点存在)几乎必然会再提一遍。
- **修法**:任何交接给新 agent 的需求文档,必须把**「要设计的」和「不要重新设计的」显式切开**,
  并单列一节「明确不做」,写清是谁在什么时候否掉的。

#### B. 缺证据标准:没说"推翻一条结论要拿什么当货币"

- **案例**:orchestrator 提出「分段用 tier 而不是 prom,因为 tier 是离散量,更不容易抖动」。
  听起来完全合理。PM agent 没有照做,而是跑了实测:**tier 三遍不一致率 4.9%,
  prom 是 4.4%——tier 反而更不稳**。orchestrator 的直觉是错的,而且错得很有说服力。
- 如果当时 prompt 里没有写「**反对我也要给证据**」,这个错误的前提百分之百会被采纳。
- **修法**:在每个 subagent 的 prompt 里写死证据标准——
  **推翻既有结论必须先跑脚本给反证,不接受纯论证**。同时明确授权它反对 orchestrator。

#### C. 缺断言标准:没说"验收该断言什么、在什么环境验"

- **案例(点值 vs 不变量)**:验收 fixture 写成 `raw 总数 == 931`。语料每天在涨
  (1018 → 1674 → 2072),这条断言**两小时后就过期了**。评估者抓到并修掉之后,
  同一类错误又在另外三条 fixture 上重演了一次。
- **案例(数字与规则来自不同配置)**:施工规格里写「正则大小写敏感」,
  但规格里所有数字都是在**不敏感**的配置下测出来的。照字面实现,首屏从 28 行掉到 9 行,
  而且规格自己列的样例有 8/12 过不了。两个评估者独立撞到同一处。
- **案例(在便利环境里验证)**:一个脚本往 stdout 打印非 ASCII 字符,
  在 cp1252 控制台下直接 `UnicodeEncodeError`。**三轮设计 + 四轮评审 + 36 条 fixture 全没抓到**,
  因为所有人(包括 orchestrator)都在已经设好 UTF-8 环境变量的 shell 里验证。
  第一次真的按定时任务的方式跑 `.bat`,立刻现形。
- **修法**:
  1. **断言不变性和结构性质,不要断言会随时间变化的点值**
  2. **规格里每个数字必须标注是在什么配置下测出来的**,规则和数字必须来自同一次运行
  3. **验收必须规定验证环境**,并且明确哪几条"必须真的跑一遍,不能只看代码"

#### D. 缺机制:把约束写成了目标

- **案例**:规格写「首屏 35 行左右」。这是一个**目标**,不是一个**机制**。
  设计时确实是 35 行,但采集量翻倍后变成 61 行、首屏 73 行——因为
  "每家公司最多 2 条"只约束单家公司,不约束总量。加了一条**强制截断**
  (超出部分进嵌套折叠)之后才真正锁住。
- **修法**:凡是"不能超过 X"的要求,都要问一句「**是什么机制在保证它?**」。
  如果答案是"设计的时候算了一下正好符合",那它迟早会漂。

#### E. 约束过简 / 角色边界过紧

这一类的特点是:**边界本身写错了,把两件不同的事压成了一件**。

- **案例(约束过简)**:「查询函数必须是全函数,永不抛异常」——这条约束本身是对的,
  但它导致「**还没处理**」和「**处理过但查无此人**」被编码成了同一个状态,
  而后者正是触发某个判定的条件。结果:上一版是响亮的 `KeyError`,
  这一版变成了**安静的错误结论**。修法是加一条:
  **"不许失败"类约束必须配一条"但不同的失败原因必须可区分"**。
- **案例(角色边界过紧)**:本文档 §1.6 原本写「orchestrator 只做编排,不做内容判断」。
  但实践中最有价值的一处发现是——**evaluator B 的两条建议自相矛盾**
  (它判某个模块不值得做,理由是产出全落在折叠区;而它自己力推的另一处改动
  恰好让那个产出进了首屏)。**两个 evaluator 各自都看不见,只有汇总者能看见。**
  这条边界如果照字面执行,就会漏掉一整类问题。§1.6 已据此修订。

### 0.4 交接文档 / prompt 的自检清单

写任何一份要交给新 agent 的需求文档或 prompt,发出去之前逐条过:

- [ ] 说清了**哪些是已定的、哪些是待议的**吗?
- [ ] 有没有一节写**明确不做什么**,以及是谁在什么时候否掉的?
- [ ] 规定了**推翻既有结论的证据标准**吗?(跑脚本 vs 讲道理)
- [ ] 明确**授权 agent 反对我**了吗?
- [ ] 验收断言的是**不变性**还是**会过期的点值**?
- [ ] 规定了**在什么环境验证**吗?哪几条必须真跑?
- [ ] 每个"不能超过 X"的要求,背后有**机制**还是只有**目标**?
- [ ] 有没有哪条约束把**两件不同的事压成了一件**?
- [ ] 文档里每个数字,标注了**是在什么配置/什么时间测出来的**吗?

---

## 1. 设计原则

1. **两层循环,而不是一条链。** "设计对不对"和"实现对不对"是两类完全不同的失败模式,修复成本也不同,必须分开处理:
   - **设计层循环(外循环)**:PM/Design ↔ Evaluator A/B。解决"方向对不对"。
   - **构建层循环(内循环)**:Engineer ↔ Tester/QA。解决"实现对不对"。
   - 只有当 Tester 判定问题是"设计缺陷"而非普通 bug 时,才从内循环穿透升级回外循环。
2. **评审必须独立、必须分工。** 两个 evaluator 如果用同一标准看同一份东西,是冗余;必须有不同的评审视角,且互相看不到对方的判断,由 orchestrator 统一汇总。
3. **状态是唯一事实来源。** Orchestrator 维护一份结构化共享状态(见第 4 节),每个 subagent 只拿到它需要的切片,不靠对话历史"传话"。
4. **反馈必须结构化。** Evaluator / Tester 的输出必须是可编程判断的结构(verdict + issues + severity),而不是自由文本,否则循环终止条件无法自动判断。
5. **必须有终止条件。** 没有 max_iterations 和收敛判据的循环,理论上会无限进行。
6. **Orchestrator 不做内容判断,但必须做交叉比对。**
   不要让顶层 agent 既写 PM 的 prompt、又亲自当 evaluator——那等于自己给自己打分。
   **但"不做内容判断"不等于"只做并集去重"**:两份独立评审之间的**互相矛盾**,
   两个 evaluator 各自都看不见,只有汇总者能看见(见 §0.3-E 的真实案例)。
   汇总时必须主动找三样东西:①两份报告独立收敛到同一处的发现(可信度极高,不必再自证);
   ②互相拆台的地方;③一份报告内部自相矛盾的地方。
7. **必须规定证据标准。** Agent 能为任何立场生成读起来很顺的论证,
   所以"讲得通"几乎不携带信息量。**推翻既有结论必须跑脚本给反证,不接受纯论证**;
   同时要**明确授权 subagent 反对 orchestrator**,否则它默认顺从(见 §0.3-B)。
8. **必须声明范围边界。** 每份交给 subagent 的材料都要把
   **「要设计的」和「不要重新设计的」显式切开**,并单列「明确不做」(见 §0.3-A)。
9. **约束要写成机制,不能只写成目标。** "不超过 X"背后必须有一个强制它的机制,
   否则它会随输入规模漂走(见 §0.3-D)。

---

## 2. 角色定义

| 角色 | 职责 | 不该做的事 |
|---|---|---|
| **Orchestrator**(你/顶层 agent) | 维护共享状态、生成各 subagent 的 prompt、路由决策(继续循环 / 通过 / 升级人类)、**交叉比对多份评审(找独立收敛 / 互相拆台 / 内部矛盾)**、最终生成 summary report | 不替 evaluator 判对错,不做代码质量判断。但**不能只做并集去重**——见 §1.6 |
| **PM / Design Agent** | 基于真实数据/需求理解问题,提出结构化设计方案 | 不写代码,不做最终评审 |
| **Evaluator A(需求契合度)** | 评审设计是否真正解决了问题、是否覆盖真实数据里的 edge case | 不评价代码可实现性 |
| **Evaluator B(技术可行性)** | 评审设计是否可实现、可维护、符合代码规范、性能可接受 | 不评价产品价值 |
| **Engineer Agent** | 按已批准设计实现代码,不重新设计 | 发现设计矛盾时不要擅自改设计,应上报 `design_defect` |
| **Tester / QA Agent** | 运行测试、验证实现是否匹配设计与原始需求 | 区分清楚是 `bug`(内循环修)还是 `design_defect`(外循环修) |

可选:**Evaluator C(对抗/红队)**——专门找边界情况和攻击面,适合高风险任务。

---

## 3. 整体流程

```
Context/Intake(真实数据/代码库检查,不是靠模型脑补)
        ↓
   ┌─────────────────────── 外循环(设计层)───────────────────────┐
   │  PM/Design → Evaluator A + B(并行独立) → 汇总 → 有 must-fix? │
   │        ↑__________________________revise_____________|      │
   └────────────────────────────↓(通过)───────────────────────────┘
        ↓
   ┌─────────────────────── 内循环(构建层)───────────────────────┐
   │  Engineer → Tester/QA → bug?    → 回 Engineer               │
   │                       → design_defect? → 回外循环(带缺陷报告)│
   │                       → pass → 结束                          │
   └────────────────────────────↓───────────────────────────────┘
        ↓
   Summary Report(基于共享状态自动汇总生成)
```

---

## 4. 共享状态 Schema(Orchestrator 维护)

```json
{
  "task_id": "string",
  "original_requirement": "string,不可更改,每轮都完整提供给 PM 和 evaluator",
  "context": {
    "data_summary": "真实数据探查结果,不是猜测",
    "codebase_notes": "相关代码规范/架构约束",
    "tool_access": ["PM: 数据查询工具", "Engineer: 代码执行/测试工具", "..."],
    "constraints": ["技术栈", "性能要求", "风格规范"]
  },
  "design_iterations": [
    {
      "version": 1,
      "design": "设计文档全文或引用",
      "evaluator_A_feedback": { "verdict": "fail", "issues": [ { "severity": "must_fix", "description": "...", "suggested_fix": "..." } ] },
      "evaluator_B_feedback": { "verdict": "conditional_pass", "issues": [] },
      "merged_decision": "revise",
      "rejected_reason_summary": "一句话"
    }
  ],
  "approved_design": "最终批准的设计文档",
  "impl_iterations": [
    {
      "version": 1,
      "diff_summary": "本轮代码改动概述",
      "qa_feedback": { "verdict": "fail", "defect_type": "bug", "details": "..." }
    }
  ],
  "final_output": "最终交付物描述/链接",
  "status": "in_progress | design_escalated | impl_escalated | completed"
}
```

**要点**:传给 PM/Evaluator/Engineer 的 prompt 只截取相关字段的**摘要**,不要把整个 state 全量塞进去——既省 token,也避免无关信息干扰判断。原始 `original_requirement` 是唯一不能被摘要或改写的字段,必须逐字传递。

---

## 5. 各 Subagent Prompt 模板

### 5.1 PM / Design Agent

```
# Role
你是产品设计 agent。任务是分析问题并提出可执行的技术方案设计,不写代码。

# Ground Truth Requirement(逐字提供,不可改写)
{original_requirement}

# Context
- 真实数据/代码库探查结果:{context.data_summary}
- 可用工具:{context.tool_access}
- 约束条件:{context.constraints}

# 范围边界(必填,见 §0.3-A)
- **本轮要设计的**:{open_questions}
- **不要重新设计的(已定,是约束不是待议项)**:{settled_decisions}
- **明确不做**:{out_of_scope} —— 由 {who} 在 {when} 否掉,不要自作主张加回来

# 证据标准(必填,见 §0.3-B)
- 你**可以**推翻上面任何一条已定结论,但**必须先跑脚本给出反证**。
  只讲道理不算 —— 你能为任何立场写出读起来很顺的理由,所以论证本身不构成证据。
- **我(orchestrator)给的建议是靶子,不是结论。** 同意要给证据,反对也要给证据。
  实践中我提过的建议被实测驳回过,照做反而会错。
- 设计文档里**每个断言背后要有一条实测**。不要写"预计效果良好"这种没有数字的话。
- **每个数字都要标注是在什么配置、什么时间测出来的** —— 规则和数字必须来自同一次运行。

# 历史(仅在第 N>1 轮提供)
- 上一版设计:{previous_design}
- Must-fix 反馈(必须逐条回应):{must_fix_issues}
- Nice-to-have 反馈(可选择性采纳,说明理由):{nice_to_have_issues}
- 之前被否决的方案及原因(避免重复犯错):{rejected_alternatives_summary}

# 任务
1. 用你自己的话复述你理解的问题(用来核对是否踩了之前的坑)
2. **先跑脚本验证你的关键假设,再动笔。** 把实测结果贴进文档
3. 给出设计方案:目标 / 方案描述 / 关键决策与理由 / 已知 tradeoff / 待澄清的开放问题
4. 每个"不能超过 X"的要求,写清**是什么机制在保证它** ——
   如果答案是"设计时算了一下正好符合",那它会随输入规模漂走,不算数(见 §0.3-D)
5. 若为修订版本,逐条说明你对每个 must-fix 做了什么改动
6. 明确列出你**放弃的方案和放弃原因**(进 rejected_alternatives,供后续轮次避坑)

# 输出格式
按上述结构化输出,不要自由发挥格式。
```

### 5.2 Evaluator(A / B 共用模板,替换 persona 和 rubric)

```
# Role
你是独立评审 agent,视角:{evaluator_persona}
你看不到设计者的推理过程,只看到最终设计文档和原始需求——保持客观、挑剔,不要因为文档写得"有道理"就照单全收。

# Ground Truth Requirement
{original_requirement}

# 待评审设计
{design_doc}

# 评审标准(rubric,必须逐条检查)
{explicit_criteria_list}

Evaluator A(需求契合度)示例 rubric:
- 是否完整覆盖原始需求的每一条?
- 是否有遗漏的边界情况(基于真实数据分布,不是假设)?
- 是否存在更简单/更稳妥的替代方案?

Evaluator B(技术可行性)示例 rubric:
- 方案是否可在当前代码库/技术栈下实现?
- 是否有明显的性能/可维护性风险?
- 是否符合既有代码规范?

# 通用检查项(所有 evaluator 都要过,来自 §0.3 的真实教训)
- **复现**:设计里的数字你自己跑一遍对不对?对上的也要说,别只挑刺
- **点值 vs 不变量**:验收断言里有没有会随时间/数据量过期的写死数字?
- **数字与规则是否同源**:文档里的规则和数字是不是在同一次运行下得到的?
  (真实案例:规格写"大小写敏感",但所有数字是在不敏感下测的,照字面实现直接崩)
- **目标 vs 机制**:"不超过 X"背后有强制机制吗,还是只是设计时正好符合?
- **约束是否过简**:有没有哪条约束把两件不同的事压成了一件?
  (真实案例:"永不抛异常"导致"还没处理"和"处理过但查无此人"变成同一个状态,
  把一次响亮的崩溃换成了安静的错误结论)
- **验证环境**:验收有没有规定在什么环境验?有没有哪条是在便利环境里验、
  但真实环境会翻车的?

# 边界(见 §0.3-A)
- 已定结论清单:{settled_decisions} —— 对这些提 must_fix 必须附实测反证,
  只讲道理的一律降级为 nice_to_have
- 另一位 evaluator 的分工:{other_evaluator_scope} —— **不要重复它的工作**

# 输出格式(结构化,不要自由文本评价)
{
  "verdict": "pass | fail | conditional_pass",
  "issues": [ { "severity": "must_fix | nice_to_have", "description": "...", "suggested_fix": "..." } ],
  "summary": "一句话总结"
}

注意:文风、措辞等非实质性问题不给 must_fix;只对影响正确性/完整性/可行性的问题给 must_fix。
```

### 5.3 Engineer Agent

```
# Role
你是工程实现 agent。基于已批准设计编写代码,不重新设计。

# 已批准设计(唯一实现依据)
{approved_design}

# Context
- 代码规范:{context.constraints}
- 可用工具(含运行/测试):{context.tool_access}

# 任务
1. 按设计实现代码
2. 自行运行测试/验证基本正确性
3. 如果发现设计本身有遗漏或矛盾、无法在不违背设计意图的前提下实现:不要擅自修改设计,明确输出 design_defect 报告,交由外循环处理

# 输出
- 代码变更
- 自测结果
-(如有)design_defect 报告:{ "type": "design_defect", "description": "...", "impact": "..." }
```

### 5.4 Tester / QA Agent

```
# Role
你是测试验证 agent。检查实现是否匹配已批准设计与原始需求,并跑测试。

# 已批准设计 / 原始需求 / 本轮代码变更
{approved_design} / {original_requirement} / {diff}

# 任务
1. 运行测试,报告结果
2. **在真实环境里真的跑一遍,不能只看代码。** {real_env_steps}
   —— 真实案例:三轮评审 + 36 条 fixture 全没抓到一个编码崩溃,
   因为所有人都在已经配好环境变量的 shell 里验证;第一次按定时任务的方式跑,立刻现形。
   **凡是"用户实际怎么用"和"我怎么方便验证"不一致的地方,都要按前者验一次。**
3. 判断问题类型:
   - bug:实现没有正确落地设计里已经写清楚的东西 → 打回 Engineer
   - design_defect:设计本身就没考虑到的情况(设计遗漏/矛盾)→ 升级回外循环
4. **跑不绿的 fixture 不许改期望值来凑绿。** 如果你确信是期望过期(点值型断言,
   数据量变了),明确说出来:哪条、期望多少、实际多少、你判断是代码错还是期望过期、依据是什么
5. 给出结构化判定

# 输出格式
{
  "verdict": "pass | fail",
  "defect_type": "bug | design_defect | null",
  "details": "..."
}
```

---

## 6. 模型选择建议

| 角色 | 关键能力需求 | 建议 |
|---|---|---|
| PM / Design | 处理模糊需求的深度推理、数据理解 | 用最强推理能力的模型,给足上下文和真实数据访问权限 |
| Evaluator A/B | 独立批判性判断 | 不同 rubric/persona 解决的是**覆盖面**(看到更多类别的问题),不是**可靠性**——如果背后是同一个模型,仍会共享同一套判断盲点和自我认同偏差(self-preference bias)。要降低同源偏差,需要用不同模型做 evaluator,或对同一个 evaluator 做多次独立评审取一致性;至少要让 evaluator 看不到 PM 的推理过程,只看最终产物 |
| Evaluator C(可选红队) | 找边界/攻击面 | 用擅长挑刺、对抗性 prompt 风格的配置,而不是"温和评审"式配置 |
| Engineer | 代码生成 + 工具调用(能跑/能测) | 用代码能力最强的模型,给运行/测试工具权限,降低创造性、强调"照设计实现"而不是"重新设计" |
| Tester/QA | 测试生成、执行、故障诊断 | 与 Engineer 类似,但重点是执行工具 + 判断力(区分 bug vs design_defect) |
| Orchestrator | 状态维护、路由决策 | 简单路由(是否继续循环)可以用轻量模型/规则判断;"是否收敛""如何合并冲突反馈"这类判断建议仍用强模型 |

**核心原则**:生成者和评审者不要"长得太像"——同一个模型自己写、自己评,容易一路自我确认下去。

### 6.1 覆盖面 vs 可靠性:两个容易混的目标

两个 evaluator 用不同 rubric 买到的是**覆盖面**——避免单个 evaluator 因为要检查的东西太多而每样都看得浅。它买不到**可靠性**——如果 A、B 背后是同一个模型,它们仍然共享同一套训练出来的判断倾向和盲点,包括对同源模型产出天然更宽容这种自我认同偏差。这两件事要用不同的杠杆解决,不要混在一起:

| 想要什么 | 该用的手段 |
|---|---|
| 覆盖更多类别的问题 | 给 evaluator 不同 rubric/persona(本文档默认做法) |
| 降低单次判断的偶然错误 | 同一个 evaluator 跑多次取一致性(self-consistency) |
| 降低同源模型的系统性盲点 | 用不同厂商/架构的模型做 evaluator(成本最高,但唯一真正打破同源偏差的办法) |
| 主动找隐藏的边界情况/攻击面 | 加一个不参与打分、专门唱反调的红队角色(见 Evaluator C) |

如果场景对"评审判断本身有多可信"要求较高(比如高风险变更),只做 rubric 分工是不够的,需要再加一层可靠性手段。

### 6.2 已确定的模型 / effort 配置(Claude Code)

以下是本项目实际采用的配置。`model` 用系列别名(而不是写死某个具体版本号),因为别名本身就会跟随该系列的最新版本;`effort` 按角色的瓶颈是"推理深度"还是"工具执行"来分配,不是一律拉满。

| Subagent | model | effort | 理由 |
|---|---|---|---|
| PM / Design | `opus`(该系列最新) | `high` | 瓶颈是推理深度——处理模糊需求、综合真实数据 |
| Evaluator A/B | `sonnet`(该系列最新) | `high` | 挑刺需要认真核对 rubric,不能走捷径 |
| Engineer | `opus`(该系列最新) | `medium` | 用最强代码能力的系列,但任务本身偏"照设计实现",不需要拉满推理强度 |
| Tester/QA | `haiku`(该系列最新) | 不设置(继承主对话) | 主要是执行 + 简单判定,不是深度推理任务 |

对应的 `.claude/agents/` frontmatter:

```yaml
# .claude/agents/pm-design.md
---
name: pm-design
description: 分析真实数据/需求,提出结构化设计方案。不写代码。
model: opus
effort: high
tools: Read, Grep, Glob, Bash
---
```

```yaml
# .claude/agents/evaluator-product-fit.md
---
name: evaluator-product-fit
description: 独立评审设计方案的需求契合度,不评价可实现性。
model: sonnet
effort: high
tools: Read, Grep, Glob
---
```

```yaml
# .claude/agents/evaluator-feasibility.md
---
name: evaluator-feasibility
description: 独立评审设计方案的技术可行性,不评价产品价值。
model: sonnet
effort: high
tools: Read, Grep, Glob, Bash
---
```

```yaml
# .claude/agents/engineer.md
---
name: engineer
description: 按已批准设计实现代码,不重新设计。
model: opus
effort: medium
tools: Read, Edit, Write, Bash, Grep, Glob
---
```

```yaml
# .claude/agents/tester-qa.md
---
name: tester-qa
description: 运行测试,验证实现是否匹配已批准设计,区分 bug 与 design_defect。
model: haiku
tools: Read, Bash, Grep, Glob
---
```

注意:`model: opus` 这类别名解决的是"给角色配对的能力档位",不是第 6.1 节说的同源偏差问题——PM 和 Engineer 都用 opus、两个 evaluator 都用 sonnet,它们仍然是同一个模型家族。如果要真正降低 evaluator 的同源偏差,需要在 Claude Code 之外接入其他厂商的模型。

---

## 7. 循环控制逻辑(伪代码)

```python
state = init_state(requirement)
MAX_DESIGN_ITERS = 4
MAX_IMPL_ITERS = 3

# 外循环:设计
for i in range(MAX_DESIGN_ITERS):
    design = call_PM(state)
    fb_a = call_Evaluator_A(state, design)   # 并行、互相不可见
    fb_b = call_Evaluator_B(state, design)
    merged = merge_feedback(fb_a, fb_b)      # orchestrator 汇总冲突意见
    state.log_design_iteration(design, fb_a, fb_b, merged)
    if merged.verdict in ("pass", "conditional_pass") and not merged.has_must_fix():
        state.approved_design = design
        break
else:
    escalate_to_human("design loop did not converge", state)
    return

# 内循环:构建
for j in range(MAX_IMPL_ITERS):
    impl = call_Engineer(state.approved_design, state)
    qa = call_Tester(state.approved_design, impl)
    state.log_impl_iteration(impl, qa)
    if qa.verdict == "pass":
        state.final_output = impl
        state.status = "completed"
        break
    elif qa.defect_type == "bug":
        continue   # 只打回 Engineer,不惊动 PM
    elif qa.defect_type == "design_defect":
        state.rejected_alternatives.append(state.approved_design)
        # 带着缺陷报告重新进入外循环(可复用上面的外循环逻辑)
        design_loop_with_defect_report(qa.details, state)
        break
else:
    escalate_to_human("implementation loop did not converge", state)
    return

generate_summary_report(state)
```

---

## 8. Summary Report 模板

```
# Summary Report:{task_name}

## 1. 原始需求

## 2. 设计迭代历史
| 版本 | 核心思路 | Evaluator A 反馈 | Evaluator B 反馈 | 结果 | 本轮修改点 |

## 3. 最终批准设计

## 4. 实现与验证历史
| 版本 | 变更概述 | QA 结果 | 问题类型 | 修复方式 |

## 5. 最终交付物描述

## 6. 已知局限 / 后续建议

## 7. 附录:被否决方案及原因(供未来任务参考,避免重复踩坑)
```

---

## 9. 与原方案的差异对照

| 原方案的问题 | 本方案的改动 |
|---|---|
| implement 后循环边界不清("要不要回 design"不明确) | 拆成外循环(设计)/内循环(构建),用 `bug` vs `design_defect` 明确路由 |
| 两个 evaluator 分工不清 | 明确拆成需求契合度 / 技术可行性两个视角 |
| evaluator 可能互相锚定 | 强制并行、独立评审,orchestrator 统一汇总 |
| PM 和 evaluator 可能同源偏差 | 区分覆盖面(不同 rubric)与可靠性(不同模型/self-consistency)两个目标,分别用不同手段解决,不能靠换 persona 一次搞定(见 6.1) |
| prompt 缺历史/缺 ground truth/缺工具权限 | 状态 schema 显式包含,每轮完整传入 |
| 反馈是自由文本,无法程序化判断 | 强制结构化输出(verdict + issues + severity) |
| 没有终止条件 | max_iterations + 升级人类兜底 |
| orchestrator 角色模糊 | 明确只做编排/路由/状态维护,不做内容判断 |
| 只有一个 evaluator 时注意力被稀释、盲点难被发现 | 加 rubric 分工解决注意力稀释(覆盖面);盲点问题靠 self-consistency 或跨模型验证(可靠性),不是单纯加数量就够 |

---

## 10. 实现方式:从 spec 到可执行

第 4-7 节是**规范**(prompt 模板 + state schema + 控制流),本身不会跑。要让它自动执行,常见三种路径:

| 方式 | 适合场景 |
|---|---|
| 手写脚本(直接调用模型 API,用 tool use 强制结构化输出,state 存成 JSON 文件) | 角色少(如本文档的 5 个)、循环逻辑不复杂——第 7 节伪代码基本可以直接翻译成代码。多数场景应该先从这里开始。 |
| LangGraph(节点 = 角色,边 = 条件路由,原生支持循环和状态持久化) | 角色会持续增多、需要长期运行/断点续跑、需要给非工程师看可视化流程图时,再切换过去。 |
| Claude Code subagents(在 `.claude/agents/` 定义角色 + 工具权限) | 想在日常编码交互里半自动跑,自己盯着每一轮结果手动决定要不要继续——它没有原生的"没通过就自动重跑"能力,循环控制得在主对话里手动完成。 |

对本文档描述的规模,优先选手写脚本;等真正遇到 LangGraph 解决的那类问题(角色暴增、要断点续跑、要可视化)再迁移过去,不必现在就上框架。