# -*- coding: utf-8 -*-
"""ROUND-3 PROBE 3 - produce design_v3.md from design_v2.md by TARGETED edits only.

The round-3 brief says: change only what A6 touches plus the four adopted
nice-to-haves, keep everything else verbatim. So this is a patch script, not a
rewrite: every edit is an exact string replacement and the script fails loudly if
any anchor text is not found exactly once.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "design_v2.md")
DST = os.path.join(HERE, "design_v3.md")

EDITS = []


def edit(tag, old, new):
    EDITS.append((tag, old, new))


# ------------------------------------------------------------------ E1 header
edit("E1 header", """# Dashboard v2 设计 v2（pm-design 第 2 轮，收口版）

> **Engineer 只需要读这一份。** 它是完整规格，不是对 v1 的增量 diff。
> 需求原文：`docs/req/req2-dashboard-v2.md`（本轮已重新逐字读过）。
> 框架：`docs/multiagent_design_build_loop.md` §0。
> 复现脚本：`dashboard_loop/v2/_pm_*.py`（第 1 轮）、`_pm2_*.py`（本轮），见 §8。
>
> **本轮方针：只做减法和收口。** 新机制只在某条 must-fix 没有它就关不掉时才引入 —— 全文只有一处（§3.6 的三视图开关），而它是把 v1 已有的「⑦ 段筛选开关」改成三选一，不是新增第二套机制。
>
> **口径**：§2 的所有语料数字来自 `_pm2_10_snapshot.py` 的**同一次运行**（2026-08-21 03:07:49）。浏览器数字单独标注（浏览器行为与语料增长无关）。语料每小时在涨，任何断言都不许写点值。""",
     """# Dashboard v2 设计 v3（pm-design 第 3 轮，定向修订版）

> **Engineer 只需要读这一份。** 它是完整规格，不是对 v2 的增量 diff。
> 需求原文：`docs/req/req2-dashboard-v2.md`（第 2 轮已重新逐字读过）。
> 框架：`docs/multiagent_design_build_loop.md` §0。
> 复现脚本：`dashboard_loop/v2/_pm_*.py`（第 1 轮）、`_pm2_*.py`（第 2 轮）、`_pm3_*.py`（本轮），见 §8。
>
> **v3 相对 v2 只做定向修订。** Evaluator B 对 v2 判 **pass**（0 must-fix）；Evaluator A 判 conditional_pass，A1-A5 全部 closed，只剩 **1 条 must-fix：A6**。本轮只改 A6 涉及的段落（§0.2 B3、§3.10、§3.11、§3.12、§4、§5.10）并采纳 4 条文档级 nice-to-have（A7 / B2-2、A8、B2-1、B9-residual），**其余内容与 v2 逐字相同，不引入任何新机制**。逐条见 §0.0。
>
> **第 2 轮方针仍然有效：只做减法和收口。** 新机制只在某条 must-fix 没有它就关不掉时才引入 —— 全文只有一处（§3.6 的三视图开关），而它是把 v1 已有的「⑦ 段筛选开关」改成三选一，不是新增第二套机制。
>
> **口径**：§2 的所有语料数字来自 `_pm2_10_snapshot.py` 的**同一次运行**（2026-08-21 03:07:49）。本轮新增的校验和与文档事实来自 `_pm3_01_checksum.py`（03:34:25，语料 2604 行）与 `_pm3_02_docfacts.py`（03:35:23）。浏览器数字单独标注（浏览器行为与语料增长无关）。语料每小时在涨，任何断言都不许写点值。""")

# ------------------------------------------------------------- E2 new §0.0
edit("E2 section 0.0", """## 0. 对 v1 评审的逐条回应

### 0.1 Must-fix（5 条，全部接受，全部已复现）""",
     """## 0. 对评审的逐条回应

### 0.0 v2 → v3 的定向修订（本轮）

Evaluator B：**pass**，0 must-fix。Evaluator A：conditional_pass，A1-A5 全部 closed，剩 A6。

#### A6 — `anchors` 只抽样 3 个坐标，大折叠段覆盖率个位数 → **接受，两条都做**

评审报告 ③ 506 行、⑤ 673 行、⑥ 198 行下覆盖率 1.8% / 1.3% / 4.6%。我按「3 个采样位置 ÷ 该段 cap2-head 行数」重算（`_pm3_01_checksum.py`，03:34:25，语料 2604 行，anchor 2026-08-21，view=all）**比评审说的还低**：

```
seg     cap2-head(N=30)   3 点覆盖率
1a_t3        79              3.8%
1a_t2       138              2.2%
1b          506              0.6%
B1           74              4.1%
B2          673              0.4%
C           198              1.5%
合计       1668 行，被抽到 18 行 = 1.1%
```

而且评审指出的第二半更要紧：v2 §5.10 的三个故意破坏项分别打 cap2 计数、`x` 位、`head`（只有首屏 ≤47 行）**顺序**，没有一项去打大折叠段中间的行序 —— 那正是 rAF 世代号（B8）没接对时会产生的形状。

**两条都做：**

- **(a) 给每段的完整渲染序列发一个顺序敏感的 32 位校验和**（`hsum` / `osum`，见 §3.10）。覆盖率从 1.1% 提到 **100%**，成本实测 `hsum` 1476 B + `osum` 1432 B。**这不是第二套机制**：同一个 6 行函数用在两条序列上，对账仍然是「JS 算一遍，跟 Python 给的数比」。
- **(b) §5.10 加第 4 项**：互换 ⑤ 段中间任意两行的坐标，确认红条。

**校验和必须两边逐字等价，所以它只用整数运算**（无浮点、无字符串编码）。实测三方一致（`_pm3_01_checksum.py`）：

```
cells：3 视图 × 5 档 N × 6 段 × {head, over} = 180
Python A1（规格伪代码直译）  vs  Python A2（独立实现，struct 走另一条路）：分歧 0
Python A1                    vs  JS（真 Chrome 151，--headless=new，file://）：分歧 0
```

顺序敏感性（同一脚本，随机种子 20260821）：

```
随机互换两行   3320 次   校验和未变（漏检）0
相邻互换两行  10024 次   校验和未变（漏检）0      <- 最难的一类，也是 rAF 串帧的形状
删掉一行       1315 次   校验和未变（漏检）0
重复一行       1315 次   校验和未变（漏检）0
```

`anchors` **保留不动**：校验和负责「有没有错」（100% 覆盖），`anchors` 负责「错在段的头/中/尾哪一段」（定位）。顺带更正 v2 的一处字节数：`anchors` 的 973 B 是在 `check` 还没按视图拆分时量的，`check[f][N]` 之后实测是 **3005 B**。

#### 采纳的 4 条 nice-to-have

| # | 来自 | 改了哪里 |
|---|---|---|
| A7 / B2-2 | 两位评审独立撞到同一处 | §5 验收第 12 条加上 `dashboard.py` 模块 docstring 第 9 行，并给出可判定的 grep 标准 |
| A8 | Evaluator A | §0.2 B4 一行措辞：改成「`● 新` 第一次有了可对账的计数」，不再暗示两条独立机制互证 |
| B2-1 | Evaluator B | §4 F23 加一条针对「段序字符串字面量数组」**形状**的正则 |
| B9-residual | Evaluator B | §3.8 hero 卡片标题自带「全部窗口」限定词，并把实测落差写进正文 |

### 0.1 Must-fix（v1 评审，5 条，全部接受，全部已复现）""")

# ------------------------------------------------------------------ E3 B3 row
edit("E3 B3 row",
     "| B3 折叠段内部无 identity 对账 | **采纳** | `check[f][N].anchors[seg]` = 该段 cap2 head 的**首 / 中 / 末**三个 `[天下标, 行下标]`。实测 6 段 × 3 坐标 × 5 档 = **973 B** |",
     "| B3 折叠段内部无 identity 对账 | **采纳** | `check[f][N].anchors[seg]` = 该段 cap2 head 的**首 / 中 / 末**三个 `[天下标, 行下标]`，实测 3 视图 × 5 档 × 6 段 = **3005 B**（v2 写的 973 B 是 `check` 按视图拆分之前量的，本轮更正）。**第 3 轮追加**：光靠 3 个采样点只覆盖 1.1% 的行（A6），所以又加了覆盖 100% 的顺序校验和 `hsum` / `osum`，`anchors` 降级为定位手段，见 §0.0 与 §3.10 |")

# ------------------------------------------------------------------ E4 B4 row
edit("E4 B4 row",
     "| B4 「● 新」无任何检查点 | **采纳** | B1 的修法让「● 新」升级成一个正式视图，`check[\"new\"][N]` 的 `head`/`anchors` 直接把它纳入对账；§5 人工清单加一条 |",
     "| B4 「● 新」无任何检查点 | **采纳** | B1 的修法让「● 新」升级成一个正式视图，于是它**第一次有了可对账的计数**（`check[\"new\"][N]` 的 `head` / `anchors` / `hsum`），而此前它完全没有任何校验点。**这不是两条独立机制互证**：`新增` 视图的谓词与 `● 新` 标记用的是同一个比较（`(days[d], r) > prev_cutoff`），谓词写错两处会一起错 —— 它买到的是「有没有渲染成预期的那些行」，不是「谓词对不对」。谓词本身由 §5 人工清单那一条看着 |")

# ------------------------------------------------------------------ E5 hero
edit("E5 hero title",
     "Python 把自己算出来的**事实**渲染成静态 HTML 放进骨架：hero 四块、「N 家未分层」健康横幅、趋势 SVG、堆叠条 SVG + 图例（含 `<a href=\"#seg-...\">`）、六个 `<details id=\"seg-...\" data-gidx=\"0..5\">` 的空壳与 summary 计数、⑦ 段空壳、面板②′、面板③、footer。",
     """Python 把自己算出来的**事实**渲染成静态 HTML 放进骨架：hero 四块、「N 家未分层」健康横幅、趋势 SVG、堆叠条 SVG + 图例（含 `<a href="#seg-...">`）、六个 `<details id="seg-..." data-gidx="0..5">` 的空壳与 summary 计数、⑦ 段空壳、面板②′、面板③、footer。

**hero / 趋势 / 堆叠条 / 图例 / 面板的标题必须自带「全部窗口」限定词**（B9-residual），例如 hero 第一块写成
`今日必看（段①，全部窗口）`、堆叠条标题写成 `今日构成（全部窗口）`。理由是实测的落差比预想大得多
（`_pm3_02_docfacts.py`，03:35:23，anchor 2026-08-21，N=3，独立复现了 Evaluator B 的数字）：

```
seg        view=all   view=new    倍数
1a_t3           99          7      14x
1a_t2          151          3      50x
1b             638         39      16x
B1              90          1      90x
B2             703         66      11x
C              374         28      13x
```

用户切到「新增」视图后，段① 的行表会正确地缩到 7 行，而 hero 的大号数字仍然是 99（R21 决定这些区块不随视图变，理由仍然成立）。**14 到 90 倍的落差，只靠开关旁边一行小字不够** —— 限定词要长在用户视线真正落点（hero 数字本身）的标题里。""")

# ------------------------------------------------------------------ E6 §3.10
edit("E6 check block", """  head:  [[28,17],[28,203],[29,4], …], // 首屏 ≤47 行的 [天下标, 行下标]，有序
  anchors: { "0": [[1,690],[0,107],[1,444]], … }   // 每段 cap2 head 的首/中/末（B3）
}
```

大小实测：`anchors` 6 段 × 3 坐标 × 5 档 = 973 B；`head` ≤47 × 15 组约 7 KB；计数部分约 3 KB。

**JS 渲染完做五件对账**，任一不过就在页面顶部显示红条（而不是安静少几行）：

1. `Σ raw == dedup` —— **I1 窗口版**
2. 自己数出来的 `raw` / `cap2` / `bars` 逐项等于 `check[f][N]`
3. 首屏渲染出的 `[天下标, 行下标]` 序列逐项等于 `check[f][N].head`
4. 每个应加载的天，`JOB_DAY[day].n == JOB_INDEX.nrows[i]`（块没加载 / 加载了旧块在这里现形）
5. **每段展开后**，该段 cap2 head 的首/中/末三行坐标等于 `check[f][N].anchors[gidx]`（B3：折叠段内部的行 identity 与顺序）
""", """  head:  [[28,17],[28,203],[29,4], …], // 首屏 ≤47 行的 [天下标, 行下标]，有序
  anchors: { "0": [[1,690],[0,107],[1,444]], … }, // 每段 cap2 head 的首/中/末，定位用（B3）
  hsum:    { "0": 1610846903, … },     // 每段 cap2-head 完整序列的顺序校验和（A6）
  osum:    { "0": 2455180042, … }      // 每段「+N more」完整序列的顺序校验和（A6）
}
```

大小实测（`_pm3_01_checksum.py`，03:34:25）：`hsum` **1476 B**、`osum` **1432 B**、`anchors` **3005 B**（3 视图 × 5 档 × 6 段；v2 写的 973 B 是 `check` 按视图拆分之前量的）；`head` ≤47 × 15 组约 7 KB；计数部分约 3 KB。

#### 顺序校验和（A6）

**要保护的是什么**：`anchors` 只抽 3 个点，实测只覆盖 1.1% 的 cap2-head 行（§0.0 的表）。其余 98.9% 的行如果被 JS 重排、漏渲染或重复渲染，v2 的五件对账全都看不见 —— 而 B8 的 rAF 世代号一旦没接对，产生的正是「段中间出现重复 / 乱序行」。

**序列的定义（Python 与 JS 必须逐字一致）**。对每个 `(视图 f, 档位 N, 段 s)`：

1. 取窗口内 `x == 0` 且满足视图谓词的行；
2. 按公司分组，组间按 `o[c]` 升序；
3. 组内按 `(r 降序, 标题 降序)`，**最后再以 `(天下标, 行下标)` 降序做确定性 tie-break**（不写这一条，两边在并列时可能给出不同顺序）；
4. `head` = 每组前 `CAP` 行按组序拼接；`over` = 每组第 `CAP` 行之后的部分按组序拼接；
5. 每行取 `[天下标, 行下标]`。

**校验和伪代码。只有整数运算：没有浮点、没有字符串、没有编码假设。** 常量是 FNV-1a 的 32 位偏移基与素数。

```
MASK      = 0xFFFFFFFF
FNV_OFF   = 2166136261        # 0x811C9DC5
FNV_PRIME = 16777619          # 0x01000193

mix(h, v):
    h = (h XOR (v AND MASK)) AND MASK
    return (h * FNV_PRIME) AND MASK

seq_hash(pairs):
    h = FNV_OFF
    for (d, i) in pairs:
        h = mix(h, d)
        h = mix(h, i)
    return mix(h, length(pairs))       # 把长度也吃进去，空序列与截断都能区分
```

Python 侧：

```python
def mix(h, v):
    h = (h ^ (v & 0xFFFFFFFF)) & 0xFFFFFFFF
    return (h * 16777619) & 0xFFFFFFFF

def seq_hash(pairs):
    h = 2166136261
    for d, i in pairs:
        h = mix(h, d); h = mix(h, i)
    return mix(h, len(pairs))
```

JS 侧（`Math.imul` 是精确的 32 位乘法，`>>> 0` 转无符号；两者合起来与 Python 的掩码写法逐位等价）：

```js
function mix(h, v){ h = (h ^ (v >>> 0)) >>> 0; return Math.imul(h, 16777619) >>> 0; }
function seqHash(pairs){
  var h = 2166136261 >>> 0;
  for (var k = 0; k < pairs.length; k++){ h = mix(h, pairs[k][0]); h = mix(h, pairs[k][1]); }
  return mix(h, pairs.length);
}
```

**实测证明**（`_pm3_01_checksum.py`，180 个 cell = 3 视图 × 5 档 N × 6 段 × {head, over}）：

```
Python A1（伪代码直译） vs Python A2（独立实现，走 struct 打包/解包）  分歧 0
Python A1              vs JS（Chrome 151.0.7922.172，--headless=new，file://）  分歧 0
随机互换 3320 次 / 相邻互换 10024 次 / 删一行 1315 次 / 重复一行 1315 次
                        校验和未改变（即漏检）的次数：全部为 0
```

相邻互换是顺序敏感哈希最难的一类，也正是串帧会产生的形状，所以它被穷举而不是抽样。

**JS 渲染完做六件对账**，任一不过就在页面顶部显示红条（而不是安静少几行）：

1. `Σ raw == dedup` —— **I1 窗口版**
2. 自己数出来的 `raw` / `cap2` / `bars` 逐项等于 `check[f][N]`
3. 首屏渲染出的 `[天下标, 行下标]` 序列逐项等于 `check[f][N].head`
4. 每个应加载的天，`JOB_DAY[day].n == JOB_INDEX.nrows[i]`（块没加载 / 加载了旧块在这里现形）
5. **每段展开后**，该段 cap2 head 的首/中/末三行坐标等于 `check[f][N].anchors[gidx]`（B3：定位错在哪一段）
6. **每段展开后**，`seqHash(该段实际渲染出的坐标序列) == check[f][N].hsum[gidx]`，「+N more」展开后同样对 `osum[gidx]`（A6：覆盖 100% 的行，包括折叠段中间那 98.9%）
""")

# ------------------------------------------------------------- E7 window_view
edit("E7 window_view keys",
     '        # -> {"dedup","raw","cap2","plan","open","bars","head","anchors","w7_days"}',
     '        # -> {"dedup","raw","cap2","plan","open","bars","head","anchors",\n'
     '        #     "hsum","osum","w7_days"}\n'
     '        # hsum/osum 由 view.seq_hash(pairs) 算；seq_hash 是 §3.10 的 6 行整数函数，\n'
     '        # 与 web/dashboard.js 里的 seqHash 逐位等价（F29 守着这条等价）')

# ------------------------------------------------------------------ E8 §3.12
edit("E8 mechanism row",
     "| 折叠段内部行不许错 | `check[f][N].anchors[gidx]` 首/中/末比对 | F22 + F24 + L2 第 5 条 |",
     "| 折叠段内部行不许错（定位） | `check[f][N].anchors[gidx]` 首/中/末比对 | F22 + F24 + L2 第 5 条 |\n"
     "| 折叠段内部**每一行**都不许错序/漏/重 | `check[f][N].hsum[gidx]` / `osum[gidx]`：整段序列的 32 位顺序校验和，覆盖 100% | F22 + **F29** + F24 + L2 第 6 条；验收 §5.10(d) 亲手互换两行验证红条 |")

# --------------------------------------------------------------- E9 fixtures
edit("E9 F22",
     '| F22 | `payload["index"]["check"][f][n] == view.window_view(payload, n, f)`，3 视图 × 5 档全对（含 `head` 与 `anchors`） | `check` 是 JS 唯一的真相来源，它自己必须被断言 |',
     '| F22 | `payload["index"]["check"][f][n] == view.window_view(payload, n, f)`，3 视图 × 5 档全对（含 `head`、`anchors`、`hsum`、`osum`） | `check` 是 JS 唯一的真相来源，它自己必须被断言 |')

edit("E9 F23",
     "| F23 | 去注释后的 `web/dashboard.js` 不含 `tier`、`prom`、`stage`、`kind`、`staffing`、`outsourcing`、`job_board`、`new grad`、`entry level`、`tnorm`（大小写不敏感），**也不含 `1a_t3` / `1a_t2`** | 把分工线从约定变成机制；后半段防 `SEGMENT_ORDER` 的硬编码副本（B2） |",
     "| F23 | 去注释后的 `web/dashboard.js`（a）不含 `tier`、`prom`、`stage`、`kind`、`staffing`、`outsourcing`、`job_board`、`new grad`、`entry level`、`tnorm`（大小写不敏感），**也不含 `1a_t3` / `1a_t2`**；（b）**不匹配 `[\\[\\(]\\s*(?:\"\\|')1a_t3(?:\"\\|')`** —— 专打「整份段序数组被硬编码」这个形状 | 把分工线从约定变成机制。(b) 是 B2-1：另外四个段 key（`1b` / `B1` / `B2` / `C`）太通用，逐个拉黑会误报，改成打数组字面量的形状。实测（`_pm3_02_docfacts.py`）对 4 段正常 JS 全部静默、对 4 种硬编码写法全部命中 |")

edit("E9 F29", """| **F28** | 3 视图 × 5 档 N：`Σ check[f][n].raw == check[f][n].dedup`，且 `view="all"` 的 dedup ≥ 另两个 | **B5**：⑦ 段 / 视图开关这块新行为的 I1 |""",
     """| **F28** | 3 视图 × 5 档 N：`Σ check[f][n].raw == check[f][n].dedup`，且 `view="all"` 的 dedup ≥ 另两个 | **B5**：⑦ 段 / 视图开关这块新行为的 I1 |
| **F29** | （a）`view.seq_hash` 与从 `web/dashboard.js` 里 grep 出的 `seqHash` 在同一批序列上结果逐位相同（能找到 Chromium 就用 `--headless=new` 真跑 JS，找不到就 `skipTest`）；（b）**属性测试**：对每个非空的 `head` / `over` 序列做若干次随机互换、相邻互换、删一行、重复一行，`seq_hash` 必须**每次都改变** | **A6**：校验和是 100% 覆盖率的唯一来源，它自己两边不一致 / 不敏感的话，L2 第 6 条就是摆设。实测基线：180 cell 三方分歧 0；随机互换 3320、相邻互换 10024、删 1315、重复 1315，漏检全为 0 |""")

# ----------------------------------------------------------- E10 acceptance
edit("E10 breakage", """10. **故意破坏回归（B11，必做）**：手工改坏三处再打开页面，确认红条真的会亮 ——
    (a) 把 `check["all"]["3"].cap2` 里某个数字改错 1；
    (b) 把某个 `data-<day>.js` 里几个 `x` 位取反；
    (c) 把 `check["all"]["3"].head` 的坐标顺序打乱。
    三次都必须出现红条并指出是哪一条对账失败。**这是唯一能验证「对账代码本身没写反」的办法**（L3 会与生产代码一起自我印证）。""",
     """10. **故意破坏回归（B11，必做）**：手工改坏四处再打开页面，确认红条真的会亮 ——
    (a) 把 `check["all"]["3"].cap2` 里某个数字改错 1；
    (b) 把某个 `data-<day>.js` 里几个 `x` 位取反；
    (c) 把 `check["all"]["3"].head` 的坐标顺序打乱；
    (d) **（A6 新增）展开 ⑤ 段，把 `check["all"]["3"].hsum["4"]` 换成任意别的数字**，或等价地手工互换 ⑤ 段 cap2-head **中间**任意两行的坐标 —— 必须命中 L2 第 6 条并报出「⑤ 段序列校验和不符」。
    这一项专打 v2 覆盖不到的那 98.9%：`anchors` 的首/中/末三点抓不到中间互换，`cap2` 计数也不会变。
    四次都必须出现红条并指出是哪一条对账失败。**这是唯一能验证「对账代码本身没写反」的办法**（L3 会与生产代码一起自我印证）。""")

edit("E10 item12",
     "12. `SCHEDULING.md` 第 204 行关于输出文件的描述已更新（不再有 `<day>.html`）。",
     """12. **两处过时描述都已更新**（A7 / B2-2，两位评审独立撞到同一处）——
    `SCHEDULING.md` 第 204 行，**以及 `dashboard.py` 自己的模块 docstring 第 9 行**
    （实测原文逐字相同：`Output: logs/dashboard/<day>.html  and  logs/dashboard/latest.html`）。
    **判定标准**：

    ```bash
    grep -rn "logs/dashboard/<day>\\|<day>.html" --include=*.py --include=*.md --include=*.bat . \\
      | grep -v "^./dashboard_loop/" | grep -v "^./docs/req/"
    ```

    必须**没有任何输出**。（`docs/req/` 是冻结的需求原文，`dashboard_loop/` 是设计过程记录，两者都不该改；
    实测这两个目录之外只有 `dashboard.py:9` 与 `SCHEDULING.md:204` 两处命中，`dashboard_loop/` 里另有 40 处。）""")

# ------------------------------------------------------------- E11 rejected
edit("E11 rejected", """| **R21** | **面板②′/③ 与趋势图跟着三视图开关变** | 它们是**窗口统计**，跟着筛选变会让「中介占比」这类数字失去可比性；且 chrome 要从 5 份涨到 15 份。改成只跟 N 变、不跟视图变，并在开关旁写明 |""",
     """| **R21** | **面板②′/③ 与趋势图跟着三视图开关变** | 它们是**窗口统计**，跟着筛选变会让「中介占比」这类数字失去可比性；且 chrome 要从 5 份涨到 15 份。改成只跟 N 变、不跟视图变。**第 3 轮补强**：实测落差是 11-90 倍（§3.8 的表），所以限定词从「开关旁一行小字」升级成「hero / 图表标题里常驻的『全部窗口』」（B9-residual） |
| **R22** | **A6 只把 `anchors` 的采样密度调大（例如每 50 行一个点）** | 评审给的另一半选项。放弃：采样密度再大也只是把漏检概率从「几乎必漏」降到「有可能漏」，而一个 32 位顺序校验和把覆盖率一次拉到 **100%**，实测只要 1476 B（`hsum`）+ 1432 B（`osum`），比把 `anchors` 加密到每 50 行一点还便宜。`anchors` 因此保留原样、只承担定位职责 |
| **R23** | **校验和用字符串哈希（把坐标拼成字符串再 hash）** | 那会把结果绑到字符串编码与拼接分隔符上，Python 与 JS 一旦有一点不同就整段对不上，而这类不一致**只会在运行时表现为永久红条**，极难定位。改成只吃整数、只用 XOR / 32 位乘法：`Math.imul` 与 Python 的掩码乘法逐位等价，实测 180 个 cell 分歧 0 |""")

# --------------------------------------------------------------- E12 scripts
edit("E12 scripts", """**本轮（第 2 轮）**""",
     """**本轮（第 3 轮）**

| 脚本 | 回答什么 |
|---|---|
| `_pm3_01_checksum.py` | **A6**：`anchors` 的真实覆盖率（1.1%）；校验和的三方一致性（Python 直译 / Python 独立实现 / 真 Chrome 的 JS，180 cell 分歧 0）；顺序敏感性（随机 3320 + 相邻 10024 + 删 1315 + 重复 1315，漏检 0）；字节成本（`hsum` 1476 B、`osum` 1432 B、`anchors` 3005 B） |
| `_pm3_02_docfacts.py` | **A7 / B2-2** 过时描述的全部落点与可判定的 grep 标准；**B2-1** 段序数组正则对 4 段正常 JS 静默、对 4 种硬编码命中；**B9-residual** all vs new 的逐段落差（11-90 倍，独立复现了 Evaluator B 的数字） |
| `_pm3_03_make_v3.py` | 由 `design_v2.md` 生成本文件：每处改动都是精确字符串替换，锚点不唯一就报错退出 —— 保证「其余内容逐字保留」这句话是机械成立的，不是人肉承诺 |

**第 2 轮**""")


def main():
    src = io.open(SRC, encoding="utf-8", newline="\n").read()
    out = src
    print("patching %s -> %s" % (os.path.basename(SRC), os.path.basename(DST)))
    for tag, old, new in EDITS:
        n = out.count(old)
        if n != 1:
            print("  FAIL %-22s anchor found %d times (need exactly 1)" % (tag, n))
            print("       anchor head: %r" % old[:90])
            sys.exit(1)
        out = out.replace(old, new, 1)
        print("  ok   %-22s  %+d chars" % (tag, len(new) - len(old)))
    io.open(DST, "w", encoding="utf-8", newline="\n").write(out)
    print("\nv2 %d lines / %d chars" % (src.count("\n") + 1, len(src)))
    print("v3 %d lines / %d chars" % (out.count("\n") + 1, len(out)))
    # prove the untouched part really is untouched
    import difflib
    d = list(difflib.unified_diff(src.split("\n"), out.split("\n"), lineterm="", n=0))
    changed = sum(1 for l in d if l.startswith("@@"))
    print("unified diff hunks: %d (one per targeted edit, %d edits declared)"
          % (changed, len(EDITS)))


if __name__ == "__main__":
    main()
