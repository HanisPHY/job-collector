# DuckDuckGo 搜索速率控制依据（2026-08-19 调研 + 本机实测）

代码落实：`ddg_client.py` 的 `MIN_INTERVAL_S / JITTER_S / BACKOFF_S / MAX_QUERIES_PER_RUN` 四个常量，间隔控制 + 指数退避 + 每轮硬上限。

## 证据

### 1. 本机实测（最直接证据，2026-08-19，住宅 IP）

```
请求 1: html.duckduckgo.com/html/?q=site:applytojob.com ...   → HTTP 200，正常结果
（间隔 4 秒）
请求 2: html.duckduckgo.com/html/?q=site:bamboohr.com ...     → HTTP 202（JS challenge）
```

**间隔 4 秒、第 2 个请求就被挑战**。DDG 的风控远比"每秒几个"严格，它看的是行为模式而非瞬时速率。

### 2. 社区经验

- `ddgs`（原 duckduckgo_search）库的 issue tracker 长期存在 RateLimitException 报告；crewAI 等下游项目专门为此写了 workaround（[crewAI#136](https://github.com/crewAIInc/crewAI/issues/136)）。
- 社区共识：无代理情况下持续抓取需要 **15～30 秒以上**的间隔，且总量要低；密集使用需要轮换代理（本项目不做——用户场景不需要，也不该做）。
- DDG 无公开的官方自动化接口和限流文档；HTML 端点的容忍度是纯经验值。

## 取值（写死在 ddg_client.py）

| 参数 | 值 | 依据 |
|---|---|---|
| `MIN_INTERVAL_S` | 20s | 实测 4s 必挑战 → 5 倍以上放大 |
| `JITTER_S` | +0~8s | 打破节拍器式规律（定时任务特征） |
| `BACKOFF_S` | 60s → 150s，之后放弃本轮 | 挑战后指数退避；持续挑战说明 IP 已被标记，继续打只会加重 |
| `MAX_QUERIES_PER_RUN` | 10（默认只用 5） | 每轮 5 query ≈ 2 分钟、5 个请求，远低于风控阈值 |

**等效 QPS ≈ 0.04（每 25 秒 1 个请求）**。

## 调度建议

- **不要**每小时跑（与 ats_direct 不同）。建议每天 2～3 次。
- query 集合通过 `ddg_state.json` 的游标轮转，多次运行自动覆盖不同的「平台 × 关键词」组合，单轮量小但累计覆盖完整。
- 若连续多轮全部被挑战：说明 IP 已进黑名单，停 24 小时再试，**不要**降低间隔重试或加代理硬闯。
