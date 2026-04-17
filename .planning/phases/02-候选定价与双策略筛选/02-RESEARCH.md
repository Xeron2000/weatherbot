# Phase 2: 候选定价与双策略筛选 - Research

**Researched:** 2026-04-17
**Domain:** Polymarket 天气市场 band probability、双策略候选筛选、CLOB 可执行盘口评估
**Confidence:** MEDIUM

## User Constraints

### Locked Decisions
无单独 `02-CONTEXT.md`；本 phase 目前没有 discuss-phase 锁定决策可抄录。[VERIFIED: `init phase-op 2` 返回 `has_context=false`]

### the agent's Discretion
本 research 需要在不违背项目总约束的前提下，自主推荐 Phase 2 的候选定价、盘口接线、双策略配置和可观测性方案。[VERIFIED: `.planning/ROADMAP.md`; VERIFIED: `.planning/REQUIREMENTS.md`]

### Deferred Ideas (OUT OF SCOPE)
真实下单、订单恢复、paper fill realism、组合级暴露控制都不在本 phase 交付范围内。[VERIFIED: `.planning/ROADMAP.md` 中 Phase 3-6 目标与依赖]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MKT-04 | 操作者可以让机器人基于当前可执行盘口信息（bid/ask、tick size、市场状态）评估是否值得挂单 | 使用 Gamma 做 discovery、CLOB token-level `/book` `/price` `/spread` `/tick-size` 做 execution snapshot；拒绝继续使用 Gamma `outcomePrices` 当执行真相。[CITED: https://docs.polymarket.com/api-reference/introduction][CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][CITED: https://docs.polymarket.com/api-reference/market-data/get-tick-size][VERIFIED: live Gamma+CLOB query 2026-04-17] |
| STRAT-01 | 操作者可以让机器人根据多源天气预测为每个温区计算 band probability，而不是只看单点温度预测 | 为每个 bucket 持久化 `per_source_probability` 与 `aggregate_probability`；停止当前“命中 bucket=1，否则=0”的逻辑。[VERIFIED: `bot_v2.py:264-271`; ASSUMED] |
| STRAT-02 | 操作者可以为低价 YES 策略配置独立的价格、概率、时间窗与仓位阈值 | 在 `config.json` 拆出 `yes_strategy.*` 配置块，并单独输出 YES 候选结果与拒绝原因。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED] |
| STRAT-03 | 操作者可以为高价 NO 策略配置独立的价格、概率、时间窗与仓位阈值 | 在 `config.json` 拆出 `no_strategy.*` 配置块，并基于 NO token 的可执行报价单独筛选。[VERIFIED: `.planning/REQUIREMENTS.md`; CITED: https://docs.polymarket.com/api-reference/markets/get-market-by-id][VERIFIED: live Gamma weather event includes YES/NO token ids] |
| RISK-03 | 操作者可以要求机器人在缺少关键市场元数据、规则映射或实时行情时自动停单 | 把 `missing_quote_book`、`tick_size_missing`、`market_closed`、`orderbook_empty` 等 reason code 加入 Phase 2 gate。[VERIFIED: `bot_v2.py:966-974`; CITED: https://docs.polymarket.com/market-data/websocket/market-channel][ASSUMED] |
| OBS-01 | 操作者可以查看每个候选机会为何被接受、拒绝、缩量或降价 | 持久化 `candidate_assessments[]`，每条候选包含 `reasons[]`、`quote_context`、`strategy_leg`、`size_adjustments`。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED] |
</phase_requirements>

## Summary

Phase 2 的规划重点不是“再找一个更聪明的温度点预测”，而是把 Phase 1 已经落地的市场语义快照，升级成**可执行候选评估**。[VERIFIED: `.planning/phases/01-市场语义与扫描基线/01-VERIFICATION.md`; VERIFIED: `bot_v2.py:943-1011`] 官方文档把职责分得很清楚：Gamma API 负责事件/市场发现与元数据，CLOB API 负责 orderbook、价格、spread、midpoint、tick size 等执行面数据；交易端才需要认证。[CITED: https://docs.polymarket.com/api-reference/introduction][CITED: https://docs.polymarket.com/developers/gamma-markets-api/overview]

因此，Phase 2 的主设计应是：**Gamma 只做 discovery，CLOB token-level 数据做 execution snapshot，候选引擎同时跑低价 YES 和高价 NO 两条策略腿，并把 accept / reject / size-down / reprice 的原因结构化持久化。**[CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][CITED: https://docs.polymarket.com/api-reference/market-data/get-spread][CITED: https://docs.polymarket.com/api-reference/market-data/get-tick-size][VERIFIED: live Gamma+CLOB query 2026-04-17][ASSUMED]

当前代码离这个目标还有三个关键缺口：一是 `bucket_prob()` 仍然对中间 bucket 返回 0/1，而不是概率质量；二是当前入场仍用 Gamma market 级 `bestAsk` / `bestBid`，没有切到 token-level CLOB book；三是 YES/NO 两条策略腿还共用一组全局阈值，无法满足 STRAT-02 / STRAT-03。[VERIFIED: `bot_v2.py:264-290`; VERIFIED: `bot_v2.py:1142-1206`; VERIFIED: `config.json:1-13`]

**Primary recommendation:** 保持 `bot_v2.py` + 本地 JSON 的 brownfield 形态，本 phase 只新增“bucket probability 表 + token-level quote snapshot + YES/NO 双策略配置 + candidate_assessments reason codes”，不要提前做订单状态机或持久化重构。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`; VERIFIED: `.planning/ROADMAP.md`]

## Project Constraints (from AGENTS.md)

- 必须在现有 `weatherbot` 代码库上演进，不重写项目。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`]
- v1 只做模拟交易，不引入真实资金风险。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`]
- 仅覆盖 Polymarket 天气温度市场，不扩到其他市场类型。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`]
- 交付目标优先“自动扫描 + 挂单”闭环，本 phase 只负责候选与定价，不提前实现后续真钱或恢复逻辑。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`; VERIFIED: `.planning/ROADMAP.md`]
- 运行时继续使用 Python CLI + 本地 JSON 持久化；本 phase 不应顺手引入数据库或大规模架构迁移。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`]
- 代码改动必须遵循现有文件本地风格、只改与 phase 直接相关的代码，避免无关重构。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`]
- Phase 2 规划应优先在 `bot_v2.py` 和 `tests/` 上做手术式增量，而不是提前拆包。[VERIFIED: `.planning/STATE.md`; VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`]

## Standard Stack

### Core

| Library / Service | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.3（当前环境） | Phase 2 运行时。[VERIFIED: `python3 --version`] | 与现有脚本和测试基座完全兼容；本 phase 无需为了候选评估改运行时。[VERIFIED: `python3 --version`; VERIFIED: `bot_v2.py`] |
| `requests` | 2.33.1（当前环境） | 继续发起 Gamma 与 CLOB 公共读请求。[VERIFIED: `python3 -m pip show requests`] | 当前仓库已广泛使用 `requests`；在 brownfield Phase 2 里继续沿用是最小改动路径。[VERIFIED: `bot_v2.py`; VERIFIED: `python3 -m pip show requests`] |
| Gamma API | public REST | 事件/市场发现、`conditionId`、`clobTokenIds`、`enableOrderBook`、`outcomePrices` 元数据。[CITED: https://docs.polymarket.com/developers/gamma-markets-api/overview] | 官方把 Gamma 定义为 market discovery 层，而不是执行盘口层。[CITED: https://docs.polymarket.com/api-reference/introduction] |
| CLOB API | public REST | token-level `/book`、`/price`、`/spread`、`/midpoint`、`/tick-size` execution snapshot。[CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][CITED: https://docs.polymarket.com/api-reference/market-data/get-market-price][CITED: https://docs.polymarket.com/api-reference/market-data/get-spread][CITED: https://docs.polymarket.com/api-reference/market-data/get-tick-size] | Phase 2 的“值不值得挂单”必须基于 token-level 可执行盘口，而不是 Gamma 的 convenience price 字段。[CITED: https://docs.polymarket.com/api-reference/introduction][VERIFIED: live Gamma+CLOB query 2026-04-17] |

### Supporting

| Library / Service | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `py-clob-client` | 0.34.6（latest available） | 官方 Python SDK；后续可接管 CLOB 读写、认证与签名。[VERIFIED: `python3 -m pip index versions py-clob-client`] | 本 phase 可选；若 planner 想提前统一 CLOB 访问层可引入，否则保留到 Phase 4 也可。[CITED: https://docs.polymarket.com/api-reference/clients-sdks][ASSUMED] |
| pytest | 9.0.2 | 现有自动化验证框架。[VERIFIED: `pytest --version`; VERIFIED: `tests/`] | 所有 Phase 2 概率、quote、candidate reason code 都应新增 pytest 覆盖。[VERIFIED: `tests/`] |
| Market channel WebSocket | official public channel | `book`、`price_change`、`tick_size_change`、`best_bid_ask`、`market_resolved` 实时事件。[CITED: https://docs.polymarket.com/market-data/websocket/market-channel] | 本 phase 即便先用 REST，也应把 quote adapter 设计成后续能接 WS 事件，不要把 Gamma price 继续写死到策略层。[CITED: https://docs.polymarket.com/market-data/websocket/market-channel][ASSUMED] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 直接继续读 Gamma `outcomePrices` / `bestAsk` | CLOB token-level `/book` `/price` `/spread` `/tick-size` | CLOB 才是执行真相；Gamma 适合 discovery，不适合做挂单可执行性判断。[CITED: https://docs.polymarket.com/api-reference/introduction][VERIFIED: live Gamma+CLOB query 2026-04-17] |
| Phase 2 直接接 market WebSocket | REST snapshot + quote adapter seam | WebSocket 是更强方案，但当前 bot 仍是 scan loop；先做 REST snapshot 可以控制改动面，同时保留后续升级口。[CITED: https://docs.polymarket.com/market-data/websocket/market-channel][ASSUMED] |
| 立即把所有 CLOB 访问切到 `py-clob-client` | 继续用 `requests` 访问公共读接口 | 官方 SDK 更规范，但本 phase 还没有认证与下单动作；沿用 `requests` 更贴近 brownfield 最小改动。[CITED: https://docs.polymarket.com/api-reference/clients-sdks][VERIFIED: `bot_v2.py`][ASSUMED] |

**Installation:**

```bash
# 本 phase 无强制新依赖；沿用现有 requests + pytest 即可。
# 若 planner 选择提前统一官方 CLOB client：
uv add py-clob-client
```

**Version verification:**
- `requests` 已安装版本为 `2.33.1`。[VERIFIED: `python3 -m pip show requests`]
- `py-clob-client` 最新可见版本为 `0.34.6`，但当前环境尚未安装。[VERIFIED: `python3 -m pip index versions py-clob-client`; VERIFIED: `python3 -m pip show py-clob-client`]

## Architecture Patterns

### Recommended Project Structure

```text
bot_v2.py                         # 继续承载 scan loop / CLI；新增 probability + quote + candidate helpers
config.json                       # 拆出 yes_strategy / no_strategy 配置块
data/markets/{city}_{date}.json   # 增加 candidate_assessments / bucket_probabilities / quote_snapshot
tests/
├── conftest.py
├── test_phase2_probability.py    # STRAT-01
├── test_phase2_quotes.py         # MKT-04, RISK-03
├── test_phase2_strategies.py     # STRAT-02, STRAT-03
└── test_phase2_reporting.py      # OBS-01
```

上面的结构遵循“只做手术式增量，不做包级重构”的项目约束。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`; VERIFIED: `.planning/STATE.md`]

### Pattern 1: Gamma discovery → CLOB execution snapshot

**What:** 先从 Gamma event/market payload 取 `conditionId`、`clobTokenIds`、`enableOrderBook`、weather 规则文本；再用 token id 从 CLOB 拉具体的 bid/ask/depth/tick size/min order size。[CITED: https://docs.polymarket.com/developers/gamma-markets-api/overview][CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][CITED: https://docs.polymarket.com/api-reference/market-data/get-tick-size]

**When to use:** 每个 admissible weather market 在进入策略筛选之前都必须走一次；如果 `enableOrderBook=false`、book 为空、tick size 缺失，直接停单并写 reason code。[CITED: https://docs.polymarket.com/developers/gamma-markets-api/overview][ASSUMED]

**Example:**

```python
# Source: official docs + current repo adaptation
# Gamma for discovery, CLOB for executable quote.
event = get_polymarket_event(city_slug, month, day, year)
contract = market_contracts[0]

yes_token_id = contract["token_id_yes"]
book = requests.get(
    f"https://clob.polymarket.com/book?token_id={yes_token_id}",
    timeout=(3, 5),
).json()

tick_size = requests.get(
    f"https://clob.polymarket.com/tick-size?token_id={yes_token_id}",
    timeout=(3, 5),
).json()
```

### Pattern 2: 全 bucket 概率表，而不是 matched bucket 二元判断

**What:** 对 event 内每个 temperature bucket 都生成 `per_source_probability`、`aggregate_probability`、`fair_yes`、`fair_no`，而不是只挑“当前 forecast 落在哪个 bucket”。[VERIFIED: `bot_v2.py:1125-1146`; ASSUMED]

**When to use:** 在天气 snapshot 新鲜且规则映射通过后，对 `mkt["all_outcomes"]` 全量计算；YES/NO 两个 evaluator 都共享这张概率表，但配置阈值分离。[VERIFIED: `bot_v2.py:978-1035`; VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED]

**Example:**

```python
# Example: phase-specific probability table pattern
# This is a planning recommendation, not an official SDK API.
bucket_probabilities = []
for outcome in mkt["all_outcomes"]:
    p_sources = {
        "ecmwf": prob_for_bucket(ecmwf_dist, outcome["range"]),
        "hrrr": prob_for_bucket(hrrr_dist, outcome["range"]),
        "metar_anchor": prob_for_bucket(metar_dist, outcome["range"]),
    }
    aggregate_p = weighted_average(p_sources)
    bucket_probabilities.append({
        "market_id": outcome["market_id"],
        "range": outcome["range"],
        "per_source_probability": p_sources,
        "aggregate_probability": aggregate_p,
        "fair_yes": aggregate_p,
        "fair_no": 1 - aggregate_p,
    })
```

### Pattern 3: 双策略 evaluator 共用市场快照，分开配置与输出

**What:** `YES_SNIPER` 和 `NO_CARRY` 使用同一份 `bucket_probabilities` 和 `quote_snapshot`，但阈值、价格带、时间窗、仓位上限完全独立。[VERIFIED: `.planning/REQUIREMENTS.md`; VERIFIED: `config.json:1-13`; ASSUMED]

**When to use:** 每个 outcome 都同时跑 YES 与 NO evaluator；同一 bucket 可能对 YES 不合格、但对 NO 合格，反之亦然。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED]

**Example:**

```python
yes_candidate = evaluate_yes_sniper(bucket, quote, yes_strategy_cfg)
no_candidate = evaluate_no_carry(bucket, quote, no_strategy_cfg)

candidate_assessments.extend([yes_candidate, no_candidate])
```

### Anti-Patterns to Avoid

- **继续把 Gamma `outcomePrices` 当 execution price：** Gamma 文档把它定义为 market data discovery 层的 convenience field；可执行盘口应改读 CLOB token-level 数据。[CITED: https://docs.polymarket.com/developers/gamma-markets-api/overview][CITED: https://docs.polymarket.com/api-reference/introduction]
- **继续沿用“matched bucket = 1，其余 = 0”：** 这会直接违背 STRAT-01 的 band probability 目标。[VERIFIED: `bot_v2.py:264-271`; VERIFIED: `.planning/REQUIREMENTS.md`]
- **YES / NO 共用一套全局阈值：** 当前 `config.json` 只有一组 `max_price` / `min_ev` / `max_bet` 风格参数，无法满足 Phase 2 双策略配置要求。[VERIFIED: `config.json:1-13`; VERIFIED: `.planning/REQUIREMENTS.md`]
- **只打印理由、不持久化理由：** Phase 2 需要 operator-facing 的 accepted / rejected / size-down / reprice 解释，必须写入 market JSON。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 可执行盘口判断 | 从 Gamma `outcomePrices` / market `bestAsk` 猜实际挂单价格 | CLOB `/book`、`/price`、`/spread`、`/tick-size` | 官方把 execution data 放在 CLOB；live query 也显示 Gamma market 字段可能与 token book 不一致。[CITED: https://docs.polymarket.com/api-reference/introduction][VERIFIED: live Gamma+CLOB query 2026-04-17] |
| tick size 规则 | 自己硬编码“通常是 0.01” | `/tick-size` 或 `tick_size_change` 事件 | 官方明确 tick size 会在极端价位变化；价格 > 0.96 或 < 0.04 时会发生 `tick_size_change`。[CITED: https://docs.polymarket.com/market-data/websocket/market-channel] |
| Polymarket 认证 / EIP-712 / HMAC | 后续自己写签名栈 | `py-clob-client` | 官方提供 Python SDK；后续 phase 不应重复踩 auth/funder/signature_type 细节坑。[CITED: https://docs.polymarket.com/api-reference/clients-sdks][CITED: https://docs.polymarket.com/api-reference/authentication] |
| 候选解释 | 只靠 free-form `print()` 文本 | 结构化 `candidate_assessments[].reasons[]` reason code | OBS-01 需要稳定可消费的 operator explanation；print-only 无法回归测试与后续订单归因复用。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED] |

**Key insight:** 本 phase 最容易“手搓错”的不是数学本身，而是**把 discovery price 当 execution price**；这会让后续所有 YES/NO 筛选都在假盘口上完成。[CITED: https://docs.polymarket.com/api-reference/introduction][VERIFIED: `bot_v2.py:1175-1206`; VERIFIED: live Gamma+CLOB query 2026-04-17]

## Common Pitfalls

### Pitfall 1: 用 Gamma market 字段做真实挂单判断

**What goes wrong:** 当前代码在入场前再次请求 `gamma-api.polymarket.com/markets/{market_id}` 并读取 `bestAsk` / `bestBid`，但 Phase 2 要评估的是 token-level 可执行报价，不是 event-level convenience field。[VERIFIED: `bot_v2.py:1175-1206`]

**Why it happens:** Gamma 事件/市场 payload 很容易拿到，且已经在现有 scan loop 中使用；但官方 API 把 orderbook/price/spread/tick size 都放在 CLOB API。[CITED: https://docs.polymarket.com/api-reference/introduction]

**How to avoid:** 在 `all_outcomes` 里保留 `token_id_yes` / `token_id_no` 后，后续所有 candidate quote 都按 token id 拉 CLOB snapshot。[VERIFIED: `bot_v2.py:993-1007`; CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book]

**Warning signs:** Gamma `bestAsk` 有值但 CLOB book 为空、book 单边、或 tick size 与价格粒度不一致。[VERIFIED: live Gamma+CLOB query 2026-04-17]

### Pitfall 2: 继续只挑“点预测落入的一个 bucket”

**What goes wrong:** 低价 YES 和高价 NO 的 edge 都来自 tail/boundary bucket 的概率质量；只挑 matched bucket 会系统性漏掉便宜 YES 与高价 NO 候选。[VERIFIED: `bot_v2.py:1125-1146`; ASSUMED]

**Why it happens:** 现有 `bucket_prob()` 对普通 bucket 返回 1/0，只对 edge bucket 用 CDF；这更像 Phase 1/旧 bot 的 point-forecast heuristic，而不是 band probability engine。[VERIFIED: `bot_v2.py:264-271`]

**How to avoid:** 对全部 bucket 使用统一的分布积分或离散质量计算，并把每个 bucket 的概率持久化到 market JSON。[ASSUMED]

**Warning signs:** `aggregate_probability` 总是只有一个 bucket 接近 1，其余都是 0；YES/NO evaluator 经常没有候选或候选只集中在当前点预测 bucket。[ASSUMED]

### Pitfall 3: 高价 NO 仍然用 YES 价格做补数近似

**What goes wrong:** 如果直接用 `1 - yes_price` 推 NO 候选，会丢掉 token-level 独立 book、spread、tick size 和空簿情况。[VERIFIED: `bot_v2.py` 当前只保存 YES侧 `price` / `bid` / `ask`; VERIFIED: live weather event has separate YES/NO token ids]

**Why it happens:** Gamma market 是 binary convenience model，但 CLOB market data endpoint 以 token id 为主，不是“一个 market 自动给你两侧可执行 book”。[CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][CITED: https://docs.polymarket.com/developers/gamma-markets-api/overview]

**How to avoid:** YES evaluator 用 `token_id_yes` quote，NO evaluator 用 `token_id_no` quote；不要用补数替代盘口。[CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][ASSUMED]

**Warning signs:** NO 候选看起来有优势，但对应 token 的实际 book 为空、最优价不同、或 min_order_size 不满足。[VERIFIED: live CLOB `/book` response contains token-specific bids/asks/min_order_size]

### Pitfall 4: 把“缺盘口”当作可继续扫描

**What goes wrong:** Phase 1 guardrail 已经能拒绝缺规则和 stale weather；Phase 2 若对空 book、closed market、缺 tick size 不停单，就会在“知道 market 语义”但“不知道能否执行”的状态下继续给候选。[VERIFIED: `bot_v2.py:945-974`; VERIFIED: `.planning/REQUIREMENTS.md`]

**Why it happens:** 当前 skip reasons 只覆盖语义与天气 freshness，不覆盖 execution layer。[VERIFIED: `bot_v2.py:951-959`]

**How to avoid:** 扩 reason code：`market_closed`、`orderbook_empty`、`tick_size_missing`、`quote_snapshot_stale`、`min_order_size_unmet`。[ASSUMED]

**Warning signs:** 市场被标记为 ready，但 `candidate_assessments` 里没有任何可执行 quote 字段，或 quote 字段为 `None`。[ASSUMED]

## Code Examples

Verified patterns from official sources:

### 公共 market WebSocket 订阅

```json
// Source: https://docs.polymarket.com/market-data/websocket/market-channel
{
  "assets_ids": ["<token_id_1>", "<token_id_2>"],
  "type": "market",
  "custom_feature_enabled": true
}
```

### 官方 Python client 读取 order book

```python
# Source: https://github.com/Polymarket/py-clob-client/blob/main/examples/get_orderbook.py
from py_clob_client.client import ClobClient

client = ClobClient("https://clob.polymarket.com")
orderbook = client.get_order_book("34097058504275310827233323421517291090691602969494795225921954353603704046623")
print(orderbook)
```

### 当前 weather market live book 形状（token-level）

```python
# Source basis:
# - https://docs.polymarket.com/api-reference/market-data/get-order-book
# - verified with live query on 2026-04-17
book = {
    "market": "0x71ce...",
    "asset_id": "314042...",
    "bids": [],
    "asks": [{"price": "0.999", "size": "2103.22"}],
    "min_order_size": "5",
    "tick_size": "0.001",
    "neg_risk": True,
    "last_trade_price": "0.996",
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 用 Gamma `outcomePrices` / `bestAsk` 粗略估价 | discovery 用 Gamma，execution 用 CLOB token-level `/book` `/price` `/spread` `/tick-size` | 官方文档当前态（2026-04-17）[CITED: https://docs.polymarket.com/api-reference/introduction] | 候选从“理论价格”变成“能否挂得出去”的评估。[CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book] |
| 用点预测挑一个 matched bucket | 为所有 bucket 计算 probability mass 表 | 当前项目需求 Phase 2 明确要求 band probability。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED] | 低价 YES 与高价 NO 才能共享同一概率真相、各自用不同阈值筛选。[ASSUMED] |
| 一套全局阈值控制所有入场 | YES / NO 分腿独立阈值 | 当前项目需求 Phase 2。[VERIFIED: `.planning/REQUIREMENTS.md`] | 满足 STRAT-02 / STRAT-03，避免一套参数同时伤害两类赔率结构。[ASSUMED] |
| 只做 print 级 scan summary | 持久化 `candidate_assessments[]` 供 CLI / report / 后续订单层复用 | 当前项目需求 Phase 2。[VERIFIED: `.planning/REQUIREMENTS.md`; ASSUMED] | OBS-01 才能自动验证，且 Phase 4 可直接继承候选解释链路。[ASSUMED] |

**Deprecated/outdated:**
- `bot_v2.py` 当前 `bucket_prob()` 只对边缘 bucket 用 CDF、对中间 bucket 用 0/1，这不再满足 STRAT-01。[VERIFIED: `bot_v2.py:264-271`; VERIFIED: `.planning/REQUIREMENTS.md`]
- `bot_v2.py` 当前以 market-level Gamma `bestAsk` / `bestBid` 二次确认 entry，不适合作为 Phase 2 execution quote source。[VERIFIED: `bot_v2.py:1175-1206`; CITED: https://docs.polymarket.com/api-reference/introduction]

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this
> section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 中间 bucket 的 band probability 应改为分布积分/离散质量，而不是 0/1 命中判断 | Phase Requirements / Pattern 2 / Pitfall 2 | 若用户其实只想做简化 point-forecast，Phase 2 任务会多出一层概率引擎实现。 |
| A2 | Phase 2 可先用 REST snapshot 落地 quote adapter，再把实时 WebSocket 强化留给后续 phase | Standard Stack / Alternatives / Pattern 1 | 若用户要求本 phase 就做实时 quote freshness，计划会低估实现量。 |
| A3 | `candidate_assessments[]` 应写入 market JSON，作为 OBS-01 和后续订单层共用事实源 | Phase Requirements / Anti-patterns / State of the Art | 若用户更想把候选与市场快照分文件存储，计划中的字段设计会偏向现有 JSON 聚合方案。 |
| A4 | YES / NO 两条策略腿应共用同一 bucket probability 真相，但独立阈值与输出 | Pattern 3 / State of the Art | 若用户希望两腿使用不同概率模型，配置与测试设计需进一步拆分。 |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. **多源 forecast 如何聚合成最终 bucket probability？**
   - What we know: Phase 2 必须从多源天气预测得到 band probability，而不是单点温度。[VERIFIED: `.planning/REQUIREMENTS.md`]
   - What's unclear: 具体是单高斯、source-weighted mixture、还是经验校准后的离散分布。[ASSUMED]
   - Recommendation: planner 先把“per-source probability + aggregate_probability + source_weights”字段和测试合同定死，具体聚合公式做成可替换 helper。[ASSUMED]

2. **高价 NO 的执行面是否直接读取 `token_id_no` 独立 book？**
   - What we know: weather market payload 已提供 YES/NO `clobTokenIds`；CLOB `/book` 是 token_id 级接口。[CITED: https://docs.polymarket.com/api-reference/market-data/get-order-book][VERIFIED: live Gamma weather event includes YES/NO token ids]
   - What's unclear: planner 是否要在 Phase 2 就显式新增 `quote_snapshot_yes` / `quote_snapshot_no` 两份结构，还是先统一为 `side` 参数化访问层。[ASSUMED]
   - Recommendation: 用参数化 `get_quote_snapshot(token_id, side_label)` helper，持久化时带 `strategy_leg` 与 `token_side` 字段即可。[ASSUMED]

3. **Phase 2 是否要输出“建议挂单价/缩量后挂单价”，还是仅输出 accept/reject？**
   - What we know: OBS-01 要求能解释接受、拒绝、缩量、降价原因。[VERIFIED: `.planning/REQUIREMENTS.md`]
   - What's unclear: 是否在本 phase 就把 quote price recommendation 算出来，还是只为 Phase 4 预留字段。[ASSUMED]
   - Recommendation: 输出 `fair_price`, `max_passive_buy`, `min_passive_sell`, `size_multiplier`, `reasons[]`，但不创建 order intent；这样既满足解释，也不越界到订单生命周期。[ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | `bot_v2.py`、pytest | ✓ | 3.14.3 | — |
| `requests` | 现有 Gamma/CLOB/天气 HTTP 调用 | ✓ | 2.33.1 | — |
| pytest | Phase 2 自动化验证 | ✓ | 9.0.2 | — |
| uv | 可选依赖管理 / optional `py-clob-client` 安装 | ✓ | 0.11.3 | 保持现有环境，不新增依赖 |
| Gamma API | discovery / metadata | ✓ | HTTP 200 | 无；不可用时无法生成候选 universe |
| CLOB API | bid/ask/spread/book/tick size | ✓ | HTTP 200 | 仅能降级成“不生成 executable candidates” |
| `py-clob-client` | 可选官方 SDK | ✗ | — | 继续用 `requests` 访问公共读接口 |

**Missing dependencies with no fallback:**
- 无阻塞本 phase 的本地依赖缺失；真正阻塞只有外部 Gamma/CLOB API 不可达，但当前已探活成功。[VERIFIED: Gamma API HTTP 200 probe; VERIFIED: CLOB API HTTP 200 probe]

**Missing dependencies with fallback:**
- `py-clob-client` 未安装，但本 phase 可继续直接访问公共 REST；后续进入 authenticated order phases 前再装即可。[VERIFIED: `python3 -m pip show py-clob-client`; CITED: https://docs.polymarket.com/api-reference/clients-sdks]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: `pytest --version`] |
| Config file | none — 现有仓库未检测到 `pytest.ini` / `pyproject.toml` 测试配置。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`; VERIFIED: repository root readout] |
| Quick run command | `pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py tests/test_phase2_reporting.py -q` [ASSUMED] |
| Full suite command | `pytest tests -q` [VERIFIED: `tests/` directory exists; ASSUMED] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MKT-04 | token-level quote snapshot 使用 bid/ask/tick size/market state 判定可执行性 | unit + integration | `pytest tests/test_phase2_quotes.py -q` | ❌ Wave 0 |
| STRAT-01 | 所有 bucket 持久化 per-source/aggregate probability，而不是 matched bucket 0/1 | unit | `pytest tests/test_phase2_probability.py -q` | ❌ Wave 0 |
| STRAT-02 | 低价 YES 独立阈值与候选输出 | unit | `pytest tests/test_phase2_strategies.py -q -k yes` | ❌ Wave 0 |
| STRAT-03 | 高价 NO 独立阈值与候选输出 | unit | `pytest tests/test_phase2_strategies.py -q -k no` | ❌ Wave 0 |
| RISK-03 | 缺 quote / closed market / empty book 时自动停单并写 reason code | integration | `pytest tests/test_phase2_quotes.py -q -k guardrail` | ❌ Wave 0 |
| OBS-01 | accepted / rejected / size-down / reprice 理由可读且稳定 | smoke | `pytest tests/test_phase2_reporting.py -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py -q` [ASSUMED]
- **Per wave merge:** `pytest tests -q` [ASSUMED]
- **Phase gate:** Full suite green before `/gsd-verify-work`。[ASSUMED]

### Wave 0 Gaps

- [ ] `tests/test_phase2_probability.py` — 覆盖 STRAT-01 bucket probability 合同
- [ ] `tests/test_phase2_quotes.py` — 覆盖 MKT-04 / RISK-03 的 token-level quote gate
- [ ] `tests/test_phase2_strategies.py` — 覆盖 STRAT-02 / STRAT-03 双 evaluator
- [ ] `tests/test_phase2_reporting.py` — 覆盖 OBS-01 operator-facing candidate explanations
- [ ] `tests/fixtures/phase2_gamma_event.json` / `phase2_clob_book_yes.json` / `phase2_clob_book_no.json` — 固定 Phase 2 fixtures

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 本 phase 只用公共读接口；不接入 trading auth。[CITED: https://docs.polymarket.com/api-reference/introduction] |
| V3 Session Management | no | 本 phase 不创建 authenticated order session。[CITED: https://docs.polymarket.com/api-reference/authentication] |
| V4 Access Control | no | 单机 CLI、无多用户权限面。[VERIFIED: project constraints in `AGENTS.md`] |
| V5 Input Validation | yes | 对 Gamma/CLOB/weather payload 做显式字段校验；缺字段直接停单而非默认继续。[VERIFIED: `bot_v2.py` 现有 guardrail pattern; ASSUMED] |
| V6 Cryptography | no | 本 phase 不应自己实现签名；后续 authenticated phases 直接交给官方 SDK。[CITED: https://docs.polymarket.com/api-reference/clients-sdks] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 上游 JSON 缺字段、空 book、closed market 被当成可继续报价 | Tampering | schema/field validation + `market_closed` / `orderbook_empty` / `tick_size_missing` reason codes；不满足即停单。[ASSUMED] |
| Phase 2 提前手搓 auth/signature 逻辑并把密钥放进 repo | Information Disclosure | 本 phase 不接 auth；后续 phase 只用 `py-clob-client` + env secrets。[CITED: https://docs.polymarket.com/api-reference/clients-sdks][CITED: https://docs.polymarket.com/api-reference/authentication] |
| 高频轮询导致 API throttling，quote 变陈旧 | Denial of Service | 限制扫描频率、批量化 token fetch、到 freshness 阈值后停止生成新候选。[CITED: https://docs.polymarket.com/api-reference/rate-limits][ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `https://docs.polymarket.com/api-reference/introduction` — Gamma/CLOB/Data API 职责边界、public vs authenticated read/write
- `https://docs.polymarket.com/developers/gamma-markets-api/overview` — Gamma 事件/市场模型、`clobTokenIds` / `conditionId` / `enableOrderBook`
- `https://docs.polymarket.com/api-reference/market-data/get-order-book` — token-level order book endpoint
- `https://docs.polymarket.com/api-reference/market-data/get-market-price` — token-level best market price endpoint
- `https://docs.polymarket.com/api-reference/market-data/get-spread` — token-level spread endpoint
- `https://docs.polymarket.com/api-reference/market-data/get-tick-size` — token-level tick size endpoint
- `https://docs.polymarket.com/market-data/websocket/market-channel` — `book` / `price_change` / `tick_size_change` / `best_bid_ask` / `market_resolved`
- `https://docs.polymarket.com/api-reference/clients-sdks` — official Python SDK existence and install path
- `https://docs.polymarket.com/api-reference/authentication` — auth 仅限 trading endpoints
- `https://polymarket.com/event/highest-temperature-in-warsaw-on-april-17-2026` — 天气市场规则文本、机场站点、整度、finalized source

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` — Phase 2 目标、success criteria、requirements mapping
- `.planning/REQUIREMENTS.md` — MKT-04 / STRAT-01/02/03 / RISK-03 / OBS-01 定义
- `.planning/STATE.md` — brownfield、Phase 1 已完成、Phase 2 约束
- `.planning/research/FEATURES.md` / `PITFALLS.md` / `STACK.md` — 项目级先验研究，作为 planner 背景，不作为最终事实源

### Tertiary (LOW confidence)
- 无仅依赖单一非官方网页的关键结论；所有关键 API / market-structure 结论均有官方 docs 或 live query 支撑。

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Gamma/CLOB/public-vs-auth 边界、market data endpoints、SDK 选择都有官方 docs 支撑。
- Architecture: MEDIUM - “REST snapshot now, WS seam later”和 bucket probability 持久化方式仍含 phase-scoping 设计判断。
- Pitfalls: MEDIUM-HIGH - Gamma/CLOB 混用、tick size change、token-level book、天气规则文本都已有官方文档或 live query 验证；概率聚合细节仍需用户/planner 定板。

**Research date:** 2026-04-17
**Valid until:** 2026-05-17
