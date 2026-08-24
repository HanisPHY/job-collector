# Dashboard v2 — 工程实现报告 v1

> 实现依据：`dashboard_loop/v2/design_v3.md`（v3.1，972 行），全文通读两遍。
> 环境：`D:\OneDrive\work\school\project\Job`，Git Bash，`export PYTHONIOENCODING=utf-8`，
> 解释器 `D:/Apps/Miniconda/envs/job-classifier/python.exe`（Python 3.10.19），
> Chrome 151（`--headless=new`，file://）。实测时间 2026-08-21 04:10–04:30 本地时间，语料 2604→2650+ 行（每小时在涨）。
> 未 commit。`logs/last_report.json` 在 `.bat` 跑完后已从 `dashboard_loop/v2/last_report.backup.json` 逐字节恢复。

---

## 1. 改动文件清单

| 文件 | 行数 | 职责 |
|---|---|---|
| `view.py` | **540**（新增） | 纯数据参考实现，零 HTML、零 I/O、全函数。常量、`open_plan`/`openable`/`open_expected`、唯一去重规则 `superseded_flags`、`seq_hash`、`build_payload`、`segment_rows`/`segment_head`/`window_view`、`carry_seq`、`encode_index`/`encode_day` |
| `dashboard.py` | 583 → **627** | 只算数据 + 填模板 + 原子写。删掉 `CSS` 常量 / `row_html` / `table_html` / `details`；`svg_trend` `TREND_DAYS` 改成参数；新增 `build_bundle` / `build`（兼容壳）/ `render_shell` / `write_bundle` / chrome 预渲染；`main` 新增 `--retain`，`--out` 改成目录 |
| `web/shell.html` | **45**（新增） | 真 HTML 骨架，12 个 `<!--SLOT:*-->` |
| `web/dashboard.css` | **130**（新增） | v1 的 95 行 CSS 常量**逐字**搬来（前 91 行未改一个字符）+ 39 行 v2 追加（`scroll-margin-top` / `:focus-visible` / 两个 radiogroup / 红条 / `[aria-busy]` / ⑦ 段 / 日期列 / `#selfcheck`） |
| `web/dashboard.js` | **856**（新增） | 经典脚本。过滤 / 计数 / 分组 / 拼 DOM / 六件对账 / rAF 世代号 / 三视图与 5 档 N / 锚点 / `#selfcheck` |
| `tests/test_lane.py` | 560 → **1237** | F10/F11/F12/F19 与三个辅助函数按 §4 推广到窗口；F9 改走 `build_bundle`；`test_dashboard_has_no_external_dependency` 换成 `assert_offline`；新增 F20–F29 |
| `SCHEDULING.md` | 第 204 行 | 输出描述改成 bundle + 「没有历史 `<day>.html`」+ `--out` 快照办法 |
| `dashboard.py` docstring 第 9 行 | — | 同上 |

**未改**：`daily_report.py`、`company_lane.py`（`git diff --stat` 两者均为空，见 §2.8）。
**未创建** `queue.py`；`web/` 里只有三个源文件。

`logs/dashboard/` 现在只有 7 个文件（`latest.html` + css + js + index + 3 个日块），
v1 遗留的 `2026-08-20.html` / `2026-08-21.html` 在第一次运行时被 `write_bundle` 删掉（见 §4 偏离 7）。

---

## 2. 自测逐项输出（原样贴）

### 2.1 `python tests/test_lane.py` 全绿

```
Ran 58 tests in 6.216s

OK (skipped=2)
```

跳过的 2 个仍然是 F1/F2（需要 `JOB_TEST_LLM=1` 的实时富化）。
基线 36 个 → 58 个：F11 拆成 4 条、F12 加 payload 版、F19 加窗口版、F9 加 3 条、
`assert_offline` 加 1 条自攻击、F20–F29 共 14 条。
**F24 与 F29a 真的启动了 Chrome 并通过，不是 skip**：

```
test_F20_no_row_is_lost_on_the_way_into_the_payload (F20F21Payload) ... ok
test_F21_the_window_never_shows_the_same_job_twice (F20F21Payload) ... ok
test_F22_check_is_exactly_window_view (F22F28Check) ... ok
test_F22_check_survives_the_json_round_trip (F22F28Check) ... ok
test_F23_no_hardcoded_segment_order_array (F23DivisionOfLabour) ... ok
test_F23_no_judgement_vocabulary_in_dashboard_js (F23DivisionOfLabour) ... ok
test_F23_the_shell_is_what_carries_the_segment_ids (F23DivisionOfLabour) ... ok
test_F24_a_broken_check_really_does_light_the_banner (F24Browser) ... ok
test_F24_headless_browser_reports_all_cells_ok (F24Browser) ... ok
test_F25_the_two_seven_days_never_get_mixed (F25F26Plumbing) ... ok
test_F26_retention_bounds_the_output_directory (F25F26Plumbing) ... ok
test_F27_the_old_day_rule_still_covers_the_same_jobs (F27DedupCanary) ... ok
test_F28_every_view_and_window_satisfies_I1 (F22F28Check) ... ok
test_F29a_python_and_the_shipped_js_agree_bit_for_bit (F29Checksum) ... ok
test_F29b_the_checksum_moves_whenever_the_sequence_moves (F29Checksum) ... ok
test_F29c_cross_day_groups_match_the_full_timestamp_oracle (F29Checksum) ... ok
```

### 2.2 序列定义与 PM 的独立参考实现对账（做完 `view.py` 立刻跑的第一件事）

拿 `_pm3_01_checksum.py` 的 `build_sequences()`（PM 第 3 轮的参考实现，含 A9 的 `canon`）
与我的 `view.window_view` 逐 cell 比 `hsum` / `osum`：

```
compared 180 disagreements 0
A1 vs A2 on one seq: True
```

180 = 3 视图 × 5 档 N × 6 段 × {head, over}。**分歧 0**，即我的段内序列与设计的定义逐位一致。

### 2.3 `--date 2026-08-20 --no-watermark --out <scratch>` 生成完整 bundle

（下面这次跑的是 `--date 2026-08-21`，数字与 §2.4 对得上；`--date 2026-08-20` 的等价运行在 F26 里每次测试都跑）

```
============================================================
Dashboard - 2026-08-21  (window 3 days, view=all)
============================================================
  ① 今日必看                   raw   99   cap2   79
  ② 大中公司应届岗                raw  151   cap2  138
  ③ 大中公司其他岗位               raw  638   cap2  506
  ④ 有自有 ATS board 的小公司     raw   90   cap2   74
  ⑤ 长尾                     raw  703   cap2  673
  ⑥ 中介 / 刷屏                raw  374   cap2  198
  raw total 2055 == deduped rows in the window 2055
  first screen (1 + 4 + 2 filler): 47   [30, 47]
  section 7 (unhandled from the last issue): 0
  7 files, 3 day blocks, 0.37 MB
```

目录自包含：

```
dashboard.css  dashboard.js  data-2026-08-19.js  data-2026-08-20.js
data-2026-08-21.js  data-index.js  latest.html
```

**这组 cap2 与设计 §0.0 的表逐个相同**（`79 / 138 / 506 / 74 / 673 / 198`），
⑦ 段 N=1 给 83 行、N≥3 给 0 行，与 [T4] 相同。

### 2.4 `--no-watermark` 生成到 `logs/dashboard/`

```
  ① 今日必看                   raw  100   cap2   80
  ...
  raw total 2083 == deduped rows in the window 2083
  first screen (1 + 4 + 2 filler): 47   [30, 47]
  7 files, 3 day blocks, 0.38 MB
  removed 2 stale file(s): 2026-08-20.html, 2026-08-21.html
```

### 2.5 Chrome 无头 `latest.html#selfcheck` — 15 格全 ok

```
SELFCHECK ok (15 cells)
  all {'1': (True, 224), '3': (True, 2083), '7': (True, 2083), '14': (True, 2083), '30': (True, 2083)}
  new {'1': (True, 177), '3': (True, 177), '7': (True, 177), '14': (True, 177), '30': (True, 177)}
  wm  {'1': (True, 47),  '3': (True, 739), '7': (True, 739), '14': (True, 739), '30': (True, 739)}
cells ok: 15 / 15
```

不带 `#selfcheck` 正常渲染时红条保持 `hidden`，DOM 里 `tr[data-k]` 共 153 行
= 段①的 cap2 head 79 + 段④的 74，其中**可见展开的正好 47 行**（35 + 12），其余在
「还有 N 条」的折叠 `<details>` 里。

### 2.6 ★ 故意破坏回归（设计 §5.10，四项全做，每项一份独立拷贝）

```
baseline (untouched bundle)
  -> BANNER STAYED HIDDEN

(a) check[all][3].cap2[2] 508 -> 509
  -> 分段 cap2 计数与 Python 不符：80/138/508/75/691/198 vs 80/138/509/75/691/198

(b) flipped 22 x bits in data-2026-08-20.js
  -> 趋势柱高与 Python 不符 | 分段 cap2 计数与 Python 不符：79/138/499/75/686/196 vs
     80/138/508/75/691/198 | 去重后行数 2063 ≠ Python 的 2083 | 首屏渲染出的 47 行与
     Python 给的首屏序列不符 | 今日必看 段序列校验和不符（共 79 行；行序、漏行或重复行
     都会命中这一条）| 分段 raw 计数与 Python 不符：99/151/634/91/715/373 vs
     100/151/643/91/723/375

(c) swapped head[3] and head[9] of the first-screen sequence
  -> 首屏渲染出的 47 行与 Python 给的首屏序列不符

(d) segment 5 cap2-head has 691 rows; swapped rows 172 and 173 (the middle)
    cap2 unchanged: True   anchors(first/mid/last) unchanged: True
    -> that swap is invisible to every v2 check; only hsum can see it
  -> 长尾 段序列校验和不符（共 691 行；行序、漏行或重复行都会命中这一条）
```

第 (d) 项是 A6 的正题：互换位置取在 `len//4`（**刻意避开首/中/末**），
所以 `cap2` 没变、`anchors` 三个采样点也没变 —— **v2 的五件对账一件都看不见，只有 `hsum` 抓到了**。
四次都亮红条，并各自点名是哪一条对账失败；baseline 保持隐藏。
脚本：`dashboard_loop/v2/` 之外的临时目录（每项在 `logs/dashboard` 的独立拷贝上做，
线上 bundle 全程未被改动）。

### 2.7 降级三连（I9 / A5）

```
===== JOB_PROFILE_PATH=<不存在的文件>
Warning: could not read ...; continuing with an empty table
  ⑥ 中介 / 刷屏                raw    0   cap2    0
  raw total 2121 == deduped rows in the window 2121
  first screen (1 + 4 + 2 filler): 16   [16, 47]

===== JOB_PROFILE_PATH=<内容为 {} 的文件>
  ⑥ 中介 / 刷屏                raw    0   cap2    0
  raw total 2121 == deduped rows in the window 2121
  first screen (1 + 4 + 2 filler): 16   [16, 47]

降级 bundle 的横幅：1327 家未分层     页面以 <!doctype html> 开头：True
降级 bundle 的 #selfcheck：SELFCHECK ok (15 cells)
```

两种情况都能生成、⑥ 段 raw 为 0、I1 成立、首屏落在 `[min(30, openable), 47]` 内
（`openable=16 < FLOOR`，所以下界就是 16 —— 这正是 A2 修正后的合同）。
`view.build_payload` / `view.window_view` / `view.carry_seq` 在空 `profiles`、空 `rows`、
空 payload、缺键 `cap2` 下都不抛异常（fixture `test_F9_degraded_payload_functions_never_raise`）。

### 2.8 `.bat` 真跑一次（B10 判定标准）

先备份 `logs/last_report.json` 与 `logs/daily/`，跑完恢复水位线。

```
EXITCODE=0
TRACEBACKS=0
STDERR_MARKER=0            (stdout/stderr 里没有 "Error occurred" / "Dashboard error")

Name               Length LastWriteTime
dashboard.css        6957 2026/8/21 4:23:22
dashboard.js        32492 2026/8/21 4:23:22
data-2026-08-19.js  26931 2026/8/21 4:23:22
data-2026-08-20.js 155986 2026/8/21 4:23:22
data-2026-08-21.js  25743 2026/8/21 4:23:22
data-index.js      132697 2026/8/21 4:23:22
latest.html         16235 2026/8/21 4:23:22
NOW=2026-08-21 04:23:23
```

七个文件的 mtime 全部是本次运行（4:23:22 vs now 4:23:23）。
水位线被真实推进到 `cutoff 2026-08-21 04:22 / hero 80`，跑完已恢复：

```
$ diff logs/last_report.json dashboard_loop/v2/last_report.backup.json
IDENTICAL
```

`logs/daily/` 三份日报（08-19 / 08-20 / 08-21）都还在，F17 依赖的 `2026-08-19.md` 未被 prune 掉。

> 注：第一次用 `cmd.exe /c` 且 stdin 被重定向时退出码是 1，来源是 `.bat` 末尾那句
> **给双击用的 `timeout /t 30`**（`ERROR: Input redirection is not supported`），
> 两个 Python 脚本都已成功跑完。设 `JOB_UNATTENDED=1`（真实调度链路里 `run_logged.bat` 就是这么设的）
> 后退出码是 **0**，上面那组就是这次的输出。

### 2.9 没有 `PYTHONIOENCODING` 的 `cmd.exe`

本机 `cmd.exe` 的默认代码页实测是 **1252**。修复前：

```
EXITCODE=1  UNICODE_ERRORS=1
UnicodeEncodeError: 'charmap' codec can't encode character '\u2460' ...
  File "dashboard.py", line 592, in main
```

**这是 v1 就有的行为**（v1 的 `main()` 打印同样的 `①`，req2 §7.1 把它列为已知坑），
但它发生在 bundle **已经写完之后**，等于一次健康的运行报告失败、并让 `.bat` 打出 "Dashboard error"。
在 `main()` 开头加了 6 行 `stream.reconfigure(errors="replace")`（只兜字符，不吞退出码）。修复后：

```
EXITCODE=0  UNICODE_ERRORS=0  TRACEBACKS=0
  ? ????                   raw  102   cap2   81
  ...
  raw total 2142 == deduped rows in the window 2142
  first screen (1 + 4 + 2 filler): 47   [30, 47]
```

cp1252 下段号退化成 `?`，不再崩。`resolve_python.bat` 的路径仍然是正常中文。

### 2.10 `daily_report.py` / `company_lane.py` 逐字节未改

```
$ git diff --stat daily_report.py company_lane.py
(空)
```

### 2.11 §5 第 12 条的 grep 判定

```
$ grep -rn "logs/dashboard/<day>\|<day>.html" --include=*.py --include=*.md --include=*.bat . \
    | grep -v "^./dashboard_loop/" | grep -v "^./docs/req/"
(无输出)
```

### 2.12 载荷大小（本次线上产物）

```
  dashboard.css              6957 B
  dashboard.js              32492 B
  data-2026-08-19.js        26931 B      (287 行, 93.8 B/行)
  data-2026-08-20.js       155986 B     (2072 行, 75.3 B/行)
  data-2026-08-21.js        26851 B
  data-index.js            135837 B
  total                    401288 B = 0.38 MB

  index.co     47030 B   index.sigs  16211 B   index.o      5711 B
  index.chrome 52532 B   index.check 12831 B   index.lpre    246 B
  hsum 1448 B   osum 1405 B   anchors 3022 B   head 3975 B
```

`hsum` / `osum` / `anchors` 与设计实测的 1476 / 1432 / 3005 B 基本一致（语料涨了一点）。
`chrome` 是 52.5 KB 而不是设计写的 29.9 KB —— 原因见 §4 偏离 2。

---

## 3. design_defect（3 条，都没有自己改设计）

### D1 —「● 新」的谓词在 §3.6 与 §0.2 B4 / §5 之间自相矛盾

- **type**: contradiction
- **description**: §3.6 第一条写 `● 新：(days[d], r) > cutoff`；而 §0.2 B4 写
  「`新增` 视图的谓词与 `● 新` 标记用的是同一个比较（`(days[d], r) > prev_cutoff`）」，
  §5 第 5 条又要求「`全部` 视图里带 `● 新` 的行数**等于** `新增` 视图的行数」。
  在 payload 的命名下 `cutoff` = 本次生成时刻的最大 `_recorded`，`prev_cutoff` = 上一期的水位线，
  两者不是一个数：照 §3.6 字面实现，`● 新` 会几乎一行都不亮（`> cutoff` 是空集），
  §5 第 5 条的人工核对项直接不可能通过。
- **impact**: 中。只影响 `● 新` 标记，不影响任何计数或对账；但它是 B4「`● 新` 第一次有了可对账的计数」这条修法的落点，写错等于 B4 白做。
- **建议的最小改法**: §3.6 第一条改成 `● 新：(days[d], r) > prev_cutoff`（与 `new` 视图同一个比较，也与 v1 `dashboard.py` 的 `table_html(R, shown, prev_cutoff)` 一致）。
- **我怎么绕开的**: 按 B4 + §5 实现（`prev_cutoff`），因为那两处互相印证且与 v1 行为一致。`#selfcheck` 与 F28 不受影响。

### D2 — F27 的断言按字面写今天就是红的

- **type**: contradiction（设计自己的两段互相打架）
- **description**: §4 F27 写「对每一天，`CL.day_rows(rows,d)` 选出的**幸存行集合** == keep-NEWEST 在该日选出的集合」。
  但 §0.1 A3 自己测过：两条规则「在三天里对 **45 组**选出了不同的物理行，目前**恰好 0 组跨段**」。
  我按当前语料复测，逐字复现了这个数：

  ```
  2026-08-19  day_rows 230  keepNEW 230  same rows? False  physical diff 14  key sets equal True  segment diffs 0
  2026-08-20  day_rows 1674 keepNEW 1674 same rows? False  physical diff 27  key sets equal True  segment diffs 0
  2026-08-21  day_rows 191  keepNEW 191  same rows? False  physical diff  4  key sets equal True  segment diffs 0
                                                            (14+27+4 = 45)
  ```

  也就是说「幸存**行**集合相同」这句话今天就不成立，F27 会在第一次运行就红，而红的原因不是任何回归。
- **impact**: 中。这条 fixture 是 A3 的全部剩余价值，写成必红等于没有 canary。
- **建议的最小改法**: 把 F27 的断言从「同一批物理行」改成「**同一批岗位键、同样的段**」——
  即 `{(norm(公司), tnorm(标题)): 段}` 两边相等，外加行数相等；物理行差异只报数不断言。
  理由正是 A3 自己的措辞：**目前是巧合的那件事是「0 组跨段」，不是「同一行」**，而 F6/F7/F19 依赖的恰恰是前者。
- **我怎么绕开的**: 按上面这条实现（`F27DedupCanary`，测试里写清了为什么这么断言）。今天 3 天全绿。

### D3 — `assert_offline` 第 3 条会被真实岗位标题误伤

- **type**: omission / false positive
- **description**: §4 写「**任何** `.js` 里不出现 `fetch(` / `XMLHttpRequest` / `WebSocket` / `importScripts` / `EventSource` / `navigator.sendBeacon`」。
  `data-<day>.js` 里装的是岗位标题原文，而语料里真的有一条：

  ```
  Big Wave Digital | Palantir | Frontend Software Engineer | Real-Time 3D Autonomous
  Systems  React | TypeScript | Three.js | WebSockets | Geospatial Data ...
  ```

  第一次跑 `tests/test_lane.py` 就红在这里：`AssertionError: data-2026-08-20.js uses WebSocket`。
  语料每小时在涨，明天换一条带 `fetch(` 的标题一样会中。
- **impact**: 中。会让一条本来很有价值的离线断言变成每隔几天误报一次，最后被人注释掉。
- **建议的最小改法**: 把 `.js` 分成两类。**数据块必须是「一个赋值 + 一个能被 `json.loads` 解析的字面量」**
  （比子串扫描更强：JSON 字符串不可能调用任何东西），子串黑名单只作用于**代码** JS（`dashboard.js`）。
- **我怎么绕开的**: 按上面这条实现，并给攻击用例加了第 7 种 ——「往数据块里夹带代码」
  （`...={};fetch("x");`），它现在会被解析这一步拦下。六种原攻击 + 这一种，全部命中。

---

## 4. 偏离设计的地方（都不改判据、不改不变量）

1. **`check[f][N].head` 的跨段顺序取 gidx 升序（DOM 顺序），不是 `OPEN_ORDER`。**
   §3.10 只说 head「有序」，没定跨段次序；`_pm2_base.first_screen_keys` 用的是 `OPEN_ORDER`（①④②）。
   若照 `OPEN_ORDER`，JS 就必须知道 `OPEN_ORDER` 是哪三个段 —— 那要么在 JS 里出现段 key 字符串（F23 立刻红），
   要么再发一个数组。改成 DOM 顺序后，JS 只是「从上往下走一遍 `[data-gidx]`」，
   `plan` 仍然完全由 Python 给。这是为了守住 §3.8 的 B2 方案，不是口味。

2. **`chrome[n]` 的键是 `{hero, trend, stack, legend, note, p2, p3}`，没有 `summ`；`p2`/`p3` 是整块面板 HTML 而不是 `<tr>` 串。**
   §3.9 明确写「折叠段的 summary 计数**直接来自 `check`**」，所以 `summ` 没有消费者，删掉；
   面板 ②′ 的那句「窗口内 X / Y 行 = Z%，来自 N 家公司」和面板 ③ 的抬头也随 N 变，
   只发 `<tr>` 会让这句话对不上。代价是 chrome 从设计估的 29.9 KB 涨到 52.5 KB（+22.6 KB，占 bundle 5.6%），
   换来的仍然是 dashboard.js 里没有 SVG 渲染器、没有面板渲染器、没有 hero 渲染器。

3. **`JOB_INDEX` 多了四个派生字段**：`cap`（=2）、`srcs`（来源文案表）、`segl`（⑦ 段「段」列的文案表）、
   `carry_segs`（`[0,1,3]`，①②④ 的 gidx）。全部是「让 JS 查表而不是判断」所必需的，
   §3.9 的列定义里「由 `s` 查表」本来就要求有这张表。它们都不含任何段 key 字符串，F23 照过。

4. **默认展开的段在加载时把整个 cap2 head 都放进 DOM**（可见的仍然只有 `plan[g]` 行，其余在折叠的「还有 N 条」里）。
   §3.9 写「加载时只渲染 `open_plan` 指定的那 ≤47 行」，但 §3.10 第 6 条要求「每段展开后
   `seqHash(该段实际渲染出的坐标序列) == hsum[gidx]`」，而 `hsum` 覆盖的是**整个 cap2 head**。
   两者只能二选一：不渲染「还有」的那部分，段① 的 `hsum` 就永远没法在页面上校验。
   实测代价是首屏 DOM 153 个 `<tr>` 而不是 47 个（v1 是把**所有段所有行**都渲染进 HTML 的，1291 个 `<tr>`）。
   **「首屏 ≤47 行」这个不变量指的是可见展开的行数，`open` 仍然精确等于 47**，F11a/F11b 断言的就是它。

5. **`--out` 从「HTML 文件路径」改成「目录」。** §3.1 / §5.3 就是这么用的（`--out <目录>`），
   但 v1 的 `--out` 是文件名。这是必要的语义变更，`--out` 下不推进水位线的行为保持不变。

6. **`main()` 开头 6 行 stdout 加固**（§2.9）。设计没提 stdout 编码；
   不加的话本机默认 cmd.exe（代码页 1252）下一次成功的运行会以退出码 1 收场。只兜字符，不动退出码。

7. **`write_bundle` 会删掉输出目录里形如 `YYYY-MM-DD.html` 的旧文件。**
   §5 第 4 条要求「`logs/dashboard/` 里**没有** `<day>.html`」，但设计没写清理机制（A1 只说「不再写」）。
   我按验收条款做了最小的一件事：只删**完全匹配 v1 命名**的那种文件，并在 stdout 打印删了什么
   （本次删掉 `2026-08-20.html` / `2026-08-21.html`）。`data-*.js` 的超期清理同理（`--retain`，F26 守着）。

8. **`health.unenriched` 的口径从「当天出现」改成「默认窗口（近 3 天）出现」**，横幅文案同步改成「近 3 天出现」。
   窗口视图下「今天出现」已经不是页面在描述的东西。数字因此比 v1 大（今天 92 vs v1 的十几家）。
   F9 断言的是「> 0 且横幅里的数字与 `stats["unenriched"]` 一致」，不是点值。

9. **`view.py` 多了三个 §3.11 没列的函数**：`segment_rows`（`window_view` 的内部实现，
   顺便让 fixture 拿得到单段 head）、`segment_head`、`carry_seq`（⑦ 段）。
   §3.11 列的是签名清单不是白名单；这三个都是纯数据、无 I/O、被 §3.6 / §4 的要求逼出来的。
   `window_view` 的返回键与设计**逐字相同**（F22 逐 cell 断言等号）。

---

## 5. 给 QA 的真实环境验证步骤

前置：`logs/dashboard/latest.html` 已经是最新一次生成的产物（§2.4 / §2.8 跑过）。

### 5.1 必做：真的双击（这条代码看不出来，F24 也覆盖不到）

本机 `.html` 的默认打开程序是 **Edge**（注册表 `MSEdgeHTM`），而 **Edge 无头在本机 `--dump-dom` 产出 0 字节**，
所以 F24 只覆盖了 Chrome。**在资源管理器里双击 `logs\dashboard\latest.html`**，逐项看：

1. **页面顶部没有红条**。有红条就停下来截图，红条会写明是哪一条对账失败。
2. **5 档 N 各点一次**（1 / 3 / 7 / 14 / 30）：页面不重载（地址栏不变、不闪白）、无红条、
   段标题上的 `raw X · cap2 Y` 跟着变。
3. **三个「显示」各点一次**（全部 / 新增 / 上一期未处理）：六个分段的计数变、无红条；
   **hero 四块、趋势图、堆叠条、图例、面板 ②′ 与 ③ 都不跟着变** —— 它们的标题里带「全部窗口」，
   这是故意的（实测「全部」与「新增」在段间差 11–90 倍）。
4. **核对「● 新」**：切到「新增」视图，**每一行都应该带 `● 新`**；
   切回「全部」，带 `● 新` 的行数应该等于「新增」视图的行数。
5. 切 N 前先**展开 ③ 段并滚到页面中部**，切完 ③ 仍展开、位置仍在那一段附近。
6. **滚到面板 ②′（那不是 `<details>`）再切 N**：不报错、不跳回页面顶部。
7. **点堆叠条的每一段、图例的每一项**：跳到对应段并自动展开；
   **手动把那个段折叠回去，再点同一个图例项 —— 必须仍然展开**（同 hash 第二次点击不触发 `hashchange`，
   这条走的是 click 处理器）。
8. **键盘**：Tab 到「窗口」和「显示」两组按钮，左右方向键切换，焦点框可见。
9. **30 天视图下连续快速点 N 三次**，然后展开 ⑤ 段：行数应等于 summary 里的 cap2，
   **没有重复行、没有乱序**，且没有红条（这条打的是 rAF 世代号）。
10. **断网（飞行模式）后重新双击**：一切照常。

### 5.2 `latest.html#selfcheck`

在地址栏后面加 `#selfcheck` 回车（或直接双击后手动改 hash）。页面不渲染表格，
只在底部输出一个 `<pre>`，第一行应该是：

```
SELFCHECK ok (15 cells)
```

后面是 3 视图 × 5 档 N 的明细，每格 `"ok": true`。任何一格 `false` 时 `why` 会写明是哪一项。

### 5.3 想要一份冻结快照时

```bash
export PYTHONIOENCODING=utf-8
D:/Apps/Miniconda/envs/job-classifier/python.exe -u dashboard.py \
    --date 2026-08-20 --no-watermark --out D:/tmp/snap0820
```

那个目录是自包含的（`latest.html` + css + js + index + 全部日块），双击即可，
与 `logs/dashboard/` 不共享任何会被改写的文件。**不要**再去找 `logs/dashboard/2026-08-20.html`，
v2 不写历史页（A1：它会引用每天被重写的数据块，从而静默改判 1.9%–3.5% 的行）。

### 5.4 每天早上的例行确认

`run_daily_report.bat` 跑完后：`logs/dashboard/` 里 7 个文件的 mtime 都是本次运行，
`logs/dashboard/` 里**没有** `YYYY-MM-DD.html`，`data-*.js` 的天数 ≤ 30。

---

## 6. 复现命令

```bash
cd D:/OneDrive/work/school/project/Job
export PYTHONIOENCODING=utf-8
PY=D:/Apps/Miniconda/envs/job-classifier/python.exe

$PY tests/test_lane.py                                   # 58 tests, OK (skipped=2)
$PY -u dashboard.py --no-watermark                       # 写 logs/dashboard/
$PY -u dashboard.py --date 2026-08-20 --no-watermark --out /tmp/snap
git diff --stat daily_report.py company_lane.py          # 必须为空
grep -rn "logs/dashboard/<day>\|<day>.html" --include=*.py --include=*.md --include=*.bat . \
  | grep -v "^./dashboard_loop/" | grep -v "^./docs/req/"   # 必须无输出

# 无头自检
"C:/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --no-first-run --user-data-dir=<临时目录> --virtual-time-budget=30000 --dump-dom \
  "file:///D:/OneDrive/work/school/project/Job/logs/dashboard/latest.html#selfcheck"
```

`.bat` 验收（**会推进水位线，先备份**）：

```powershell
Copy-Item logs\last_report.json <备份>
$env:JOB_UNATTENDED="1"; cmd.exe /c ".\run_daily_report.bat"    # 退出码 0，无 Traceback
Copy-Item <备份> logs\last_report.json                          # 跑完恢复
```

---

## 7. Round 2 —— 按 PM 裁决（`pm_ruling_impl_v1.md` / 设计 v3.2）的两处小改

D1 / D2 / D3 全部被接受，绕开实现即最终形态，**未动一行**。9 处偏离 8 条 ratify、
第 7 条 ratify-with-amendment。本轮只改两处：

### 7.1 偏离 #7 —— 删旧 `YYYY-MM-DD.html` 只在默认输出目录做

`dashboard.py`：

```python
def write_bundle(out_dir, files, prune_html=False):
    ...
        elif prune_html and DAY_HTML_RE.match(fn):
    ...
    removed = write_bundle(out_dir, files, prune_html=(args.out is None))
```

`--out` 是调用者自己挑的路径，按「名字长得像日期」去删一个文件不可逆，而 §5 第 4 条只对
`logs/dashboard/` 提要求。`data-*.js` 的 `--retain` 清理**到处照做**（F26 依赖）。

新增 fixture `test_F26_out_never_deletes_a_file_the_user_put_there`：
往 `--out` 目录里预置 `2020-01-01.html` / `notes.html` / `2020-01-01.txt` 与一个过期的
`data-1999-12-31.js`，跑完之后**三个 .html/.txt 原封不动（内容也逐字比对）**，
而 `data-1999-12-31.js` 仍然被清掉 —— 两条规则各归各位。

默认目录那一支仍然有效（实测：手工放一个 `logs/dashboard/2026-08-18.html`，下一次运行打印
`removed 1 stale file(s): 2026-08-18.html`）。

### 7.2 偏离 #8 —— 让横幅「等明早 07:30」这句承诺自我看管

新增 fixture `test_F9_the_banner_promise_is_self_guarding`（**只加测试，生产代码未改**）。
断言的是**蕴含式**而不是那个 0：

> `health` 计入的公司**全部首见于 anchor 日** ⟹ 允许出现「等明早」；
> 只要有一家首见于更早的天，**页面里就不许出现「等明早」**（并在失败信息里点名是哪几家）。

理由与 PM 一致：一家在窗口里躺了三天还没富化的公司，已经错过两次 07:30 的富化了，
对它说「等明早」是错的。今天实测（anchor `2026-08-21`）：

```
anchor 2026-08-21   health.unenriched 98   fixture 独立重算 98
first-seen BEFORE anchor: 0   []
```

与 PM 裁决里的 98 / 0 逐字一致。fixture 同时交叉核对「自己数出来的那批公司数 == `health.unenriched`」，
所以口径一旦漂移也会红。

### 7.3 Round 2 复测

```
Ran 60 tests in 7.510s

OK (skipped=2)
```

（58 → 60：本轮两条新 fixture。跳过的仍是 F1/F2。）

```
$ python -u dashboard.py --no-watermark
  98 company/companies not yet enriched (they stay out of lane C)
  7 files, 3 day blocks, 0.38 MB
  removed 1 stale file(s): 2026-08-18.html          <- 默认目录那一支仍然有效

$ ls logs/dashboard/
dashboard.css  dashboard.js  data-2026-08-19.js  data-2026-08-20.js
data-2026-08-21.js  data-index.js  latest.html

$ diff logs/last_report.json dashboard_loop/v2/last_report.backup.json
IDENTICAL

Chrome 无头 latest.html#selfcheck :  SELFCHECK ok (15 cells)   all 15 ok: True

$ git diff --stat daily_report.py company_lane.py
(空)
```

### 7.4 `git status` 核对（回应协调者的问题）

本次工作产生的改动**只有**：

```
 M SCHEDULING.md          M dashboard.py          M tests/test_lane.py
?? view.py               ?? web/                 ?? dashboard_loop/v2/impl_v1_report.md
```

`git status --porcelain --untracked-files=all` 里其余条目都不是我产生的，逐项核对过：

| 条目 | 谁的 | 证据 |
|---|---|---|
| `M ats_registry.json` | 采集器 | mtime 03:09，早于我开工（约 04:00） |
| `M docs/multiagent_design_build_loop.md` | 框架文档 | mtime 02:38 |
| `?? .claude/agents/*.md` | 编排者 | 5 个 agent 定义 |
| `?? dashboard_loop/v2/` 里的其余文件 | PM / evaluator / QA / 编排者 | `_pm*` `_eval*` `design_v*` `qa_*` `pm_ruling_*` `state.json` 等；我只新增了 `impl_v1_report.md` |

**仓库根目录没有任何我产生的残留文件**（`-uall` 下根目录只有 `view.py` 一个新增项）；
协调者删掉的那个乱码文件名残留确认已不在。
