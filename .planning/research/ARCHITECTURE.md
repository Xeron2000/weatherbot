# Architecture Research

**Domain:** brownfield Polymarket 天气市场交易机器人（被动挂单 + 双策略 + 模拟执行）
**Researched:** 2026-04-17
**Confidence:** MEDIUM

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                           CLI / Loop Layer                          │
├──────────────────────────────────────────────────────────────────────┤
│  bot_v3.py / run_once / run_loop / status / report / dashboard feed │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Domain Orchestration                        │
├──────────────────────────────────────────────────────────────────────┤
│  Scanner  →  Strategy Engine  →  Router  →  Order Manager          │
│     │              │                 │                │              │
│     └──────► Market State ◄──────────┘                │              │
│                              │                        │              │
│                              └──────► Position State ◄┘              │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Execution Boundary                          │
├──────────────────────────────────────────────────────────────────────┤
│   Simulation Adapter        |        Polymarket Adapter (later)     │
│   fill model / queue model  |  py-clob-client / CLOB REST endpoints │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Persistence Layer                           │
├──────────────────────────────────────────────────────────────────────┤
│ state.json | markets/*.json | orders/*.json | fills.jsonl | config  │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Scanner | 拉天气预测、市场元数据、order book 摘要，产出统一 `MarketSnapshot` | 纯 Python functions + 小型 client wrappers |
| Strategy Engine | 对每个 market 计算低价 YES / 高价 NO 两类机会，不直接下单 | 纯函数，输入 snapshot，输出 `StrategyCandidate[]` |
| Router | 在候选之间分配 bankroll、限额、城市/日期暴露，生成 `OrderIntent[]` | 单模块资金分配器，不要做成通用 rule engine |
| Order Manager | 管 working orders 生命周期：报价、挂单、排队、部分成交、撤单、超时、重挂 | 单状态机模块，拥有订单真相来源 |
| Execution Adapter | 把 `OrderIntent` 翻译成模拟撮合或真实 API 调用 | `ExecutionPort` + `SimExecutionAdapter` + `ClobExecutionAdapter` |
| Persistence Store | 保存 market/order/position/account 状态，支持重启恢复 | JSON 文件 + 原子写入 + append-only fill log |
| Reporting | 状态、报告、dashboard 数据投影 | 从持久化状态只读生成 |

## Recommended Project Structure

```text
weatherbot/
├── bot_v3.py                 # 新主入口；保留 bot_v2.py 作为迁移对照
├── config.json               # 继续使用现有配置文件
├── trading/
│   ├── models.py             # MarketState / OrderState / Position / Intent dataclasses
│   ├── scanner.py            # 天气 + Gamma/CLOB 读取与标准化
│   ├── strategy.py           # 双策略评估
│   ├── router.py             # 资金分配、限额、去重
│   ├── order_manager.py      # 被动订单状态机
│   ├── execution.py          # ExecutionPort + sim/live adapters
│   ├── simulation.py         # fill / queue / timeout 假设
│   └── persistence.py        # JSON load/save + atomic writes
├── reporting/
│   ├── status.py             # CLI 状态输出
│   └── report.py             # 汇总报表与 dashboard projection
└── data/
    ├── state.json
    ├── markets/
    ├── orders/
    └── fills.jsonl
```

### Structure Rationale

- **继续单进程、单入口：** 这个项目当前目标是 20+ 城市扫描 + 模拟挂单，不需要 worker queue、message bus、数据库。
- **只拆 1 层模块，不拆服务：** 从 `bot_v2.py` 抽出 6–8 个边界明确的模块就够了；超过这个粒度会开始为“架构美感”付复杂度税。
- **订单与仓位分离：** 当前脚本偏“发现机会→直接入场”，新系统必须把 `order` 和 `position` 拆开，否则被动挂单、部分成交、撤单无法建模。
- **持久化继续 JSON：** 对现在阶段最关键的是“可恢复 + 可审计”，不是 SQL 查询能力。用 `orders/*.json` + `fills.jsonl` 已足够。

## Architectural Patterns

### Pattern 1: Snapshot → Candidate → Intent → Order

**What:** 把“看市场”“算策略”“分配资金”“执行订单”拆成四个阶段，每阶段只消费上一步产物。
**When to use:** 需要同时支持双策略、模拟/实盘切换、以及重跑决策解释时。
**Trade-offs:** 多一层中间对象，但换来可测试性和迁移清晰度。

**Example:**
```python
candidates = strategy_engine.evaluate(markets)
intents = router.allocate(candidates, portfolio_state)
actions = order_manager.reconcile(intents, open_orders, positions)
execution_results = execution.execute(actions)
```

### Pattern 2: Single Owner State Machine for Orders

**What:** 只有 `OrderManager` 可以修改订单生命周期；策略层只能发 intent，执行层只能回报结果。
**When to use:** 被动挂单、部分成交、撤单、超时重挂都存在时。
**Trade-offs:** 初期写起来比“if 条件满足就买”麻烦，但这是这次改造的核心收益点。

**Example:**
```python
class OrderStatus(str, Enum):
    PLANNED = "planned"
    WORKING = "working"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELED = "canceled"
    EXPIRED = "expired"

next_status = order_manager.transition(order, event)
```

### Pattern 3: Execution Port Boundary

**What:** 用同一个接口屏蔽 simulation 与 live CLOB 差异。
**When to use:** v1 先模拟，后面要接 Polymarket 真下单时。
**Trade-offs:** 会多一个 adapter 层，但这是避免未来重写 orchestration 的最低成本方式。

**Example:**
```python
class ExecutionPort(Protocol):
    def place(self, action: PlaceOrder) -> ExecutionResult: ...
    def cancel(self, action: CancelOrder) -> ExecutionResult: ...
    def sync(self) -> list[ExecutionEvent]: ...
```

### Pattern 4: Restartable File-Backed State

**What:** 每轮 loop 都从磁盘恢复状态、执行增量更新、原子写回。
**When to use:** 单机 CLI bot，需要 crash recovery，但还不想引入 DB。
**Trade-offs:** 查询不灵活，但对当前只读报告完全够用。

## Data Flow

### Core Trading Flow

```text
[Loop Tick]
    ↓
[Scanner]
    ↓  产出 MarketSnapshot[]
[Strategy Engine]
    ↓  产出 StrategyCandidate[]
[Router]
    ↓  产出 OrderIntent[]
[Order Manager]
    ↓  产出 Place/Cancel/Hold actions
[Execution Adapter]
    ↓  产出 ExecutionEvent[]
[Persistence]
    ↓
[Status / Report / Next Tick]
```

### State Management

```text
state.json
    ├── bankroll / realized_pnl / reserved_cash
    ├── positions[]
    └── strategy_exposure{}

orders/*.json
    └── one logical order chain per market-side-strategy

markets/*.json
    └── snapshot history + market metadata + forecast history

fills.jsonl
    └── append-only execution events for audit / replay
```

### Key Data Flows

1. **市场扫描流：** 天气源 + Gamma market metadata + CLOB 价格/盘口 → 标准化 `MarketSnapshot` → 保存到 `markets/*.json`。
2. **策略决策流：** `MarketSnapshot` → 双策略 evaluator → `StrategyCandidate`，此时只表达“值得挂什么价、什么 size”。
3. **资金路由流：** 候选集合 + 当前暴露 + 可用资金 → `OrderIntent`，解决“YES 猎杀”和“NO 稳赚”抢资金的问题。
4. **订单协调流：** `OrderIntent` + open orders + fills → place/cancel/reprice/expire；只有这里能决定是否改价或撤单。
5. **执行回写流：** simulator/live adapter 返回 `ExecutionEvent` → 更新 `orders`、`positions`、`state`。
6. **恢复流：** 进程重启后先加载 `state.json`、`orders/*.json`、最近 `markets/*.json`，再做一次 `sync()`，防止丢单或重复下单。

## Suggested Component Boundaries

| Component | Owns | Does Not Own | Communicates With |
|-----------|------|--------------|-------------------|
| Scanner | 外部数据拉取、标准化 snapshot | 策略判断、资金分配、订单状态 | Persistence, Strategy Engine |
| Strategy Engine | EV/概率/价位规则、策略标签 | 账户资金、挂单状态、API 调用 | Router |
| Router | bankroll 分配、风险限额、去重 | 盘口读取、订单执行 | Strategy Engine, Order Manager |
| Order Manager | open order ledger、订单状态机、超时和重挂规则 | 概率模型、天气逻辑 | Router, Execution Adapter, Persistence |
| Simulation Adapter | 撮合假设、排队假设、fill events | 策略逻辑、资金规则 | Order Manager |
| Live Adapter | py-clob-client / CLOB place-cancel-sync | 风控决策、仓位 sizing | Order Manager |
| Persistence | durable state schema、原子写盘 | 业务决策 | All components |

## Brownfield Migration Path

### Step 1: 先抽“数据结构”，不要先抽“框架”

从 `bot_v2.py` 提炼 4 个核心对象：

- `MarketState`
- `StrategyCandidate`
- `OrderRecord`
- `PositionRecord`

第一步不改变行为，只让现有 dict 变成更稳定的 schema。这样后续任何迁移都不会继续在匿名 dict 上滚雪球。

### Step 2: 把扫描逻辑从交易逻辑里剥离

把当前 `scan_and_update()` 里的：

- forecast fetch
- market lookup
- snapshot persistence

抽到 `scanner.py`。目标不是变快，而是让“扫描”可以单独跑、单独验证、单独缓存。

### Step 3: 引入双策略 evaluator，但仍旧不做被动订单

先让系统输出：

- `YES_SNIPER` 候选
- `NO_CARRY` 候选

并记录推荐 price/size，不急着实现 queue/fill。先证明“双策略发现层”是稳定的。

### Step 4: 引入 Router，解决策略抢资金

在现有直接入场逻辑前面插一层 router：

- 每城市/日期最大暴露
- YES 总预算上限
- NO 总预算上限
- 同市场不能同时挂互相冲突的单

到这一步仍可沿用简化模拟成交。

### Step 5: 单独落地 Order Manager

这是最关键的新增边界。把“订单”和“仓位”拆开：

- order posted ≠ filled
- partial fill 可转 position
- timeout 后 cancel / reprice
- unresolved open order 在重启后可恢复

这一步完成后，系统才真正从“信号脚本”升级为“挂单机器人”。

### Step 6: 最后替换 Execution Adapter

先接 `SimExecutionAdapter`：

- 用 order book top-of-book + queue 假设模拟成交
- 支持 partial fill / no fill / expiry

之后若进入实盘，只替换为 `ClobExecutionAdapter`。上层 Scanner / Strategy / Router / OrderManager 不改。

## Suggested Build Order

1. **State schema 与 persistence 重整**
   - 先定义 order / position / market / account schema
   - 验证：能从现有 `data/` 恢复并写回

2. **Scanner 模块化**
   - 抽出天气、Gamma、CLOB 读取
   - 验证：单独执行 scanner 仍能生成市场快照

3. **Dual-strategy evaluator**
   - 同时输出低价 YES 与高价 NO 候选
   - 验证：同一轮扫描可得到策略标签和建议报价

4. **Router / risk allocator**
   - 解决 bankroll、暴露、候选排序
   - 验证：输入固定 candidates，输出稳定 intents

5. **Order Manager state machine**
   - 增加 planned/working/partial/filled/canceled/expired
   - 验证：模拟 event sequence 能正确迁移状态

6. **Simulation adapter**
   - 把“直接成交”升级为“挂单→等待→成交/取消”
   - 验证：能产生 fills、unfilled、expiry 三类结果

7. **Reporting / dashboard projection**
   - 新增 open orders、reserved cash、per-strategy exposure
   - 验证：CLI/report 与状态文件一致

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 20–50 市场 / 单机模拟 | 当前推荐架构足够；单进程 + JSON 即可 |
| 100–300 市场 / 高频轮询 | 优先优化 scanner 缓存、批量 CLOB 请求、写盘频率 |
| 300+ 市场 / 准实时实盘 | 再考虑 websocket、SQLite、异步 I/O；不要现在就上 |

### Scaling Priorities

1. **First bottleneck:** 外部 API 拉取与 reconciliation 频率，不是 Python 计算本身。
2. **Second bottleneck:** JSON 文件越来越大时的恢复速度；到那时再把 `fills` 或 `orders` 迁到 SQLite。

## Anti-Patterns

### Anti-Pattern 1: 继续把新逻辑塞回 `scan_and_update()`

**What people do:** 在现有大函数里再加 if/else，把双策略、挂单、模拟撮合都堆进去。
**Why it's wrong:** 很快就没人能回答“这个订单为什么还挂着”“这个仓位是哪个 intent 生成的”。
**Do this instead:** 让 `scan -> candidate -> intent -> order -> fill` 成为显式流水线。

### Anti-Pattern 2: 订单和仓位混成一个对象

**What people do:** 一旦决定下单，就直接创建 position。
**Why it's wrong:** 被动挂单场景下，绝大多数时间你拥有的是“未成交订单”，不是“已持仓位”。
**Do this instead:** order ledger 单独持久化，只有 fill event 才能生成或增加 position。

### Anti-Pattern 3: 为未来实盘过早引入分布式架构

**What people do:** 现在就上 PostgreSQL、Redis、Celery、微服务。
**Why it's wrong:** 当前复杂度来自订单生命周期，不来自吞吐量。基础设施升级解决不了领域边界混乱。
**Do this instead:** 先把单进程边界理顺；等 live trading 真受 I/O 和恢复速度限制时再升级。

### Anti-Pattern 4: 模拟层直接复制真实 API 响应结构

**What people do:** simulator 完全模仿 Polymarket 原始响应，业务层到处判断 live/sim 差异。
**Why it's wrong:** 上层会被 transport 细节污染。
**Do this instead:** 定义统一 `ExecutionEvent`，让 sim/live adapter 都向这个内部格式收敛。

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Weather sources | read-only polling via current forecast clients | 继续复用现有多源天气抓取 |
| Polymarket Gamma API | read-only market discovery | 官方 docs 指出 Gamma 负责 markets/events 发现 |
| Polymarket CLOB market-data | read-only book/price/midpoint polling | 官方 docs 提供 `/book` `/price` `/midpoint` |
| Polymarket CLOB trading | authenticated place/cancel/order sync | 官方 docs 与 `py-clob-client` 支持下单、查 open orders、撤单、heartbeat |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scanner ↔ Strategy | in-memory `MarketSnapshot[]` | 不要让 Strategy 自己调 API |
| Strategy ↔ Router | `StrategyCandidate[]` | candidate 必须带 strategy tag、price、size、confidence |
| Router ↔ Order Manager | `OrderIntent[]` | intent 是“想挂什么单”，不是“已经下了单” |
| Order Manager ↔ Execution | `Place/Cancel` actions + `ExecutionEvent[]` | 这是 sim/live 互换点 |
| All modules ↔ Persistence | repository-style read/write functions | 不要在业务代码里散落 `open()` |

## Build Order Recommendation for Roadmap

最合理的 phase 顺序不是“先做实盘接口”，而是：

1. **状态与数据模型收口** — 先建立 order/position/account/market 真相来源。
2. **双策略发现与路由** — 先让系统知道该挂什么单、为什么挂。
3. **被动订单管理** — 让系统能长期维护 working orders。
4. **模拟撮合与恢复** — 验证整条链路在重启和长时间运行下成立。
5. **实盘 adapter（后续）** — 只在前 4 步稳定后再接。

原因：这个项目当前真正缺的不是“能调用下单 API”，而是“能持续管理未成交订单并解释状态演化”。

## Sources

- `.planning/PROJECT.md` — 项目目标、约束、active requirements
- `.planning/codebase/ARCHITECTURE.md` — 当前脚本式架构与数据流
- `.planning/codebase/STRUCTURE.md` — 当前目录结构与 brownfield 约束
- Polymarket API docs: https://docs.polymarket.com/api-reference/introduction
- Polymarket API docs: https://docs.polymarket.com/api-reference/authentication
- Polymarket API docs: https://docs.polymarket.com/api-reference/rate-limits
- Polymarket API docs: https://docs.polymarket.com/api-reference/trade/post-a-new-order
- Polymarket API docs: https://docs.polymarket.com/api-reference/trade/get-user-orders
- Polymarket API docs: https://docs.polymarket.com/api-reference/trade/send-heartbeat
- Official Python client: https://github.com/Polymarket/py-clob-client

---
*Architecture research for: brownfield Polymarket weather-market trading bot*
*Researched: 2026-04-17*
