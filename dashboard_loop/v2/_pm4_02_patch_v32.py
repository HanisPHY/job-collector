# -*- coding: utf-8 -*-
"""v3.2 - patch design_v3.md IN PLACE with the PM ruling on impl_v1.

Targeted string replacements only; exits non-zero if an anchor is not unique.
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


# ------------------------------------------------------- Q1  D1: the new marker
edit("Q1 D1 marker",
     "- **`● 新`**：`(days[d], r) > cutoff`，纯比较。",
     "- **`● 新`**：`(days[d], r) > prev_cutoff`，纯比较。**是 `prev_cutoff`，不是 `cutoff`** —— "
     "`cutoff` 是本次生成时刻的 `max(_recorded)`，`> cutoff` 按定义是空集（实测 0 行，"
     "而 `> prev_cutoff` 是 285 行，`_pm4_01_ruling.py` 04:32:53）。这与 §0.2 B4、§5 第 5 条、"
     "以及 v1 `dashboard.py` 把 `prev_cutoff` 传进 `table_html` 的行为一致。")

# ---------------------------------------------------------- Q2  D2: F27 wording
edit("Q2 D2 F27",
     "| **F27** | **canary**：对每一天，`CL.day_rows(rows,d)` 选出的幸存行集合 == keep-NEWEST 在该日选出的集合 | **A3**：两条规则一旦分家要立刻知道，而不是让两套测试静默各测各的 |",
     "| **F27** | **canary**：对每一天，两条规则的**行数相等**、**岗位键集合相等**、且**每个键落在同一个段**；两边选出的物理行不同的组数只报数不断言 | **A3**：写成「同一批物理行」今天就是红的 —— §0.1 A3 自己量过两条规则已经在 45 个组里选了不同的行。**当前是巧合、也正是 F6/F7/F19 赖以成立的那件事，是「0 组跨段」**，canary 要盯的就是它 |")

# ------------------------------------------------- Q3  D3: assert_offline clause
edit("Q3 D3 offline",
     "3. 任何 `.js` 里不出现 `fetch(` / `XMLHttpRequest` / `WebSocket` / `importScripts` / `EventSource` / `navigator.sendBeacon`；",
     "3. **数据块与代码 JS 分开查**（岗位标题里真的有 `WebSockets`，实测 2026-08-21 语料里就有一条 "
     "`... React | TypeScript | Three.js | WebSockets | Geospatial Data ...`，子串扫描必然误伤）：\n"
     "   - `data-index.js` / `data-<day>.js` 必须是**一个赋值 + 一个能被 `json.loads` 解析的字面量**"
     "（比子串黑名单更强：JSON 字符串调不动任何东西，连夹带代码都进不来）；\n"
     "   - 子串黑名单 `fetch(` / `XMLHttpRequest` / `WebSocket` / `importScripts` / `EventSource` / "
     "`navigator.sendBeacon` 只作用于**代码** JS（`dashboard.js`），并断言代码 JS 非空（否则空 bundle 会假装通过）；")

# ----------------------------------------- Q4  #4: what "<=47 rows" actually binds
edit("Q4 render wording",
     "- 加载时只渲染 `open_plan` 指定的那 ≤47 行；折叠段的 summary 计数直接来自 `check`，不需要遍历行。",
     """- 加载时**可见**的行是 `open_plan` 指定的那 ≤47 行；折叠段的 summary 计数直接来自 `check`，不需要遍历行。
- ⚠ **默认展开的两段要把自己整个 cap2 head 放进 DOM**，超出 `plan[g]` 的部分收进「还有 N 条」的嵌套 `<details>`。
  这不是可选项：§3.10 第 6 条要求「每段展开后 `seqHash(实际渲染出的序列) == hsum[gidx]`」，而 `hsum` 覆盖的是**整个 cap2 head**；
  只渲染可见的 47 行，①④ 两段的 `hsum` 就永远没有校验点。
  **代价是有界的**（`_pm4_01_ruling.py`，04:32:53）：`cap2 ≤ 2 × 该段公司数`，实测 N=30 时 ①81 + ④75 = **156 个 `<tr>`**，
  结构上界 2 ×（①59 + ④55）= 228；Chrome 建 153 行 + 强制布局实测 **4.5 ms**，800 行 23 ms，3200 行 98 ms。
  对照 v1：v1 把**所有段所有行**都写进 HTML，实测 1291 个 `<tr>`。
  **「首屏 ≤47 行」约束的是可见展开的行数**（`open`），不是 DOM 里的 `<tr>` 数 —— F11a/F11b 断言的就是 `open`。""")

# ------------------------------------------------- Q5  #4: mechanism table row
edit("Q5 mechanism row",
     "| 折叠段内部**每一行**都不许错序/漏/重 | `check[f][N].hsum[gidx]` / `osum[gidx]`：整段序列的 32 位顺序校验和，覆盖 100% | F22 + **F29** + F24 + L2 第 6 条；验收 §5.10(d) 亲手互换两行验证红条 |",
     "| 折叠段内部**每一行**都不许错序/漏/重 | `check[f][N].hsum[gidx]` / `osum[gidx]`：整段序列的 32 位顺序校验和，覆盖 100% | F22 + **F29** + F24 + L2 第 6 条；验收 §5.10(d) 亲手互换两行验证红条 |\n"
     "| 加载时进 DOM 的 `<tr>` 数不随采集量涨 | 只有 ①④ 两段的 cap2 head 进 DOM，而 `cap2 ≤ 2 × 该段公司数` —— 上界来自公司表，不是行数 | 实测 156（N=30）/ 结构上界 228；人工验收第 5.9 条（30 天视图展开 ⑤ 段） |")

# ------------------------------------------------ Q6  #2: chrome byte correction
edit("Q6 chrome bytes",
     "实测（`_pm2_03_size.py`，03:06）：5 档 N 合计 **29,896 B**（N=1 3.0 KB … N=30 10.2 KB）。这 30 KB 换来 `dashboard.js` 里**没有 SVG 渲染器、没有面板渲染器、没有 hero 渲染器**，`svg_trend` / `svg_stack` 直接复用 `dashboard.py` 现有代码（`TREND_DAYS` 改成参数）。",
     "实测（`_pm2_03_size.py`，03:06）：5 档 N 合计 **29,896 B**（N=1 3.0 KB … N=30 10.2 KB）。"
     "**实现后的真实值是 52.5 KB**：`summ` 被删掉（§3.9 已规定 summary 计数来自 `check`，它没有消费者），"
     "而 `p2` / `p3` 改成整块面板 HTML 而不是只发 `<tr>` —— 面板 ②′ 抬头那句「窗口内 X / Y 行 = Z%，来自 N 家公司」"
     "本身随 N 变，只发 `<tr>` 会让它对不上。+22.6 KB = bundle 的 5.6%，换来的仍然是 `dashboard.js` 里"
     "**没有 SVG 渲染器、没有面板渲染器、没有 hero 渲染器**，`svg_trend` / `svg_stack` 直接复用 `dashboard.py` 现有代码"
     "（`TREND_DAYS` 改成参数）。")

# --------------------------------------------------- Q7  #7 / #8 acceptance item
edit("Q7 acceptance 4",
     "4. `logs/dashboard/` 里**没有 `<day>.html`**；`data-*.js` 的天数 ≤ 30。",
     """4. `logs/dashboard/` 里**没有 `<day>.html`**；`data-*.js` 的天数 ≤ 30。
   清理机制：`write_bundle` 每次运行删掉输出目录里 (i) 不在本次 `files` 里的 `data-*.js`（保留窗口，F26 守着）
   和 (ii) 形如 `YYYY-MM-DD.html` 的 v1 遗留页，并把删掉的文件名打进 stdout。
   **(ii) 只允许发生在默认输出目录 `logs/dashboard/`**，不允许发生在 `--out` 指定的目录 ——
   `--out` 是用户自己挑的路径，误删一个同名文件是不可逆的，而 §5 第 4 条只对 `logs/dashboard/` 提要求。
   (i) 在 `--out` 下仍然要做，F26 依赖它。""")

# ------------------------------------------------------------- Q8  §0.0 record
edit("Q8 v3.2 record",
     "| B9-residual | Evaluator B | §3.8 hero 卡片标题自带「全部窗口」限定词，并把实测落差写进正文 |",
     """| B9-residual | Evaluator B | §3.8 hero 卡片标题自带「全部窗口」限定词，并把实测落差写进正文 |

#### v3.2（对 impl_v1 的裁决，不是新一轮）

Engineer 按 v3.1 实现完毕（58 tests OK），上报 3 条 design_defect 与 9 处偏离。
完整裁决与证据在 `dashboard_loop/v2/pm_ruling_impl_v1.md`，结论：**3 条 defect 全部成立，按 Engineer 的最小改法接受；9 处偏离 8 条 ratify、1 条 ratify-with-amendment。**
本文因此改了 7 处（`_pm4_02_patch_v32.py`，其余逐字未动）：

| 改动 | 起因 | 实测依据（`_pm4_01_ruling.py`，2026-08-21 04:32:53，语料 2713 行） |
|---|---|---|
| §3.6 `● 新` 的谓词 `cutoff` → `prev_cutoff` | **D1** | `> cutoff` 命中 **0 行**（`cutoff = max(_recorded)`，按定义是空集），`> prev_cutoff` 命中 **285 行**；v1 传的就是 `prev_cutoff` |
| §4 F27 断言改成「行数 + 岗位键 + 段」 | **D2** | §0.1 A3 自己量过两条规则已在 **45 组**选出不同物理行；写成「同一批物理行」第一次跑就红 |
| §4 `assert_offline` 第 3 条拆成数据块/代码块 | **D3** | 语料里真有一条标题含 `WebSockets`；数据块改判「必须是一个赋值 + 一个 `json.loads` 得动的字面量」，比子串黑名单更强 |
| §3.9 说清「≤47 行」约束的是**可见**行 | 偏离 #4 | ①④ 的 cap2 head 必须整个进 DOM 才有 `hsum` 校验点；实测 N=30 是 **156 个 `<tr>`**，结构上界 `2 × 公司数` = 228，Chrome 建 153 行 **4.5 ms**（v1 是 1291 个 `<tr>`） |
| §3.12 增一行「加载时 DOM 不随采集量涨」的机制 | 偏离 #4 | 上界来自公司表而不是行数 |
| §3.8 chrome 字节数 29.9 KB → 实现值 52.5 KB | 偏离 #2 | `summ` 删除、`p2`/`p3` 改整块面板；+22.6 KB = bundle 的 5.6% |
| §5 第 4 条写清清理机制，并把 `<day>.html` 的删除**限制在默认输出目录** | 偏离 #7 | `--out` 是用户挑的路径，误删同名文件不可逆；`data-*.js` 的清理仍然到处都做（F26 依赖） |""")


def main():
    src = io.open(DOC, encoding="utf-8", newline="\n").read()
    out = src
    print("patching design_v3.md in place (v3.2, ruling on impl_v1)")
    for tag, old, new in EDITS:
        n = out.count(old)
        if n != 1:
            print("  FAIL %-18s anchor found %d times" % (tag, n))
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
