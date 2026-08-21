# Round 1 评估 A —— 数据与方法论审查

## 结论：FAIL

> 评估者：评估者 A（数据/方法论）
> 日期：2026-08-20
> 立场：试图证伪。下面每个数字我都自己跑过，脚本落在 `dashboard_loop/_evalA_*.py`。
> 我又花了 **9 次 gpt-4o-mini 调用**（约 $0.006）做 LLM 可靠性测试。

**为什么 FAIL 而不是 PASS**：方案的**静态复现性极好**（§「我核对通过的部分」列了 12 条我一次跑通的数字，
作者没有虚报任何一个），但它的三个核心判据在**时间维度**和**重跑维度**上不成立：

1. 中介判定的唯一主力信号 `S5` 用的是**跨天累计的绝对阈值**，实测约 10 天数据后会把 **100% 的
   tier-0 公司**判成中介；
2. LLM 标签在 **temperature=0、同一 prompt、同一批次**下重跑，**10% 的公司标签变化、4.2% 换 lane**，
   而方案的验收标准和回归 fixture 全部建立在这个不稳定的 oracle 上；
3. tier 0 里**埋掉了 44 家独角兽/上市公司**（8/20 有 55 条岗位），包括 GE Vernova（S&P 500）、
   Ramp、ClickHouse、Character.AI —— 这正是「找 new grad 工作的人最想看」的那一段。

这三条都落在「会让用户看到错误结论 / 漏掉重要岗位」的 FAIL 判据上，且都不能推到 P1。
好消息是**五条阻断项加起来大概是 1 天的修改量**，判定层的骨架（公司档案表 + kind/tier 正交 +
override）我认为是对的，不需要推倒重来。

---

## 复现环境

```bash
export PYTHONIOENCODING=utf-8
cd D:/OneDrive/work/school/project/Job/dashboard_loop
D:/Apps/Miniconda/envs/job-classifier/python.exe _evalA_repro.py            # §6.1 全量复现
D:/Apps/Miniconda/envs/job-classifier/python.exe _evalA_threshold_drift.py  # 阻断-1
D:/Apps/Miniconda/envs/job-classifier/python.exe _evalA_lanec_fp.py         # 阻断-3
D:/Apps/Miniconda/envs/job-classifier/python.exe _evalA_tier0_buried.py     # 阻断-4
D:/Apps/Miniconda/envs/job-classifier/python.exe _evalA_queue_order.py      # 阻断-5
D:/Apps/Miniconda/envs/job-classifier/python.exe _evalA_signal_ablation.py  # 非阻断-1
```

> 注：`_verify_queue.py` 有一个坑 —— 它 `from base import *`，需要把 `_verify_base.py`
> 改名成 `base.py`，且**文件名不能叫 `queue.py`**（会 shadow 掉 stdlib 的 `queue`，
> `openai` → `httpcore` → `trio` 导入链直接炸）。我的 `_evalA_*.py` 已经修好这两点，可以原地跑。

---

# 阻断项（blocking）

## 阻断-1 ★★★ `S5` 用累计绝对阈值，10 天后中介层会吞掉整个 tier 0

**这是我认为最严重的一条。**

`_verify_queue.py:classify()` 里 `n = len(allg[c])` 是这家公司在**全部 CSV、全部日期**上的
累计岗位数，不是当日数。规则 `kind=="unknown" and tier==0 and n>=5` 因此是一个
**单调增长的量**去比一个**固定的绝对数**。今天数据只有 2 天，所以看起来很干净；
数据越攒越多，这条规则必然滑向「凡是 LLM 不认识的公司都是中介」。

实测（`_evalA_threshold_drift.py`）—— 当前 300 家 tier-0/unknown 公司的累计岗位分布：

```
n=1:227家  n=2:45  n=3:11  n=4:8  n=5:3  n=6:1  n=8:2  n=13:1  n=15:1  n=39:1
```

保持阈值 5 不变，把每家公司的累计量按 k 倍线性外推（= 攒 2k 天数据）：

```
k= 1 (~2 天，今天)  :   9 / 300 家被判中介 (  3%)
k= 2 (~4 天)        :  28 / 300 家       (  9%)
k= 3 (~6 天)        :  73 / 300 家       ( 24%)
k= 5 (~10 天)       : 300 / 300 家       (100%)   ← 全线崩溃
k=14 (~28 天)       : 300 / 300 家       (100%)
```

**后果是双向的**：中介面板（Panel ③）会从 62 行涨到几百行变成噪音表；同时 Lane B 里
每一家 LLM 不认识的真实小公司（含下面阻断-4 那 44 家独角兽）都会被扔进「中介」，
用户会直接看到**错误结论**。这不是「以后再优化」，是这套规则跑第二周就坏。

顺带：同一段代码里 `S4` 的判据是 `len(stacks)/n >= 0.25`，分母也是累计 n，
所以它的漂移方向**正好相反 —— 越攒数据越不触发**：

```
Infosys  stacks=3 n=11 ratio=0.27 → 10 倍数据后 0.027（失效）
Surge    stacks=8 n=15 ratio=0.53 → 10 倍数据后 0.053（失效）
Capgemini stacks=3 n=6 ratio=0.50 → 10 倍数据后 0.050（失效）
```

**S5 越来越疯，S4 越来越哑，两条都在漂。**

**建议改法（P0）**

1. `S5` 的 n 必须限定窗口：改成「**最近 7 天（或最近 N 个采集日）内的岗位数**」，
   并且改成**相对量**：`该公司当窗口岗位数 / 当窗口总岗位数 >= p`。用今天的数据反解
   p ≈ 5/1252 ≈ 0.4%，就能同时命中 BeaconFire(39) 和放过 ClickHouse(3)。
   同时加一个绝对下限（如 ≥3）防止小样本日误伤。
2. `S4` 的分母同样换成窗口内岗位数，或者干脆改成**不看比例只看栈数下限 + 单日栈数**。
3. 在 P0 验收标准里加一条**时间稳定性断言**：把 CSV 人为复制 5 份（模拟 10 天），
   断言 Lane C 公司数增长不超过 X 倍。现在的验收标准（`Lane C 条数 ∈ [170,200]`）
   只锁了 8/20 这一天，锁不住漂移。

---

## 阻断-2 ★★★ LLM 标签在 temperature=0 下不可复现：重跑 10% 变标签、4.2% 换 lane

方案把 `tier`/`kind` 当成公司的**客观属性**（「LLM 世界知识」），P0-5 还要拿它做回归
fixture 断言 FP=0。我实测它不是属性，是**一个分布的采样**。

**测试 1 —— 重跑作者自己的生产批次。** 我按 `_verify_enrich_all.py` 的分批方式
（680 家按小写名排序、每批 40）重建第 1 / 6 / 11 批，用同一个 prompt、同一个模型、
temperature=0 重跑，与 `company_profiles.sample.json` 对比（`_evalA_llm_rerun_diff.py`）：

```
re-ran 3 of the 17 production batches (120 companies)
  label changed (kind or tier): 12/120 = 10.0%
  of which LANE changed        :  5/120 =  4.2%
  rows the model failed to return: 0
```

换 lane 的 5 家，每一家都很要命：

| 公司 | 缓存值 | 重跑值 | 影响 |
|---|---|---|---|
| **Exadel** | outsourcing/t1 | unknown/t0 | **Lane C → B**：一家真外包跑出了中介层 |
| **Five Rings** | employer/t2 | employer/t1 | **Lane A → B**：作者 60 家 fixture 里点名的头部量化掉出第一屏 |
| **FlexTrade** | employer/t2 | employer/t1 | Lane A → B |
| **Fluence** | employer/t2 | employer/t1 | Lane A → B |
| **Founders.Careers** | unknown/t0 | aggregator/t1 | **Lane B → C**：一家真实雇主（也可能真是聚合站）被翻牌 |

另外 7 家只是 tier 抖动但同样刺眼：`Fiserv` t3→t2、`Florida International University` t3→t2、
`NXP Semiconductors` t2→t3、`NTT DATA` t2→t3、`FinThrive`/`FlexGen` employer/t1→unknown/t0、
`Onvida Health` unknown/t0→employer/t1。

**测试 2 —— 同一批 48 家问两遍。** 我构造了一个 48 家的对抗集（真实但小众、名字有歧义、
名字体面的中介、我编的假公司），同一个文件连问两次：

```
kind/tier disagreements between two identical temperature-0 runs: 4 / 48 = 8.3%
  iTech US   outsourcing/t1 → unknown/t0      ← 中介逃逸
  Crusoe     employer/t1    → unknown/t0
  IMC        employer/t2    → unknown/t0      ← 头部量化，A2 → B
  WHOOP      employer/t1    → employer/t2     ← B → A2
```

**为什么这是阻断项**，而不是「LLM 就这样」：

- P0 的验收标准是 `Lane A1 cap-2 行数 ∈ [120,160]`、`Lane C 条数 ∈ [170,200]`、`FP = 0`。
  在 10% 标签噪声下，**改 prompt 引入的退化和随机抖动无法区分** —— 这套 gate 是失效的。
- §7.1 明确把「全量重跑（换模型 / 改 prompt）$0.014」列为常规操作。实测这个操作会
  **静默重排约 4% 公司的 lane**，用户第二天看到的第一屏和昨天不一样，且没有任何提示。
- §7.5 已经处理了「批次少返回行」（按 name 回填），但没处理「批次返回了行、内容是另一次采样」。

**建议改法（P0）**

1. **富化对同一家公司只跑一次，缓存即真理，永不因重跑而改写。**
   `enrich_companies.py` 必须硬性只对 `company_profiles.json` 里**不存在的键**发请求；
   全量重跑要写成一个显式的、会产出 diff 报告的独立命令，不能是日常路径。
2. **对进第一屏的公司做 self-consistency**：只对 `tier>=2` 或 `kind ∈ INTER` 的候选
   跑 3 次取多数（约 380 家 × 2 次额外 = +$0.015，一次性，完全可接受）。
   低置信采样自动降级成 tier 0 + 标注 `unstable`。
3. **回归 fixture 断言的对象改成 `company_profiles.json` 里的缓存值，不是模型**。
   模型漂移用另一个「季度体检」脚本测，输出 diff 给人看，不进 CI 断言。

---

## 阻断-3 ★★ 「0 误伤」是 fixture 选择偏差：8/19 的中介面板里就躺着一家 KAYAK

方案的核心卖点是 §4.4 / §6.4 的 `FALSE POSITIVES: 0 / 60`。这 60 家是作者自己挑的，
而 §4.5 的「人工复核这 62 家没有一家是真实雇主」只复核了 **8/20**。我把 8/19 也跑了
（`_evalA_lanec_fp.py`）：

```
=== 2026-08-19 Lane C : 10 companies / 17 jobs ===
    4  Infosys              llm:outsourcing|stack3
    3  Capgemini            stack3
    2  TEKsystems           llm:staffing
    2  Epic Placements      llm:staffing
    1  NPAworldwide         llm:staffing
    1  Pop-Up Talent        llm:staffing
    1  BioSpace             llm:aggregator
    1  Jobgether            llm:aggregator   <-- HAS OWN ATS BOARD
    1  KAYAK                llm:aggregator   <-- HAS OWN ATS BOARD   ★ 误伤
    1  Ace IT Careers       llm:training     <-- HAS OWN ATS BOARD
```

`KAYAK` 的档案是 `{'kind':'aggregator','tier':3,'conf':0.8,'why':'household name'}`，
它的 2 条岗位**全部来自 `ats_jobs.csv`（ats_direct，8/19，"Associate Software Engineer"）**
—— 也就是全流水线里信号最强的那一档：直连自有 ATS board。

它照样进了中介层，因为 §4.2 的决议顺序把 `S1`（LLM kind）排在 `V1`（ATS 否决位）**之前**。
这个顺序是为 `Jobgether` 量身定的（n=1 的样本），代价是：**任何被 LLM 判成 `aggregator`
的公司，即使它有自有 board、即使这条岗位就是从它自己 board 上抓的，也救不回来。**

而 `aggregator` 这个词在 prompt 里的定义是「job board / job aggregator」，模型显然把
KAYAK 的**机票聚合**业务读成了聚合站。这个语义碰撞不是一次性的 —— Booking、Expedia、
Zillow、Yelp、Kayak 这一整类「metasearch / marketplace 业务的正经雇主」都会踩。
8/19 的中介面板 FP 率 = **1/10 家 = 10%**，不是 0。

**建议改法（P0，很小）**

1. `V1` 对 `aggregator` **恢复否决权**，只对 `staffing` / `training` 保持 S1 优先：
   「有自己的 Greenhouse/Lever/Ashby board 且岗位来自该 board」≈ 真实雇主这条对
   Jobgether 也不算错（Jobgether 招自己的员工时确实是雇主）。
   或者更保守：`aggregator + 有自有 board` → 不进 Lane C，进 Panel ③ 的「疑似待确认」子表。
2. prompt 里把 `aggregator` 改写成 **`job_board`**，定义收紧为「**转贴其他公司招聘信息**
   的平台」，并显式写「聚合非招聘信息的产品（机票/酒店/商品比价）不算」。
3. 把 FP fixture 从「60 家我挑的真实雇主」改成「**全部 Lane C 成员，逐天全量人工过一遍**」——
   现在 62 家的规模完全过得来，而且这才是真正的 FP 面。

---

## 阻断-4 ★★★ tier 0 埋掉了 44 家独角兽 / 上市公司（8/20 共 55 条岗位）

§3.3 说「降级正确」，证据是抽查了 8 个名字（Fionics / Netic / Gradial / Sundayy /
Onyx Chambers / Stellar Alpina / Thomas To / フジアルテ）。这 8 个是**从长尾里挑的**。
我把 8/20 Lane B 的 252 家全扫了一遍（`_evalA_tier0_buried.py`）：

```
8/20 Lane B（默认折叠成一行）: 301 jobs / 252 companies
其中我判为「值得看」的（独角兽 / 上市公司 / 头部创业公司）: 44 家 / 55 条岗位 = Lane B 的 18%
```

44 家的完整名单（全部 tier 0，除 Oklo 是 tier 1）：

```
Muon Space 3   Confido 3   Gradial 3   ClickHouse 3   GE Vernova 2   Hadrian 2   ECS 2
Core4ce  Vantor  Superhuman  Rhombus Power  AstroForge  Oklo(t1)  Character.AI  Fonzi AI
Warp  Flock  Netic  Wonderschool  Atticus  Otter  Ramp  Overland AI  Fubo  Doppel
HappyRobot  Nooks  Traba  Nscale  Radiant  Red Cat Holdings  11x  Amplify  Circana
OPENLANE  Zelis  Enigma  Waystar  Xendit  DataBank  Xaira Therapeutics  Mintegral
Baseten  Squint
```

**最硬的一个反例：`GE Vernova`。** 它是 2024 年从 GE 分拆的 S&P 500 成分股，
市值约千亿美元，在方案的 tier 定义里毫无疑问是 tier 3。它被判 `unknown / tier 0`，
落进默认折叠的 Lane B。

其余里还有一批**已上市公司**：`Fubo`(NYSE)、`OPENLANE`(NYSE)、`Waystar`(NASDAQ)、
`Red Cat Holdings`(NASDAQ)、`Circana`、`Zelis`；一批**独角兽**：
`Ramp`、`ClickHouse`、`Flock`、`Abridge`、`Vultr`、`Baseten`、`Nscale`、`WHOOP`、
`Traba`、`Xaira`；以及一整批**新 grad 最想投的国防/太空早期公司**：
`Hadrian`、`Muon Space`、`AstroForge`、`Overland AI`、`Rhombus Power`、`Radiant`、`Oklo`。

**这不是模型能力问题，是 prompt / 批次设计问题。** 我把其中 14 家丢进一个混了知名公司的
批次重问，**7 家立刻被认出来**：

```
                 生产缓存(batch40)   我的对抗批次 run1   run2
GE Vernova       unknown/t0          employer/t2        employer/t2   （单独问又变 t3）
ClickHouse       unknown/t0          employer/t2        employer/t2
Waystar          unknown/t0          employer/t2        employer/t2
Fubo             unknown/t0          employer/t2        employer/t2
WHOOP            unknown/t0          employer/t1        employer/t2
IMC              unknown/t0          employer/t2        unknown/t0
Crusoe           unknown/t0          employer/t1        unknown/t0
```

同一个模型、同一个 prompt、同一个名字字符串，**只是邻居不同**，答案就从
「完全不认识」变成「tier 2 雇主」。40 家一批里全是陌生名字时，模型会集体退化成
`"Too generic."`（我做了对照：把这 18 家和 32 家真·无名公司拼成一批 → 全部 unknown）。

叠加**知识截止**问题：gpt-4o-mini 的世界知识停在 2023 年底，而今天是 2026-08。
GE Vernova(2024 分拆)、Anysphere/Cursor、Sierra AI、Physical Intelligence 我实测全部
`unknown/t0`；`Anthropic` 只给到 tier 2（prompt 里 tier 3 明写「famous AI lab」，
`OpenAI` 和 `Google DeepMind` 都拿了 3）。**「大公司」这个属性是有时效的，
方案却用一个 3 年前的快照去回答它，且把结果永久缓存。** 对一个找工作的人来说，
最想看的恰恰是最近 3 年起来的那批公司。

**建议改法（P0）**

1. **批次内混入锚点**：每批 40 家里固定塞 5 家已知大公司做 anchor，或把批次缩到 15-20 家。
   我实测 48 家混合批次的识别率显著高于 40 家纯陌生批次。（成本影响 < $0.02，可忽略）
2. **不要把「LLM 不认识」和「小公司」画等号。** 加一条零成本的正交信号：
   `ats_registry.json`（227 家）里有自有 Greenhouse/Lever/Ashby board 的公司，
   即使 tier 0 也应该排在**纯 tier 0 之前**（Lane B 内部再分 B1/B2）。
   §9.7 说得对 —— 它不是「大公司」信号，但它是「这是个正经在招人的公司」信号，
   足够把 Ramp / ClickHouse / Hadrian 从 252 家里拎出来。
3. **补一份「近 3 年热门公司」名单**。§9.1 否掉了扩名单，理由是维护成本，
   但这里需要的不是 Fortune 1000，而是一份**几百行的、离线的、手工可维护的
   `hot_companies.txt`**（YC/a16z/Sequoia 近年组合 + 近 3 年 IPO/分拆）。
   它只需要补 LLM 知识截止后的那一段，正好是名单方案成本最低、LLM 最弱的一段。
4. 无论如何，Panel ① 里 Lane B **不能只折叠成一行**。至少要把「有 ATS board」
   或「在 hot 名单里」的那 44 家单独提出来做成 Lane B1，默认展开。

---

## 阻断-5 ★★ tier 内字母序 = 用户读前 30 行看不到任何一家 FAANG

用户原话是「**要把大中公司的岗位排在前面先看到**」。方案在 tier 层面做到了
（tier 3 在最前），但 tier 3 内部是**纯字母序**，作者把细排序推到了 P1-2。
实测这 140 行里各家公司的实际行号（`_evalA_queue_order.py`）：

```
Amazon      5,6      Deloitte  35,36    Google    63,64    Meta       87
Microsoft   91       NVIDIA    100      OpenAI    103      Palantir   105,106
SpaceX      122,123  Stripe    127,128
```

而前 30 行长这样：

```
 1 ABB / 2 Accenture Federal Services / 3-4 Adobe / 5-6 Amazon / 7 AMD /
 8-9 BAE Systems / 10 Bank of America / 11 Baxter International /
12 BlackRock / 13 Blue Cross Blue Shield of MA / 14-15 Boeing /
16-17 Booz Allen / 18 Bridgestone Americas「Manufacturing Infrastructure Tech I」/
19 Broadcom / 20 Capgemini Engineering / 21-22 Cargill / 23 Caterpillar /
24 Charles Schwab / 25-26 Cisco / 27-28 Citi / 29 City of Houston「Engineer-in-Training」/
30 Collins Aerospace
```

作者自己在 §6.2-3 承认「140 行仍然偏多，一天读 140 行还是有负担」。
**如果 140 行读不完，那读完的就是前 30-50 行 —— 而这段里 Google / Meta / Microsoft /
NVIDIA / OpenAI / Palantir / SpaceX / Stripe 一家都没有**，取而代之的是
`City of Houston 的 Engineer-in-Training` 和 `Bridgestone Americas 的
Manufacturing Infrastructure Tech I`。这直接违背需求 2 的字面要求。

作者拒绝细排序的理由是「不想编一个我无法验证的分数」。这个顾虑是对的，
但**不做排序本身也是一个选择，而且是一个可以验证为更差的选择**。而且他自己已经给出了
正确答案（P1-2 的 `priority_companies.txt` 20 行置顶名单）—— 那就不该是 P1，
它是 20 行文本 + 5 行代码。

**建议改法（P0，最小改动）**

1. `priority_companies.txt` 从 P1-2 提到 P0。20-40 行，用户自己维护，
   命中的公司在 tier 内置顶。这**不引入任何假分数**，是纯人工偏好，符合作者自己的原则。
2. 兜底排序从「公司名 A-Z」改成「**该公司当日岗位数降序 → 公司名 A-Z**」。
   在 tier 3 内部按量排序是**安全**的（中介已经在上一步被剥离了，量大只剩真实雇主），
   这恰好是 §9.2 那张「按量排行榜」在**剥离中介之后**变得有意义的地方。
   实测这样排 Booz Allen(9) / SpaceX(7) / Amazon(6) / Deloitte(5) 直接上前排。
3. `cap 2` 我认为**不阻断**，但 §5.1 说的「折叠成 +N 条」必须落成真正的
   `<details>/<summary>`（方案说 Panel ③ 的 checkbox「纯 HTML 无 JS 也能勾」，
   同理这里用 `<details>` 即可）。实测 cap 2 在 Lane A1 只藏了 32 条
   （Booz Allen 藏 7、SpaceX 藏 5、Amazon 藏 4），代价可接受 —— 前提是能一键展开。

---

# 非阻断项（可进 P1）

## NB-1 `S2` / `S3` 是两条 n=1 规则，且实测**改变零个分类**

编排者问「有没有从 Jack & Jill / BeaconFire 反推出来的 n=1 规则」—— 有，而且是两条。
全库 680 家公司里：

```
S2「标题含 ' at X' 比例 ≥50%」 命中公司: [Jack & Jill (34 条)]      —— 就 1 家
S3「标题以 Jobs 结尾 ≥50%」    命中公司: [Surge Software (15 条)]  —— 就 1 家
```

消融实验（`_evalA_signal_ablation.py`）：

```
ablate ('S2',)            : 0 companies change lane
ablate ('S3',)            : 0 companies change lane
ablate ('S2','S3')        : 0 companies change lane
ablate ('S4',)            : 2 companies change lane  ['Infosoft, Inc.', 'Capgemini']
ablate ('S5',)            : 7 companies change lane
```

Jack & Jill 本来就被 `llm:aggregator` 抓到，Surge Software 本来就被 `unkvol15` 抓到。
**S2 和 S3 是纯冗余，删掉对结果零影响**，却各自往 P0-4 的决议链里加了一条
只见过 1 个样本的正则。S4 的净贡献是 2 家 / 8-20 当日 6 条，其中 `Capgemini`
作者自己承认是「歪打正着」。

**建议**：S2/S3 从判定链移到 Panel ③ 的**证据展示列**（「这家 85% 的标题是转贴格式」
对用户是有用的解释，但不该是判据）。这样 P0-4 从 5 条信号缩到 3 条（S1 / S4 / S5），
代码更小、可解释性不降、回归面更窄。

## NB-2 中介召回的长尾漏得比方案说的多，Panel ④ 的「中介占比」被系统性低估约 8 个百分点

方案自报 `LLM kind 单独 recall = 35/59 = 59%`。我扫了 Lane A/B 的 609 家公司名，
挑出 50 家我判为中介/外包/猎头但**没有任何信号命中**的：

```
Delphi-US, LLC - Peacemakers in the Talent War   Hirematic Talent Solutions   W3Global
JSR Tech Consulting   Technogen, Inc.   Amtex Systems Inc   Q1 Technologies, Inc.
Centraprise   Arkhya Tech. Inc.   KPG99 INC   Tavas Technologies Inc
Willsmarg Technologies LLC   Glint Tech Solutions   PALNAR   AXISCADES   Excelra
Zetheta Algorithms Private Limited   Matrix USA   AddSource   Xtreme Solutions Inc
Zodiac Solutions, Inc   Prudent Technologies and Consulting, Inc.   TekValue IT Solutions
Four Seas Infotech   Ztek Consulting   Transcend Softech LLC   Solverix Global Inc.
Precision Technologies   Tech Consulting   AVP VIGILANT TECHNOLOGY PVT LTD
HRK Technologies Inc.   Base-2 Solutions   Nexcade   XChange Software Inc
—— 一整簇英国金融猎头（LLM 抓了一半漏了一半）——
Vallum Associates   Saragossa   Orbis Group   Albert Bow   Haveron James
Alexander Chapman   Delmar Nord   The Developer Link   Nord Resume
（对照：Radley James / Arcus Search / Darwin Recruitment / Initi8 被抓到了）
—— 聚合站/求职服务 ——
BoF Careers   Founders.Careers   Jobverse.io   AdaMarie   Scout Global   Soilair Selection
Venture Up
```

回答编排者的问题「中/印背景 IT 外包和培训机构，62 家会不会太少」——**是，太少了**。
把上面 50 家算进去：

```
方案的 Lane C     : 62 家 / 185 条 = 当日 22.7%
加上我找到的 50 家: 112 家 / 248 条 = 当日 30.5%
```

**Panel ④ 的主指标「中介占比」因此被低估约 8 个百分点（相对低估 34%）。**

我还做了一个测试想看这是不是批次效应：把这 50 家和 5 家已知中介（TEKsystems /
Insight Global / Robert Half / Revature / Jack & Jill 作 anchor）拼成一批重问 ——
**5 个 anchor 全部正确识别，50 家目标 0 家翻牌**。所以这是**真实的知识盲区**，
不是 prompt 或批次问题，LLM 确实没听说过这些小 body shop，而且它诚实地说了不知道
（这点值得表扬，见下）。

**为什么这条我判非阻断**：这 50 家一共只有 63 条岗位（8/20），且每家 1-4 条，
它们混在 Lane B 里默认是折叠的，不会刷屏；用户看到的第一屏不受影响。
但两件事必须做：
1. Panel ④ 的中介占比旁边必须标注「**这是下界**」，不能当成精确指标画趋势线；
2. P1 里加一条**廉价的名字启发式**（`Staffing|Recruit|Talent|Search|Consulting|Infotech|
   Softech|Solutions Inc|Pvt Ltd|Technologies Inc` + tier 0 + kind unknown）
   → 不自动分流，只喂进 Panel ③ 的「疑似待确认」子表，让用户一次性勾掉。
   实测这条正则在上面 50 家里能覆盖约 35 家。

## NB-3 `Capgemini` 和 `Capgemini Engineering` 被分到相反的 lane，且都在第一屏

```
Capgemini              t3 employer  n=6  → Lane C（靠 stack3 触发，作者承认是巧合）
Capgemini Engineering  t3 employer  n=2  → Lane A1，第 20 行
```

同一个集团，一个在「中介刷屏区」，一个在「今天最该看的 140 条」里。用户会当场发现矛盾，
并且会开始不信任整个分流。§7.5 的「别名分裂」条目只考虑了 `cap 失效`，没考虑
**别名分裂会导致 lane 不一致**。P1-5 建议把这条从「影响 ~16 条，收益小」改成
「同一 override 键下的别名必须落同一 lane」的一致性检查。

## NB-4 文档里的小数字错误 / 复现指引失效

| 位置 | 文档写的 | 我实测 |
|---|---|---|
| §3.1 表格 | tier1 = 34 条，tier0 = 267 条 | tier1 = **26**，tier0 = **275**（合计 629 一致） |
| §3.2 | LLM 岗位覆盖 61.1% | 61.2%（766/1252，四舍五入差异） |
| 附录 A | `python _verify_queue.py 2026-08-20 3` 可复现 §6.2 | **不能**。该脚本 (a) 默认 cap=3，(b) Lane A 是 `tier>=2` 混合不是 A1，(c) 排序键是 `(-tier, -conf, name)` 不是纯字母序 → 跑出来 top1 是 Amazon 不是 ABB。§6.2 的输出需要另一个脚本（我复现在 `_evalA_queue_order.py`）|
| 附录 B | tier 3 名单 130 家 | 130 家 ✅，但名单里漏抄了 `Twitch`，且 `GDIT` 在 profiles 里的实际名是 `General Dynamics Information Technology` |
| §4.5 | Lane C = 62 家（8/20） | 62 ✅，但**全库口径是 69 家**（含只在 8/19 出现的 KAYAK / Ace IT Careers / BioSpace 等）|

## NB-5 tier 3 名单里我不同意的几家（不阻断，但影响第一屏观感）

作者说「130 家人工复核无误判」。我逐条看过，**没有明显的假公司**（这点我确认），
但有一批「体量大 ≠ new grad 想看」的组织被顶到了第一屏：

```
City of Houston / NJ Department of Environmental Protection / Florida International University
Blue Cross Blue Shield of Massachusetts / Sentara Health / Dignity Health / CommonSpirit Health
Emory Healthcare / NYU Langone Health / The University of Texas Medical Branch
Bridgestone Americas / Hermès / Quora / Panasonic Energy Corporation of North America
```

它们占了 140 行里约 14 行（10%），而且岗位标题多是 `Engineer-in-Training`、
`Associate IT Analyst (Epic)`、`Manufacturing Infrastructure Tech I`、
`Bioinformatics Research Analyst` 这类非软件岗。这跟 §6.2-3 说的 P1-3
（岗位相关性过滤）是同一个问题的两面。我同意这条不阻断，但建议把 P1-3 的优先级
提到 P1 最前 —— 它比 Panel ④ 趋势图（P1-1，反正没数据）值钱得多。

## NB-6 `conf` 字段作为显示列可能误导

§7.2 的结论「conf 只做显示列」我同意判定不该用它。但既然实测 `conf=0.2 ⟺ kind=unknown`
是 100% 对应的编码，把它当成「这条判定有多硬」展示给用户就是**假精度** ——
用户会以为 0.7 和 0.9 有区别。建议 Panel ③ 直接显示 `kind` 和触发信号，
不显示 conf，或者把它二值化成「LLM 认识 / LLM 不认识」。

---

# 我核对通过的部分（作者没有虚报）

我想明确说：**这份方案的实测部分是我见过的少有的诚实。以下每个数字我都独立跑通了，
一次就对上**，没有一个是编的：

| # | 作者的声称 | 我的实测 | 结果 |
|---|---|---|---|
| 1 | 三 CSV 跨源 uid 去重后 1252 行 / 680 家 | 1252 / 680 | ✅ 精确 |
| 2 | 8/20: 965 → 814 → 629 → tier3 172 → cap2 = **140 行** | 965 → 814 → 629 → 172 → **140** | ✅ 逐级精确 |
| 3 | 8/19: 287 → 230，A1 55/26→35，A2 47/33→42，B 111/79→98，C 17/10→14 | 完全一致 | ✅ |
| 4 | 8/20 中介层 **62 家 / 185 条 / 22.7%** | 62 / 185 / 22.7% | ✅ |
| 5 | 阈值扫描 ≥5 → **7 家 / 94 条 / 0 误伤** | 原始 9 家 104 条，减去 ATS 否决的 2 家 10 条 = **7 家 94 条**，且这 7 家我逐个看过确实没有真实雇主 | ✅ 含推导过程 |
| 6 | ATS 否决位恰好命中 2 家：Handshake、Texas Sports Academy Main | 全库精确 2 家，就是这两家 | ✅ |
| 7 | tier 3 共 **130 家** | 130 家 | ✅ 数量精确，且逐条看过没有假公司 |
| 8 | 用户点名 6 家 Deloitte/Palantir/SpaceX/Booz Allen/Micron/Anduril 全在 Lane A、无中介信号 | 全部确认 | ✅ |
| 9 | §3.2 覆盖率表：unicorn 7.1%/11.4%、fortune500 3.1%/3.7%、并集 9.0%/13.3%、LLM 55.9%/61.1% | 7.1%/11.3%、3.1%/3.7%、9.0%/13.3%、55.9%/61.2% | ✅ |
| 10 | §9.3 标题重复率反直觉：Deloitte 87% / PHR 90% / Gartner 75% / Appian 70% / Cisco 60% vs Jack&Jill 9% / Surge 7% / Infosys 9% | 逐条一致 | ✅ 这个反直觉发现是对的，很有价值 |
| 11 | §6.3 全量 680 家 token 用量 in 16,799 / out 18,987 | 我实测每批 40 家约 in 990 / out 1050，×17 批 ≈ 16.8k / 17.9k | ✅ 数量级和绝对值都对得上 |
| 12 | `gpt-4o-mini` 不在 `LLMCostTracker.MODEL_PRICING` 里 | `cost_tracker.py:13-30` 只有 gpt-3.5-turbo / gpt-4 / gpt-4-turbo / gpt-4o | ✅ P0-3 有效 |
| 13 | `ats_registry.json` 227 家 | `d["companies"]` 长度 227 | ✅ |

**另外，我用比作者更狠的幻觉测试，防线 1 依然守住了。** 我造了 4 家假公司，
其中一家专门起了会诱导模型答 `staffing` 的名字：

```
Zorbatex Quantum Dynamics LLC       → unknown / t0 / conf 0.2  ✅
Fleebware Solutions Group           → unknown / t0 / conf 0.2  ✅
Quantalytix Meridian Systems Inc    → unknown / t0 / conf 0.2  ✅
Vexadyne Global Talent Partners     → unknown / t0 / conf 0.2  ✅   ← 名字里有 "Talent Partners" 也没上钩
```

同时 `Diverse Lynx / Mastech Digital / Collabera / Artech / Compunnel / Nagarro /
LTIMindtree / SynergisticIT / Tech Mahindra / V-Soft / eTeam / Pyramid Consulting`
12 家真中介**全部正确分类**。§7.2「防线 1：把不知道定义成正确答案」这条 prompt 设计
是有效的，是这份方案里最扎实的一块，**不要改它**（阻断-4 的修法只动批次组成，不动硬规则）。

我也同意并复核了作者放弃的这几个方案，理由都成立：
❌ 扩离线名单（9.0% 覆盖，实测确认）、❌ 按量排行榜、❌ 标题重复率当中介信号、
❌ 跨天突发信号（8/19 是残缺日，97.8% 会被判突发）、❌ gpt-3.5-turbo、
❌ conf 阈值门控、❌ 前缀自动合并别名、❌ 岗位级 LLM 打分。这 8 条**不需要重新论证**。

---

# 进入实现前的最小修改清单

| 阻断项 | 改什么 | 规模 |
|---|---|---|
| 阻断-1 | S5 的 n 换成「最近 N 个采集日」窗口 + 改相对阈值；S4 分母同改；验收标准加时间稳定性断言 | ~20 行 + 1 条测试 |
| 阻断-2 | 富化只对新公司发请求（缓存即真理）；tier≥2 / kind∈INTER 的候选做 3 次多数投票；fixture 断言缓存而非模型 | ~30 行 + $0.015 一次性 |
| 阻断-3 | `aggregator` 恢复 V1 否决（或降级到「疑似待确认」）；prompt 里 `aggregator` → `job_board` 并收紧定义；FP fixture 改成「Lane C 全量逐天人工过」 | ~10 行 + prompt 1 段 |
| 阻断-4 | 批次混入 anchor（或批次缩到 20）；Lane B 按「有无自有 ATS board」拆 B1/B2，B1 默认展开；补 `hot_companies.txt` | ~40 行 + 一份手工名单 |
| 阻断-5 | `priority_companies.txt` 从 P1-2 提到 P0；tier 内兜底排序改「当日岗位数降序 → 名字」；`+N more` 落成 `<details>` | ~10 行 + 20 行文本 |

改完之后我认为这个方案可以进实现。骨架（公司档案表 / kind⊥tier / override 闭环 /
两级去重 / cap）是对的，问题全部集中在**判据的时间稳健性和 oracle 的可复现性**上。
