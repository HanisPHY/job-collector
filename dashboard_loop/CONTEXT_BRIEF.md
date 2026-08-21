# 共享 CONTEXT BRIEF —— dashboard 设计 loop
> 所有 subagent 必读。这里的数字都是编排者在 2026-08-20 实测出来的，不要凭空推翻，
> 要推翻请自己跑脚本验证后再说。

## 环境
- 仓库根目录：`D:\OneDrive\work\school\project\Job`
- Python：`D:/Apps/Miniconda/envs/job-classifier/python.exe`（有 pandas 2.3.3）
- Bash 里跑脚本前先 `export PYTHONIOENCODING=utf-8`，否则中文列值输出会 UnicodeEncodeError
- 约束：**零外部依赖**（文件在 OneDrive，离线要能打开，不引 CDN），纯内联 SVG + 内联 CSS
- `req1.md` 是上一轮的交接文档，包含日报现状 / 重构方案 / 已被数据推翻的假设，必读

## 用户的两个需求（原文）
1. dashboard 能清楚看到每天的岗位变化。把刷屏中介单独摆开（IT 外包/培训、聚合站、外包），
   **但不能排除掉岗位多的正常公司**。
2. 一天抓太多岗位看不过来。**要把大中公司的岗位排在前面先看到**。
   「大中公司」可能有多个维度：知名度、赚钱能力、声誉、公司人数。
   如果 dashboard 解决不了，就设计另一种方式解决。

## 数据现状（实测）

三个 CSV，跨源按 `unique_id` 去重后共 **1247 条 / 678 家公司**：

| 文件 | 行数 | 公司数 | 8/19 | 8/20 | 性质 |
|---|---|---|---|---|---|
| newgrad_classifications.csv | 1060 | 594 | 101 | 959 | LinkedIn，量大噪音多，唯一走 LLM |
| ats_jobs.csv | 180 | 90 | 179 | 1 | 直连公司 ATS，**高信号，必定真实雇主** |
| ddg_jobs.csv | 18 | 14 | 17 | 1 | DDG X-ray，用于发现新 board |

列：`unique_id, job_title, job_link, company_name, sponsorship_status, company_type,
date_posted, date_recorded, category, applied`（ats/ddg 多 `source, platform, location`）

### 已知的坏字段
- `company_type` 只有两个值：`Others`(775) / `独角兽/上市公司/Big Tech`(483)。
  后者占 **39%**，里面混了 Boyd Gaming、Stormont Vail Health、Robert Half、AAA Global。
  **没有区分度，不能直接当「大公司」信号。**
- `category` = sponsorship + company_type 的拼接，同样无区分度（只有 2 个值）。
- `sponsorship_status`：只有 ats_direct 真做了分类；newgrad/ddg 全是
  "Not (Maybe Not) Sponsor"，含义是**未知**不是否定。
- `applied` 列全库 100% 为空，从没被用过。

### 公司岗位数分布（长尾）
```
678 家公司；1 个岗位的 435 家，2 个 93，3 个 31，4 个 10，5 个 6，6+ 约 20 家
```
按数量排序的 top（这是「刷屏排行」不是「好公司排行」）：
```
52 Deloitte        39 BeaconFire Inc.(IT外包)  34 Jack & Jill(聚合站)  18 Palantir
17 SpaceX          16 Booz Allen Hamilton      15 Surge Software       13 Haystack
11 TCS(外包)       11 Jobright.ai(聚合站)      11 Infosys(外包)        10 Power Home Remodeling
10 Appian          8 RemoteHunter              8 Yara AI               8 Amazon
```
**注意 Palantir 18 / SpaceX 17 / Deloitte 52 都是真实雇主。纯按量打「中介」标签必然误伤。**

### 中介的可用信号（实测）
1. 标题含 ` at X` 转贴特征：全库 **29 条，100% 来自 Jack & Jill**。signature 干净但覆盖极窄。
2. 来源：ATS 直连 = 这家公司有自己的 Greenhouse/Lever board = 必定真实雇主。
   中介问题只存在于 LinkedIn 那一条线。
3. 跨天持续性：BeaconFire / Jack & Jill 只在 8/20 出现（突发）；Deloitte 两天都 25-27（常态）。
4. 高频发帖方占比很稳：8/19 >=3/天的 21 家占 46%；8/20 >=3/天的 59 家占 40%。

### ★ 现有公司参考名单严重不足（这是本 loop 最关键的一条）
仓库里有三份离线名单：
- `unicorn_companies.csv`（1085 行）—— **被污染**：TCS、Infosys、Cisco、Capgemini、
  Handshake、Twitch 都在里面，它不是真的独角兽名单，是个混杂表
- `fortune_500_companies.csv`（**只有 72 行**，名字就骗人）
- `company_database_cache.json`（1147 条小写公司名，来源同上两者）

实测精确名匹配的覆盖率：
```
678 家公司里只有 60 家能被任一名单命中（8.8%）
1247 条岗位里只有 163 条被覆盖（13%）
命中的：Palantir, TCS, Infosys, Amazon, Capgemini, Twitch, Cisco, Handshake ...
没命中的真大厂：Deloitte, SpaceX, Booz Allen Hamilton, Leidos, Micron Technology,
                NetApp, L3Harris, Anduril, Accenture Federal Services, Anthropic...
```
**结论：任何「查名单给公司打分」的方案，在现有名单上有 87% 的岗位无分可打。
设计方案必须正面回答这个覆盖率问题**（扩名单？换信号？分层降级？），不能假装它不存在。

## 日报现状
`daily_report.py`（662 行，25907 字节）三段式 读取→分析→渲染，markdown 语法烤进了分析层
（`build_alerts()` 返回带 `**` 的字符串）。req1.md 第 2 节有一份「把分析和渲染切开」的
重构方案：`collect_report(day)` 返回纯数据 → `render_markdown` / `render_html`。
关键函数行号见 req1.md 第 47 行的表。

日志：`logs/runs.jsonl` 是唯一被解析的结构化源；`logs/daily/<day>.md` 是已生成的日报。
岗位数只信 CSV 的 `date_recorded`，不解析 .log。

## 已被数据推翻、不要重蹈覆辙的假设
1. ❌「按公司统计岗位数做面板」→ 排出来的是刷屏排行榜，主动误导。
2. ❌「ATS 今天塌方了」→ ATS 完全健康。`jobs_new` 自然趋近 0，**绝不能拿它当健康信号**；
   健康告警必须挂在覆盖度 `jobs_matched` / `companies_ok` 上。
3. ⚠️ `company_type` 不适合当 KPI，降级为表格里的一个标注列。
