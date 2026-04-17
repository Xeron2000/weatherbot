# Project Research Summary

**Project:** Polymarket Weather Asymmetry Bot
**Domain:** simulation-first Polymarket 天气温度市场被动执行机器人
**Researched:** 2026-04-17
**Confidence:** MEDIUM-HIGH

## Executive Summary

这是一个**不是做方向预测演示，而是做可执行、可恢复、可解释的天气市场被动挂单系统**的项目。研究结论很一致：专家做这类产品，不会把重点放在“模型猜温度”本身，而是放在三件事上——把天气 forecast 转成 **temperature band probability**，把候选机会转成 **可执行 edge**，再用 **订单生命周期 + 保守仿真** 验证 edge 是否真的能拿到。换句话说，这不是通用 trading bot，也不是通用 market maker，而是一个围绕 Polymarket 天气 bucket、低价 YES / 高价 NO 不对称结构构建的专用执行系统。

推荐路线也很明确：先把仓库升级成 **Python 3.12 + uv** 的可安装项目，建立统一域模型与 execution boundary；然后优先做 **市场语义/规则映射、CLOB 实时数据接入、订单状态机、paper execution**，最后才考虑 live adapter。核心架构应保持单进程、单入口、清晰流水线：`snapshot -> candidate -> intent -> order -> execution event`。策略、路由、订单管理、执行适配器必须分层，尤其订单管理要成为唯一真相来源。

最大风险不在“预测不准”，而在**执行假设过于乐观**和**状态一致性失控**：误读天气结算规则、只靠 REST 轮询、把 passive fill 当作迟早会成交、继续用松散 JSON 管订单与仓位，都会让 paper 结果失真并在接近实盘时崩掉。缓解手段也很清楚：按 market 保存 resolution metadata，实时订阅 CLOB 关键事件，建立显式订单状态机，用保守 queue/latency/partial-fill 仿真替代“命中即成交”，并把执行账本升级为可对账的持久化层。

## Key Findings

### Recommended Stack

栈建议偏保守，但方向非常统一：保持 Python 生态、降低迁移成本，同时把项目从脚本提升到可测试、可恢复的执行机器人。最重要的不是“再加更多框架”，而是用最少的新依赖建立清晰边界：官方 SDK 负责 Polymarket 交易，`httpx` 统一外部调用，`pydantic` 只守边界，核心策略和仿真保持纯 Python。

另一个关键综合判断是：**市场快照和调试导出可以继续文本化，但订单/成交/仓位真相来源不该继续停留在松散 JSON 上。** STACK.md 明确推荐 SQLite，PITFALLS.md 又把 brownfield JSON 错账列为高风险，因此路线图应尽早把 execution ledger 做成可恢复、可对账的持久化层，JSON 仅作为导出与审计视图。

**Core technologies:**
- Python 3.12：主运行时 — 迁移成本最低，兼容官方 Polymarket SDK，工程默认稳妥。
- uv + `pyproject.toml` + `uv.lock`：项目与依赖管理 — 让仓库从脚本变成可安装、可锁版本、可重复运行的应用。
- `py-clob-client`：Polymarket CLOB 读写与签名 — 避免自写 EIP-712/HMAC 与认证细节。
- `httpx`：天气源、Gamma、CLOB 非交易 HTTP 调用 — 超时模型更安全，测试替身生态更好。
- SQLite：订单、fills、仓位、仿真事件账本 — 解决部分成交、撤单、重启恢复、三方对账问题。
- `pydantic` / `pydantic-settings`：配置与边界 schema — 用于配置、API 清洗、输入校验，不侵入核心策略。
- `pytest` + `respx` + `ruff`：测试与质量基础设施 — 是当前仓库最缺、但最值得先补的基础。

### Expected Features

功能研究表明，v1 不是“做一个会给买卖建议的 bot”，而是**先打通自动扫描 → 概率打分 → 被动挂单 → 订单管理 → 纸面成交 → 风控复盘**闭环。凡是不能支撑这个闭环的功能，都不该挤进首发范围。

**Must have (table stakes):**
- 多城市/多市场持续扫描与 market/token/condition 映射 — 没有完整 universe，就没有执行对象。
- band 概率驱动的候选打分 — 必须按温区概率定价，不能只看 forecast mean。
- tick-size/fee-aware 被动限价单引擎 — 真正把策略变成可执行订单。
- 显式订单生命周期状态机 — 支持 live/partial/canceled/expired/filled，不能只记“下过单”。
- 保守 paper execution — 必须建模延迟、排队、partial fill、touch-not-fill。
- 风险预算与 event-level 暴露控制 — 防止同城同日多 bucket 隐性集中。
- 数据质量与规则映射防线 — freshness、单位、source disagreement、resolution rules 全要管。
- 结构化 observability — 能解释为什么挂、为什么撤、为什么没成交、为什么亏。

**Should have (competitive):**
- 双策略资金路由器（低价 YES / 高价 NO 分腿）— 提高资本效率，避免两类 edge 互相污染。
- forecast disagreement-aware quoting — 在多源分歧上升时自动缩量或降 aggressiveness。
- 队列质量/成交质量评分 — 直接检验 simulator 是否过于乐观。
- 场景化压力测试 — 用 forecast drift、流动性抽干、close-window shock 验证执行边界。
- 研究-执行统一日志模型 — 为后续实盘迁移保留连续证据链。

**Defer (v2+):**
- 小额真钱 shadow/live mode — 只在 paper 与 replay 误差已知后再做。
- 通用化到体育/政治等其他市场 — 会稀释天气场景的专用优化。
- 黑盒 ML 自动定价器 — 当前阶段会掩盖数据与执行问题。
- 更复杂的 L3-like 回放或全局资本优化器 — 等单 sleeve 执行闭环成立后再升级。

### Architecture Approach

架构研究推荐的主线是对的：保持**单进程、单入口、显式流水线**，不要过早服务化。系统应由 Scanner、Strategy Engine、Router、Order Manager、Execution Adapter、Persistence、Reporting 组成，其中最重要的边界有两个：一是 `snapshot -> candidate -> intent -> order` 的决策流水线；二是 `PaperVenue/SimExecutionAdapter` 与后续 `PolymarketVenue/ClobExecutionAdapter` 的执行边界。真正需要强化的是持久化层：市场快照和导出可以文件化，但订单与仓位账本必须尽早走可恢复、可对账的 authoritative store。

**Major components:**
1. Scanner — 拉取天气、Gamma、CLOB 数据并标准化为 `MarketSnapshot`。
2. Strategy Engine — 基于温区概率评估低价 YES 与高价 NO 候选，不直接下单。
3. Router — 按 bankroll、event/date/city 暴露和策略分腿规则分配资金，输出 `OrderIntent`。
4. Order Manager — 订单唯一真相来源，负责报价、重挂、部分成交、撤单、超时与恢复。
5. Execution Adapter — 将意图转成 sim/live 执行事件，屏蔽 Polymarket 传输细节。
6. Persistence / Reporting — 保存账本、支持对账恢复，并提供状态/报告/仪表盘投影。

### Critical Pitfalls

1. **把信号 edge 当成可执行 edge** — 每笔单都要扣掉 spread、fee、stale risk、adverse fill cost，并实时感知 tick size / min size / fee。
2. **高估 passive fill** — 仿真必须建模 queue、latency、partial fill、adverse fill，不能把“挂上去”当“迟早成交”。
3. **只靠 REST 轮询** — CLOB 实时盘口、`tick_size_change`、`market_resolved` 必须走 WebSocket；REST 只做冷启动和补快照。
4. **没有显式订单状态机** — 订单、仓位、成交要分离；状态迁移必须幂等、可恢复、可对账。
5. **误读天气结算规则** — 每个 market 都要保存 resolution text、结算站点、单位、整度和 finalized source 映射。
6. **继续用 brownfield JSON 承担执行真相** — 所有外部动作要有 journal / idempotency / reconciliation，避免静默错账。

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: 市场语义与核心域模型
**Rationale:** 先解决“我们到底在交易什么”与“系统内部对象是什么”，否则后续所有定价、风控、对账都会建在错抽象上。
**Delivers:** `MarketSnapshot`、`StrategyCandidate`、`OrderRecord`、`PositionRecord`、resolution metadata schema、event/date/city 维度标识。
**Addresses:** 市场扫描映射、规则/单位校验、band 概率定价前置建模。
**Avoids:** 误读天气市场 resolution 规则；订单和仓位混在一起。

### Phase 2: CLOB 实时市场数据与可执行性层
**Rationale:** 在谈挂单前，必须先能拿到实时 book、tick size、best bid/ask、market_resolved 等执行真相。
**Delivers:** Gamma discovery + CLOB REST 冷启动 + WebSocket 订阅、tick-size/fee/min-size 校验、executable edge 计算。
**Uses:** `py-clob-client`、`httpx`、官方 WebSocket/CLOB API。
**Implements:** Scanner + market-data boundary。
**Avoids:** 信号 edge ≠ 可执行 edge；只用轮询导致 stale quote。

### Phase 3: 候选评估与资金路由
**Rationale:** 有了 market semantics 和实时执行边界后，才能稳定地产出“值得挂什么、挂多少、哪条策略先拿资金”。
**Delivers:** 低价 YES / 高价 NO 双 evaluator、event-level exposure ceiling、初版 router、分策略预算。
**Addresses:** band 概率候选打分、风险预算、双策略冲突处理。
**Avoids:** 把高价 NO / 低价 YES 当作独立仓位；未校准概率直接重仓。

### Phase 4: 订单生命周期与执行账本
**Rationale:** 这是项目从“信号脚本”升级为“执行机器人”的关键跃迁，必须在仿真前先把订单真相来源立住。
**Delivers:** planned/working/partial/filled/canceled/expired 状态机、GTD/TTL、cancel fallback、heartbeat watchdog、authoritative order ledger。
**Uses:** SQLite 账本 + append-only events + repository-style persistence。
**Implements:** Order Manager + Persistence。
**Avoids:** 无订单状态机；heartbeat/GTD/撤单兜底缺失；brownfield JSON 错账。

### Phase 5: 保守 paper execution 与回放验证
**Rationale:** 在没有高保真仿真前，任何 paper PnL 都不可信；这一步决定系统有没有资格进入 live-readiness 讨论。
**Delivers:** queue/latency/partial-fill/touch-not-fill/adverse-fill 模型、order-book replay、fill quality 指标。
**Addresses:** simulation-first 闭环、成交真实性、未成交容忍机制。
**Avoids:** 高估 passive fill；只看最终 PnL 不看成交质量。

### Phase 6: 可观测性、对账与上线闸门
**Rationale:** 只有当系统能解释每笔单并稳定恢复，paper 结果才具备决策价值；这一步是 roadmapping 到 live adapter 之前的硬门槛。
**Delivers:** candidate/quote/fill/cancel/PnL 统一日志模型、reconciliation、dashboard projection、paper→replay→shadow 的 go-live gates。
**Addresses:** 可解释 observability、重启恢复、执行质量评估。
**Avoids:** dashboard/CLI 状态分叉；没有纸面到自动执行闸门。

### Phase 7: Live adapter（仅在前六阶段稳定后）
**Rationale:** 真实下单不是前置依赖，而是前六阶段验证通过后的替换件。
**Delivers:** `PolymarketVenue` / `ClobExecutionAdapter`、auth/funder/allowance/nonce/heartbeat 健康检查、小额 shadow/live-readiness。
**Addresses:** 后续实盘接入。
**Avoids:** “先加真钱，paper 以后再说”。

### Phase Ordering Rationale

- 先做**语义与数据模型**，再做**实时市场数据**，否则 executable edge 和 resolution correctness 无法成立。
- 先做**策略/路由**，再做**订单状态机**，可以避免把资金分配逻辑硬编码进执行层。
- **订单状态机必须早于高保真仿真**；没有订单真相来源，就不存在可信的 fill 模型。
- **对账与可观测性不是收尾装饰**，而是 paper 验证门槛的一部分；否则无法判断系统究竟是信号错还是执行错。
- **live adapter 必须最后做**，因为主要复杂度在执行真实性与状态一致性，不在 API 调用本身。

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** CLOB WebSocket 事件模型、tick size 变化、market_resolved、自定义特性订阅细节较多，适合单独做 API research。
- **Phase 5:** queue position、adverse selection、replay realism 是项目最难做真的部分，需要额外研究与验证样例。
- **Phase 7:** funder/signatureType、allowance、geoblock、heartbeat、故障恢复是 live-only 复杂区，进入实盘前必须专项研究。

Phases with standard patterns (skip research-phase):
- **Phase 1:** 域模型、schema 收口、项目结构升级属于标准 brownfield 重构模式。
- **Phase 3:** 候选→路由→intent 的分层和风险限额属于成熟模式，主要是业务参数选择，不是技术未知。
- **Phase 6:** 结构化日志、事件投影、报告派生和 gate checklist 都有稳定工程模式可直接落地。

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | 官方 Polymarket、uv、HTTPX 文档支撑强；SQLite vs JSON 的取舍有综合判断成分，但方向明确。 |
| Features | MEDIUM | 需求轮廓清晰，且与项目边界吻合；但双策略细节、sizing 曲线和 fill-quality 指标仍需实现中校准。 |
| Architecture | MEDIUM | 单进程流水线与边界设计合理，但原 ARCHITECTURE.md 对 JSON 持久化更保守，需在实施时按执行复杂度调整。 |
| Pitfalls | HIGH | 大量直接来自官方 Polymarket 文档与 weather-market 规则，且与被动执行经验高度一致。 |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Band probability calibration 方法仍未定型：** 规划阶段需明确如何从 forecast distribution / 多源分歧生成 bucket probability 与 calibration 指标。
- **Polymarket 用户流与 market 流事件归并细节仍需验证：** Phase 2/4 应先做最小订阅原型，确认状态机事件源。
- **Paper fill realism 需要本地样本验证：** 需要用真实盘口回放数据校准 queue/latency/partial-fill 假设，不能只凭经验参数上线。
- **Authoritative store 的落地形态需尽快定板：** 建议 execution ledger 用 SQLite，但要在 roadmap 早期明确 journal/schema/recovery 方案，避免半途回迁。
- **Go-live gate 指标阈值尚未量化：** 需要在 requirements 阶段明确 fill quality、cancel latency、drawdown、reconciliation drift 的门槛值。

## Sources

### Primary (HIGH confidence)
- Polymarket Docs — API introduction, authentication, trading, orders, heartbeat, rate limits, WebSocket market data — 用于确认 CLOB 执行边界、事件模型、认证与运行约束。
- Polymarket weather market rules page — 用于确认天气市场按指定机场站点、整度、finalized source 结算。
- PyPI / official repo for `py-clob-client` — 用于确认官方 Python SDK、版本范围与交易能力。
- uv Docs — 用于确认 `pyproject.toml`、lockfile、`uv_build`、workspace 取舍。
- HTTPX / pytest 官方文档 — 用于确认 HTTP client 与测试基础设施选择。

### Secondary (MEDIUM confidence)
- `.planning/PROJECT.md`、`.planning/codebase/ARCHITECTURE.md`、`.planning/codebase/STRUCTURE.md` — 用于对齐 brownfield 现实约束与现有系统形态。
- `hftbacktest`、`lobsim` — 用于支持 queue position、replay realism、diagnostics 方向。
- Nick Rae weather bot postmortem、`sonnyfully/polymarket-bot` — 用于补充 weather/paper/live gate 的实战经验。
- Adverse selection / fill probability 学术论文（2025）— 用于支持 passive fill realism 与成交后不利选择风险判断。

### Tertiary (LOW confidence)
- 无关键结论仅依赖单一低可信来源；主要不确定性来自实现细节，而不是方向判断。

---
*Research completed: 2026-04-17*
*Ready for roadmap: yes*
