# Round 3 收口验证 A —— 放行判定

## 结论：FAIL

> 评估者 A · 2026-08-20 · 第三轮（只审增量）
> 本轮零 LLM 花费（全部用它交付的 `passes_v4.json` / `stage2_*.json` 离线复算）。
> 脚本：`dashboard_loop/_evalA3_*.py`，可原地跑。

**FAIL 只挂在 2 条上，两条都是 1 行改动，改完立刻可以开工。**

1. **阻断-2 有第三扇门没关**：富化调用返回了这一批、但**漏掉了某家公司的对象**时，
   `enrich_v4.run_pass` 写入的兜底字典**不带 `stage` 字段**，而 `build_profiles`
   给全部 stage-1 条目统一盖 `stage=1`。于是「API 没把这家返回来」被记成
   「LLM 认识流程走过了，它说不认识」—— 正是 S5 的触发态。**没有任何一条 fixture 守这个门。**
2. **§3.1 的相关性正则和它自己的验收值互相矛盾**：`REL_INC` 按 §3.1 明文
   「大小写敏感」实现时，段① = **9 行**、默认可见 = **20 行**，直接违反 F10[20,45] 与 F11[30,55]；
   加上 `re.IGNORECASE` 后**六个分段全部精确复现 spec 的数字**。
   工程师照抄 §3.1 无法通过自己的验收表。

**其余全部通过。** 我的两条阻断项在主路径上确实修死了（F6 实测 Lane C = 0 行、
F7 实测 0 家真实雇主、背景压测恒定 8 家，我逐条复算无误）；
mini b20 没有把问题换形式装回来（段① 完全不变）；对 steer-1 的反驳成立。
其余问题一律写成「给工程师的注意事项」。

---

## 1. 我的 2 条阻断项：修死了吗

### 阻断-1（删相对项）—— 主路径修死了，但 F5 只盖住了一个方向

**复现通过**（`_evalA3_segments.py` / round2 的 `_evalA2_window_stress.py`）：
删掉相对项后，背景流量 0 → 6000 行/天，S5 命中**恒定 8 家**，与 spec 一致。
今天的实际命中就是那 8 家，**0 家真实雇主**：

```
 41 BeaconFire   34 Jack & Jill   15 Surge Software   14 Haystack
  8 Yara AI(存疑) 8 Jack           6 Visionary…        6 Hire Feed
------- 阈值 5 -------
  4 Soilair Selection / H Company / Fionics / Base-2 Solutions /
    AVP VIGILANT TECHNOLOGY PVT LTD / AfterQuery Experts        ← 边际只有 1 条岗位
```

**极端语料两端都成立**（`_evalA3_window_fill.py`，realistic scaling = 每家公司量同比缩放）：

```
当日 214 行  → 命中  1 家，0 误伤
当日 1191 行 → 命中  8 家，0 误伤     ← 今天
当日 3216 行 → 命中 43 家，3 家我不同意（Hadrian / HappyRobot / Gradial）
当日 6432 行 → 命中186 家，19 家我不同意
```

**注意这不是「相对项该留下」的证据** —— 相对项在同一场景下是往 0 掉，更糟。
它说明的是另一件事，见注意事项 N-1。

**F5 的盲区**：F5 注入的背景行每行来自一家独立新公司，**按构造不改变任何真实公司的
`n_7d`**，所以它只能证明「S5 不随语料总量膨胀」，证明不了「S5 不随单家公司的 7 天累计量膨胀」。
它是旧 gate（复制同一天）的**镜像盲区**。这不阻断 —— 因为 F5 要盖的那个方向
（round2 的相对项失效）确实被盖住了 —— 但工程师要知道它只测一个轴。

### 阻断-2（stage 门控）—— 主路径修死了，第三扇门没关 ★ 阻断

**主路径复现通过**（`_evalA3_fixtures.py`）：

```
F6 空档案表      : Lane C = 0 行；Deloitte / Amazon / Booz Allen 均不在 C   ✅
F7 过期档案表    : Lane C 仅 4 家，其中真实雇主(employer 且 tier>=2) = 0    ✅
（round2 同一测试：空表 168 行 / 10 家真实雇主含 Deloitte）
```

**第三种状态（编排者点名要查的）—— 有，而且就是同一个失效类：**

| 状态 | `stage` 值 | 会被 S5 判中介吗 |
|---|---|---|
| 公司不在档案表 | 0 | 否 ✅ 已修 |
| 富化过，LLM 真的说不认识 | 1 | 是 ✅ 设计如此 |
| **富化调用返回了这批，但漏掉了这一家的对象** | **1（错）** | **是 ❌ 漏网** |
| 公司改名 → 新 norm 键 | 0 | 否 ✅ 安全方向 |
| override 只覆盖 `prom` | 被抬成 1 | 否（`if c in OVERRIDES` 先短路返回）✅ 实测确认 |

证据（`_evalA3_third_state.py`）：

```
enrich_v4.run_pass 的兜底字典是否含 'stage': False
   {"name": nm, "kind": "unknown", "tier": 0, "prom": 0, "conf": 0.0, "why": "LLM_NO_ROW"}
r2.build_profiles: for k,v in s1.items(): w=dict(v); w["stage"]=1      ← 一律盖 1
spec §4 的 profile() 也没有区分 why == "LLM_NO_ROW"
当前 passes_v4.json pass1 里 LLM_NO_ROW 条目数 = 0（今天没踩到）
```

**这不是理论风险**：round2 §7.5 记录过「40 家输入只回 32 个对象」真实发生过，
round3 §9 的坑表里也把「LLM 少返回行」列为必读坑。batch 从 40 降到 20 只是降低概率。
触发条件 = 某家**新**公司的行被漏返 **且** 它 7 天内有 ≥5 条岗位 —— 而恰恰是
高频发帖的新公司最值得正确分层（例如现在还没富化的 `Amazon Web Services (AWS)`、`Peraton`、
`CVS Health`、`Analog Devices`）。后果与我 round2 的阻断-2 完全同类：**真实雇主进中介面板**。

**改法（1 行 + 1 条 fixture，不是新设计）**

```python
# enrich_companies.py，漏返兜底字典里加一个字段
{"name": nm, "kind": "unknown", "tier": 0, "prom": 0, "conf": 0.0,
 "why": "LLM_NO_ROW", "stage": 0}          # <- 不算已富化，下次富化会重问
```

并在 §7 加一条：**F18 —— 一条 `why=="LLM_NO_ROW"` 的档案在 `n_7d=40` 时不得进 Lane C。**
（F8 现在只断言「档案表缺该公司时 `stage==0` 且不抛异常」，盖不到这一格。）

---

## 2. ★ 阻断：§3.1 正则与它自己的验收值矛盾

`_evalA3_regex.py` / `_evalA3_segments.py`。把 §3.1 的代码块**逐字符**跑起来：

```
语料 1470 条标题
  §3.1 原文（REL_INC 无 re.I，明文写「大小写敏感」）  命中  99 条
  同一正则加 re.I                                     命中 365 条
```

**spec 自己列在段①里的 12 行样例，有 8 行过不了它自己的正则：**

```
spec=False  AI Software Engineering Intern                    (Intel)
spec=False  Software Engineer, New Grad                       (Palantir)
spec=False  Software Engineer, New Grad - Production Infra…    (Palantir)
spec=False  Associate Data Scientist                          (Gartner)
spec=False  Associate, Software Engineer                      (L3Harris)
spec=False  New College Grad - EDA/CAD Engineer               (Micron)
spec=False  Entry Level Software Engineer                     (BAE)
spec=False  Graduate Field Service Engineer Electrical        (GE Vernova)
spec=True   …2026 New College Grad / …2027… / Software Engineer 1   ← 只有带年份和标级的过
```

逐个分支的命中数说明了原因 —— **除了年份，其它分支在大小写敏感下几乎全哑**：

```
分支              大小写敏感   加 re.I
new\s*grad              2        79
new college             0         7
entry[ -.]level         0        39
university              0         2
campus                  0         1
graduat                 0        24
intern(?!ational)       0        17
202[6-8]               48        48     ← 唯一在干活的
junior                  0        60
associate               0        71
apprentic               0         3
rotational              0         0
\bI\b$ / \b1\b$         0         0     ← spec 用来论证「必须大小写敏感」的两个分支，一次都没命中
```

分段实测对比（口径 cap2，语料已涨到 1464 行 / 814 家，8/20 去重后 1006 行）：

```
                 8/19 段① 段② 段③ | 8/20 段① 段② 默认可见①+④
spec 声称          13   40   36  |      28   43        38
§3.1 字面实现       2   22   64  |       9   18        20     ← F10[20,45]、F11[30,55] 双双失败
加 re.I            13   40   36  |      28   43        39     ← 六个分段全部精确复现
```

**结论：spec 的所有实测数字都是用大小写不敏感的正则跑出来的，但发布的是大小写敏感版，
还专门写了一句「`REL_INC` 大小写敏感（`\bI\b$` 要区分 I 与 i）」来强化它。**
那句理由本身也不成立：`\bI\b$` 和 `\b1\b$` 在整个语料上命中 0 次
（语料里确实有 40 条以 ` I` 结尾、9 条以 ` 1` 结尾的标题，例如
`Software Engineer I`、`Web Developer I`、`Agile Developer 1`，但它们都先被别的分支命中了）。

**改法（1 个 flag + 1 条 fixture，不是新设计）**

```python
REL_INC = re.compile(r"...", re.I)     # 与 REL_EXC 一致
```
删掉 §3.1 里「REL_INC 大小写敏感」那句话。并加一条**表驱动** fixture：

```
F19  is_entry() 逐条断言：
  True : "Software Engineer, New Grad" / "Entry Level Software Engineer" /
         "Graduate Field Service Engineer" / "AI Software Engineering Intern" /
         "Associate Data Scientist" / "Software Engineer I" / "2027 Analyst Program"
  False: "Senior Software Engineer" / "Staff Engineer" / "Engineering Manager" /
         "Software Engineer II" / "Principal Architect" / "International Sales Engineer"
```

这一条比 F10 的区间断言值钱得多：F10 会红，但只给出一个「9 ≠ 28」的谜；F19 直接指出哪一条炸了。

---

## 3. mini b20 有没有把问题换形式装回来

**段①（用户唯一默认展开的岗位段）完全不受影响 —— 这一点 spec 是对的。**

```
                    8/19 段① 段② ④ | 8/20 段① 段② ④ | Lane C
stage2 = gpt-4o      13   40  70  |      28   43 11 |  222 行 / 82 家 (21.8%)
stage2 = 4o-mini b20 13   32  76  |      28   43 11 |  204 行 / 67 家 (20.0%)
```

回收量 30 vs 44 我复现了（`_evalA3_mini_vs_4o.py`）。**但 spec 只比了 `tier`，没有比 `kind`
—— 而 `kind` 才是中介判定的主力**，这里的账明显更难看：

```
tier>=2 差集：4o 有 mini 没有 22 家（spec 只列了 8 家，低报）
              mini 有 4o 没有  8 家（Character.AI / Crusoe / Drata / Arcfield …）
kind 跨中介边界的分歧 19 家，其中 17 家是「4o 说 staffing/outsourcing/job_board，mini 说 unknown」

换成 mini 后逃出 Lane C 的 16 家（全部是我 round1 手工挖出来的长尾 body shop / 猎头）：
  Technogen · JSR Tech Consulting · Q1 Technologies · KPG99 INC · Centraprise ·
  Prudent Technologies · Ztek Consulting · Precision Technologies · Delphi-US ·
  AXISCADES · Charter Global · Envision Technology Solutions · Delta Computer Consulting ·
  CPS Inc. · Akkodis · Founders.Careers

我那 50 家长尾中介：gpt-4o 抓到 16/50  →  gpt-4o-mini 抓到 5/50
```

另有一处方向相反的风险：`Handshake` 在 4o 下是 `employer/t2`（Lane A2），
在 mini 下是 **`job_board`** —— 如果它是新公司走 mini 路径，它的 newgrad 行会掉进 Lane C。
（今天不受影响：初始缓存是 gpt-4o 版，Handshake 已经是 employer。）

**判定：不阻断。** 理由是这些公司落在⑤/⑥折叠区，不进段①，不产生错误结论；
spec 已经把「中介占比是下界」写进已知缺口 3，且 `--deep`（gpt-4o）开关已保留为兜底。
**但 spec §2「68% 的回收量」这个结论是按错误的坐标轴算的，必须在文档里更正**，
否则将来有人会以为 mini 只损失 32%。见注意事项 N-2。

---

## 4. 17 条 fixture 够不够

**先说对的：我 round2 抓的两个问题都改到位了。**
F4 明确写「断言**缓存值**，不调模型」（不再拿会漂的 oracle 当断言）；
F5 明确写「旧的『复制同一天』gate **作废**」并换成背景流量压测。这两条是本轮质量最高的部分。

我逐条过了 17 条，问题只有三类：

| fixture | 问题 | 严重度 |
|---|---|---|
| **F13**「段① 前 30 行里明确应届岗的比例 = 30/30」 | **恒真，等于什么都没测**。段① 的定义就是 `is_entry()`，所以 `sum(is_entry)/30` 必然 = 30/30（我实测 28/28，因为段① 只有 28 行）。若按字面「明确应届岗」理解，那是人工判断，不能自动断言 | 应改成人工签核项，或换成 F19 那种表驱动断言 |
| **F5** | 只测「语料总量膨胀」一个轴；按构造无法看见「单家公司 7 天累计量膨胀」（见 N-1） | 补一句口径说明即可 |
| **无 fixture** | ① `why=="LLM_NO_ROW"` 的 stage 语义（阻断-2 第三扇门）② `is_entry()` 的逐条行为（本轮新增的、唯一的分段主判据） | 就是上面两条阻断项要补的 F18 / F19 |

其余数值型 fixture 的健壮性我也看了一遍：F10/F11 给了区间而不是点值 ✅；
F12 是自洽不变式（`各段 raw 相加 == 当日去重行数`），我实测 1006 == 1006 成立 ✅
（**注意 F12 里写死的「931」两小时内就过期了 —— 语料已从 1391 涨到 1464 行，
8/20 去重后从 931 涨到 1006。工程师要把它实现成不变式，不要写死数字**）；
F3「初始缓存 680 条」是对固定产物的断言 ✅；F17 逐字节 diff ✅。

---

## 5. 对编排者 steer-1 的反驳：**对，而且比它自己说的更对**

`_evalA3_tier_vs_prom.py`：

```
3 遍之间分段会变的公司：prom 阈值(85/60) 30/680 = 4.4%    tier 阈值(3/2) 33/680 = 4.9%
```

**spec 的两个数字都精确复现，「tier 比 prom 稳」这个前提确实不成立。**

编排者追问「那分段判据里含 tier3 是不是也带 4.9% 抖动、会不会有公司在段①段②之间跳」——
**会，但实测只有 1 行**：

```
tier 在 3 与 2 之间抖动的公司：13 家
其中在 8/20 有『应届相关』岗位、因而真的会在段①/段② 之间跳的：1 家
    Truist   应届岗 1 条   三遍 tier = [3, 2, 2]
段① raw = 31 行，会因 tier 抖动进出的 = 1 行 = 3%
```

原因正是 spec §1.1 说的那个机制：**两道判据串联，噪声只在第二道上，而第二道的定义域已经被
第一道（零噪声的正则）切得很小**。而 prom 被降级成段内排序后，它 4.4% 的抖动
（tier>=2 的 286 家里 36 家振幅 ≥20）**完全不影响可见性** —— Amazon 是 92 还是 88 都在段① 第一屏。

跳动的代价也是最小的一档：一行从「默认展开的段①」挪到「折叠但标题带条数的段②」，
用户多点一次。**这条我判通过，且认为是 round3 最扎实的一处设计。**

---

## 6. 给工程师的注意事项（不阻断）

**N-1 · 绝对阈值 5 是在「约 1 天的量」上标定的，却用在 7 天窗口上。**
round1 §4.3 的阈值扫描（≥3 误伤 ClickHouse/Muon Space/Gradial，≥5 零误伤）是在
**当时全库累计 ≈ 1.3 天**的数据上做的；round3 把同一个 5 放进 7 天窗口。
今天窗口里只有 2 天真实数据，所以还是 0 误伤、边际 1 条岗位。
`_evalA3_window_fill.py` 模拟「同样的日流量持续 D 天」：

```
窗口内 1 天 → 命中   8 家，0 家我不同意
窗口内 3 天 → 命中  51 家，4 家我不同意（Hadrian / Confido / HappyRobot / Gradial）
窗口内 7 天 → 命中 191 家，22 家我不同意
              （Flock · Baseten · Nscale · Traba · Xaira · AstroForge · Overland AI ·
                Circana · OPENLANE · Radiant · Doppel · Otter · Atticus · Vantor · 11x …）
```

**这个模型是最坏情况**，因为 `date_recorded` 是首次收录时间、同一岗位只记一次，
而实测 8/20 的公司里 97.8% 是当天首次出现（一次性长尾），不会天天贡献新行。
所以这**不是 round1/round2 那种「按算术必然发生」的炸弹**，而是一个**取决于真实发帖复现率的经验风险**，
两天数据判不了。它也不会无界增长（窗口封顶 7 天）。

→ 不阻断。但开工后请把 **Lane C 公司数**当成一个要盯的量：
今天基线 8 家（S5 部分）。如果它随着历史积累爬到 20 以上，就是这条在发作，
处置是把阈值按窗口天数标定，不是把相对项加回来（相对项已被证明是反向炸弹）。

**N-2 · §2 的「68% 回收量」是按 `tier` 算的，`kind` 上只剩 31%。**
见第 3 节。请在文档里改成两个数字并列，并把「初始缓存必须是 gpt-4o 版」的理由
从「已经付过钱」改成「gpt-4o 版比 mini 版多抓 16 家长尾中介」—— 后者才是真正的理由，
也是将来有人想「重跑省钱」时唯一拦得住他的论据。

**N-3 · F12 里的 931 已过期。** 语料在本轮评审期间从 1391 涨到 **1464 行 / 814 家**
（8/20 去重后 931 → 1006）。所有点值型期望（F3 的 680 除外，那是固定产物）
都要按不变式或区间实现。同理 §3 分段表里的绝对行数只能当基线看。

**N-4 · `if c in OVERRIDES` 短路的副作用（不是 bug，但要知道）。**
`company_lane()` 第一步对任何有 override 条目的公司直接返回，
所以**只覆盖了 `prom` 的公司也会永久豁免 S5**。实测确认（空表 + `{"hadrian":{"prom":40}}`
→ `("ok", ["override"])`）。方向是 fail-open，安全；但如果有人把某个刷屏方写进 override
只为了调 prom，它会同时逃出 Lane C。

**N-5 · 公司改名。** 改名 = 新 `norm()` 键 = 不在档案表 = `stage 0` = 永不进 Lane C，
安全方向。反向风险（中介改名后逃出 Lane C 直到被富化）属于已知长尾，不是本轮新增。

**N-6 · `Yara AI` 的措辞已经改对了**（§7 人工签核项写成「1 家存疑」），
和 round1 §5.3 的 override 示例一致。我复核 8/20 Lane C 全量 82 家，
除 Yara AI 外没有新的存疑项。

---

## 7. 我本轮复现通过的清单

| # | spec 的声称 | 我的实测 | |
|---|---|---|---|
| 1 | 删相对项后背景压测 0→6000 行/天 S5 恒定 8 家 | 恒定 8 | ✅ |
| 2 | 空档案表 Lane C = 0 行 / 0 家真实雇主 | 0 行；Deloitte / Amazon / Booz Allen 均不在 C | ✅ |
| 3 | 过期档案表 Lane C 里真实雇主 = 0 | Lane C 仅 4 家，真实雇主 0 | ✅ |
| 4 | `gpt-4o-mini` b20 回收 tier≥2 = 30 家 | 30（tier1 = 19） | ✅ |
| 5 | `gpt-4o` b50 回收 tier≥2 = 44 家 | 44（tier1 = 61） | ✅ |
| 6 | 段① / ② / ③ / ④ / ⑤ / ⑥ 全部 6 个 8/19 数字 | 13 / 40 / 36 / 70 / 21 / 13 —— **六个全中**（需 re.I） | ✅ |
| 7 | 8/20 段① = 28、段② = 43 | 28 / 43（需 re.I） | ✅ |
| 8 | 8/20 Lane C = 82 家 | 82 家 | ✅ |
| 9 | 分段 3 遍变动率 prom 4.4% / tier 4.9% | 4.4% / 4.9% | ✅ |
| 10 | 段① 前 12 行内容（Intel / NVIDIA / Palantir×2 / Intuit / BofA / BlackRock / Gartner / L3Harris / Micron / BAE / GE Vernova） | 名单一致（顺序因语料增长微调，多出 Honeywell） | ✅ |
| 11 | 按行求值：KAYAK 两条 ats_direct 在 A 段；Jobgether newgrad→C、ats_direct→非 C | 一致 | ✅ |
| 12 | 段 raw 相加 == 当日去重行数 | 1006 == 1006 | ✅ |
| 13 | `r2.py:has_board` 是死代码（等于全体公司） | 确认，`{norm(...) for r in rows}` 无过滤 | ✅ |

同时确认这些**接受意见落地正确**：删 S2/S3/S4、配额整段删除、`BATCH` 50→20、
删掉「stage-2 必须全残差」那条反向规则、`MODEL_PRICING` 只缺 `gpt-4o-mini`、
F4 改断言缓存值、F5 换掉盲测 gate、已知缺口 1（2023 后公司拿不到 tier）与
已知缺口 3（中介占比是下界）都写进了脚注。§9 的坑表我逐条看过，与我和 B 踩过的一致。

---

## 8. 放行条件

改完这两行就可以开工，不需要再回来找我：

| | 改哪里 | 改什么 |
|---|---|---|
| **1** | `enrich_companies.py` 的漏返兜底字典 | 加 `"stage": 0`；并加 fixture **F18**：`why=="LLM_NO_ROW"` 且 `n_7d=40` 的公司不得进 Lane C |
| **2** | `dashboard.py` 的 `REL_INC` | 加 `re.I`；删掉 §3.1 里「REL_INC 大小写敏感」那句；加表驱动 fixture **F19**（第 2 节给了正反各 6 条） |

另外把 F13 从自动断言改成人工签核项（它现在恒真），把 F12 的 931 实现成不变式。
这三处不改也不会出错误结论，但会让验收表失去意义。
