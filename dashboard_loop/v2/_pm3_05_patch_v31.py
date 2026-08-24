# -*- coding: utf-8 -*-
"""ROUND-3.1 - patch design_v3.md IN PLACE for A9 (no v4).

Four targeted string replacements; the script exits non-zero if any anchor is not
found exactly once, so "nothing else moved" is mechanical rather than a promise.
"""
import difflib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "design_v3.md")

EDITS = []


def edit(tag, old, new):
    EDITS.append((tag, old, new))


# ------------------------------------------------- P1  3.10 sequence step 3
edit("P1 3.10 step3",
     "3. 组内按 `(r 降序, 标题 降序)`，**最后再以 `(天下标, 行下标)` 降序做确定性 tie-break**（不写这一条，两边在并列时可能给出不同顺序）；",
     """3. 组内按 **`(天下标 降序, r 降序, 标题 降序, 行下标 降序)`** —— **天下标必须排在 `r` 前面**：
   `r` 是 `HH*100+MM`（§3.2），它**不含天**，先比 `r` 会把「昨天 03:22」排在「今天 02:22」前面。
   行下标是最后的确定性 tie-break（不写这一条，两边在并列时可能给出不同顺序）。
   这个键与「按完整 `_recorded` 字符串降序」**完全等价**（实测 1374 个公司组 0 例外，`_pm3_04_a9.py` B 节），
   §3.5 说的就是它。JS 侧写成：

   ```js
   function cmpRow(a, b){            // a,b = [rank, d, r, title, i]
     if (a[1] !== b[1]) return b[1] - a[1];        // 天下标 降序  <- 必须第一
     if (a[2] !== b[2]) return b[2] - a[2];        // r 降序
     if (a[3] !== b[3]) return a[3] < b[3] ? 1 : -1;   // 标题 降序
     return b[4] - a[4];                            // 行下标 降序
   }
   ```

   ⚠ **这一条错了 `hsum`/`osum` 抓不到**：Python 与 JS 会一致地错，校验和只证明两边一致，不证明两边对。
   所以 F29 另有一条 (c) 用真实的跨天公司组直接钉住它。""")

# ------------------------------------------------------------ P2  3.5 wording
edit("P2 3.5 wording",
     "`CL.sort_key(c)` 是与段无关的公司全序，所以一个全局名次数组对所有段、所有 N、所有视图都成立。段内行序 = 先按 `o[c]` 升序，同公司内按 `(_recorded 降序, 标题)`。",
     "`CL.sort_key(c)` 是与段无关的公司全序，所以一个全局名次数组对所有段、所有 N、所有视图都成立。段内行序 = 先按 `o[c]` 升序，同公司内按 **`(天下标 降序, r 降序, 标题 降序, 行下标 降序)`** —— 载荷里没有完整时间戳字符串，`(d, r)` 就是 `_recorded` 的等价表示（实测等价，见 §3.10 与 `_pm3_04_a9.py`）。**`d` 必须排在 `r` 前面**，理由与完整定义都在 §3.10。")

# ---------------------------------------------------------------- P3  F29 (c)
edit("P3 F29",
     "（b）**属性测试**：对每个非空的 `head` / `over` 序列做若干次随机互换、相邻互换、删一行、重复一行，`seq_hash` 必须**每次都改变** | **A6**：校验和是 100% 覆盖率的唯一来源，它自己两边不一致 / 不敏感的话，L2 第 6 条就是摆设。实测基线：180 cell 三方分歧 0；随机互换 3320、相邻互换 10024、删 1315、重复 1315，漏检全为 0 |",
     "（b）**属性测试**：对每个非空的 `head` / `over` 序列做若干次随机互换、相邻互换、删一行、重复一行，`seq_hash` 必须**每次都改变**；（c）**跨天公司组**：从真实语料里取至少一个行跨 ≥2 天的公司组（当前语料里段① 的 Micron Technology、Morgan Stanley 都是），断言 `view.window_view` 给出的 CAP=2 head **与按完整 `_recorded` 排序的结果相同** | **A6**：校验和是 100% 覆盖率的唯一来源，它自己两边不一致 / 不敏感的话，L2 第 6 条就是摆设。实测基线：180 cell 三方分歧 0；随机互换 3320、相邻互换 10024、删 1315、重复 1315，漏检全为 0。**(c) 是 A9**：`hsum`/`osum` 只能证明 Python 与 JS 一致，证不了两者都对 —— 组内排序键写错时两边会一致地错，只有拿「完整时间戳」这个外部 oracle 才抓得到。实测 61 个跨天组里 54 个（88.5%）在两种读法下 head 不同 |")

# ------------------------------------------------------------- P4  0.0 v3.1
edit("P4 v3.1 record",
     """| B9-residual | Evaluator B | §3.8 hero 卡片标题自带「全部窗口」限定词，并把实测落差写进正文 |""",
     """| B9-residual | Evaluator B | §3.8 hero 卡片标题自带「全部窗口」限定词，并把实测落差写进正文 |

#### v3.1（定向修正，不是新一轮）— A9：组内排序键在 §3.5 与 §3.10 里写法不一致

Evaluator A 对 v3 判 A6 closed（独立复现 180 cell 0 分歧、16k 次变异 0 漏检）、A7/A8 采纳、diff 无漂移，但抓到一处**文档内部不一致**：§3.10 的序列定义第 3 条写「组内按 `(r 降序, 标题)`，再用 `(天下标, 行下标)` tie-break」，而 §3.2 定义的 `r` 是 `HH*100+MM`、**不含天**；§3.5 写的却是「`_recorded` 降序」（含天）。跨天的公司组下这两种读法不是一回事，而且 **Python 与 JS 若都照字面实现会一致地错，`hsum`/`osum` 完全看不见**。

实测复现（`_pm3_04_a9.py`，2026-08-21 03:52:02，语料 2604 行，anchor 2026-08-21）：

```
跨天公司组 61 个，其中 CAP=2 head 在两种读法下不同的：54 个（88.5%）
段① micron technology（3 行跨 2 天）
    正确 (d,r)     -> 08-21 0222 | 08-20 0322
    字面 r-only    -> 08-20 0322 | 08-21 0222
段① morgan stanley
    正确 (d,r)     -> 08-20 2223 | 08-19 2328
    字面 r-only    -> 08-19 2328 | 08-20 2223
```

改了三处（其余逐字未动）：**§3.10 第 3 条**改成 `(天下标 降序, r 降序, 标题 降序, 行下标 降序)` 并附 JS 比较函数原文；**§3.5** 同步写成同一个键，并说明 `(d, r)` 就是 `_recorded` 的等价表示；**§4 F29 加 (c)**，用真实跨天组直接对「完整 `_recorded` 排序」这个外部 oracle 断言，而不是只靠 Python/JS 互相对账。

验证（同一次运行）：修正后的键与「按完整 `_recorded` 排序」在 **1374 个公司组上 0 例外**；把 JS 的比较函数同步改成 `cmpRow` 后**让 JS 自己分组、自己排序、自己算 `hsum`/`osum`**（12134 行、90 个 cell），与 Python **分歧 0**；`_pm3_01_checksum.py` 按新键重跑，180 个 cell 三方（Python 直译 / Python 独立实现 / 真 Chrome）**仍然 0 分歧**，变异测试漏检仍为 0。""")


def main():
    src = io.open(DOC, encoding="utf-8", newline="\n").read()
    out = src
    print("patching design_v3.md in place (v3.1, A9)")
    for tag, old, new in EDITS:
        n = out.count(old)
        if n != 1:
            print("  FAIL %-18s anchor found %d times (need exactly 1)" % (tag, n))
            print("       %r" % old[:100])
            sys.exit(1)
        out = out.replace(old, new, 1)
        print("  ok   %-18s %+d chars" % (tag, len(new) - len(old)))
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(out)
    hunks = [l for l in difflib.unified_diff(src.split("\n"), out.split("\n"),
                                             lineterm="", n=0) if l.startswith("@@")]
    print("")
    print("before %d lines / %d chars" % (src.count("\n") + 1, len(src)))
    print("after  %d lines / %d chars" % (out.count("\n") + 1, len(out)))
    print("diff hunks: %d for %d declared edits" % (len(hunks), len(EDITS)))
    for h in hunks:
        print("   " + h)


if __name__ == "__main__":
    main()
