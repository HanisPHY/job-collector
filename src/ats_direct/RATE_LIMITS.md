# ATS 直连速率控制依据（2026-08-19 调研）

代码落实：`rate_limiter.py` 中的令牌桶（`PLATFORM_QPS`），每平台独立桶，阻塞式 `acquire()`，带随机抖动。

## 各平台证据与取值

| 平台 | 证据类型 | 已知上限 | 本项目取值 | 安全余量 |
|---|---|---|---|---|
| Greenhouse | **官方文档** ([developers.greenhouse.io](https://developers.greenhouse.io/harvest.html)) | 50 req/10s（=5 QPS），超限返 429 + `Retry-After` | **1.0 QPS** | 5x |
| Lever | **官方文档** ([github.com/lever/postings-api](https://github.com/lever/postings-api)) | 10 req/s 稳态，burst 20；文档注明"不保证" | **1.0 QPS** | 10x |
| SmartRecruiters | 公开匿名 API，无公开限流文档 | 未知 | **1.0 QPS** | 保守 |
| Ashby | 有文档的公开 posting-api，但未公布限流数字 | 未知 | **0.5 QPS** | 保守 |
| Workable | widget API（未文档化但稳定） | 未知 | **0.5 QPS** | 保守 |
| Workday | **非官方** CxS 端点，租户各自部署在 Akamai/CDN 后 | 未知，社区经验：低频无碍 | **0.4 QPS** | 最保守 |
| JazzHR/BambooHR/Jobvite | 普通网页抓取 | — | **0.5 QPS** | 礼貌抓取 |

## 设计原则

1. **每平台独立桶**：对 Greenhouse 的请求不占用 Lever 的配额，总吞吐仍然可控（典型一轮 60 家公司 ≈ 70 个请求，2～3 分钟）。
2. **无并发**：单线程顺序请求。任务本身不是延迟敏感的，没必要并发去逼近限流线。
3. **429 处理**：collector 捕获 429 计入 `rate_limit_hits` 指标（测试标准要求该值 = 0）。若未来出现 429，应先降 QPS 而不是加重试。
4. **描述按需拉取**：SmartRecruiters/Workday 的列表接口不含 JD，只对**通过 NG 过滤的岗位**（每公司 0～10 个）发详情请求，请求数比全量拉取低 1～2 个数量级。

## 实测记录（2026-08-19）

- 9 家预解析公司冒烟测试：11 个请求，13.0s，**0 个 429**，3148 岗位入手。
- 与预算一致：greenhouse 5 req @1QPS + lever 2 @1QPS + ashby 1 @0.5 + workday 2 @0.4 ≈ 13s。
