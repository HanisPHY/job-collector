# Round 2 设计方案（增量）—— 对 11 条阻断项的回应与修正

> 作者：PM/设计负责人（round2）
> 日期：2026-08-20
> **这是增量文档。** round1_design.md 的骨架保留，被作废的小节在 §0 的表里逐条列出。
> 本轮又花了 **约 $0.30** 做实测（3 次全量富化 + 3 模型对比 + 2 次 stage-2 全量），
> 所有数字都是跑出来的。脚本与产物见 §8。
>
> **一个必须先说的事实：语料在我做实验期间变大了。** round1 快照是 1252 行 / 680 家；
> 现在是 **1391 行 / 767 家**（8/20 从 965 涨到 1104，采集器还在跑）。
> 所以本文的 round1 vs round2 对比**一律在当前同一份语料上重跑**，不与 round1 文档里的
> 旧数字直接相减。另外：**767 家里有 87 家在富化表之外** —— 这正好现场演示了
> 阻断项 B5 说的「`P[c]` 直接下标会 KeyError」，见 §5.3。

---

## 0. round1 哪些内容作废

| round1 小节 | 处置 |
|---|---|
| §4.1 信号清单（S1-S5 五条） | **作废**，替换为 §3.1 的四步链（S2/S3/S4 删除，实测只多抓 1 家 3 条） |
| §4.2 决议顺序（V1 在 S1 之后，公司级） | **作废**，替换为 §3.2「按行求值 + job_board 不再由公司级否决」 |
| §4.3 阈值 ≥5（累计岗位数） | **作废**，替换为 §3.3 的 7 天滑动窗口 + 相对速率 |
| §4.4 / §4.5 / §6.4 的误伤与召回数字 | **作废**（基于旧语料 + 旧判定链），替换为 §3.5 / §6 |
| §5.2「140 行第一屏」 | **作废**，替换为 §4.2 的「必看段 35 行 + 渐进展开」 |
| §6.2 TOP 30（tier 内字母序）与其中的自我批评第 2、3 点 | **作废**，替换为 §4.1 的 prom 排序 TOP 30 |
| §7.1 成本表 | **作废**，替换为 §5.1（两段式富化，贵了一个数量级，但仍在预算内） |
| §7.2 防线 2「conf 只做显示列」 | **保留判定结论，但改为完全不显示 conf**（采纳 A 的 NB-6） |
| §8 P0/P1 切分 | **作废**，替换为 §7 |
| §3.2 覆盖率表、§9 全部 11 条放弃方案、§7.2 防线 1/3、§5.3 override 闭环 | **保留**（两位评估者都复核通过；§9 的 8 条 A 明确说不需重新论证） |

---

## 1. 对 11 条阻断项的逐条回应

### A1 / B4（两人独立收敛）：累计计数器 —— ✅ **完全接受**

两位说的是同一件事，我不再自证。改法：`S5` 的岗位计数改成**以报告日为右端的 7 天滑动窗口**，
并叠加一个相对速率下限。判据：

```
n_win = 该公司在 [day-6, day] 内的岗位数
触发  = kind=="unknown" and tier==0 and n_win >= 5 and n_win / 窗口内总岗位数 >= 0.4%
```

绝对项 `>=5` 防小样本日误伤，相对项 `>=0.4%` 防日产量整体放大时阈值失效
（0.4% 是用当前数据反解的：5/1252）。

**实测证明炸弹拆除**（把 8/20 的 1104 行复制成 N 天的合成语料，在最后一天求值）：

```
 days     rows  累计规则(round1)   7天窗口规则(round2)
    2     2208     20 家              8 家
    4     4416     56 家              8 家
    7     7728    278 家              8 家     ← 累计规则第 7 天已经饱和
   14    15456    278 家              8 家
   30    33120    278 家              8 家
   90    99360    278 家              8 家
```

累计规则第 7 天就把 278 家全吞了（语料里 tier0/unknown 共 242 家，加上跨过 tier 门槛的
其它公司），窗口规则**在任意语料年龄下恒定为 8 家**。A 外推的「10 天 100%」方向正确，
实测比他预计的还快。

`S4` 的分母漂移问题不用单独修 —— **S4 整条被删了**（见 A 的 NB-1 / B 的 §5.1，我采纳）。

> 顺带自查其它「量」类判据：round1 里只有 S4 / S5 两处用了 `n`。round2 的四步链里
> 只剩 S5 一处，且已窗口化。Panel ② 漏斗、Panel ③ 的「今日/累计」两列是**展示**不是判据，
> 保留累计值但必须在表头标注「累计（不参与判定）」。

### A2：LLM 不可复现 —— ⚠️ **部分接受，但编排者的修法我实测后反对**

**接受的部分**：`tier`/`kind` 不是客观属性，是采样。所以：

1. **缓存即真理**：`enrich_companies.py` 只对 `company_profiles.json` 里**不存在的键**发请求。
   全量重跑必须是显式独立命令 `--rebuild`，产出 diff 报告，不进日常路径。
2. **回归 fixture 断言缓存值，不断言模型**。模型漂移用季度体检脚本看 diff，不进 CI。
3. **单调升级**：一家公司一旦被判 `tier>=2`，后续富化不允许自动降级，只允许人工降。

**反对的部分 —— 编排者 steer #1「跑 3 遍取多数票 / 取 max tier，能回收一半被埋的公司」。
我实测了，这个方案不成立。**

我按 steer 跑了 3 遍全量（680 家，锚点批次，$0.0983，388 秒，锚点零失误）：

```
3 遍之间 tier 完全一致: 634/680 = 93.2%
3 遍之间 kind 完全一致: 658/680 = 96.8%

对 round1 的 300 家 tier0 公司做 3-pass 聚合：
  agg = max      -> 回收到 tier>=2:  5 家 (1.7%)
  agg = majority -> 回收到 tier>=2:  4 家 (1.3%)

对 A4 点名的 44 家被埋公司：3-pass max 只回收 2 家（Zelis、Xendit）
```

而且**多采样同时造成了反向损失**：3 遍聚合把 round1 判为 `tier>=2` 的 **37 家降级**，
里面正好包含 A 自己点名的 `Five Rings`、`FlexTrade`、`Fluence`，还有
`BigBear.ai`、`Draper`、`Drata`、`Q2`。净效果是**回收 5 家、赔进去 37 家**。

结论：**多次采样提高的是一致性（93.2%/96.8%），不是召回。** A4 观察到的
「换个批次问，7/14 立刻认出来」是**批次组成效应**，不是采样方差 —— 他那个对抗批次
把 14 个「知名但被埋」的名字高密度混在一起，模型的上下文变成「这批是值得认识的公司」。
生产批次里 20 个陌生名字配 5 个锚点，**复现不出这个效应**（我加了锚点，反而比 round1
的无锚点 batch-40 更保守：tier>=2 从 317 家掉到 272 家）。

**我的替代方案见 A4 的回应（两段式富化），它实测回收 44 家。**

### A3：KAYAK 误伤 —— ✅ **接受，且实测发现根因在 prompt 不在决议顺序**

我做了两件事，第二件才是真正的修复：

1. **决议顺序改成按行求值**：ATS 否决位是**这一行岗位**的属性（这条岗位是不是从该公司
   自己的 Greenhouse/Lever/Ashby board 上抓来的），不是公司的属性。
   实测 `Jobgether` 因此被正确拆开：
   ```
   Jobgether 8/20 newgrad × 4 条  -> Lane C（转贴别家岗位）
   Jobgether 8/19 ats_direct × 1 条 -> Lane B1（它自己招 QA，这是真实雇主岗位）
   ```
   这比 round1「整家公司进 C」和 A 建议的「整家公司恢复否决」都更准确。
2. **prompt 里 `aggregator` → `job_board`，并写死语义边界**：
   ```
   CRITICAL: this is about aggregating JOB POSTINGS only. A company whose product
   aggregates anything else - flights, hotels, prices, restaurants, real-estate
   listings, shopping, news - is an "employer", NOT a job_board.
   Kayak, Booking, Expedia, Zillow, Yelp, Google are employers.
   ```
   **实测：`KAYAK` 从 `aggregator/t3` 变成 `employer/t3, prom 70`，两条岗位都落 Lane A1。**
   A 预言的整类风险（Booking/Expedia/Zillow/Yelp）从源头堵住了。

3. FP fixture 改成「**Lane C 全量逐天人工过**」（A 的第 3 条建议），见 §6.2。

### A4：tier 0 埋掉 44 家独角兽/上市公司 —— ✅ **接受，改法是两段式富化**

既然多采样无效（A2），我测了另一条路：**A4 自己给出的线索是「批次里全是值得认识的名字时，
模型认得出来」。生产上我事先不知道谁值得认识 —— 但 stage-1 跑完之后我知道了：
就是那堆 `unknown/tier0` 的残差。** 把残差单独拎出来组成高密度批次，再用更强的模型问一遍。

三模型对照（56 个难样本一批，含 5 个我编造的假公司）：

| | gpt-4o-mini | gpt-4o | gpt-4.1-mini |
|---|---|---|---|
| 成本（该批） | $0.0019 | $0.0266 | $0.0038 |
| GE Vernova | **t3** | **t3** | **t3** |
| ClickHouse / Ramp / Fubo / Waystar | t2/t1/t1/t1 | **t2/t2/t2/t2** | t2/t2/t2/t1 |
| Five Rings / Enigma / DataBank / Mintegral | t0/t0/t0/t0 | **t2/t2/t2/t2** | t2/t1/t1/t1 |
| 5 个假公司幻觉 | 0/5 | **0/5** | **1/5**（`Vexadyne Global Talent Partners` → staffing） |

**注意 `GE Vernova` 三个模型在密集批次里都给 tier 3。** A4 归因的「知识截止到 2023，
2024 分拆的公司必然不认识」**被证伪** —— 它是纯批次效应，模型是知道的。

**生产规模实测（stage 2 = gpt-4o 跑 stage-1 的 347 家残差，7 批 × 50）：**

```
残差 347 家 -> 回收 tier>=2: 44 家   tier1: 61 家   仍 tier0: 242 家
wall 40.5s   in 9018 / out 14939   cost $0.1719   missing rows 0
```

**对 A4 点名的 44 家被埋名单：13 家升到 tier>=2，8 家升到 tier1，23 家仍 tier0。**

```
->tier2+: ClickHouse, GE Vernova, ECS, Superhuman, Ramp, Fubo, Amplify, Zelis,
          Enigma, Waystar, Xendit, DataBank, Mintegral
->tier1 : Muon Space, Core4ce, Rhombus Power, Oklo, Character.AI, Warp,
          Wonderschool, Red Cat Holdings
```

顺带回收的还有 A2 点名的不稳定样本：`Handshake` t0→t2、`IMC` t0→t2、`WHOOP` t0→t2、
`Crusoe` t0→t1。**幻觉防线没有破**：`Thomas To` / `Sundayy` / `Onyx Chambers` /
`Stellar Alpina` / `Fionics` / `Forcepull` / `フジアルテ株式会社` 全部仍是
`unknown/t0/prom 0/"no knowledge"`。

**仍有 23 家没救回来**（Hadrian、AstroForge、Traba、Baseten、Flock、Nscale、
Overland AI、Xaira、Circana、OPENLANE、Red Cat…）。对这 23 家，我采纳 A 的第 2 条建议
而**拒绝**第 3 条：

- ✅ **采纳「用 `ats_registry` 拆 Lane B」**：零成本、零维护。有自有 ATS board 的
  tier0 公司进 **Lane B1**（默认展开），纯 tier0 进 **Lane B2**（默认折叠）。
  实测 8/19 的 B1 有 80 条 / 55 家 —— `Hadrian`、`Muon Space`、`Crusoe`、`Freeform`、
  `True Anomaly` 这类正好在里面。
- ❌ **拒绝「补一份几百行的 `hot_companies.txt`」**：硬约束写的是「人工介入必须是
  几十行的覆盖文件级别」，几百行的热门公司名单要人持续维护、会过期，正是 round1 §9.1
  否掉离线名单的同一个理由。而且实测 stage-2 已经把最值钱的一批（GE Vernova / ClickHouse /
  Ramp / Fubo / Waystar / Handshake / IMC / WHOOP）捞回来了，剩下 23 家全是
  1-3 条岗位的早期公司，落 B1 展开已经能看到。若用户以后确实想要，
  `company_overrides.json` 就是那个几十行文件。

### A5：tier 内字母序 —— ✅ **完全接受，且 LLM 给得出可用的分数**

采纳编排者 steer #2：富化时多输出一个 `prom`（0-100 大众知名度），prompt 里给了
锚点刻度（Google/Amazon/Microsoft = 100，OpenAI/NVIDIA/SpaceX/Meta = 95，
Stripe/Palantir/Databricks/Anduril = 85，Cisco/Adobe/Deloitte = 75，
Boeing/Ford/Micron/Leidos = 60，热门 Series-B = 40，没听说过 = 0）。

**实测这个分数可用，我不需要退回手工名单。** 8/20 队列里各档的实际成员：

```
prom 100 : Amazon, Google, Intel, Microsoft, Toyota North America
prom  95 : Google DeepMind, Meta, NVIDIA, OpenAI, SpaceX
prom  85 : AMD, Amazon Lab126, Anduril, Anthropic, Cloudflare, Intuit, JPMorganChase,
           Morgan Stanley, Palantir, Qualcomm, Salesforce, Stripe, eBay
prom  75 : Accenture Federal, Adobe, BofA, BlackRock, Booz Allen, Cisco, Deloitte, EY,
           Gartner, Lockheed Martin, Snowflake, Vanguard, Volvo
prom  70 : Blue Origin, Broadcom, Coinbase, Ford, John Deere, KLA, L3Harris, Vercel
prom  60 : ABB, BAE, Boeing, Cargill, Caterpillar, Charles Schwab, Citi, Dell, Discord,
           Draper, Epic, Ericsson, Esri, Micron, GE Vernova …
prom  40 : 1Password, Adyen, Alarm.com, Appian, Brex, ClickHouse, Five Rings, Handshake,
           IMC, Nuro, Ramp, WHOOP …
```

**它是稳的、不是编的**：3 遍富化之间 tier 一致率 93.2%，而 prom 直接由同一次调用给出；
prom 与 tier 的秩序不冲突（tier 0 强制 prom 0）。
新 TOP 30 见 §4.1 —— **前 15 行全是 Amazon / Google / Intel / Microsoft / SpaceX /
NVIDIA / DeepMind / Meta / OpenAI**，A5 完全解决。

`priority_companies.txt` 我**保留成一个空文件 + 5 行代码的钩子**（Lane A0，排在 prom 之前），
但不再是解决 A5 的手段，而是给用户表达个人偏好用（比如「我就想先看国防」）。默认为空。

### B1：「每天的岗位变化」P0 没产物 —— ✅ **完全接受**

Panel ④ 的折线推到 P1 是对的（2 个点画折线没信息量），但**「变化」本身必须进 P0**，
形式改成 B 建议的对照表。实测数据（round2 lane 口径，两天）：

```
              8/19    8/20      Δ
A1 大厂        42     147     +105
A2 大中        71     197     +126
B1 有自有board 80      10      -70
B2 其他       21     362     +341
C  中介/刷屏   16     214     +198
今日合计      230     930     +700
中介占比      7.0%   23.0%    ▲16.0pp
今日首次出现的公司  148/148   619/644
```

三个衍生量全部进 Panel ②′：中介占比、今日首次出现公司数、各 lane 的 Δ。
另外采纳 B 的提醒，在面板上写死一句：
**「本 dashboard 只追踪新增侧；`date_recorded` 是首次收录时间，岗位下架不会反映。」**

### B2：时间窗漏掉 2/3 + 无已读 —— ✅ **完全接受，进 P0**

我复核了 B 的实测，成立。8/20 逐小时累计：

```
00时 34  01时 126  02时 83  03时 74  04时 68  05时 108  06时 102  07时 78   <- 08:00 报告窗口到此，累计 673
08时 117  09时 147  10时 28   ...                                        <- 292 条落在窗口外
```

改法照 B 的方案：

- `logs/last_report.json` 存 `cutoff`；Panel ① 的行 = `date_recorded > cutoff`；
  生成成功后推进 cutoff。`--since` / `--no-advance` 供手动重跑。
- `a:visited` 变淡色作为「已点过」。
- **md 日报继续按自然日，视觉零变化**（这也是 B3 的要求）。

采纳 B 的第 4 节要求：`:visited` 是纯颜色编码，与「状态色必须配图标+文字」冲突，
**写成一条显式豁免**：浏览器隐私模型只允许 `:visited` 改颜色，做不到加图标；
且它编码的是「你自己点过没有」这种低风险信息，看不出来最多是重看一眼。

### B3：两级去重会搞坏 md 日报 —— ✅ **完全接受**

`(公司,标题)` 去重**只作用于 dashboard 的 Panel ①**，不进 `daily_report.py` 的共用
`dedup()`；自检告警的分母永远用 uid 去重后的条数；Panel ① 里同标题**折叠**成
`+13 条相同标题` 而不是删除。
按 §2 采纳 B 的简化方案后，`daily_report.py` 根本不被改，这条从机制上不可能发生。

### B5：失败隔离没落地 —— ✅ **完全接受**

三条全收，并加一条本轮现场撞到的：

1. 富化**移出日报任务**，单独一个 Task Scheduler 任务（07:30），日报/dashboard 只读缓存。
2. 富化整体墙钟上限 300 s（实测 stage1+stage2 全量 = 51.6 + 40.5 ≈ 92 s，留 3 倍余量），
   超时放弃本次富化。
3. `company_profiles.json` **原子写**（写临时文件 + `os.replace`）；读取时 JSON 解析失败
   降级为空表而不是崩溃。
4. **`resolve()` 必须是全函数** —— 本轮现场验证：我做实验期间采集器又跑了，语料从 680 家
   涨到 **767 家，其中 87 家不在富化表里**。`P[c]` 直接下标当场 KeyError。
   缺失一律返回 `{kind:"unknown", tier:0, prom:0, why:"not enriched"}`。
   这条要进回归 fixture。
5. 离线时仍生成 dashboard，并在面板顶部显式标注「今日富化失败/超时，N 家新公司未分层」。
   静默降级比报错更危险。

### B6：md 逐字节回归 —— ✅ **接受，但按 §2 之后这条自动消失**

采纳 B 的简化：不重构 `daily_report.py`，所以没有「md 可能变」的风险面。
保险起见仍保留一条 CI：`python daily_report.py --date 2026-08-19 --no-prune` 输出到临时路径，
与归档的 `logs/daily/2026-08-19.md` 逐字节 diff。这条现在是**防止别人以后手滑**，不是防本轮改动。

---

## 2. 采纳 B 的简化（编排者 steer #7）—— ✅ 全部采纳，实测支持

### 2.1 删掉 S2 / S3 / S4

我在 round2 的判定链上重跑了消融（不是照抄 B 的 round1 数字）：

```
round2 四步链之外，S2/S3/S4 还能额外抓到的公司：
    Infosoft, Inc.  (3 条)  靠 S4 stacks=3
    合计 1 家 / 3 条
```

比 round1 时更少了，因为新 prompt 直接把 `Capgemini` 和 `Capgemini Engineering`
**都判成 `outsourcing/t3`** —— 顺带把 A 的 **NB-3（同集团两个别名落相反 lane）** 一并修掉，
不需要额外的一致性检查。`Jack & Jill`（round2 里 LLM 判 unknown）由窗口速率规则抓到，
`Surge Software` 同理。

**S2 保留为 Panel ③ 的证据展示列**（「这家 85% 的标题是 `... at X` 转贴格式」对用户是
有用的解释），但不参与判定。S3/S4 整条删除，连带删掉那张 23 词技术栈表。

### 2.2 不重构 `daily_report.py`

采纳。新建 `dashboard.py`，`from daily_report import load_jobs, dedup, day_of`。
`daily_report.py` 只改 4 行（`gpt-4o-mini` 进 `MODEL_PRICING`）。

我同意 B 对 round1 §5.1 的批评：「用户不该开两个文件」被我错误地推导成了
「所以代码要合并」。**用户看到的文件数和代码怎么组织是两回事。**

### 2.3 面板 6 → 4

| 面板 | 去留 | 理由 |
|---|---|---|
| ① 阅读队列（含必看段/展开段/B1/B2/C） | **P0** | 需求 2 全部产物 |
| ②′ 今日 vs 昨日 + 中介占比 + 新公司数 | **P0** | 需求 1 上半句（B1） |
| ③ 中介证据表 + 疑似待确认子表 | **P0** | 需求 1 下半句 |
| ⓪ hero 数字「今天必看 35 条（昨天 25）」 | **P0** | 采纳 B 的 N-8，成本近零 |
| ② 漏斗 | P1 | 信息量被 ②′ 覆盖大半 |
| ⑤ 采集器健康 / ⑥ 告警+花费 | P1 | md 日报第 2、3 节已有，用户仍在看 md |

### 2.4 其它采纳的非阻断项

- **N-1**：去掉 checkbox（零 JS 下是死 UI），改成每行直接显示可复制的 `norm()` 键名，
  表格下方给一段全部注释掉的 override 模板。
- **N-3**：折叠状态定死 —— A0/必看段展开，其余全部 `<details>` 折叠。
- **N-4 / 配色**：lane 是**有序**类别，改用单一色相 5 级顺序色阶，天然免掉配对校验；
  三个来源保留槽位 1-3。同时记录一条事实：`scripts/validate_palette.js` **不存在**，
  req1 那条「实现前跑校验脚本」是悬空的 —— P0 里要么补这个脚本，要么把这条约定删掉。
- **N-5**：`JOB_PROFILE_PATH` 环境变量把 profiles 挪出 OneDrive（照抄 `JOB_LOG_ROOT` 模式）。
- **N-6**：`--refresh-unknown` 只重问 `kind=unknown` 的。
- **N-7**：额外写一份 `logs/daily/latest.html`（`shutil.copyfile`），给桌面快捷方式用。
- **N-9**：富化的 `run_summary` 用独立 `script` 名，md 日报按脚本分行显示花费。
- **NB-6**：`conf` **完全不显示**（0.2 ⟺ unknown 是 100% 对应的编码，展示 0.7 vs 0.9 是假精度）。
  Panel ③ 只显示 `kind` + 触发信号 + 一个二值的「LLM 认识 / 不认识」。
- **NB-5**：把 round1 的 P1-3（岗位相关性过滤）提到 P1 最前，排在趋势图之前。
  A 是对的 —— `City of Houston / Engineer-in-Training`、`Bridgestone / Manufacturing
  Infrastructure Tech I` 这类占了队列约 10%。
- **NB-2**：Panel ②′ 的中介占比旁标注「**这是下界**」。P1 加名字正则
  （`Staffing|Recruit|Talent|Search|Consulting|Infotech|Softech|Solutions Inc|Pvt Ltd`）
  → 只喂「疑似待确认」子表，不自动分流。

---

## 3. 修正后的中介识别

### 3.1 信号清单（5 条 → 3 条）

| # | 信号 | 判据 |
|---|---|---|
| O1 | 人工覆盖 | `company_overrides.json` |
| S1 | LLM `kind` | `staffing` / `outsourcing` / `training` / `job_board` |
| V1 | ATS 否决位 | **该行岗位**来自 `ats_jobs.csv`（公司自有 board） |
| S5 | 窗口内量大 + 查无此人 | `kind=="unknown" and tier==0 and n_7d>=5 and n_7d/总数>=0.4%` |

### 3.2 决议顺序（按**行**求值）

```
1. O1  override 命中                                   → 采用人工结论
2. S1  kind ∈ {staffing, outsourcing, training}        → Lane C（否决位救不回）
3. S1  kind == job_board                               → 公司标记中介，但继续第 4 步
4. V1  这一行来自公司自有 ATS board                     → 真实雇主行，出 Lane C
5. S5  窗口速率触发（且该公司无自有 board）             → Lane C
6. 否则                                                 → 真实雇主，按 tier/prom 分层
```

第 3+4 步的组合就是 KAYAK / Jobgether 的正确解：公司可以既是聚合站又是雇主，
**决定 lane 的是这条岗位的来源，不是公司的身份**。

### 3.3 分层

| lane | 定义 | 8/20 |
|---|---|---|
| A0 | `priority_companies.txt` 命中（默认空） | 0 |
| A1 | tier 3 | 147 条 / 81 家 |
| A2 | tier 2 | 197 条 / 162 家 |
| B1 | tier ≤1 **但有自有 ATS board**（正经在招人的公司） | 10 条 / 8 家 |
| B2 | 其余 | 362 条 / 312 家 |
| C | 中介 | 214 条 / 81 家 |

（8/19 的 B1 有 80 条 / 55 家 —— ats_direct 首日全量收割都落在这里。）

### 3.4 实测误伤：0

用户点名的 6 家 + A 点名的全部反例，在 round2 判定链下：

| 公司 | round1 | round2 | lane |
|---|---|---|---|
| Deloitte | t3/employer | t3/employer prom 75 | A1 |
| Palantir | t3/employer | t3/employer prom 85 | A1 |
| SpaceX | t3/employer | t3/employer prom 95 | A1 |
| Booz Allen Hamilton | t3/employer | t3/employer prom 75 | A1 |
| Micron Technology | t3/employer | t3/employer prom 60 | A1 |
| Anduril / Anduril Industries | t2/employer | t2/employer prom 85 | A2 |
| **KAYAK** | **t3/aggregator → Lane C ❌** | **t3/employer prom 70** | **A1 ✅** |
| **Handshake** | t0/unknown（靠否决位勉强救回） | **t2/employer** | A2 ✅ |
| **IMC** | t0/unknown（A2 测出会抖） | **t2/employer** | A2 ✅ |
| **WHOOP** | t0/unknown | **t2/employer** | A2 ✅ |
| **Five Rings / FlexTrade** | t2（A 实测会抖到 t1/t0） | t2/employer（stage2 稳定复现） | A2 ✅ |
| **Exadel** | t1/outsourcing（A 实测会逃逸） | t1/outsourcing | C ✅ |
| Texas Sports Academy Main | t0（靠否决位） | t0（自有 board） | B1 ✅ |
| **Fluence** | t2 | **t0/unknown** ❌ | B2 ⚠️ 唯一一处倒退 |

**Lane C 全量 81 家逐条人工复核（8/20）+ 9 家（8/19）：没有一家真实雇主。**
8/19 那张表里 round1 的 KAYAK / Ace IT Careers / Jobgether 全部消失，现在是
Infosys(4) / Capgemini(3) / TEKsystems(2) / Epic Placements(2) / NPAworldwide /
Pop-Up Talent / BioSpace / Capgemini Engineering / Mathys+Potestio，全部正确。

### 3.5 召回改善（A 的 NB-2）

A 手工列了 50 家「被漏掉的中介」。round2 的档案表：

```
现在被 LLM kind 抓到: 16/50   （round1: 0/50）
新抓到的: W3Global, KPG99 INC, Technogen, JSR Tech Consulting, Delphi-US,
          Hirematic Talent Solutions, Prudent Technologies, Precision Technologies,
          Ztek Consulting, AXISCADES, Amtex Systems, Centraprise, Q1 Technologies,
          BoF Careers, Founders.Careers, Jobverse.io
仍漏 34 家：一簇英国金融猎头（Vallum / Saragossa / Orbis / Albert Bow …）
            + 一簇极小的印度背景 body shop（Tavas / Willsmarg / Glint Tech / PALNAR …）
```

Lane C 从 62 家/185 条涨到 **81 家/214 条**（当日占比 22.7% → 23.0%）。
剩下 34 家仍按 A 的判断走 P1 的名字正则 → 「疑似待确认」子表，不自动分流。
Panel ②′ 的中介占比继续标注为**下界**。

---

## 4. 修正后的阅读队列

### 4.1 新 TOP 30（prom 排序，8/20，cap 2/公司）

排序键：`(不在 priority 名单, -tier, -prom, -窗口内岗位数, 公司名)`。

```
  1. [T3 p100] Amazon                | Software Development Engineer, Sponsored Products
  2. [T3 p100] Amazon                | Software Development Engineer, Personalization
             (+5 more from Amazon)
  3. [T3 p100] Google                | Software Engineer, Embedded Systems/Firmware
  4. [T3 p100] Google                | TV Partner Engineer, YouTube
             (+1 more from Google)
  5. [T3 p100] Intel                 | Hardware Platform Applications Engineer - Military
  6. [T3 p100] Intel                 | AI Software Engineering Intern
  7. [T3 p100] Microsoft             | Quantum Software Engineer
  8. [T3 p100] Toyota North America  | Snowflake & Analytics Platform Engineer
  9. [T3 p 95] SpaceX                | Software Engineer, CDN (Starlink)
 10. [T3 p 95] SpaceX                | Full Stack Software Engineer, Data (Starlink)
             (+5 more from SpaceX)
 11. [T3 p 95] NVIDIA                | HPC Middleware Developer
 12. [T3 p 95] NVIDIA                | Software Quality Assurance Engineer - 2026 New College Grad
 13. [T3 p 95] Google DeepMind       | Research Engineer, AGI Safety and Alignment
 14. [T3 p 95] OpenAI                | Full Stack Software Engineer, ChatGPT Finances
 15. [T3 p 95] Meta                  | Software Engineer - Storage
 16. [T3 p 85] Qualcomm              | QGOV Security Software Engineer
 17. [T3 p 85] Qualcomm              | #System Software Engineer - Power
             (+2 more from Qualcomm)
 18. [T3 p 85] Morgan Stanley        | AI Full Stack Engineer (Prime Brokerage Technology)
 19. [T3 p 85] Salesforce            | Technical Support Engineer - Agentforce & Data 360
 20. [T3 p 85] Salesforce            | Cloud Development Environment Engineer
 21. [T3 p 85] Stripe                | Fullstack Engineer, Privy
 22. [T3 p 85] Stripe                | Forward Deployed Engineer, Professional Services
 23. [T3 p 85] Amazon Lab126         | Software Development Engineer, Abuse Prevention
 24. [T3 p 85] Cloudflare            | Software Engineer, Cloudflare Network Interconnect
 25. [T3 p 85] Cloudflare            | GRC Engineer
 26. [T3 p 85] Palantir Technologies | Software Engineer, New Grad
 27. [T3 p 85] Palantir Technologies | Software Engineer, New Grad - Production Infrastructure
 28. [T3 p 85] AMD                   | CPU Core Design Verification Engineer
 29. [T3 p 85] eBay                  | Network Security Automation Engineer
 30. [T3 p 85] Intuit                | Software Engineer 1
```

并排对比 round1 的同一位置：

| 行 | round1（tier 内字母序） | round2（prom 排序） |
|---|---|---|
| 1-5 | ABB, Accenture Federal, Adobe×2, Amazon | **Amazon×2, Google×2, Intel** |
| 6-10 | Amazon, AMD, BAE×2, Bank of America | **Intel, Microsoft, Toyota NA, SpaceX×2** |
| 11-15 | Baxter, BlackRock, BCBS-MA, Boeing×2 | **NVIDIA×2, DeepMind, OpenAI, Meta** |
| 29 | **City of Houston「Engineer-in-Training」** | eBay「Network Security Automation Engineer」|
| FAANG 首次出现 | 第 63 行（Google） | **第 3 行** |

A5 解决。

### 4.2 「用户一天能看多少条」—— 正面回答（编排者 steer #6）

**目标：首屏 35 行左右，全部内容通过渐进展开可达，零丢弃。**

`prom` 给了一个可调的刀。实测 8/20 各档的 cap-2 行数：

```
prom>=  行数(cap2)  公司数
   95      15         10
   85      35         23     ← 「今日必看」段
   75      55         39
   70      70         49
   60     138         98
   40     292        236
    0     299        243
```

分段设计（全部用 `<details>`，零 JS）：

| 段 | 内容 | 8/20 行数 | 默认 |
|---|---|---|---|
| ⓪ hero | 「今天必看 **35** 条（昨天 25）」 | 1 | — |
| ① 今日必看 | A0 + prom≥85，cap 2 | **35** | 展开 |
| ② 还想看 | prom 60-84，cap 2 | 103 | 折叠 |
| ③ 其余大中公司 | prom<60 的 A1/A2 | 161 | 折叠 |
| ④ 正经在招人的小公司 | B1（有自有 ATS board） | 10 | 折叠 |
| ⑤ 长尾 | B2 | 362 | 折叠 |
| ⑥ 中介/刷屏 | C | 214 | 折叠 |

**首屏 35 行，对比现在用户实际在看的 md 日报 3076 行 / 938 个链接，是 27 倍压缩；
对比 round1 的 140 行是 4 倍。** 而且不丢任何东西 —— 六段加起来 = 当日全部 930 条。

叠加 B2 的水位线之后，②-⑥ 的内容第二天不会重复出现，`a:visited` 让点过的行变淡。
再叠加 P1 的岗位相关性过滤，预计 ①段还能再降三成。

---

## 5. 成本 / 冷启动 / 失败模式（更新）

### 5.1 成本（全部实测）

**生产流程 = stage1 一遍 + stage2 一遍**（多采样已被 A2 的实测否掉）：

| 阶段 | 模型 | 范围 | 耗时 | 花费 |
|---|---|---|---|---|
| stage 1 | gpt-4o-mini | 680 家，batch 20 + 5 锚点 | 129 s | $0.0109 |
| stage 2 | gpt-4o | 347 家残差，batch 50 | 41 s | $0.1719 |
| **合计（首次全量）** | | 680 家 | **170 s** | **$0.183** |

单家成本 $0.00027，比 round1 的 $0.0000204 贵 13 倍。**这个涨价是买 A4 的 44 家回收 +
A3 的 KAYAK 修复 + NB-2 的 16 家召回，我认为值。**

日增量（按 B 的 N-5 实测外推 500-1200 家新公司/天，其中约 60% 落残差）：

```
乐观 500 家/天 : stage1 $0.008 + stage2 $0.149 ≈ $0.16/天
悲观 1200 家/天: stage1 $0.019 + stage2 $0.357 ≈ $0.38/天
```

**悲观值已经逼近 `LLM_DAILY_COST_ALERT_USD = 0.50`。** 所以 P0 必须带一个
**确定性预算闸门**：每天 stage-2 最多升级 400 家（按窗口内岗位数降序优先），
其余排到明天。这把日花费钉死在 ≤ $0.13（stage2）+ stage1。

我实测过一个更省的闸门（只升级岗位数 ≥2 的残差）并**否决了它**：

```
gate n>=1 : 升级 347 家，回收 44 家，$0.172
gate n>=2 : 升级  88 家，回收 13 家，$0.044   ← 丢掉 BigBear.ai / Draper / DataBank / Amplify …
gate n>=3 : 升级  33 家，回收  2 家，$0.016
```

回收价值最高的公司恰恰只有 1 条岗位（一条 Google 级岗位就是全部意义），按量设闸门
正好砍掉最想要的东西。**按天配额（先到先服务）比按量设阈值正确。**

更便宜的 stage-2 模型我也测了，**不推荐**：

```
gpt-4.1-mini  $0.0211（便宜 8 倍）  回收 26 家（vs 4o 的 44 家）
              与 4o 的 tier 一致率 74.6%
              丢掉：ClickHouse, Five Rings, FlexTrade, IMC, Enigma, DataBank, ECS,
                    Superhuman, Mintegral
              且 5 个假公司里编了 1 个（Vexadyne Global Talent Partners → staffing）
```

`gpt-4o` 也要进 `MODEL_PRICING`（P0-3 从 1 个模型变 2 个）。

### 5.2 冷启动

判定层依然零跨天依赖（`tier`/`prom`/`kind` 来自世界知识，S5 的窗口在 2 天数据下
= 全量，与 round1 等价 —— 这也是 B 说的「零精度损失」）。
Panel ②′ 只要 2 天就能用。折线图仍等 ≥7 天。

### 5.3 失败模式（新增 4 条，round1 §7.5 的旧条目保留）

| 失败模式 | 本轮实测 | 缓解 |
|---|---|---|
| **`json_object` 模式报 400** | 本轮真撞到：prompt 里没有字面的 "json" 一词，OpenAI 直接 400，而我的重试循环**吞掉了异常**，跑完 117 秒才发现 3 遍全空 | prompt 里保留字面 "JSON"；重试耗尽必须打印异常；批次全空要让整个 run 非零退出 |
| **富化表落后于语料** | 本轮实测：实验期间语料从 680 家涨到 767 家，**87 家不在表里** | `resolve()` 全函数；面板顶部显示「N 家未分层」 |
| **stage-2 把小公司抬太高** | 未观察到：242 家仍 tier0，7 个对照名（含 3 个真实小公司）全部 `unknown/t0/prom 0` | 保留 prompt 硬规则原文，改 prompt 必须重跑 fixture |
| **批次组成效应** | 已量化：同一模型同一 prompt，稀疏批次 tier0，密集残差批次 tier2/t3 | 这已经是 stage-2 的设计前提；stage-2 的批次必须**全部由残差组成**，不要混入已知公司 |

---

## 6. 验收标准（替换 round1 §8 的 5 条）

round1 的验收 gate 建立在会漂移的 oracle 上（A2），现在改成断言**缓存值**和**结构性质**：

1. `resolve()` 对 60 家真实雇主 fixture 的中介误判 = **0**（断言 `company_profiles.json` 缓存值）
2. `resolve()` 对 profiles 里**不存在**的公司返回 tier 0 且不抛异常
3. **时间稳定性**：把语料复制成 30 天的合成集，断言 Lane C 公司数增长 ≤ 1.5 倍
   （实测窗口规则恒定 8 家；累计规则会到 278 家 —— 这条 gate 专门锁 A1）
4. 8/20 首屏（prom≥85, cap2）行数 ∈ [25, 50]（现测 **35**）
5. 8/19 与 8/20 的 Lane C **全量**成员逐家列出，人工签核无真实雇主（现测 9 家 + 81 家全过）
6. `KAYAK` 两条 ats_direct 岗位在 Lane A1；`Jobgether` 的 newgrad 行在 C、ats_direct 行不在 C
7. Deloitte / Palantir / SpaceX / Booz Allen / Micron / Anduril 在 Lane A
8. `python daily_report.py --date 2026-08-19 --no-prune` 与归档 md **逐字节相同**
9. 富化全量：dropped rows = 0，墙钟 < 300 s，花费 < $0.30

---

## 7. 更新后的 P0 / P1

### P0

| # | 任务 | 新增行 | 改动行 |
|---|---|---|---|
| 1 | `enrich_companies.py`：两段式（4o-mini 锚点批 20 → gpt-4o 残差批 50）、只问新公司、按 name 回填、原子写、整体超时 300 s、每日 stage-2 配额 400、`--rebuild` / `--refresh-unknown` | ~200 | 0 |
| 2 | 用 `dashboard_loop/company_profiles.round2.json` 作初始缓存（680 家已富化） | 0 | 0 |
| 3 | `company_lane.py`：4 步决议、**按行求值**、7 天窗口、全函数 | ~90 | 0 |
| 4 | `company_overrides.json` + `priority_companies.txt`（默认空）读取 | ~25 | 0 |
| 5 | `dashboard.py`：hero + Panel ①（6 段 `<details>`）+ ②′ + ③、水位线、`a:visited`、`latest.html` | ~300 | 0 |
| 6 | `gpt-4o-mini` 与 `gpt-4o` 进 `MODEL_PRICING` | 0 | 8 |
| 7 | 回归 fixture（§6 的 9 条） | ~120 | 0 |
| 8 | 新增 Task Scheduler 任务 `run_logged.bat run_enrich_companies`（07:30） | 3 | 0 |
| | **合计** | **~740** | **8** |

对比 round1 的 ~950 新增 + ~165 改在用户每天依赖的文件里。比 B 的 580 行估算多约 160 行，
差额来自两段式富化、按行求值、和 §6 多出来的 4 条 fixture。

### P1（按价值排序，已按 A 的 NB-5 调整顺序）

1. 岗位相关性过滤（把非软件岗剔出队列，预计首屏再降三成）
2. 名字正则 → Panel ③「疑似待确认」子表（覆盖 NB-2 剩下的 34 家）
3. `mark_applied.py` 真正的已投写入路径
4. Panel ④ 趋势折线（等 ≥7 天）
5. Panel ② 漏斗 / ⑤ 健康 / ⑥ 花费
6. `override.py add "..." --kind staffing` 一行命令（B 的 N-2）
7. `JOB_PROFILE_PATH` + 90 天未出现的 tier0 公司清理（B 的 N-5）
8. 补 `scripts/validate_palette.js`，或删掉 req1 里那条悬空约定

---

## 8. 复现

产物已拷进 `dashboard_loop/`：

| 文件 | 说明 |
|---|---|
| **`company_profiles.round2.json`** | **680 家 round2 档案（含 `prom`/`stage`），P0 的初始缓存** |
| `enrich_v4.py` | stage-1：v4 prompt（`job_board` 收紧 + `prom`）+ 锚点批次 |
| `stage2.py` | stage-2：残差密集批 + 强模型 |
| `r2.py` | round2 resolver（4 步、按行、7 天窗口、全函数） |
| `passes_v4.json` | 3 遍 stage-1 原始输出（A2 的稳定性数据） |
| `stage2_gpt-4o.json` | stage-2 输出 |

```bash
export PYTHONIOENCODING=utf-8
cd D:/OneDrive/work/school/project/Job
# 注意：脚本目录里不能有名为 queue.py 的文件（会 shadow stdlib queue，
# openai -> httpcore -> trio 导入链直接炸）。评估者 A 已经踩过，我也踩了一次。
D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/enrich_v4.py 1
D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/stage2.py gpt-4o
```

本轮 LLM 实测花费明细：3 遍 stage-1 $0.0983 + 三模型对照 $0.0323 +
stage-2 gpt-4o $0.1719 + stage-2 gpt-4.1-mini $0.0211 = **$0.3236**。

---

## 9. 我在本轮明确反对的两条 steer

1. **steer #1「跑 3 遍取多数票 / max tier，能回收一半被埋的公司」** —— 实测反对。
   3 遍全量（$0.0983）只回收 5 家、赔掉 37 家；对 A4 的 44 家名单只回收 2 家。
   多采样买到的是一致性（93.2%/96.8%），不是召回。
   **回收要靠改批次组成 + 换强模型（两段式），实测回收 44 家。**
   「单调升级」规则我仍然采纳，但它的作用是防漂移，不是回收。

2. **A4 建议 3「补一份几百行的 `hot_companies.txt`」** —— 反对。
   违反「人工介入 = 几十行覆盖文件」的硬约束，且 stage-2 已经把最值钱的一批捞回来了。
   剩下 23 家用零成本的 Lane B1（有自有 ATS board，默认展开）兜住。

其余 9 条阻断项全部接受并已给出实测过的改法。
