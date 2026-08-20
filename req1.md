# 日报重构 + HTML Dashboard —— 交接文档

> 目的：把 markdown 日报的现状、「分析/渲染切开」的重构方案、以及 HTML dashboard 的设计
> 收在一处，方便在新对话里直接作为 context 提供。
>
> 状态：**日志系统和 markdown 日报已完成并在运行**；本文档描述的重构和 HTML dashboard
> **尚未实施**。文档写于 2026-08-20。

---

## 0. 项目背景（新对话必读）

Windows 11 上的求职岗位采集项目，根目录 `D:\OneDrive\work\school\project\Job`，
conda 环境 `job-classifier`。三条采集路径，各写各的 CSV：

| 采集器 | 入口 | 输出 CSV | 说明 |
|---|---|---|---|
| newgrad (LinkedIn) | `main.py` × 9 个 query | `newgrad_classifications.csv` | 经 JobSpy 抓 LinkedIn，**量大噪音多**，唯一会调 LLM 的路径 |
| ats_direct | `ats_direct.py` | `ats_jobs.csv` | 直连公司 ATS API（Greenhouse/Lever/Ashby…），**高信号** |
| ddg_search | `ddg_search.py` | `ddg_jobs.csv` | DuckDuckGo X-ray，主要用于发现新的公司 board |

**日志系统（已完成）**：Task Scheduler 的 12 个任务全部指向 `run_logged.bat <collector>`，
由它捕获输出到 `logs/<script>/<时间戳>.log`，并往 `logs/runs.jsonl` 写 `run_start` /
`run_end`；Python 入口通过 `run_log.py`（55 行，只有 `run_summary()`）写 `run_summary`。
详见 `SCHEDULING.md`。

---

## 1. markdown 日报现在是怎么生成的

`daily_report.py`（662 行）。三段式：**读取 → 分析 → 渲染**。

```
main()
 ├─ load_runs()                  logs/runs.jsonl → list[dict] (+ bad_lines)
 ├─ group_runs(records, day)     按 run_id 聚成 {start, end, summaries, script, log}
 ├─ load_jobs(day)               3 个 CSV，按 date_recorded[:10] 筛当天 → {source: rows}
 ├─ dedup(rows_by_source)        按 unique_id 跨源去重（ddg 和 ats 真的会重叠）
 ├─ collect_llm_usage()          汇总 llm_cost_usd / llm_api_calls / llm_tokens
 ├─ build_alerts(...)      →  list[str]     ← markdown 已烤进字符串
 ├─ render(...)
 │    ├─ render_todo(...)  →  list[str]     ← 同上
 │    └─ render_runs(...)  →  list[str]     ← 同上
 └─ 写 logs/daily/<day>.md + 控制台摘要 + prune_logs()
```

### 关键函数（当前行号）

| 行 | 函数 | 作用 |
|---|---|---|
| 87 | `load_runs()` | 解析 runs.jsonl，容忍尾部半行 |
| 104 | `day_of(value)` | 前 10 字符严格匹配 `YYYY-MM-DD`，否则 None |
| 117 | `load_jobs(day)` | 只读当天。**加趋势图需要改成一次读全部再按天分桶** |
| 143 | `dedup()` | 跨源 unique_id 去重 |
| 169 | `group_runs()` | 按 run_id 分组，wrapper 的 id 是 `YYYY-MM-DD_HH-MM-SS`，手动跑是 `manual-*` |
| 211 | `run_status()` | ok / failed / crashed(有 start 无 end) / unknown |
| 228 | `tracked_summaries()` | 只保留 output 落在 SOURCES 里的 summary（排除 smoke test） |
| 255 | `llm_usage()` | 聚合花费；`runs` 字段单独计数以兼容没有 `llm_api_calls` 的旧记录 |
| 292 | `build_alerts()` | 所有告警规则 |
| 428 | `render_todo()` | 第 1 节 |
| 490 | `render_runs()` | 第 3 节 |
| 552 | `render()` | 拼三节 |

### 配置常量（39-80 行）

```python
LOG_RETENTION_DAYS = 30
SELF_SCRIPT = "run_daily_report"        # 报告排除自己，否则永远自报 crashed
EXPECTED_SCRIPTS = {run_newgrad_collector, run_ats_collector, run_ddg_collector}
SOURCES = {csv 文件名 -> 来源标签}
SPONSORSHIP_MEANINGFUL_SOURCES = {"ats_direct"}
BIG_TECH_MARKER = "Big Tech"
ATS_HTTP_ERROR_THRESHOLD = 20
ATS_RATE_LIMIT_THRESHOLD = 1
LLM_DAILY_COST_ALERT_USD = 0.50
```

### 数据来源的可靠性约定

- **岗位数只信 CSV 的 `date_recorded`**，不解析日志。该列是「首次收录时间」，
  CSV 重写时逐字保留（已核实全链路）。
- **`.log` 文件从不被程序读取**，只在报告里给路径。
- `runs.jsonl` 是唯一被解析的结构化源。

---

## 2. 重构：把分析和渲染切开

### 为什么必须先做

markdown 语法**烤进了分析层**，没有中间的结构化表示：

```python
# build_alerts 第 392 行附近
alerts.append(f"**{script}** ran {count} time(s), expected at least ...")
#              ^^ markdown 加粗写死在告警文本里

# render_todo 第 461 行附近
lines.append(f"### {company}{tag} — {len(jobs)}")
lines.append(f"- [{title}]({link})  \n  <sub>{meta}</sub>")
```

直接加 `render_html()` 的话，它无法复用 `build_alerts()` 的输出（里面全是 `**`），
只能把格式化逻辑再抄一份 → 两份逻辑必然分叉。

### 目标结构

```
collect_report(day)  →  纯数据 dict（不含任何格式）
                        ├─ render_markdown(data)  →  .md    （视觉保持不变）
                        └─ render_html(data)      →  .html  （新增）
```

### 具体改动（约 150 行，机械为主）

1. **`build_alerts()` 返回结构化 dict**，不返回字符串：
   ```python
   {"level": "critical|warning|info", "title": str, "detail": str, "log": str|None}
   ```
   markdown 渲染器拼 `**{title}** {detail}`；HTML 渲染器做成带状态色的卡片。

2. **抽出 `collect_report(day)`**，把现在散在 `main()` 里的加载/去重/聚合收进去，
   返回：
   ```python
   {day, rows, rows_by_source, duplicates, yesterday_count, trend,
    llm, yesterday_llm, runs_today, alerts, unparseable, bad_lines}
   ```

3. **`render_todo` / `render_runs` 里的字符串拼接搬进 `render_markdown`**，
   分析部分（分组、排序、过滤）留在 collect 层。

4. **`load_jobs` 改成一次读全部**，返回 `{day: rows}`，今天/昨天/趋势都从这一次
   读取里取。三个 CSV 合计约 1200 行，开销可忽略。

5. **CLI**：`--format md|html|both`，默认 `both`。

---

## 3. HTML Dashboard 设计

### 设计过程中被数据推翻的两个假设

这部分很重要，新对话不要重蹈覆辙。

#### ❌ 假设一：「按公司统计岗位数」是个有用的面板

实测 2026-08-20 当天 937 条去重后：

```
542 家公司，其中 402 家（74%）只有 1 个岗位
分布： 1个:402  2个:81  3个:28  4个:9  5+:22
```

而且按量排序排出来的是**垃圾**：

```
BeaconFire Inc. 39（IT 外包）   Jack & Jill 34（聚合站）   Deloitte 27
Booz Allen 16   Surge Software 15   Jobright.ai 11（聚合站）   TCS 11（外包）
```

「岗位数最多的公司」= 「刷屏最凶的中介」。做成图表是主动误导。**已砍掉。**

#### ❌ 假设二：「ATS 今天塌方了，被总量掩盖」

查 `runs.jsonl` 里 ATS 当天的三次运行：

```
03:10  fetched=41060  matched=186  new=0
06:10  fetched=41421  matched=187  new=1
09:11  fetched=41456  matched=187  new=0
```

**ATS 完全健康。** 8/19 的 179 条是首次全量收割，之后每次 0-1 新增才是正常稳态
（`run_ats_collector.bat` 的注释也写了 "ATS boards change slowly"）。

由此得出的**核心设计原则**：

| 指标 | 衡量 | 稳态 | 能否当健康信号 |
|---|---|---|---|
| `jobs_new` | 新鲜度（今天有什么可投） | 自然趋近 0 | ❌ **不能**，归零是正常的 |
| `jobs_matched` | 覆盖度（还看得见多少） | 稳定 186-187 | ✅ 能，掉下来才是故障 |
| `companies_ok` / `http_errors` | 抓取可达性 | 稳定 | ✅ 能 |

**健康告警必须挂在覆盖度上，绝不能用 `jobs_new`。**
按新增量做「跌幅告警」会每天误报一次 —— 任何来源的第一天都是全量回填。

现有 `build_alerts()` 里的「全天 0 新增」规则也要相应改成按来源 + 按覆盖度判断。

#### ⚠️ 另一个已知问题：`company_type` 不适合当 KPI

当天 397 条被标为 `独角兽/上市公司/Big Tech`，来自 **239 家不同公司**，抽样包含：

```
Boyd Gaming   Stormont Vail Health   Life Time Inc.   Farm Bureau
Robert Half   AAA Global   Johnson Controls   Toyota North America
```

字段名是「独角兽/上市公司/Big Tech」，Boyd Gaming 确实是上市公司，标签没说谎 ——
但它覆盖 **42% 的岗位，不具区分度**。当前 markdown 日报里的「🏆 Big Tech 置顶」
比原本以为的要弱，dashboard 里不要给它独立 KPI 卡，降级为表格里的一个标注列。

### 中介识别：能做什么、不能做什么

**不能**：光靠数量自动打「中介」标签。ATS 直连里 Palantir 发 18 个、SpaceX 发 9 个，
Deloitte 两天稳定 25-27 —— 都是真实雇主。误伤比没有这个面板更糟。

**能**：把三个判别信号摆出来让人判断。

1. **标题带 ` at X`（转贴特征）** —— 全库 34 条，**100% 来自 Jack & Jill**：
   ```
   Forward Deployed Engineer at CommodityAI
   Product Engineer ($150k-$190k + Equity) at River
   ```
   一家公司把别家岗位挂自己名下 = 聚合站/猎头平台。signature 很干净。

2. **来源** —— ATS 直连 = 这家公司有自己的 Greenhouse/Lever board = **必定真实雇主**。
   中介问题只存在于 LinkedIn 那条线。

3. **跨天持续性** —— BeaconFire(39)、Jack & Jill(34) 只在 8/20 出现 = 突发；
   Deloitte 两天都 25-27 = 常态雇主。

### 高频发帖方占比（实测，两天很稳定）

```
8/19   >=3/天: 21家 133条 46%    >=5/天: 11家 101条 35%    >=10/天: 3家 53条 18%
8/20   >=3/天: 59家 373条 40%    >=5/天: 22家 253条 27%    >=10/天: 8家 166条 18%
```

**约 40% 的日产出来自不到 5% 的公司。** 这个比例本身就是值得盯的指标 ——
它上涨说明刷屏在加剧。

### 面板清单

| # | 面板 | 形式 | 说明 |
|---|---|---|---|
| ① | **今日可投**（未投递 + 已过滤噪音） | Hero 数字 + 迷你趋势 | 数字小是对的 |
| ② | **今日漏斗** 总量 → 高频发帖方 → 长尾 → 可投 | 横向堆叠条 | 部分-整体，3 类用调色板 1-3 槽 |
| ③ | **14 天趋势，按来源堆叠** | 堆叠柱 | 看构成变化，**不拿它判断塌方** |
| ④ | **采集器健康** | 状态列表（图标+文字+状态色） | 以 `matched` / `companies_ok` 为准；`new=0` 显示为正常不是红色 |
| ⑤ | **中介 / 高频发帖方** | 占比趋势 + 明细表 | 见下 |
| ⑥ | **告警 + LLM 花费** | 状态卡片 | 告警规则同步改成按覆盖度 |

**砍掉**：各公司岗位数（542 行）、sponsorship 分布（当天 100% 单一值，画出来是直线）、
Big Tech 独立 KPI 卡。

### 面板 ⑤ 明细表（不自动打标签，只摆证据）

| 公司 | 今日 | 近 7 天 | 来源 | 转贴 | 状态 |
|---|---|---|---|---|---|
| BeaconFire Inc. | 39 | 39 | LinkedIn | — | 🔺 突发 |
| Jack & Jill | 34 | 34 | LinkedIn | **34 条带 "at X"** | 🔺 突发 |
| Deloitte | 27 | 52 | LinkedIn | — | 持续 |
| Palantir | 0 | 18 | **ATS 直连** | — | 真实雇主 |
| SpaceX | 6 | 15 | **ATS 直连** | — | 真实雇主 |

每行一个勾选框 → 生成可粘贴的 `noise_companies.txt` 内容。**判断权在人，dashboard 只给证据。**

### 可视化实现约定

遵循 dataviz 方法（先定形式 → 再定颜色 → **跑校验脚本**，不靠眼睛判断色盲可辨性）：

- **形式**：头条数字用 stat tile / hero，不用单柱柱状图；>7 个类别用表格不用饼图；
  时间趋势用线/面积；部分-整体用堆叠条。
- **颜色**：三个来源用参考调色板槽位 1-3（蓝 `#2a78d6` / 橙 `#eb6834` / 青 `#1baf7a`，
  全配对校验通过）；趋势用单一蓝色顺序色阶；运行状态用独立 status 色，
  且**永远配图标+文字，不能只靠颜色表意**。
- **技术**：纯内联 SVG + 内联 CSS，**零外部依赖**（文件在 OneDrive 里，离线也要能开；
  不引 CDN 的 Chart.js）。悬停用 SVG `<title>` 拿浏览器原生提示，零 JS。
- **深色模式**：支持 `prefers-color-scheme`。
- 实现前跑 `scripts/validate_palette.js` 确认配色。

### 待定项

1. 趋势窗口 14 天还是 30 天（只是个常量）
2. 日报任务跑完**不自动打开浏览器**（定时任务弹浏览器很烦），需要的话在
   `run_daily_report.bat` 里加一行 `start`
3. `noise_companies.txt` 过滤逻辑建议和 dashboard 一起做 —— 没有它，
   面板 ① 的「今日可投」还是 937 条，Hero 数字没意义

---

## 4. 当前数据规模（2026-08-20 快照）

```
newgrad_classifications.csv   8/19: 101   8/20: 936
ats_jobs.csv                  8/19: 179   8/20:   1
ddg_jobs.csv                  8/19:  17   8/20:   1
去重后合计                     8/19: 297   8/20: 937   （ats/ddg 交集 10 条）

applied 列：全库 100% 为空，尚未被使用过
sponsorship：只有 ats_direct 真正做分类（8/19: Sponsor 85 / Not 94）；
             newgrad 和 ddg 全部是 "Not (Maybe Not) Sponsor"，含义是**未知**不是否定
LLM 花费：8/20 全天 $0.0265，模型 gpt-3.5-turbo，只有 LinkedIn 路径会调用
```

趋势图初期只有 2 天数据，14 天的坑位大部分是空的 —— 不影响实现。
