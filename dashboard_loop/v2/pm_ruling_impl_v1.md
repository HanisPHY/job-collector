# PM 裁决 — impl_v1（设计方对 Engineer 实现报告的回执）

> 对象：`dashboard_loop/v2/impl_v1_report.md`（58 tests OK，skipped 2）
> 依据：`design_v3.md`（本裁决把它改成 **v3.2**，§0.0 有记录）与 req2 §1.5 的边界
> 证据：`dashboard_loop/v2/_pm4_01_ruling.py`，**2026-08-21 04:32:53 本地时间**，语料 2713 行 / 3 天，
> Python 3.10.19（`D:/Apps/Miniconda/envs/job-classifier/python.exe`），Chrome 151.0.7922.172（`--headless=new`，file://）。
> 我读了 `view.py` / `web/dashboard.js` / `web/shell.html` / `dashboard.py` / `tests/test_lane.py`，**一行代码都没改**。

**总裁决：3 条 design_defect 全部成立，按 Engineer 的最小改法接受；9 处偏离 8 条 ratify、1 条 ratify-with-amendment（#7）。没有一条触碰 I1-I9、六段判据、五档 N、分工线，`daily_report.py` / `company_lane.py` 逐字节未改（`git diff --stat` 为空）。**

---

## 1. design_defect 裁决

### D1 「● 新」谓词 `cutoff` vs `prev_cutoff` — **接受（设计错了，实现对了）**

`cutoff` 在 payload 里的定义就是**本次生成时刻的 `max(_recorded)`**，所以 `_recorded > cutoff` 按定义是空集。实测：

```
payload cutoff      = 2026-08-21 04:24   ->  命中   0 行
payload prev_cutoff = 2026-08-21 00:24   ->  命中 285 行
v1 dashboard.py 传进 table_html 的就是 prev_cutoff          True
```

§3.6 那一行是我写错的（§0.2 B4 与 §5 第 5 条都写的是 `prev_cutoff`，两处互相印证）。
**已在 v3.2 把 §3.6 改成 `> prev_cutoff` 并附上这两个数**，防止下一个人再照字面实现一次。
Engineer 的绕开方式（按 B4 + §5 实现）**保留，不用改代码**。

### D2 F27 按字面写今天就红 — **接受（设计错了，实现对了）**

§4 的 F27 写「幸存**行**集合相同」，但 §0.1 A3 是我自己量的：两条规则**已经**在 45 组里选出不同的物理行。
也就是我在同一份文档里先证明了 A、再要求断言 not A。Engineer 复测逐字复现了这个数（14 + 27 + 4 = 45）。

canary 该盯的是 **F6/F7/F19 真正依赖的那个巧合 —— 「0 组跨段」**，不是「同一行」。
Engineer 实现的 `F27DedupCanary` 断言：行数相等、岗位键集合相等、每个键落在同一段，物理行差异只报数不断言 —— 正是这个。
**已在 v3.2 把 F27 的措辞改成这三条**。代码不用改。

### D3 `assert_offline` 被真实岗位标题误伤 — **接受（设计错了，实现比建议更强）**

§4 第 3 条写「**任何** `.js`」，而 `data-<day>.js` 装的是岗位标题原文；语料里真有
`... React | TypeScript | Three.js | WebSockets | Geospatial Data ...`。这是我把「代码」和「数据」压成了一件事
（正是我自己在 §7 自检清单里列为要防的那类错误）。

Engineer 的改法比 A/B 两位评审建议的都强：**数据块必须是「一个赋值 + 一个 `json.loads` 解析得动的字面量」**——
JSON 字符串调不动任何东西，连「往数据块里夹带代码」都进不来（他还为此加了第 7 种攻击用例）；
子串黑名单只作用于 `dashboard.js`，并额外断言代码 JS 非空（否则空 bundle 会假装通过）。
**已在 v3.2 把 §4 第 3 条拆成数据块 / 代码块两条**。代码不用改。

---

## 2. 9 处偏离裁决

| # | 偏离 | 裁决 | 理由 |
|---|---|---|---|
| 1 | `check.head` 跨段顺序取 gidx 升序（DOM 顺序）而不是 `OPEN_ORDER` | **ratify** | §3.10 只说 head「有序」，没定跨段次序。照 `OPEN_ORDER`（①④②）就得让 JS 知道那是哪三个段 —— 要么 JS 里出现段 key 字符串（F23 立刻红），要么再发一个数组，两者都退回 B2 那个失败模式。gidx 升序同时**就是用户从上往下读的顺序**（①②④），`plan[g]` 仍然完全由 Python 给，首屏的**行集合一模一样**，只是拼接次序不同。这是守住 §3.8 的必然结果 |
| 2 | `chrome[n]` 删掉 `summ`，`p2`/`p3` 改成整块面板 HTML；52.5 KB 而非 29.9 KB | **ratify** | §3.9 已经规定 summary 计数来自 `check`，`summ` 没有消费者；面板 ②′ 抬头那句「窗口内 X / Y 行 = Z%，来自 N 家公司」本身随 N 变，只发 `<tr>` 会让它对不上。+22.6 KB = bundle 的 5.6%，买到的仍是 `dashboard.js` 里没有 SVG / 面板 / hero 渲染器。**v3.2 已把 29.9 KB 更正为实现值** |
| 3 | `JOB_INDEX` 多 `cap` / `srcs` / `segl` / `carry_segs` 四个派生字段 | **ratify** | 全是查表用的常量表，§3.9 的列定义（「由 `s` 查表」）本来就要求有这张表。`carry_segs=[0,1,3]` 把「⑦ 段取 ①②④」这个**判断**留在 Python、只把结果发给 JS —— 正是分工线要的方向。四个字段都不含段 key 字符串，F23 照过 |
| 4 | 默认展开段把整个 cap2 head 放进 DOM（首屏 153 `<tr>`，可见仍 47） | **ratify** | **不是违背 §3.9，是 §3.10 第 6 条的必然。** `hsum` 覆盖的是整个 cap2 head；只渲染可见的 47 行，①④ 两段的 `hsum` 就永远没有校验点 —— A6 白做一半。而且代价**有界且与采集量无关**：`cap2 ≤ 2 × 该段公司数`，实测 N=30 时 ①81+④75 = **156 个 `<tr>`**，结构上界 2×(59+55) = **228**；Chrome 建 153 行并强制布局实测 **4.5 ms**（800 行 23 ms、3200 行 98 ms）。对照 v1：v1 把所有段所有行都写进 HTML，**1291 个 `<tr>`**。「首屏 ≤47 行」这个不变量约束的是**可见展开的行数**（`open`），F11a/F11b 断言的就是它，`open` 仍精确等于 47。**v3.2 已把 §3.9 的措辞改清楚，并在 §3.12 增加一行「加载时 DOM 不随采集量涨」的机制**（上界来自公司表而不是行数） |
| 5 | `--out` 从文件路径改成目录 | **ratify** | §3.1 与 §5.3 本来就写 `--out <目录>`；`--out` 下不推进水位线的行为未变 |
| 6 | `main()` 开头 6 行 stdout `errors="replace"` 加固 | **ratify** | 修的是 req2 §7.1 那个 v1 就有的坑：本机 `cmd.exe` 代码页 1252，打印 `①` 会让一次**已经写完 bundle** 的成功运行以退出码 1 收场。代码只改编码错误处理器，不碰退出码、不吞异常（我读过），且 §5 第 2 条的判定标准（退出码 0 + 无 Traceback）正需要它 |
| 7 | `write_bundle` 删掉输出目录里形如 `YYYY-MM-DD.html` 的旧文件 | **ratify with amendment** | 方向对：§5 第 4 条要求 `logs/dashboard/` 里没有 `<day>.html`，而设计只说了「不再写」、没说清理，是我漏的。**但删除必须限制在默认输出目录**：`--out` 是用户自己挑的路径，误删一个同名文件不可逆，而 §5 第 4 条只对 `logs/dashboard/` 提要求。`data-*.js` 的清理仍然到处都做（F26 依赖它）。**请 Engineer 加这一个条件**（`elif DAY_HTML_RE.match(fn) and out_dir == OUT_DIR:`）。v3.2 §5 第 4 条已写明 |
| 8 | `health.unenriched` 口径从「当天出现」改成「默认窗口（近 3 天）出现」 | **ratify** | 窗口页面就该用窗口口径。而且**实测这次改动今天是个 no-op**：`今天出现` 210 家 / 未富化 **98**；`近 3 天出现` 1364 家 / 未富化 **98** —— 同一批公司，且其中**首见于更早那天的有 0 家**。（Engineer 报告里「92 vs v1 的十几家」的差别来自测量时刻不同，不是来自口径。）横幅那句「等明早 07:30」今天对全部 98 家都成立。**但它只在「被计入的公司全部首见于 anchor 日」时才成立**，所以请 Engineer 在现有 F9 里补一条断言（**只加测试，不改生产代码**）：`health` 计入的公司要么全部首见于 anchor 日，要么横幅文案不得出现「等明早」。这样这句承诺是自我看管的，而不是靠今天恰好为 0 |
| 9 | `view.py` 多 `segment_rows` / `segment_head` / `carry_seq` 三个函数 | **ratify** | §3.11 是签名清单不是白名单；三个都是纯数据、无 I/O，且 `window_view` 的返回键与设计逐字相同（F22 逐 cell 断言等号） |

---

## 3. 我核对过、结论与 Engineer 一致的地方

- `git diff --stat daily_report.py company_lane.py` 为空（I8 / 分工线未破）。
- `F27DedupCanary`、`assert_offline`、`web/dashboard.js` 的 `fresh = HAS_WM && after(days[di], col.r[i], PC)`（`PC = prev_cutoff`）都与上面的裁决一致。
- `write_bundle` 走 `tmp + os.replace`（OneDrive，req2 §7.3）。
- §2.6 的故意破坏回归第 (d) 项**把互换位置取在 `len//4`，刻意避开首/中/末** —— 这正是 A6 的正题：`cap2` 没变、`anchors` 三点没变，**只有 `hsum` 抓到了**。这条比我在 §5.10(d) 写的还严格，很好。

## 4. 需要 Engineer 做的全部动作（两处，都很小）

1. **偏离 #7**：`write_bundle` 里删 `YYYY-MM-DD.html` 的分支加一个「仅默认输出目录」的条件。
2. **偏离 #8**：F9 里补一条断言 —— `health` 计入的公司全部首见于 anchor 日，否则横幅不得出现「等明早」。

其余全部保留原样。三条 design_defect 的绕开实现**就是最终形态**，设计文档已经改到与实现一致（v3.2）。
