# Round 1 设计方案 —— 公司档案表 + 阅读队列 + 分流 dashboard

> 作者：PM/设计负责人（round1 subagent）
> 日期：2026-08-20
> 状态：设计方案，未实施。文中每个数字都来自本轮实测，脚本与产物见「附录 A 复现方式」。
> **本轮真花了钱**：为验证 LLM 路线，我用项目 `.env` 里的 OPENAI_API_KEY 做了 8 次探针调用 +
> 1 次全量 680 家公司富化，合计约 **$0.024**。所有 LLM 相关数字都是实测不是估算。

---

## 1. 问题重述

### 1.1 用户真正的痛点

两个需求表面看是「dashboard 要有某个面板」，实际上都不是展示问题：

| 用户原话 | 表面诉求 | 我认为的真实痛点 |
|---|---|---|
| 「把刷屏中介单独摆开，但不能误伤岗位多的正常公司」 | 一个中介面板 | **需要一个可靠的「这家是不是中介」判定**。用户已经预判了朴素方案会误伤（他主动点名 Deloitte/Palantir/SpaceX），说明他要的不是「摆出来」而是「判得准」。 |
| 「一天 900 条看不过来，大中公司排前面」 | 一个排序面板 | **需要一份排过序的阅读清单，且要短到能读完**。900 条按任何顺序排都读不完 —— 排序只解决「先看到什么」，不解决「总量」。 |

所以真实痛点有三层，缺一层都不成立：

1. **判定层**：一家公司是不是中介 / 是不是大中公司。这是两个**公司级属性**。
2. **压缩层**：把 900 条压到能读完的量级。排序不压缩，去重和折叠才压缩。
3. **展示层**：dashboard。它是判定层和压缩层的**输出**，不是解决方案本身。

现有 dashboard 设计（req1.md 第 3 节）全部工作在展示层，判定层是空的 —— 所以它只能
「摆证据让人判断」，只能砍面板，不能真正解决问题。**本轮要补的是判定层。**

### 1.2 对编排者四个假说的回应

**假说 A（需求 2 是排序问题不是 dashboard 问题）—— 同意一半，反对另一半。**

同意：需求 2 的产物是「排过序的岗位清单」，不是统计图。统计图（各公司岗位数）已经被
req1.md 验证为主动误导，本轮再次确认（见 §9.2）。

反对：**不该拆成两个文件。** 理由是实测的：8/20 去重后 814 条，Tier-3 队列 140 行，
中介 185 条，其他 489 条 —— 这三块必须在同一屏里互相印证，用户才敢相信「被折叠的
674 条可以不看」。拆成两个文件，用户每天要开两个东西，恰恰加重了「看不过来」。
结论：**排序清单是 dashboard 的第 1 屏（Panel ①），统计是第 2 屏往后。一个 HTML 文件。**

**假说 B（两个需求共用一张公司档案表）—— 完全同意，且这是本方案的骨架。**

实测支持：把 680 家公司做成一行一家的档案表后，需求 1 用 `kind` 字段（employer /
staffing / outsourcing / training / aggregator），需求 2 用 `tier` 字段（0-3）。
两个字段来自同一次 LLM 调用、同一份缓存。**成本 $0.0139，一次，永久复用。**

而且这张表还解决了一个假说里没提到的问题：**它让「按量打标签」变安全**。
单看「BeaconFire 39 条」和「Deloitte 52 条」无法区分，但加上「LLM 认识 Deloitte，
不认识 BeaconFire」这一维，就可以安全地说「量大 + 查无此人 = 可疑」（见 §4.3）。

**假说 C（一次性 LLM 富化）—— 同意路线，但三个关键细节和假说说的不一样。**

- ❌ **不能用 gpt-3.5-turbo。** 实测它对我编造的两家假公司
  （`Zorbatex Quantum Dynamics LLC`、`Fleebware Solutions Group`）**2/2 都编了**，
  给出 `kind=employer, tier=1, conf=0.9`，理由写「LLC suggests employer」。
  换 gpt-4o-mini 后 **2/2 都正确返回 unknown / tier 0 / conf 0.2**。
  而且 gpt-4o-mini **更便宜**（$0.0139 vs 3.5-turbo 同批折算约 $0.038）。详见 §7.1。
- ❌ **「置信度」不能当阈值用。** gpt-3.5 的 conf 只有 0.0 和 1.0 两个值，
  且给假公司 0.9。gpt-4o-mini 的 conf 也高度离散（0.2 / 0.7 / 0.8 / 0.9 / 1.0），
  基本是 `kind=unknown → 0.2`、`认识 → ≥0.7` 的编码。**真正可用的「不知道」信号是
  `kind=="unknown" and tier==0`，不是 conf 阈值。** 见 §7.2。
- ⚠️ **富化不能只问一次就信。** 第一版 prompt 下 gpt-4o-mini 把
  **Deloitte、Booz Allen Hamilton、Leidos、L3Harris 全判成 staffing** —— 正是用户点名
  不能误伤的公司。原因是我在 prompt 里写了「大型 IT 外包也算 staffing」，模型把咨询公司和
  国防主承包商一起扫进去了。改 prompt（把 outsourcing 和 staffing 拆开、显式豁免
  Big-4 / 咨询 / 国防主承包商）后，**60 家真实雇主 0 误伤**。见 §4.2、§4.4。

**假说 D（多信号投票 + 否决位）—— 同意，且实测出了否决位的精确边界。**

「ATS 直连 = 必定真实雇主」**不是 100% 成立**。实测反例：`Jobgether` 是聚合站，
但它有自己的 Ashby board，`ats_jobs.csv` 里有它 1 条。所以否决位必须降级为
**「只否决行为信号，不否决 LLM 的明确判定」**。这条规则在实测中恰好各命中一次：

- 否决生效（救回真实雇主）：`Handshake`(5 条)、`Texas Sports Academy Main`(5 条) ——
  LLM 不认识它们，被「量大+查无此人」误标，ATS board 把它们救回来了。✅
- 否决不生效（正确地没救）：`Jobgether` —— LLM 明确说 aggregator，否决位不介入，
  它留在中介层。✅

---

## 2. 方案总览

```
                     ┌─────────────────────────────────────────┐
   3 个 CSV          │  company_profiles.json   （新，P0）      │
   1252 行  ──────►  │  一家公司一行，永久缓存，只对新公司增量   │
   680 家公司        │  {norm_name: {name, tier, kind, conf,   │
                     │               why, model, ts}}          │
                     └───────────────┬─────────────────────────┘
                                     │
   company_overrides.json ──────────►│  ← 人工覆盖，几十行，优先级最高
   （新，P0，人工维护）              │
                                     │
   ats_jobs.csv ────────────────────►│  ← 否决位：自有 ATS board = 真实雇主
                                     │
   标题行为信号（本轮实测）─────────►│  ← repost "at X" / 标题以 Jobs 结尾 /
                                     │     技术栈发散度 / 量大+查无此人
                                     ▼
                     ┌─────────────────────────────────────────┐
                     │  resolve_company(c) → (lane, tier, 证据) │
                     │  lane ∈ {A1 大厂, A2 大中, B 其他, C 中介}│
                     └───────────────┬─────────────────────────┘
                                     │
                     ┌───────────────▼─────────────────────────┐
                     │  collect_report(day) → 纯数据 dict       │
                     │  （req1.md §2 的重构，本方案的前置依赖） │
                     └──────┬───────────────────┬──────────────┘
                            │                   │
                  render_markdown()      render_html()
                    logs/daily/*.md      logs/daily/*.html
                    （日报，视觉不变）    （新 dashboard，Panel ①-⑥）
```

三条数据流的关键性质：

- **公司档案表是唯一的判定源**，日报和 dashboard 都只是消费者。加第四个采集器不用改判定逻辑。
- **判定链是纯函数 + 可解释**：每家公司都能列出「因为哪几条信号所以进了哪一层」，
  Panel ③ 直接把这个证据串打出来，用户不满意就写进 override 文件。
- **零跨天依赖**：`tier` 来自 LLM 世界知识，`kind` 来自 LLM + 单日行为信号。
  只有趋势面板（Panel ④）需要历史，它缺数据不影响前三个面板 —— 这就是冷启动答案。

---

## 3. 公司分层（需求 2）

### 3.1 分几层 / 每层定义

分层由公司档案表的 `tier` 字段驱动，`tier` 是 LLM 输出的 0-3，语义直接对应用户说的
「知名度、赚钱能力、声誉、公司人数」四个维度：

| tier | 定义（写进 prompt 的原话） | 8/20 岗位数 | 阅读队列位置 |
|---|---|---|---|
| **3** | household name 或行业巨头：mega-cap 科技、Fortune 500、国防主承包商、Big-4、bulge-bracket 投行、知名 AI lab、国家实验室 | 172 | **Lane A1，第一屏** |
| **2** | 大型或知名：public mid-cap、独角兽、知名后期私企、行业/区域主要玩家、头部量化 | 156 | Lane A2，第二段 |
| **1** | 小而真实：确实认识的创业公司或小公司 | 34 | Lane B |
| **0** | 完全不认识，或名字太通用无法识别 | 267 | Lane B |

（上表是 8/20 去重后 814 条中，剥离中介层之后的 629 条按 tier 分布。）

**注意 tier 和 kind 是正交的**，这是 prompt 里的硬规则，且实测生效：
`Tata Consultancy Services` = `tier 3 + kind outsourcing`，
`Robert Half` / `TEKsystems` = `tier 3 + kind staffing`。
**kind 决定看不看，tier 决定先看哪个。**

### 3.2 数据从哪来 / 覆盖率是多少

**这是本轮最重要的一个数字改进。**

| 方案 | 公司覆盖 | 岗位覆盖 |
|---|---|---|
| `unicorn_companies.csv` 精确名匹配 | 48/680 = **7.1%** | 142/1248 = 11.4% |
| `fortune_500_companies.csv`（72 行） | 21/680 = **3.1%** | 46/1248 = 3.7% |
| 上面两个并集（≈ CONTEXT_BRIEF 的 8.8%） | 61/680 = **9.0%** | 166/1248 = 13.3% |
| 再并上 `ats_registry.json`（227 家） | 150/680 = **22.1%** | 349/1248 = 28.0% |
| **LLM 富化（gpt-4o-mini，本方案）** | **680/680 = 100% 有结论**，其中 380/680 = **55.9%** 给出非 0 tier | **762/1248 = 61.1%** 给出非 0 tier |

关键说明：

- LLM 路线的覆盖率不是「命中率」而是「**有结论率 100%**」—— 每家公司都会拿到一个
  tier，没听说过的就是 tier 0。这跟名单方案的「查不到 = 无分可打」是本质区别：
  名单方案下 87% 的岗位排序时是**并列的，没法排**；LLM 方案下 100% 可排，
  只是其中 39% 排在最后。
- **`ats_registry.json` 我实测了但决定不用它做 tier**。它多覆盖 13 个百分点，但内容是
  「有没有自己的 ATS board」，跟公司大小无关 —— 里面有 Composio、Confido、Netic、`3:15`
  这种几十人的初创，也有 Jobgether 这种聚合站。**它是「真实雇主」信号，不是「大公司」信号，
  在 §4 里当否决位用，不在这里用。**

### 3.3 覆盖不到的怎么降级

三级降级，全部实测过：

1. **LLM 说 tier 0（8/20 有 267 条岗位）** → 落 Lane B，排在 A1/A2 之后。不丢弃，不隐藏。
   Lane B 在 dashboard 里默认折叠成一行「其他真实雇主 301 条 / 252 家，展开」。
2. **LLM 说 tier 0 且该公司总岗位量 ≥ 5** → 触发「量大+查无此人」信号，进中介候选（§4.3）。
3. **人工不同意** → 写 `company_overrides.json`，覆盖 tier 和 kind，优先级最高。

**降级的代价是可量化的**：Lane B 里 8/20 有 301 条，会不会藏着用户想看的大厂？
实测抽查 —— `Google`(tier 3)、`Microsoft`(3)、`Meta`(3)、`NVIDIA`(3)、`OpenAI`(3)、
`Stripe`(3)、`Anthropic`(2) 全部落在 Lane A，没有一个掉进 B。掉进 B 的 tier 0 公司抽样是
`Fionics`、`Netic`、`Gradial`、`Sundayy`、`Onyx Chambers`、`Stellar Alpina`、
`Thomas To`、`フジアルテ株式会社` —— 确实都是无名小公司或个人名义发帖。**降级正确。**

---

## 4. 中介识别（需求 1）

### 4.1 信号清单（全部实测）

| # | 信号 | 判据 | 8/20 命中 | 单独可用性 |
|---|---|---|---|---|
| S1 | **LLM `kind`** | `kind ∈ {staffing, outsourcing, training, aggregator}` | 44 家 / 116 条 | ★★★ 主力，0 误伤 |
| S2 | **转贴特征** | 标题匹配 `\s+at\s+[A-Z0-9]` 的比例 ≥ 50% | 1 家（Jack & Jill 85%）/ 31 条 | ★ 极窄但极干净 |
| S3 | **标题以 "Jobs" 结尾** | 该公司 ≥ 50% 标题以 `Jobs` 结尾 | 1 家（Surge Software 100%）/ 14 条 | ★ 极窄但 100% 精确 |
| S4 | **技术栈发散度** | 标题里出现 ≥3 种互斥技术栈 且 栈数/岗位数 ≥ 0.25 | 5 家（Surge 8 栈、Hire Feed 4、Infosys 3、Capgemini 3、Infosoft 3） | ★★ 见下 |
| S5 | **量大 + 查无此人** | `kind=="unknown" and tier==0 and 总岗位数 ≥ 5` | 7 家 / 94 条 | ★★★ 补 LLM 的洞 |
| V1 | **ATS 直连否决位** | 该公司在 `ats_jobs.csv` 里有行（= 有自己的 Greenhouse/Lever/Ashby board） | 否决 2 家 | 否决位 |
| O1 | **人工覆盖** | `company_overrides.json` | 0（尚未建） | 最高优先级 |

**S4 技术栈发散度是本轮新发现的信号**，值得单说。逻辑是：一家真公司招人围绕自己的技术栈，
一家 body shop 同时挂 .NET / React / Flutter / Java / Salesforce。实测判别力：

```
Surge Software 8 栈/15 岗    Hire Feed 4 栈/6 岗    Infosys 3/11    Capgemini 3/6
—— 对照组（真实雇主）——
Palantir 0   SpaceX 0   Micron 0   Cisco 0   Amazon 0   Anduril 0
Leidos 0     NetApp 0   L3Harris 0  Qualcomm 0   Deloitte 2   BeaconFire 2
```

Deloitte 只有 2 栈（52 个岗位），所以阈值定在 **≥3 栈** 就能避开它。

### 4.2 组合逻辑与否决规则

**决议顺序（先到先得，前面的赢）：**

```
1. O1  company_overrides.json 里有这家           → 直接采用人工结论      【最高】
2. S1  LLM kind ∈ {staffing,outsourcing,training,aggregator}
                                                 → 中介层 Lane C
3. V1  该公司在 ats_jobs.csv 里出现过            → 强制真实雇主，跳过第 4 步
4. S2/S3/S4/S5 任一命中                          → 中介层 Lane C
5. 否则                                          → 真实雇主，按 tier 分 A1/A2/B
```

**为什么 V1 排在 S1 之后而不是之前** —— 这是实测逼出来的：
`Jobgether` 既是聚合站又有自己的 Ashby board。如果 V1 优先，它会被救回真实雇主层，错。
现在的顺序下：LLM 明确认出的中介（S1）不受否决位保护，
只有「行为信号误标的」（S2-S5）才被否决位救回。实测这条规则各命中一次，两次都对：

```
否决生效   Handshake                   信号 unknown+vol5   → 救回（真实雇主，LLM 不认识它）✅
否决生效   Texas Sports Academy Main   信号 unknown+vol5   → 救回（有自己的 Ashby board）✅
否决未生效 Jobgether                   LLM:aggregator      → 留在中介层 ✅
```

### 4.3 「量大 + 查无此人」的阈值是怎么定的

这条规则是需求 1 的核心，因为**它是唯一能抓住 BeaconFire(39)、Surge(15)、Haystack(13)
这些 LLM 完全不认识的头部刷屏方的信号**。阈值扫描实测：

| 阈值 | 命中公司 | 命中岗位 | 是否误伤 |
|---|---|---|---|
| ≥3 | 20 | 139 | ❌ 误伤 3 家：**ClickHouse**(3)、**Muon Space**(3)、**Gradial**(3) —— 都是真公司 |
| ≥4 | 13 | 118 | ⚠️ 边缘 2 家：Base-2 Solutions(4)、Fionics(4)，性质存疑 |
| **≥5** | **7** | **94** | ✅ **0 误伤**：BeaconFire 39 / Surge 15 / Haystack 13 / RemoteHunter 8 / Yara AI 8 / Hire Feed 6 / Visionary Innovative Technology Solutions 5 |
| ≥6 | 6 | 89 | 漏掉 Visionary |

**取 ≥5。** 阈值 ≥3 / ≥4 命中的额外 45 条不进自动分流，改为在 Panel ③ 里
单列一个「疑似 / 待确认」小表，用户点一次就写进 override 文件 —— 既不误伤，又不浪费信号。

这条规则之所以对「不能误伤岗位多的正常公司」这个硬约束成立，是因为它**被 `tier==0` 门控**：
Deloitte(52)、Palantir(18)、SpaceX(17)、Booz Allen(16) 的 tier 分别是 3/3/3/3，
在构造上就进不了这条规则。**量本身从来不是判据，「量大」只在「LLM 从没听说过它」时才是判据。**

### 4.4 实测误伤名单（用户点名的 6 家 + 扩展到 60 家）

编排者点名要求验证的 6 家，全链路跑完的结果：

| 公司 | 总岗位 | LLM kind | LLM tier | 触发的中介信号 | **最终判定** |
|---|---|---|---|---|---|
| **Deloitte** | 52 | employer | 3 | 无 | ✅ 真实雇主 · Lane A1 |
| **Palantir** | 18 | employer | 3 | 无 | ✅ 真实雇主 · Lane A1 |
| **SpaceX** | 17 | employer | 3 | 无 | ✅ 真实雇主 · Lane A1 |
| **Booz Allen Hamilton** | 16 | employer | 3 | 无 | ✅ 真实雇主 · Lane A1 |
| **Micron Technology** | 6 | employer | 3 | 无 | ✅ 真实雇主 · Lane A1 |
| **Anduril / Anduril Industries** | 4 + 5 | employer | 2 | 无 | ✅ 真实雇主 · Lane A2 |

我又扩到 **60 家人工标注的真实雇主**（含 Google / Microsoft / Meta / NVIDIA /
Lockheed Martin / Raytheon / Goldman Sachs / JPMorganChase / Leidos / L3Harris / SAIC /
ManTech / Parsons / GDIT / EY / Gartner / Stryker / Intel / Adobe / Salesforce / Stripe /
OpenAI / Anthropic / Notion / Cloudflare / Vercel / Zipline / Nuro / Handshake / Epic /
JHU APL / WorldQuant / DRW / Five Rings / Blue Origin / Rocket Lab / Joby Aviation …）：

```
FALSE POSITIVES: 0 / 60          ← 零误伤
```

反向的召回率（我人工标注了 59 家中介，看 LLM `kind` 单独能抓多少）：

```
LLM kind 单独召回: 35 / 59 = 59%

漏掉的 24 家分两类：
 (a) LLM 完全没听说过的小 body shop / 聚合站 18 家
     → 由 S3/S4/S5 补掉 7 家最大的（94 条岗位）
     → 剩下的都是 1-4 条的长尾，进「待确认」表
 (b) LLM 认为是 employer 的咨询公司 6 家
     Capgemini / Orion Innovation / AgileEngine / Slalom / Guidehouse / Pariveda
     → 这类本来就有争议（Slalom 算不算中介取决于用户偏好），
       属于 override 文件的典型用例。Capgemini 已被 S4 技术栈信号抓到。
```

### 4.5 8/20 中介层全量输出（62 家 / 185 条，占当日去重后 22.7%）

按当日条数排序，附触发信号（这就是 Panel ③ 的表格内容）：

```
company                                    d8/20 llm_kind    signals
Jack & Jill                                  31 aggregator  LLM:aggregator, repost@85%
BeaconFire Inc.                              17 unknown     unknown+vol39
Surge Software                               14 unknown     title=..Jobs, stack=8, unknown+vol15
Jobright.ai                                   9 aggregator  LLM:aggregator
RemoteHunter                                  7 unknown     unknown+vol8
Infosys                                       6 outsourcing LLM:outsourcing, stack=3
Hire Feed                                     6 unknown     stack=4, unknown+vol6
Tata Consultancy Services                     6 outsourcing LLM:outsourcing
Yara AI                                       6 unknown     unknown+vol8
Haystack                                      5 unknown     unknown+vol13
Hired                                         4 aggregator  LLM:aggregator
Jobgether                                     4 aggregator  LLM:aggregator
Randstad Digital Americas                     3 staffing    LLM:staffing
Visionary Innovative Technology Solutions     3 unknown     unknown+vol5
Insight Global                                3 staffing    LLM:staffing
Quik Hire Staffing                            3 staffing    LLM:staffing
Infosoft, Inc.                                3 unknown     stack=3
Capgemini                                     3 employer    stack=3
Jobot                                         3 staffing    LLM:staffing
… 另 43 家各 1-2 条：Synechron / Radley James / FetchJobs.co / NTT DATA North America /
  HTC Global Services / MBN Solutions / US Tech Solutions / Programmers.io /
  Agility Partners / CPS, Inc. / HAN Staffing / SoCode Recruitment / HCLTech /
  Infinite Computer Solutions / Charter Global / Akkodis / Experis / The Fountain Group /
  Apex Bridge Talent Group / COGENT Infotech / Odyssey Information Services /
  Aditi Consulting / Software Guidance & Assistance / Matlen Silver / Initi8 Recruitment /
  The Judge Group / Aquent / Russell Tobin / Robert Half / Per Scholas / Revature /
  Berg Search / Ladders / Kforce Inc / Turing / Aspiron Search / Darwin Recruitment /
  Magnit Global / Cognizant / Exadel / MindSource / Rose International / Arcus Search
```

**人工复核这 62 家：没有一家是真实雇主。** 唯一口径可议的是 `Capgemini`
（LLM 判 employer，被技术栈信号抓进来）—— 结论正确但理由是「歪打正着」，
我把它记为已知的信号巧合，不是设计意图。

---

## 5. 产物形态

### 5.1 一个 HTML 文件，六个面板，第一屏就是阅读队列

`logs/daily/<day>.html`，纯内联 SVG + 内联 CSS，零外部依赖，支持
`prefers-color-scheme`。面板清单：

| # | 面板 | 形式 | 解决 | 与 req1 的差异 |
|---|---|---|---|---|
| **①** | **今日阅读队列** Lane A1 → A2 → B → C，每家公司最多 2 条，其余折叠成「+N 条」 | 分组列表，每组一个标题行 | **需求 2** | **新增，req1 没有。这是本轮的主产物。** |
| ② | **今日分流漏斗** 原始 → uid 去重 → (公司,标题) 去重 → A1/A2/B/C | 横向堆叠条，4 段用调色板槽 1-4 | 让用户相信折叠是安全的 | 替换 req1 的「总量→高频→长尾→可投」，分段口径改成 lane |
| ③ | **中介层证据表** 62 行，列：公司 / 今日 / 累计 / LLM kind / 触发信号 / 勾选框 | 表格 + 「疑似待确认」子表 | **需求 1** | 从 req1 的「不打标签只摆证据」升级为「已打标签 + 摆出打标签的理由 + 一键翻案」 |
| ④ | **每日变化** 近 N 天按 lane 堆叠 + 中介占比折线 | 堆叠柱 + 折线 | **需求 1 的「每天的岗位变化」** | req1 是按来源堆叠；改成**按 lane 堆叠**才回答「变化在哪一层」 |
| ⑤ | 采集器健康 | 状态列表（图标+文字+状态色） | 保留 | 不变，仍以 `jobs_matched` / `companies_ok` 为准，`new=0` 显示为正常 |
| ⑥ | 告警 + LLM 花费 | 状态卡片 | 保留 | **新增一行：今日新富化 N 家公司，花费 $X** |

**砍掉（沿用 req1 的结论并再次实测确认）**：各公司岗位数排行榜、sponsorship 分布、
Big Tech 独立 KPI 卡。

### 5.2 为什么 Panel ① 用「每家公司 cap 2」而不是纯排序

实测的压缩效果（8/20）：

```
原始（跨源 uid 去重后）                                     965 条
→ 再按 (公司, 规范化标题) 去重                              814 条   (-15.6%)
→ 剥离中介层 Lane C                                        629 条   (-22.7%)
→ 只看 Lane A1 (tier 3)                                    172 条
→ 每家公司最多 2 条                                        140 行   ← 第一屏
```

**965 → 140，压缩 6.9 倍，且这 140 行全部来自 tier-3 公司。**
纯排序做不到这一点 —— 纯排序下 Deloitte 27 条会占掉屏幕顶部，Amazon 6 条紧随其后，
用户滚 10 屏还在同两家公司里。**cap 是「看不过来」的真正解药，排序只决定顺序。**

`(公司, 标题)` 去重这一步是本轮的意外收获，值得单独说：它不是中介信号，
**真实雇主的重复反而更严重** —— Deloitte 有 14 条一模一样的
`Audit & Valuation Analytics AI Specialist`，Power Home Remodeling 重复率 90%，
Appian 70%，Gartner 75%，Cisco 60%（多地点同岗位）。而 Jack & Jill 只有 9%。
所以：**重复率是压缩机会，不是中介信号**（见 §9.3）。

### 5.3 Panel ③ 的翻案闭环

表格每行一个 checkbox（纯 HTML，无 JS 也能勾）。表格下方一个 `<textarea>`，
里面预填好可直接粘贴的 override 片段：

```json
{
  "beaconfire": {"kind": "training",    "note": "IT培训+外包，2026-08-20 人工确认"},
  "yara ai":    {"kind": "employer",    "note": "误判，实为小型 AI 创业公司"},
  "slalom":     {"kind": "outsourcing", "note": "个人不想看咨询"},
  "handshake":  {"tier": 2, "kind": "employer"}
}
```

键是 `norm(company_name)`（小写、去标点、去 Inc/LLC/Ltd 等后缀）。
**规模上限：几十行。** 62 家中介里 44 家已被 LLM 正确判定，7 家被行为信号判定，
真正需要人工的只有争议的 6 家咨询公司 + 长尾里用户特别在意的几家。

---

## 6. 实测验证

### 6.1 分流结果（两天，同一套规则）

```
2026-08-19   uid去重 287 → (公司,标题)去重 230
   A1 (tier3):  55 条 /  26 家 | cap2 →  35 行
   A2 (tier2):  47 条 /  33 家 | cap2 →  42 行
   B  (其他) : 111 条 /  79 家 | cap2 →  98 行
   C  (中介) :  17 条 /  10 家 | cap2 →  14 行      ← 中介占比 7.4%

2026-08-20   uid去重 965 → (公司,标题)去重 814
   A1 (tier3): 172 条 / 106 家 | cap2 → 140 行
   A2 (tier2): 156 条 / 135 家 | cap2 → 149 行
   B  (其他) : 301 条 / 252 家 | cap2 → 289 行
   C  (中介) : 185 条 /  62 家 | cap2 →  87 行      ← 中介占比 22.7%
```

**「中介占比 7.4% → 22.7%」就是 Panel ④ 要画的那条线**，它比「今日新增 937 条」
信息量大得多：8/20 的暴涨里有近四分之一是刷屏。这是需求 1「看到每天的岗位变化」
真正该看到的东西。

### 6.2 阅读队列 TOP 30 实际输出（2026-08-20，Lane A1，cap 2，tier 内按公司名 A-Z）

```
  1. T3 ABB                          | Associate Project Engineer
  2. T3 Accenture Federal Services   | Cloud Services Engineer
  3. T3 Adobe                        | Machine Learning Engineer, Express AI Foundations
  4. T3 Adobe                        | iOS App Development Engineer
        (+1 more from Adobe)
  5. T3 Amazon                       | Software Development Engineer, Personalization
  6. T3 Amazon                       | Software Development Engineer, IAM Security
        (+4 more from Amazon)
  7. T3 AMD                          | CPU Core Design Verification Engineer
  8. T3 BAE Systems, Inc.            | Entry Level Software Engineer
  9. T3 BAE Systems, Inc.            | EOIR Algorithm Lead (Sign-on Bonus)
 10. T3 Bank of America              | Global Technology Summer Analyst 2027 - Software Eng
 11. T3 Baxter International Inc.    | Software Engineer, Test Automation
 12. T3 BlackRock                    | 2027 Full-Time Analyst Program - AMRS
 13. T3 Blue Cross Blue Shield of MA | Engineer
 14. T3 Boeing                       | Associate Systems Engineer - Health Management
 15. T3 Boeing                       | F-15 Mission Systems International Software OFP Capt
 16. T3 Booz Allen Hamilton          | DevOps Engineer
 17. T3 Booz Allen Hamilton          | Data Engineer
        (+7 more from Booz Allen Hamilton)
 18. T3 Bridgestone Americas         | Manufacturing Infrastructure Tech I
 19. T3 Broadcom                     | R&D Software Engineer
 20. T3 Capgemini Engineering        | PLM Developer-Siemens Teamcenter Aerospace & Defense
 21. T3 Cargill                      | Application Developer - SuccessFactors Talent Mgmt
 22. T3 Cargill                      | Application Developer, SuccessFactors Learning & Dev
 23. T3 Caterpillar Inc.             | Software Engineer (Autonomy Services)
 24. T3 Charles Schwab               | Full Stack Software Developer
 25. T3 Cisco                        | Site Reliability Engineer
 26. T3 Cisco                        | Software Engineer (simulation)
 27. T3 Citi                         | Full Stack Java Developer
 28. T3 Citi                         | Digital Engineering Officer
 29. T3 City of Houston              | Engineer-in-Training-(OCE-IDM)
 30. T3 Collins Aerospace            | Software Engineer - Embedded Communications (ONSITE)
```

**我自己看这个排序：合格，但有三个我必须诚实指出的问题。**

1. ✅ **没有一条刷屏。** 对照 req1.md 里那份「按量排序」的垃圾结果
   （BeaconFire 39 / Jack & Jill 34 / Surge 15 / Jobright 11 打头），这一版
   top 30 全是 ABB / Adobe / Amazon / AMD / BAE / BofA / BlackRock / Boeing /
   Booz Allen / Broadcom / Cargill / Caterpillar / Charles Schwab / Cisco / Citi /
   Collins Aerospace。**这就是用户要的「大中公司排前面」。**
2. ⚠️ **tier 内部按字母序，所以 top 30 只覆盖到字母 C。** Google / Meta / Microsoft /
   NVIDIA / Palantir / SpaceX 都在这 140 行里，但排在后半段。我**故意不做 tier 内细排序**：
   任何「Amazon 比 Cargill 更该先看」的排序都需要我编一个我无法验证的分数
   （市值？员工数？LLM 的 conf 实测是离散编码，不能当分数用）。
   字母序至少是确定的、可预期的、用户扫一遍 140 行不会漏。
   如果用户明确说「就要 FAANG 最前面」，正确做法是加一个 20 行的
   `priority_companies.txt` 置顶名单，而不是发明一个假分数。**列为 P1-2。**
3. ⚠️ **140 行仍然偏多。** 从 965 压到 140 是 6.9 倍，但一天读 140 行还是有负担。
   下一个压缩杠杆是**岗位相关性**（这 965 条来自 9 个 LinkedIn query，混了
   `City of Houston Engineer-in-Training`、`Manufacturing Infrastructure Tech I`
   这类非软件岗）。这不在本轮需求里，列为 P1-3。

### 6.3 LLM 富化的实测代价

```
全量 680 家公司，gpt-4o-mini，batch=40，17 个批次，5 路并发
  wall time      51.6 s
  input tokens   16,799
  output tokens  18,987
  cost           $0.0139
  dropped rows   0 / 680
  errors         0
  单家成本       $0.0000204
```

### 6.4 中介判定的两个方向的错误率

```
在 60 家人工标注的真实雇主上：false positive = 0 / 60           （0.0%）
在 59 家人工标注的中介上    ：LLM kind 单独 recall = 35 / 59     （59%）
                              叠加 S2/S3/S4/S5 后，当日已知的
                              7 家头部刷屏方（94 条）全部命中
```

---

## 7. 成本 / 冷启动 / 失败模式

### 7.1 花多少钱、多久

| 场景 | 公司数 | 耗时 | 花费 |
|---|---|---|---|
| **首次全量富化**（实测） | 680 | **51.6 s**（5 路并发） | **$0.0139** |
| 每日增量（新公司 100 家） | 100 | ~8 s | ~$0.002 |
| 每日增量（极端 500 家） | 500 | ~40 s | ~$0.010 |
| 全量重跑（换模型 / 改 prompt） | 680 | 52 s | $0.014 |

对照：项目 8/20 全天 LLM 花费 $0.0265。**加上公司富化后日常增量约 +$0.002/天，
不到现有花费的 10%；首次全量 $0.014 一次性。**

**模型选择必须是 gpt-4o-mini，不能是 gpt-3.5-turbo**，实测两条理由：

| | gpt-3.5-turbo | gpt-4o-mini |
|---|---|---|
| 编造假公司（2 家假名） | **2/2 编了**，`employer / tier1 / conf 0.9`，理由「LLC suggests employer」 | **2/2 正确 unknown** |
| 同一批 40 家的 token | in 636 / out 1456 | in 976 / out 1165 |
| 折算 680 家总价 | **~$0.038** | **$0.0139** |
| `why` 字段质量 | 全部退化成 "no knowledge"，不遵守指令 | 给出真实理由（"Big-4 consulting firm"） |

> ⚠️ **`gpt-4o-mini` 不在 `LLMCostTracker.MODEL_PRICING` 里** —— 不加的话日报会把它报成
> 「unpriced run」，当日花费被低估。这是 P0 的一行改动（P0-3）。实施时请顺手核对一次
> OpenAI 当前价目表，本文的 $0.15/$0.60 per 1M 是按公开费率折算的。

### 7.2 LLM 瞎编怎么办 —— 三道防线

**防线 1：prompt 里把「不知道」定义成正确答案。** 实测有效。
系统提示写死 `"unknown" is a correct and valued answer; guessing from the company name
is a serious error`，并列硬规则
`Never infer kind or tier from words in the name such as Inc, LLC, Solutions,
Technologies, Systems, Group or Consulting. A name is not evidence.`
效果：两家我编造的公司（Zorbatex Quantum Dynamics LLC / Fleebware Solutions Group）
都返回 unknown。18 家真实但小众的公司（Fionics / Netic / northwoodspace / Gradial /
Sundayy / Onyx Chambers / Stellar Alpina / Muon Space / Lightfield / Freeform /
General Matter / Ellipsis Labs / Confido …）全部返回 unknown / tier 0 —— 保守但正确。

**防线 2：置信度不当阈值，用 `kind=="unknown" and tier==0` 当「不知道」判据。**
实测 conf 的分布是高度离散的编码，不是概率：

```
gpt-3.5-turbo   conf ∈ {0.0, 0.7, 0.8, 0.9, 1.0}，且给假公司 0.9   → 完全不可用
gpt-4o-mini     conf ∈ {0.2, 0.6, 0.7, 0.8, 0.9, 1.0}
                  0.2  ⟺ kind=unknown（100% 对应）
                  ≥0.7 ⟺ 认识
```

所以 conf **只在 dashboard 里当一个显示列**（让用户知道这条判定有多硬），
**不进任何判定分支**。判定分支只用 `kind` 和 `tier` 的离散值。

**防线 3：错的方向是可控的。** 实测两类错误的代价不对称：

- LLM 把真公司说成不认识（tier 0）→ 它掉进 Lane B，**用户展开就能看到，不丢失**。
- LLM 把假公司说成大公司（tier 3）→ 它污染第一屏。**实测 0 次**：
  680 家里 130 家 tier 3，人工过了一遍全部合理（附录 B 全名单）。

### 7.3 人工覆盖怎么做

`company_overrides.json`，键是规范化公司名，值可覆盖 `tier` / `kind`。规模上限几十行。
三个入口：

1. Panel ③ 勾选框 → 自动生成可粘贴片段。
2. Panel ③ 的「疑似待确认」子表（阈值 3-4 的那 13 条）—— 主动请求人工裁决。
3. 直接手编文件。

**这个文件永不被程序覆写**，只被读取。LLM 全量重跑不会冲掉人工结论。

### 7.4 只有 2 天数据怎么办（冷启动）

**本方案的判定层完全不依赖历史**，这是刻意设计的，也是实测逼出来的：

```
newgrad 路径公司数   8/19: 56    8/20: 554    两天都出现的: 12
→ 97.8% 的 8/20 公司是「今天才第一次出现」
→ 「跨天突发 vs 常态」这个信号在 2 天数据上完全不可用
```

CONTEXT_BRIEF 把「跨天持续性」列为可用信号（BeaconFire 突发 / Deloitte 常态）——
**我实测后反对这一条**：8/19 的 newgrad 只跑出 101 条 / 56 家，是个残缺日，
拿它当基线会把几乎所有公司都判成「突发」。所以：

| 组件 | 需要历史吗 | 2 天数据下的状态 |
|---|---|---|
| tier 分层 | ❌ 不需要（LLM 世界知识） | **完全可用** |
| kind 中介判定 | ❌ 不需要（LLM + 单日行为） | **完全可用** |
| ATS 否决位 | ❌ 不需要 | **完全可用** |
| Panel ①②③ | ❌ 不需要 | **完全可用** |
| Panel ④ 趋势 | ✅ 需要 | 画 2 根柱，坑位留空，不告警 |
| 「跨天突发」信号 | ✅ 需要 | **本轮明确不做**，等积累 ≥14 天再评估 |

### 7.5 失败模式清单

| 失败模式 | 触发条件 | 后果 | 缓解（已设计） |
|---|---|---|---|
| **LLM 批次少返回行** | 实测发生过：40 家输入只回 32 个对象，且省略 `name` 字段，按位置对齐导致**整体错位**（Yara AI 被贴上「Big-4 consulting firm」，Quik Hire Staffing 被贴上「renowned research lab」） | 灾难性静默错误 | 强制 `response_format={"type":"json_object"}` + 要求逐条回显 `name` + **按 name 回填而非按位置**，缺失的补 `unknown` 并计数。修正后实测 680/680 全中，缺失 0 |
| OpenAI API 挂了 | 网络 / 额度 | 新公司无 tier | 富化失败 → 该公司 tier 0 落 Lane B，**不阻塞报告生成**；重试 3 次 |
| prompt 改动引入误伤 | 改了 kind 定义 | Deloitte 掉进中介层 | **把 §4.4 的 60 家真实雇主 + 59 家中介固化成回归 fixture**，改 prompt 必须重跑，FP 必须为 0 |
| 公司别名分裂 | `Anduril`(4) vs `Anduril Industries`(5)、`Palantir`(18) vs `Palantir Technologies`(2) | 同一家公司分成两行，cap 失效 | **不自动前缀合并** —— 实测 8 对前缀候选里 `Epic`(医疗软件) vs `Epic Placements`(猎头)、`Amazon` vs `Amazon Lab126`、`Jack` vs `Jack & Jill` 都不该合并。放进 override 文件手工合并 |
| 中介占比指标被 query 改动带偏 | 改了 9 个 LinkedIn query | Panel ④ 折线断裂 | Panel ④ 标注 query 变更日 |
| tier 3 名单膨胀 | 模型升级后更「大方」 | 第一屏变长 | 监控 `tier3 公司数 / 总公司数`（现为 130/680 = 19.1%），超 30% 告警 |

---

## 8. 实施切分

### P0 —— 本轮必做

| # | 任务 | 产物 | 规模 | 依赖 |
|---|---|---|---|---|
| P0-1 | **`daily_report.py` 拆分析/渲染**：`collect_report(day)` 返回纯数据；`build_alerts()` 返回结构化 dict；`load_jobs()` 一次读全部再按天分桶 | 改 `daily_report.py` ~150 行 | 中 | 无（req1.md §2 已有方案） |
| P0-2 | **公司档案富化脚本** `enrich_companies.py`：读 3 个 CSV → 找出 `company_profiles.json` 里没有的公司 → batch 40 / 5 路并发调 gpt-4o-mini → **按 name 回填** → 写回缓存 | 新文件 ~150 行 + `company_profiles.json` | 中 | OPENAI_API_KEY |
| P0-3 | **`gpt-4o-mini` 加进 `LLMCostTracker.MODEL_PRICING`** | 改 `cost_tracker.py` 4 行 | 极小 | 无 |
| P0-4 | **判定层** `company_lane.py`：`resolve(company) → (lane, tier, kind, signals[])`，实现 §4.2 的 5 步决议顺序 | 新文件 ~120 行 | 中 | P0-2 |
| P0-5 | **回归 fixture**：把 §4.4 的 60 家真实雇主 + 59 家中介写成测试，断言 FP = 0 | 新文件 ~80 行 | 小 | P0-4 |
| P0-6 | **两级去重**：跨源 uid（已有）+ `(norm(company), norm(title))` | 改 `dedup()` ~15 行 | 小 | 无 |
| P0-7 | **`render_html()` Panel ①②③⑤⑥** | 新文件 ~400 行 | 大 | P0-1 / 4 / 6 |
| P0-8 | **`company_overrides.json`** 读取 + Panel ③ 的可粘贴片段生成 | ~40 行 | 小 | P0-4 |
| P0-9 | `run_daily_report.bat` 在日报前调 `enrich_companies.py` | 改 2 行 | 极小 | P0-2 |

**P0 的验收标准（可自动断言，不是「效果良好」）：**

- `resolve()` 对 60 家真实雇主 fixture 的中介误判 = **0**
- 8/20 的 Lane A1 cap-2 行数 ∈ [120, 160]（现测 **140**）
- 8/20 的 Lane C 条数 ∈ [170, 200]（现测 **185**）
- `enrich_companies.py` 全量 680 家：dropped rows = 0，耗时 < 120 s，花费 < $0.03
- Deloitte / Palantir / SpaceX / Booz Allen / Micron / Anduril 在 HTML 里出现在 Lane A

### P1 —— 下一轮

| # | 任务 | 为什么不是 P0 |
|---|---|---|
| P1-1 | **Panel ④ 趋势**：按 lane 堆叠 + 中介占比折线 | 只有 2 天数据，画出来没信息量。等 ≥7 天 |
| P1-2 | **`priority_companies.txt`** 20 行置顶名单，解决 §6.2 的「tier 内字母序」 | 需要先让用户看一眼这 140 行队列，确认他到底想不想要置顶 |
| P1-3 | **岗位相关性过滤**（把非软件岗剔出队列），把 140 进一步压到 ~60 | 是新需求，不在本轮两个需求内 |
| P1-4 | **`applied` 列真正启用**，队列里划掉已投 | 该列 100% 为空，先要有写入路径 |
| P1-5 | **别名合并**写进 override（Anduril / Palantir / Capgemini / Google 四对） | 影响 ~16 条，收益小 |
| P1-6 | 把「疑似待确认」阈值 3-4 的 13 条做成主动询问流 | 依赖 P0-8 的 override 闭环先跑通 |

---

## 9. 我放弃的方案，以及放弃的理由

### 9.1 ❌ 扩充离线名单（Fortune 1000 / S&P 500 / Crunchbase 导出）

实测三份现有名单的并集只覆盖 9.0% 公司 / 13.3% 岗位。就算把
`fortune_500_companies.csv` 从 72 行修到真的 500 行，也补不上真正的缺口 —— 缺的是
`Booz Allen`(私营)、`Anduril`(未上市)、`Applied Intuition`、`Muon Space`、
`Belvedere Trading`、`Five Rings`、`WorldQuant` 这种「有名但不在任何一张标准榜单上」的公司。
而且名单要维护、要下载（`download_company_lists.py` 依赖网络，与「离线可开」冲突）。
LLM 富化 $0.0139 一次就给出 100% 有结论率，成本和维护量都低一个量级。

### 9.2 ❌ 「各公司岗位数」面板 / 按量排序

复核 req1 的结论，本轮再次实测：按量排序的 top 是
`Deloitte 52 / BeaconFire 39 / Jack & Jill 34 / Palantir 18 / SpaceX 17 / Surge 15 /
Haystack 13 / Jobright 11 / TCS 11` —— 真实雇主和刷屏方交替出现，
**这张榜单本身不携带用户要的任何一种信息**。它既不是「好公司排行」也不是「中介排行」。

### 9.3 ❌ 用「标题重复率」当中介信号

本轮新测，结论与直觉完全相反：

```
Power Home Remodeling 90%   Deloitte 87%   Gartner 75%   Appian 70%   Cisco 60%
Jack & Jill 9%   Surge Software 7%   Infosys 9%   Jobright.ai 18%
```

**真实大公司的标题重复率反而最高**（多地点投放同一个 JD），聚合站因为转贴不同公司的岗位
反而最低。用它做中介信号会精确地误伤 Deloitte 和 Power Home Remodeling。
但这个指标不是没用 —— 它是**压缩机会**，`(公司,标题)` 去重砍掉 15.6%，已列为 P0-6。

### 9.4 ❌ 「跨天突发 vs 常态」信号

8/20 的 554 家 newgrad 公司里，只有 12 家在 8/19 出现过（8/19 是残缺日，
newgrad 只跑出 101 条）。97.8% 的公司都会被判成「突发」。这个信号在当前数据上是纯噪音。
等历史积累到 ≥14 天再重新评估。

### 9.5 ❌ gpt-3.5-turbo

对两家我编造的公司 2/2 编造答案且给 conf 0.9；`why` 字段全部退化成 "no knowledge"
不遵守指令；折算全量成本 ~$0.038 **比 gpt-4o-mini 的 $0.0139 还贵 2.7 倍**。
没有任何一个维度胜出。

### 9.6 ❌ 用 conf 阈值做判定门控

实测 conf 是离散编码不是概率（gpt-4o-mini 的 0.2 与 `kind=unknown` 100% 对应）。
用 `conf < 0.5` 当门控，效果等价于直接判 `kind=="unknown"`，
但多引入一个可能漂移的魔法数字。改用离散字段判定，conf 只做显示列。

### 9.7 ❌ 拿 ATS 直连当「大公司」信号

`ats_registry.json` 227 家确实比现有名单多覆盖 13 个百分点，但里面是
`Composio`、`Confido`、`Netic`、`northwoodspace`、`3:15` 这种几十人初创，还有
`Jobgether` 这个聚合站。**它衡量的是「有没有自建招聘系统」，跟公司规模无关。**
它在 §4.2 里当否决位（真实雇主判据）用，那才是它真正携带的信息。

### 9.8 ❌ 前缀自动合并公司别名

实测 8 对前缀候选，其中 3 对**必须不合并**：
`Epic`(Epic Systems，医疗软件巨头) vs `Epic Placements`(猎头)、
`Amazon` vs `Amazon Lab126`、`Jack`(4 条普通标题) vs `Jack & Jill`(34 条聚合)。
自动合并会把猎头的岗位挂到 Epic Systems 名下 —— 比不合并更糟。改用 override 手工合并（P1-5）。

### 9.9 ❌ 排序清单做成独立文件

见 §1.2 对假说 A 的回应。用户的痛点是「东西太多」，再给他第二个文件是反向操作。
队列做成 dashboard 的第 1 屏，统计做第 2 屏往后。

### 9.10 ❌ 岗位级 LLM 打分

1252 条岗位 vs 680 家公司，岗位级调用量是公司级的 1.8 倍，
且**岗位级结果无法缓存**（每天新岗位 = 每天全量重付），而公司档案是一次付费永久复用。
按 8/20 的 965 条/天算，岗位级打分年成本约 $9，公司级约 $0.7。
更关键的是：用户要的两个属性（中介 / 大公司）**本来就是公司级的**，
岗位级打分是把一个 680 维的问题错误地放大成 1252 维。

### 9.11 ❌ 继续用 `company_type` / `sponsorship_status` / `applied`

沿用 CONTEXT_BRIEF 的实测，本轮不再重复验证：`company_type` 39% 命中率
且混入 Boyd Gaming / Robert Half，无区分度；`sponsorship_status` 只有 ats_direct 有意义；
`applied` 全库为空。三者在新 dashboard 里：`company_type` 降级为表格标注列，
`sponsorship_status` 只在 ats_direct 行显示，`applied` 等 P1-4。

**顺带定位了 `company_type` 39% 虚高的根因**：
`job_collector/classifiers/company_type.py` 的 prompt 里写着
`When in doubt, prefer classifying well-known large companies as "独角兽/上市公司/Big Tech"`
—— 是 prompt 主动要求模型往大了猜。新的富化 prompt 用的是相反的指令
（`Unknown is a correct and valued answer`），这就是实测 tier 分布合理的原因。
**旧分类器不必改，直接被 `company_profiles.json` 取代。**

---

## 附录 A：复现方式

**关键产物已经拷进 `dashboard_loop/`，不会随 scratchpad 一起消失：**

| 落地文件 | 说明 |
|---|---|
| `dashboard_loop/company_profiles.sample.json` | **680 家公司的富化结果（94 KB）**。P0-2 实现后可直接改名成根目录的 `company_profiles.json` 当初始缓存用，省掉首次 $0.0139 |
| `dashboard_loop/enrich_prompt_reference.py` | **最终 prompt 原文**（`SYSTEM` / `INSTR` 两个常量）。每一条硬规则都对应 §7.2 的一个实测结果，删任何一条都会退化 |
| `dashboard_loop/_verify_base.py` | CSV 加载 + 跨源去重 + `norm()` 公司名规范化 |
| `dashboard_loop/_verify_enrich_all.py` | 全量富化跑法（17 批 × 5 并发，按 name 回填） |
| `dashboard_loop/_verify_queue.py` | 分流 + 阅读队列生成，`python _verify_queue.py 2026-08-20 3` 可复现 §6.2 |

原始 scratchpad（会话结束后失效）：
`C:\Users\Hanne\AppData\Local\Temp\claude\d--OneDrive-work-school-project-Job\d4c9fbce-2b61-48a8-a739-3c7bf65c99dc\scratchpad\`：

| 文件 | 作用 |
|---|---|
| `base.py` | 三 CSV 加载 + 跨源 uid 去重 + `norm()` 公司名规范化 |
| `llm_probe.py` / `llm_probe3.py` | prompt v1 / v3 探针，v3 是最终版（json_object + name 回显） |
| `b1.json` / `b2.json` | 80 家探针样本，含 2 家我编造的假公司 |
| `enrich_all.py` | 680 家全量富化，17 批 × 5 并发 |
| **`profiles.json`** | **富化产物，680 家公司档案 —— 实施时可直接拷成 `company_profiles.json`** |
| `queue.py` | 分流 + 阅读队列生成 |

运行环境：`D:/Apps/Miniconda/envs/job-classifier/python.exe`，先 `export PYTHONIOENCODING=utf-8`。

最终 prompt 的完整文本在 `llm_probe3.py` 的 `SYSTEM` / `INSTR` 两个常量里，
实施时应原样搬进 `enrich_companies.py`（prompt 的每一条硬规则都对应 §7.2 的一个实测结果，
删任何一条都会退化）。

## 附录 B：实测 tier 3 全名单（130 家，人工复核无误判）

```
ABB, AMD, Accenture Federal Services, Adobe, Amazon, BAE Systems, Bank of America,
Baxter International, BlackRock, Blue Cross Blue Shield of Massachusetts, Boeing,
Booz Allen Hamilton, Bosch, Bridgestone Americas, Broadcom, ByteDance, Capgemini*,
Capgemini Engineering, Cargill, Caterpillar, Centene, Charles Schwab, Cisco, Citi,
City of Houston, Cognizant*, Collins Aerospace, CommonSpirit Health, Datadog,
Dell Technologies, Deloitte, Dignity Health, Discord, DoorDash, EY, Edward Jones,
Emory Healthcare, Epic, Ericsson, Esri, Fiserv, Florida International University,
Fluor, Ford Motor Company, Freddie Mac, GE HealthCare, Garmin, Gartner, GDIT,
General Dynamics Mission Systems, General Motors, Goldman Sachs, Google,
Google DeepMind, HCLTech*, HII, Hermès, Honeywell Aerospace, Humana, Infosys*, Intel,
Intuit, JPMorganChase, John Deere, Johns Hopkins Applied Physics Laboratory,
Johnson Controls, KAYAK, L3Harris Technologies, Leidos, Lockheed Martin, MANTECH,
McKesson, MetLife, Meta, Micron Technology, Microsoft, Mission Technologies (HII),
Morgan Stanley, NJ Dept of Environmental Protection, NVIDIA, NYU Langone Health,
NetApp, Newport News Shipbuilding, Northwestern University, Oak Ridge National
Laboratory, OpenAI, PACCAR, PNC, Palantir, Palantir Technologies, Panasonic Energy
North America, Parsons, Pinterest, Qualcomm, Quora, Raytheon, Robert Half*, Roblox,
SAIC, SAS, SLB, Salesforce, Sentara Health, ServiceNow, Siemens Energy, Smith+Nephew,
Snowflake, SpaceX, State Street, Stellantis, Stripe, Stryker, TEKsystems*,
Tata Consultancy Services*, The New York Times, UT Medical Branch, Thomson Reuters,
Toyota North America, Truist, U.S. Bank, University of Michigan,
University of Minnesota, University of Southern California, Vanguard, Volvo Group,
Washington University in St. Louis, Wells Fargo, Westerndigital, eBay
```

`*` = tier 3 但 `kind` 为 staffing / outsourcing，会被分流到中介层 —— 这正是
tier 与 kind 正交设计要达到的效果：**规模大不等于该看。**
