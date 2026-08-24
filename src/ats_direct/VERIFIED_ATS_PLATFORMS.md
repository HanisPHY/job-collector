# ATS 平台直连验证报告（2026-08-19 实测）

背景：最初的 10 平台清单来自一张 LinkedIn 帖子截图。逐一实测后发现**原帖多处域名错误**，且各平台可直连性差异巨大。下表为经过真实 HTTP 请求验证的准确对照。

## ✅ 一级：结构化 JSON API，完全可直连（6 个）

| 平台 | 端点（原帖写法 → 实测正确写法） | 认证 | 验证方式 |
|---|---|---|---|
| **Greenhouse** | `boards.greenhouse.io` → **`boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`** | 无需 | stripe/databricks/anthropic 等 200 + 全量 JD |
| **Lever** | `lever.co` → **`api.lever.co/v0/postings/{slug}?mode=json`** | 无需 | palantir 309 岗 + JD 全文 |
| **Ashby** | （原帖没有）→ **`api.ashbyhq.com/posting-api/job-board/{slug}`**（官方文档化 API） | 无需 | openai 734 岗 |
| **SmartRecruiters** | → **`api.smartrecruiters.com/v1/companies/{slug}/postings`** | 无需 | Visa/ServiceNow 200。⚠️ 陷阱：任意 slug 都返回 200+`totalFound:0`，probe 必须要求 `>0` |
| **Workable** | `workable.com` → **`apply.workable.com/api/v1/widget/accounts/{slug}?details=true`** | 无需 | monzo 200（合法空板） |
| **Workday** | （原帖没有）→ **`{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`**（POST JSON） | 无需 | nvidia 实测直接返回 "New College Grad 2026" 岗位。⚠️ tenant/wd 编号/site 名无法自动探测，需手工配置 |

## ⚠️ 二级：模式存在但租户难发现（3 个）

| 平台 | 实测正确模式 | 状态 |
|---|---|---|
| **JazzHR** | 原帖 `apply.jazz.co` **错误** → 实际 **`{tenant}.applytojob.com/apply/`**（HTML 可解析） | 已实现 provider；活租户实测通过（brightvisiontechnologies）；无效租户 302 到 jazzhr.com 营销页（probe 以此判别） |
| **BambooHR** | 原帖 `jobs.bamboohr.com` **错误** → 实际 **`{tenant}.bamboohr.com/careers/list`**（JSON） | 已实现 provider；未找到活租户样本验证数据流（SMB 平台，靠 DDG 发现补充） |
| **Jobvite** | `jobs.jobvite.com/{tenant}` | 测试的历史租户全部 302 到 jobvite.com（客户大量迁移）；**未实现**，价值低 |

## ❌ 三级：不可直连（1 个）

| 平台 | 原因 |
|---|---|
| **iCIMS** | 每租户子域名不可预测（`careers-{x}.icims.com` / `{x}.icims.com` 混用），页面重 JS 渲染，无公开列表 API。实测 meijer/sedgwick 均 404。**不实现**——用其的大厂（多为传统企业）从其他渠道覆盖 |

## 对原帖的修正总结

1. 原帖 4/10 域名不准确（JazzHR、BambooHR、Workable 给的是营销域而非租户域；Greenhouse 给的是页面域而非 API 域）
2. 原帖遗漏了两个**质量最高**的入口：Ashby 官方 posting-api、Workday CxS API
3. 原帖把 iCIMS 列为可搜索平台，实际上 X-ray 搜索能搜到它的页面，但**程序化直连不可行**
4. 各平台覆盖能力实测（本项目 217 家公司注册表）：Greenhouse ≈ 41%，Ashby ≈ 28%，Lever ≈ 15%，SmartRecruiters ≈ 9%，Workable ≈ 7%，其余长尾
