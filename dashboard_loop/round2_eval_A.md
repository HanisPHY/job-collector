# Round 2 评估 A —— 数据与方法论复审

## 结论：FAIL

> 评估者：评估者 A（数据/方法论）· 2026-08-20 · 第二轮
> 本轮我又跑了 **约 $0.09** 的 LLM 实验（stage-2 换模型对照、批次尺寸阶梯、知识截止探针）。
> 脚本落在 `dashboard_loop/_evalA2_*.py`，全部可原地跑。

**先说结论的性质**：round2 是一份**明显更强**的文档。我上一轮 5 条阻断项里，
**A3(KAYAK)、A5(字母序) 完全修好并复现，A4 大幅改善（回收 20/44），A2 修到了它能修的程度**。
round2 自报的数字我抽查了 **21 条，全部一次复现**，包括它用来反驳我和反驳编排者的那些。
它没有虚报任何一个数字。

**但我仍然判 FAIL，只有 2 条阻断项，而且都是 1-2 行的改动：**

1. **A1 的修法引入了方向相反的等价炸弹。** 7 天窗口本身是对的（实测在任意语料规模下恒定 8 家），
   但**额外加的 `0.4% 相对速率`** 会随语料变大而收紧：在方案自己预测的稳态（~1100 行/天）下
   S5 只剩 **2/8** 命中，1500 行/天时 **归零**。方案用「把同一天复制 N 遍」验证它 ——
   这种合成语料让分子分母同比放大，**在构造上就看不见这个失效**，验收标准第 3 条把同一个盲测固化了。
2. **B5 的「全函数」修法把「没富化过」和「LLM 说不认识」编码成了同一个状态**，
   而 S5 的触发条件恰好是这个状态 + 量大。实测：富化只要**晚一天**，
   `Amazon / Booz Allen / Leidos / L3Harris / Micron / Esri / TCS` 就出现在中介面板；
   档案表 JSON 解析失败（方案自己设计的降级路径）时 **Deloitte 也进去**。

两条都是「用户看到错误结论」，都在 P0 判定链里，都不能推 P1。改完我认为可以进实现。

---

## 0. 复现环境

```bash
export PYTHONIOENCODING=utf-8
cd D:/OneDrive/work/school/project/Job/dashboard_loop
py=D:/Apps/Miniconda/envs/job-classifier/python.exe

$py _evalA2_repro.py            # round2 全部 lane 数字
$py _evalA2_queue.py            # TOP30 + prom 分段行数
$py _evalA2_prom_variance.py    # prom 稳定性（离线，用 passes_v4.json，免费）
$py _evalA2_3pass_check.py      # 核实它对编排者 3-pass 提案的反驳（离线，免费）
$py _evalA2_window_stress.py    # ★ 阻断-1
$py _evalA2_unenriched_bomb.py  # ★ 阻断-2
$py _evalA2_recall.py           # S2/S3/S4 删除后的召回 + Lane C 全量名单

# 要花钱的（合计约 $0.09）：
$py stage2.py gpt-4o-mini       # 归因裁决 EXP-1（产物 stage2_gpt-4o-mini.json 已落地）
$py _evalA2_attrib_exp2.py      # 归因裁决 EXP-2
$py _evalA2_attrib_exp3.py      # 归因裁决 EXP-3（批次尺寸阶梯）
$py _evalA2_cutoff_probe.py     # 知识截止探针 EXP-4
```

---

# 一、裁决：A4 的归因到底谁对

**裁决结果：批次效应我是对的，知识截止我也是对的；方案的工程结论（stage-2 用 gpt-4o）碰巧是对的，
但它给出的机制解释是错的，而且据此写进 §5.3 的运行规则方向是反的。**

方案的反驳建立在一个关键实验上：「加了锚点后复现不出批次效应」。它的实验有一个混杂 ——
stage-1 到 stage-2 **同时换了两个变量**（模型 4o-mini→4o，批次 20+锚点→50 全残差）。
我把两个变量拆开测。

### EXP-1：批次组成完全不变，只换模型

直接跑 `stage2.py gpt-4o-mini`（同一份 `passes_v4.json` 残差、同样 7 批 × 50、同 prompt、同 seed）：

```
gpt-4o       残差 347 → 回收 tier>=2  44 家 / tier1 61 / 仍 t0 242    $0.1719
gpt-4o-mini  残差 347 → 回收 tier>=2   3 家 / tier1  5 / 仍 t0 339    $0.0121
```

**模型换掉，回收从 44 掉到 3。** 所以在**生产批次组成下**，起决定作用的确实是模型。方案这一半是对的。

### EXP-2：模型完全不变，只换批次组成

把 gpt-4o 回收的那 44 家名字单独拎出来，组成**一批 44 家、100% 可识别**的批次，
仍然用 **gpt-4o-mini** 问：

```
gpt-4o-mini · 50 家残差批 · 这 44 家里认出        →   3 家
gpt-4o-mini · 44 家全可识别批 · 认出              →  35 家   ← 同一个模型，同一个 prompt
gpt-4o      · 同一个 44 家批                      →  38 家
```

**同一个模型从 3 家变成 35 家，唯一变量是批次组成。批次效应不但存在，而且是数量级的。**
方案说「加了锚点复现不出」—— 是因为 5 个锚点混进 20 个陌生名字（20% 密度）**强度不够**，
那是一个 underpowered 的阴性结果，不是证伪。

### EXP-3：模型固定 4o-mini，只改批次**尺寸**（同一批 150 个残差名字）

```
参照  gpt-4o      batch 50 → 回收 23/150
      gpt-4o-mini batch 50 → 回收  1/150    $0.0052
      gpt-4o-mini batch 20 → 回收 13-14/150 $0.0060   ← 两次独立运行 13 / 14
      gpt-4o-mini batch 10 → 回收  8-9/150  $0.0071
```

**光把 stage-2 的 batch 从 50 缩到 20，4o-mini 就能拿到 gpt-4o 六成的回收量，成本只有 1/30。**
这是方案完全没试过的杠杆，而它现在的 `stage2.py` 里 `BATCH = 50` 恰好是最差的那一档。

### EXP-4：知识截止 —— 我原判成立，方案的证伪用错了样本

方案用 `GE Vernova` 证伪「知识截止」。**GE Vernova 是最不该拿来做这个测试的样本**：
它的名字里带着母公司品牌，模型可以靠拆名字答对。实测两个模型给出的理由分别是
`"GE spinoff"` 和 `"part of General Electric"` —— 这是**名字可分解**，不是记得这家公司。

我改用真正无法靠名字分解的 2023 年之后的公司，放进一个**最有利的密集批次**
（24 个名字、大部分可识别），用**最强的 gpt-4o**：

```
Anysphere(Cursor)          unknown t0 p0     Skild AI       unknown t0 p0
Sierra AI                  unknown t0 p0     Decagon        unknown t0 p0
Physical Intelligence      unknown t0 p0     Harvey AI      unknown t0 p0
Thinking Machines Lab      unknown t0 p0     Figure AI      unknown t0 p0
Safe Superintelligence Inc unknown t0 p0     Cognition AI   unknown t0 p0
World Labs                 unknown t0 p0
Solventum（3M 分拆, S&P500） unknown t0 p0   ← 百亿级上市公司，gpt-4o 也不认识

--- 认识的三家也只给到 tier1 / prom 15（= Lane B2，折叠） ---
Perplexity AI t1 p15   Glean t1 p15   Mistral AI t1 p15

--- 对照组（名字可分解 / 2023 前就出名）---
GE Vernova t3 p60   Kenvue t2 p40   ClickHouse t2 p40   Ramp t2 p40   Stripe t3 p85
```

**换批次、换模型都救不回真正的 post-cutoff 公司，它们全部落 Lane B2（默认折叠）。**
对 new grad 来说 Cursor / Sierra / Harvey / Figure / Decagon 恰恰是最想投的一批。

### 三个因素的份额，以及对「每天怎么调用」的意义

| 因素 | 是否成立 | 实测量级 |
|---|---|---|
| 批次组成 / 尺寸 | ✅ **成立**（我对） | 同模型 3 → 35（组成）；1 → 14（尺寸 50→20） |
| 模型能力 | ✅ **成立**（方案对） | 同组成 3 → 44 |
| 知识截止 | ✅ **成立**（我对，方案证伪的样本选错） | gpt-4o 在最有利条件下仍 10/14 不认识 post-2023 公司 |

**对增量调用的直接影响（编排者关心的点）：**

- 方案 §5.3 写死的规则「**stage-2 的批次必须全部由残差组成，不要混入已知公司**」
  —— **实测方向是反的，应当删掉**。EXP-2 证明可识别名字的密度越高，回收越好。
- `stage2.py` 的 `BATCH = 50` 应降到 **20**。
- 正确的省钱路线是三段而不是两段：
  `stage1 (mini, batch20+锚点)` → `stage1b (mini, batch20, 只跑残差)` → `stage2 (4o, batch20, 跑剩下的残差)`。
  按 EXP-3 的比例，stage1b 能几乎免费吃掉约六成可回收量，把 gpt-4o 的调用面砍到四成，
  日成本从 ~$0.20 降到 ~$0.09。**建议进 P0，它同时缓解成本压力。**

---

# 二、核实：方案对编排者「3 遍取多数票」的反驳

**这个反驳成立，我完全确认。** 我用它自己交出来的 `passes_v4.json` 离线复算（不花钱）：

```
3 遍之间 tier 完全一致  634/680 = 93.2%   （方案说 93.2%）✅
3 遍之间 kind 完全一致  658/680 = 96.8%   （方案说 96.8%）✅
对 round1 的 300 家 tier0：agg=max → 回收 5 家（说 5）✅   agg=majority → 4 家（说 4）✅
对我 A4 点名的 44 家    ：3-pass max 只回收 2 家（Zelis / Xendit）（说 2）✅
反向损失：3-pass majority 把 round1 的 tier>=2 降级 49 家（方案说 37 —— 它低报了自己的坏处）
          含 Five Rings / FlexTrade / Fluence / Draper / Q2 / BigBear.ai / Drata（三遍全是 t0）
对照 stage-2(gpt-4o)：同一份 44 家名单回收 12 家 tier>=2 + 8 家 tier1（说 13+8，差一家是 Zelis 的口径）
```

**多采样买到的是一致性不是召回 —— 方案是对的，编排者的 steer #1 应该撤回。**

## 那我 A2「LLM 不可复现」算不算修好了？—— 算修好了，但是靠冻结，不是靠消除

诚实地拆开说：

| A2 的三个危害 | round2 的处置 | 我的判定 |
|---|---|---|
| 验收 gate / 回归 fixture 建立在会漂的 oracle 上 | §6 改成断言 `company_profiles.json` **缓存值** | ✅ 真修好了 |
| 日常路径重跑会静默重排 4% 公司的 lane | 只问新公司；`--rebuild` 变显式命令 + diff 报告；单调升级 | ✅ 真修好了 |
| 标签本身是一次采样，带 7-10% 的任意性 | **没有消除，冻结了** | ⚠️ 残留 |

我认为**冻结是对这种 oracle 的正当工程答案，不是「绕过」**——
因为多采样已被实测证明只增加一致性、不增加正确性，花 7 倍的钱换 5 家回收是负收益。
但残留必须写进文档：**「哪家公司在第一屏」大约有 4.4% 是一次 API 调用的掷骰结果，且永久生效。**
量化见下节。

---

# 三、新引入的东西：prom / gpt-4o 成本 / 窗口 / KAYAK 补丁

## 3.1 `prom`：不会天天变，但「谁进必看段」有 4.4% 是永久掷骰

编排者问「会不会今天 Amazon 92 明天 78」。**不会** —— 缓存即真理，一家公司只问一次，
分数落盘后不动，所以**排序没有日间抖动**。这一点方案是安全的。

但 prom 本身的采样方差**比 tier 还大**，而分段又是拿 prom 切硬线（85 / 60）：

```
3 遍完全相同的调用（temperature=0、同 prompt、同批次）：
  tier 一致 93.2%    kind 一致 96.8%    prom 一致 84.6%   ← prom 是最不稳的那个，方案没测
  prom 有波动的公司 105/680 = 15.4%，波动者平均振幅 18.2 分，最大 50 分
  只看真正参与排序的 286 家（任一遍 tier>=2）：prom 一致率仅 72.7%，36 家振幅 >= 20
```

落到 §4.2 的分段上：

```
三遍之间「首屏分段」会变的公司：30/680 = 4.4%
其中跨过「必看 prom>=85」这条线的 8 家：
  Adobe [75,85,75]  Intuit [85,75,75]  Amazon Lab126 [85,85,75]  Pinterest [40,60,85]
  Roblox [75,85,85] ServiceNow [75,85,85] Snowflake [75,85,85]  X, The Moonshot Factory [60,85,60]
跨过 60 这条线的另 22 家：Datadog / Zoox / Zipline / Stellantis / State Street /
  Oak Ridge National Laboratory / Truist / Parsons / PACCAR / Westerndigital / NYU Langone …
```

准确的说法是：**`Adobe`、`Snowflake`、`ServiceNow`、`Roblox`、`Pinterest` 进不进那 35 行的
「今日必看」，取决于当初那一次调用掷出了多少 —— 而且永远不会再改。**

判**非阻断**，理由：(a) 缓存冻结了它，无日间 churn；(b) 影响面 4.4%，
被漏掉的公司就在②段第一行，展开一次就看到；(c) 编排者的多采样解法已被证伪，没有更好替代。
**但必须做两件事**（P1）：面板脚注写明「prom 是一次采样、不是客观分数」；
`company_overrides.json` 支持覆盖 `prom`（`r2.py` 的 `prof()` 其实已经支持了，文档没写）。

另外两个小事实（非阻断）：

- `prom must be 0 whenever tier is 0` 这条硬规则在 680 家上**零违反** ✅。
  tier1 prom∈[15,40]、tier2∈[30,85]、tier3∈[60,100]，秩序合理。
- 排序键是 `(-tier, -prom, …)` 而分段**只看 prom**，两者口径不同，
  所以「必看段」不是排序队列的前缀：`Anthropic` / `Anduril Industries`（t2 p85）
  排在第 32 行以后却属于①段。只影响 4 行，是渲染实现细节，不是缺陷。

## 3.2 gpt-4o 的成本：数字算错 52%，但仍在预算内；配额不是炸弹，但会饥饿

```
实测 stage-2：347 家 → in 9018 / out 14939 → $0.1719   （方案说 $0.1719）✅
单家 $0.000495 → 配额 400 家/天 = $0.1982
方案 §5.1 写「这把日花费钉死在 <= $0.13（stage2）」—— 实际 $0.198，低报 52%
```

加 stage-1 悲观 $0.019，日上限约 **$0.22/天**（年约 $80）。仍低于
`LLM_DAILY_COST_ALERT_USD = 0.50`，所以**非阻断**，但 P0 文档里的数字要改。
若采纳 EXP-3 的三段式，可降到 ~$0.09/天。

**编排者担心的「配额用完 → 被误判成中介」没有兑现，我实测确认了：**

```
配额 400，优先级 = 窗口内岗位数降序。
今天残差里 n_7d>=6（即会被 S5 判中介）的只有 8 家 —— 全部排在配额最前面。
=> 配额推迟掉的一定是低量公司，S5 打不到它们。
实测：87 家未富化公司中，被 S5 判中介的 0 家 ✅
```

**但有一个饥饿问题：**

```
方案自己预测 500-1200 家新公司/天；实测残差率 347/680 = 51%
悲观 1200 家/天 → 残差 612 家/天 > 配额 400 → 积压每天净增 212 家，无界增长
而优先级只看「当前窗口岗位数」，昨天积压的 1 条岗位公司会被今天的 1 条岗位公司无限期挤后
```

→ **非阻断，P0 小改**：配额要么设成 ≥ 预期日残差量，要么优先级加入队时间做次序
（`sort by (-n_7d, first_seen)`），保证老积压能排空。

## 3.3 ★ 阻断-1：7 天窗口是对的，但外挂的 0.4% 速率会随语料变大杀死 S5

方案的验证方式是「**把 8/20 的 1104 行复制成 N 天**」。这种语料里每家公司的**占比按构造不变**，
所以比例判据当然恒定 —— **这个测试在构造上就看不见比例判据的失效**。
验收标准第 3 条（「复制成 30 天合成集，断言 Lane C 公司数增长 ≤ 1.5 倍」）
把同一个盲测固化成了 gate。

真实世界的形态是：**刷屏方在某一天爆发，窗口随后被别人的流量填满**
（CONTEXT_BRIEF 已实测 BeaconFire / Jack & Jill 只在 8/20 出现，是突发不是常态）。
我按这个形态造语料 —— 在 8/20 之前 6 天注入背景流量，**每行来自一家独立的新公司**
（因此不改变任何真实公司的 `n_7d`，只让 `win_total` 变大）：

```
背景(唯一公司)/天   win_total  |  仅 7 天窗口 >=5   round2(窗口 + 0.4%)
             0        1391    |         8                 7
           300        3191    |         8                 4
           700        5591    |         8                 2
          1100        7991    |         8                 2   ← 方案自己预测的稳态
          1500       10391    |         8                 0
          3000       19391    |         8                 0
          6000       37391    |         8                 0
```

**「7 天窗口 + 绝对 >=5」在任意语料规模下恒定 8 家 —— A1 的炸弹是窗口拆掉的，不是比例拆掉的。
比例项是纯负作用。** 稳态 1100 行/天时被它放掉的：

```
Surge Software(15) · Haystack(13) · Yara AI(8) · Hire Feed(6) ·
Visionary Innovative Technology Solutions(5) · Jack(8)
—— 只剩 BeaconFire(41) 和 Jack & Jill(34)。1500 行/天时一家不剩。
```

这正是 round1 §4.3 说的「**唯一能抓住 LLM 完全不认识的头部刷屏方的信号**」。

**用户看到的错误结论**：Panel ②′ 的「中介占比」会从 23% 一路掉到个位数，
读起来像「刷屏消失了」，实际是判据死了；同时这些刷屏岗位回流进 Lane B2 长尾。

编排者点名的另外两个极端我也测了（当日总量本身变化，窗口内其它天不变）：

```
当日 200 条 → S5 命中 2 家 | 当日 1104 条 → 7 家 | 当日 3000 条 → 8 家
```

这一维是安全的。问题**只出在窗口被别的流量填满**这一维 —— 而那一维必然会发生。

**建议改法（P0，删 1 个条件）**

1. **删掉 `n_win / win_total >= 0.004`，只保留 `n_7d >= 5`。**
   实测在 0 → 6000 行/天 背景下恒定 8 家，窗口化已经提供了全部的时间稳健性。
2. 若一定要一个自适应项，**不能拿总行数做分母**（分母被长尾公司的数量支配）。
   正确的比较对象是**公司发帖量的分布**，例如 `n_7d >= max(5, p99(所有公司的 n_7d))`，
   或「窗口内发帖量前 N 名且 kind unknown」。这类判据对总量变化不敏感。
3. **验收标准第 3 条必须换掉**：合成语料不能靠复制同一天，
   必须是「固定住刷屏方的 `n_7d`、只放大背景流量」（`_evalA2_window_stress.py` 干的就是这件事），
   断言 **S5 命中数不随背景流量下降**。现在这条 gate 会在规则失效时照样绿灯。

## 3.4 ★ 阻断-2：「没富化过」被当成「LLM 说不认识」，富化晚一天就把 Amazon 送进中介面板

B5 的第 4 条修法（`resolve()` 全函数，缺失返回 `{kind:"unknown", tier:0, prom:0}`）
和 S5 的触发条件（`kind=="unknown" and tier==0` + 量大）**正面冲突**：
两个语义完全不同的状态被编码成了同一个值。`r2.py` 现在就是这么写的：

```python
v = self.P.get(c) or {"name": c, "kind": "unknown", "tier": 0, "prom": 0,
                      "conf": 0.0, "why": "not enriched", "stage": 0}
...
if v["kind"] == "unknown" and v["tier"] == 0 and n >= S5_MIN and n / self.win_total >= S5_RATE:
    return "inter", [...]        # <- "not enriched" 走进了这一支
```

实测三种档案表状态（`_evalA2_unenriched_bomb.py`）：

```
FULL profile（今天）            Lane C 214 行 | S5 判中介  7 家 | 其中真实雇主  0   ✅
STALE（富化在 8/20 失败一次）    Lane C 152 行 | S5 判中介 16 家 | 其中真实雇主  7   ❌
   -> Esri, Tata Consultancy Services, Amazon, L3Harris, Leidos, Booz Allen Hamilton, Micron
EMPTY（档案表 JSON 解析失败）    Lane C 152 行 | S5 判中介 20 家 | 其中真实雇主 10   ❌
   -> 上面 7 家 + Infosys, Capgemini, Deloitte
```

**这两条路径都是方案自己在 §5.3 里设计出来的**：
「富化整体墙钟上限 300 s，超时放弃本次富化」、
「`company_profiles.json` 读取时 JSON 解析失败**降级为空表**而不是崩溃」。
它的缓解是在面板顶部挂一句「今日富化失败，N 家新公司未分层」——
**这句话不阻止 Amazon 出现在中介表里**。用户看到的是「Amazon 是刷屏中介」，
外加一句他不会读的横幅。

对比 round1：`P[c]` 直接下标会 KeyError，报告**响亮地崩掉**。
round2 把响亮的失败换成了安静的错误结论。这是典型的「修复引入新问题」。

**建议改法（P0，1 行）**

```python
enriched = v.get("stage", 0) >= 1          # 或 v.get("why") != "not enriched"
if enriched and v["kind"] == "unknown" and v["tier"] == 0 and <窗口判据>:
    return "inter", [...]
```

**没富化过的公司永远不进 Lane C**，一律落 B2（或一个显式的「未分层」桶）。再加两条：

- 回归 fixture 增加一条：「档案表为空时，Deloitte / Amazon / Booz Allen 不得出现在 Lane C」。
  现有 fixture 第 2 条只断言「不抛异常」，抓不到这个。
- 富化失败横幅保留，但不能作为唯一缓解。

## 3.5 KAYAK 的 prompt 补丁：没有误伤，这条修得漂亮

我把补丁后的全部 `job_board` 判定拉出来逐条看（`_evalA2_recall.py`）：

```
BioSpace t1 · BoF Careers t1 · FetchJobs.co t1 · Founders.Careers t1 · Hired t2 ·
Jobgether t1 · Jobright.ai t1 · Jobverse.io t1 · Ladders t2 · RemoteHunter t1
—— 10 家，全部是真的招聘板 / 聚合站，零误伤。

KAYAK     → employer / t3 / prom 70 → Lane A1  ✅（两条 ats_direct 岗位都在第一屏）
Handshake → employer / t2（stage2 回收）→ A2   ✅
```

编排者点名要核实的几家：

```
Jack & Jill   LLM 退步成 unknown/t0（round1 是 aggregator）→ 被窗口速率抓到 ✅
Jobright.ai   job_board t1 → C ✅       Jobgether  job_board t1 → C ✅
RemoteHunter  job_board t1 → C ✅       Hire Feed  unknown → 被窗口速率抓到 ✅
```

**按行求值也确实生效**，Jobgether 被正确拆开：

```
2026-08-20 newgrad    Software Engineer - Performance and Tools  -> C
2026-08-20 newgrad    Software Engineer, Trustus                 -> C
2026-08-20 newgrad    Devops Engineer                            -> C
2026-08-20 newgrad    Full Stack Engineer                        -> C
2026-08-19 ats_direct Junior Manual QA Engineer (Web, CRM)       -> B1   ← 它自己招的人
```

这比我建议的「整家公司恢复否决」更准确，**这一条方案比我想得对，我采纳它的做法**。

⚠️ 但注意：这个修法把 `Jack & Jill` 和 `Hire Feed` 的兜底**全押在了阻断-1 那条规则上**。
阻断-1 一旦在稳态失效，`Jack & Jill`（34 条/天）直接回到 Lane B2。
两条缺陷是耦合的，修阻断-1 更要紧。

---

# 四、我上一轮的非阻断项：删掉 S2/S3/S4 之后漏判变多了吗

**没有变多，反而大幅变好。方案的「只多漏 1 家 3 条」精确成立。**

```
S2/S3/S4 若保留，在 round2 判定链之外还能额外抓到：
   2026-08-19：0 家 / 0 条
   2026-08-20：1 家 / 3 条  ——  Infosoft, Inc.（靠 S4 stacks=3）
```

我上一轮手工列的 50 家长尾中介：

```
round1：LLM kind 抓到  0/50
round2：LLM kind 抓到 16/50   （方案说 16）✅
  新抓到：Delphi-US / Hirematic Talent Solutions / W3Global / JSR Tech Consulting /
          Technogen / Amtex Systems / Q1 Technologies / Centraprise / KPG99 INC /
          AXISCADES / BoF Careers / Founders.Careers / Jobverse.io /
          Prudent Technologies / Ztek Consulting / Precision Technologies
仍漏 34 家（英国金融猎头簇 + 极小印度 body shop），8/20 携带 44 条

中介占比：实测 23.0%  →  把我剩下 34 家算进去的下界 27.7%
（round1 是 22.7% → 30.5%，缺口从 7.8pp 收窄到 4.7pp）
```

删信号 + 换 prompt 的净效果是**判定链从 5 条缩到 3 条、代码更小、召回反而涨了 16 家**。
这一条方案做得很好。Panel ②′ 标注「下界」的要求继续保留。

## 新发现的一个小 FP（非阻断）

Lane C 8/20 的 81 家我逐条过了一遍，**只有一家我不同意**：

```
Yara AI   8 条  unknown/t0  触发 unknown+rate 8 in 7d
   标题：Forward Deployed Engineer / AI Engineer / Software Engineer (New Grad) /
         Product Engineer / Full Stack Engineer (New Grad) …
```

这看起来是一家处在招聘爆发期的早期 AI 创业公司，不是 body shop ——
而且 **round1 §5.3 的 override 示例里，方案作者自己就写了
`"yara ai": {"kind": "employer", "note": "误判，实为小型 AI 创业公司"}`**。
§3.4 的「Lane C 全量 81 家逐条人工复核：没有一家真实雇主」和作者自己写过的这行注释矛盾。

这是量判据的固有代价（招聘爆发期的初创 ≡ body shop），**不阻断**，
它正是 override 文件的典型用例。但 §3.4 的措辞应改成「1 家存疑：Yara AI，已进 override 示例」。
（`Haystack` 13 条清一色 `Software Engineer`，我也存疑，但证据不足以翻案。）

---

# 五、其它非阻断项

## NB-A：§4.2 的分段表口径混用，「六段加起来 = 930」是错的

```
方案 §4.2 表：① 35 + ② 103 + ③ 161 + ④ 10 + ⑤ 362 + ⑥ 214 = 885 ≠ 930
```

原因是①②③ 用的是 **cap-2 之后的行数**，④⑤⑥ 用的是**原始行数**。两种口径我都测了，各自都对：

```
cap2 口径：prom>=95→15 / >=85→35 / >=75→55 / >=70→70 / >=60→138 / >=40→292 / 全部→299  ✅
原始口径：①50 ②125 ③169 ④10 ⑤362 ⑥214 = 930 ✅
Lane A 原始 344 行，cap2 后 299 行 → 45 行躲在「+N more」后面
```

「零丢弃」在**有真 `<details>` 展开**的前提下成立，但表格不能这么加。P0 里统一成一种口径。

## NB-B：TOP 30 与全部 lane 数字精确复现，A5 确认解决

`_evalA2_repro.py` / `_evalA2_queue.py` 一次跑通，与 §3.3 / §4.1 / §4.2 完全一致。
**A5 完全解决**：FAANG 从第 63 行提到第 3 行，前 15 行是
Amazon / Google / Intel / Microsoft / Toyota NA / SpaceX / NVIDIA / DeepMind / OpenAI / Meta。

顺带：tier3 从 130 缩到 100，掉出去 38 家，其中恰好包含我 NB-5 抱怨的那一整批
（`City of Houston` / `Florida International University` / `NJ Department of Environmental Protection` /
`Emory Healthcare` / `Dignity Health` / `CommonSpirit Health` / `Sentara Health` /
`The University of Texas Medical Branch`）—— **NB-5 被顺手修掉了**。
另外掉下去的 `ByteDance / DoorDash / Discord / Datadog / Pinterest / NetApp / Fiserv / Garmin /
Collins Aerospace / Parsons / State Street / Stellantis / Esri / Epic / HII / Bosch`
都落到 tier2（Lane A2），由 prom 决定顺序，不影响可见性。
新进 tier3 的 8 家（`Amazon Lab126 / Cloudflare / GE Vernova / KLA / Lam Research /
NTT DATA North America / Tata Technologies / Textron GSE`）我看都合理。

## NB-C：跨模型的 prom 可比性没有验证

档案表里 **575 家的 prom 来自 gpt-4o-mini（stage1），105 家来自 gpt-4o（stage2）**，
而排序把两者的分数直接放在一起比。我抽测的重合样本大部分一致
（ClickHouse / Ramp / Waystar / Stripe / Databricks / GE Vernova / Kenvue 两模型给同一个值），
但 `Anthropic` 出现三个值：shipped 85 / gpt-4o 75 / gpt-4o-mini 40。
样本太小不足以判定系统性偏移，**列为 P1 的一次性核对**：
同一批 40 家跑两个模型，看 prom 的中位差是否为 0。

## NB-D：`MODEL_PRICING`

`job_collector/tracking/cost_tracker.py:13-30` 已经有 `gpt-4o`，缺的只有 `gpt-4o-mini`。
P0-6 写「2 个模型 8 行」略多算了，实施时核对一下即可。

---

# 六、我核对通过的部分（round2 自报数字，一次复现，无一虚报）

| # | 方案的声称 | 我的实测 | |
|---|---|---|---|
| 1 | 语料涨到 1391 行 / 767 家，其中 87 家不在富化表 | 1391 / 767 / 87 | ✅ |
| 2 | 8/19 lane：A1 42 / A2 71 / B1 80 / B2 21 / C 16，中介 7.0% | 逐个一致 | ✅ |
| 3 | 8/20 lane：A1 147 / A2 197 / B1 10 / B2 362 / C 214，中介 23.0% | 逐个一致 | ✅ |
| 4 | 8/20 TOP 30（prom 排序） | 30 行逐字一致 | ✅ |
| 5 | prom 分档 cap2 行数 15 / 35 / 55 / 70 / 138 / 292 / 299 | 完全一致 | ✅ |
| 6 | 3 遍 tier 一致 93.2% / kind 96.8% | 93.2% / 96.8% | ✅ |
| 7 | 3-pass max 对 300 家 tier0 只回收 5 家；majority 4 家 | 5 / 4 | ✅ |
| 8 | 3-pass 对 A4 的 44 家只回收 2 家（Zelis、Xendit） | 2 家，同名 | ✅ |
| 9 | stage-2(gpt-4o)：残差 347 → tier≥2 44 / tier1 61 / 仍 t0 242 | 44 / 61 / 242 | ✅ |
| 10 | stage-2 对 A4 的 44 家：13 家 →t2+，8 家 →t1 | 12 →t2+（差 Zelis 一家口径），8 →t1 名单完全一致 | ✅ |
| 11 | stage-2 成本 in 9018 / out 14939 / $0.1719 | 一致 | ✅ |
| 12 | 累计规则的炸弹方向（A1）成立 | 我 round1 用不同方法测到「10 天 100%」，方向一致 | ✅ |
| 13 | 幻觉防线没破：Thomas To / Sundayy / Onyx Chambers / Stellar Alpina / Fionics / Forcepull / フジアルテ 仍 unknown/t0/prom0 | 7/7 一致 | ✅ |
| 14 | KAYAK → employer/t3/prom70 → Lane A1 | 一致 | ✅ |
| 15 | Jobgether 按行拆开：newgrad→C，ats_direct→B1 | 一致 | ✅ |
| 16 | 用户点名 6 家 + Handshake / IMC / WHOOP / Five Rings / FlexTrade / Exadel 全部落对 lane | 逐个一致 | ✅ |
| 17 | Fluence 是唯一一处倒退（t2→t0） | 确认 t0/unknown → B2 | ✅ 主动披露 |
| 18 | 删 S2/S3/S4 只多漏 1 家 3 条（Infosoft） | 8/19 0 家、8/20 1 家 3 条 | ✅ |
| 19 | 我的 50 家长尾里现在抓到 16 家 | 16 家，名单一致 | ✅ |
| 20 | prom 硬规则「tier0 → prom0」 | 680 家零违反 | ✅ |
| 21 | job_board 补丁不误伤真聚合站 | 10 家 job_board 全部正确 | ✅ |
| 22 | gpt-4.1-mini 回收 26 家 / 一致率 74.6% / 编 1 个假公司 | 未复跑（信任），与我的 EXP-1/EXP-3 完全自洽 | ○ |

**我也确认它对我 round1 的 NB-1 / NB-3 / NB-5 / NB-6 的处置是对的**：
S2/S3/S4 删除（NB-1）；`Capgemini` 与 `Capgemini Engineering` 现在都是 `outsourcing/t3` 同落 Lane C
（NB-3 从机制上消失，不需要额外的一致性检查）；tier3 里的政府 / 医院 / 大学退出（NB-5 顺带解决）；
`conf` 完全不显示（NB-6）。

---

# 七、进入实现前的最小修改清单

| 阻断项 | 改什么 | 规模 |
|---|---|---|
| **阻断-1** | `r2.py` 删掉 `n_win / win_total >= S5_RATE` 这一个条件（或换成基于公司量分布的判据）；**验收标准第 3 条换成「固定刷屏方 n_7d、只放大背景流量」的合成语料**，断言命中数不随背景下降 | 删 1 行 + 换 1 条 gate |
| **阻断-2** | S5 增加 `v.get("stage",0) >= 1` 前置条件，未富化公司永不进 Lane C；fixture 加一条「空档案表下 Deloitte / Amazon / Booz Allen 不在 Lane C」 | 加 1 行 + 1 条 fixture |

**强烈建议一并做（非阻断，但便宜且价值高）**

| | 改什么 | 依据 |
|---|---|---|
| 1 | 删掉 §5.3 的规则「stage-2 批次必须全部由残差组成」；`stage2.py` 的 `BATCH` 50 → 20；加一段 `stage1b`（mini、batch20、只跑残差）挡在 gpt-4o 前面 | EXP-2 / EXP-3：日成本 $0.20 → ~$0.09，回收量不降 |
| 2 | §5.1 的「配额 400 钉死在 $0.13」改成 **$0.198**；配额优先级加 `first_seen` 次序防积压饥饿 | 实测算术；悲观场景残差 612 > 配额 400 |
| 3 | §4.2 分段表统一口径（885 vs 930），标明 Lane A cap2 藏了 45 行 | 实测 |
| 4 | §3.4 的「Lane C 零真实雇主」改成「1 家存疑：Yara AI」，并放进 override 示例 | round1 §5.3 作者自己写过 |
| 5 | 面板脚注写明「prom 是一次 LLM 采样、永久缓存；约 4.4% 的公司分段由这次采样决定」；override 支持 `prom`（代码已支持，文档补上） | prom 3 遍一致率 84.6%，跨 85 线 8 家 |
| 6 | 文档里记一条已知缺口：**2023 年之后成立 / 分拆的公司（Cursor·Anysphere、Sierra AI、Harvey、Figure、Decagon、Solventum…）任何模型任何批次都拿不到 tier，永远落 B2**。这是 LLM 路线的结构性上限，用户应当知道 | EXP-4 |

改完 1、2 两条阻断项，我认为 round2 可以进实现。判定层的形状
（公司档案 + kind/tier/prom 正交 + 按行否决 + 窗口化 + 两段式富化 + 缓存即真理）已经站得住，
剩下的都是参数和文档。
