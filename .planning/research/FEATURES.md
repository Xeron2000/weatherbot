# Feature Research

**Domain:** Polymarket 天气温度市场被动执行机器人（simulation-first，低价 YES + 高价 NO 双策略）
**Researched:** 2026-04-17
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

严肃的被动挂单天气机器人，最低要求不是“会找机会”，而是“会持续、可审计地挂单并知道自己为什么成交/没成交”。

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| 多城市/多市场持续扫描 | 天气温度边际通常分散在 20+ 城市和多个窄区间，不扫全会直接漏 alpha | MEDIUM | 必须支持按城市、日期、温区、策略腿（YES/NO）批量发现 market/token/condition |
| 天气概率归因与候选打分 | 这类 bot 的核心不是技术指标，而是把天气分布转成各温区命中概率和 EV | MEDIUM | 需要把 forecast mean / range / source disagreement 映射到单个 temperature band 的概率 |
| 被动限价单执行引擎 | 官方 CLOB 是限价单模型；严肃 bot 默认以 GTC/GTD 被动挂单为主 | HIGH | 必须支持 tick-size 对齐、min-order-size 校验、批量下单、撤单、按 market/token 管理 |
| 订单生命周期状态机 | serious bot 不能只记“下过单”，必须知道 quoted / live / partial / stale / canceled / expired / filled | HIGH | 依赖 market WS + user WS + 本地状态归并；需要处理部分成交和剩余量 |
| tick size / min order size / fee 感知 | Polymarket 订单不符合 tick size 会被拒；天气市场有 taker fee，执行边际很薄 | MEDIUM | 低价 YES 特别要处理极端价位 tick_size_change；模拟和报价都要 fee-aware |
| 被动挂单刷新与超时失效 | 天气预报和盘口会变，挂单不刷新就会变成坏单 | MEDIUM | 需要 TTL、stale quote 判定、市场关闭前自动撤单、条件触发 cancel-all |
| simulation-first 纸面执行 | 项目 v1 明确不接真钱；没有 paper execution 就没法验证策略闭环 | HIGH | 不是“假装成交”的回测，而是订单级 paper engine |
| 保守的成交模拟 | 被动单策略如果不建模 queue/latency，会系统性高估低价 YES 命中和高价 NO 胜率 | HIGH | 至少要建模：下单延迟、排队位置近似、touch-not-fill、部分成交、撤单生效延迟 |
| 风险预算与暴露约束 | 温度市场高度相关；同城相邻温区、同一天多腿、YES/NO 双策略容易叠加风险 | MEDIUM | 要有限额：单市场、单城市、单日、单策略 sleeve、总资金利用率 |
| 天气数据质量控制 | 天气 bot 最大风险之一不是“信号错”，而是数据 stale / unit 错 / forecast source 异常 | MEDIUM | 必须有时效检查、单位统一、异常值拒绝、源间分歧阈值 |
| 结算/规则感知 | 天气市场最终按规则和来源结算，不按 bot 自己理解结算 | MEDIUM | 每个市场都要记录 resolution rules、单位、日期、城市和 cutoff，避免错误映射 |
| 可解释 observability | 交易者必须能回答“为什么挂这单、为什么撤、为什么这笔模拟没成交” | MEDIUM | 结构化日志、候选原因、fill/cancel 原因、策略分腿报表、日终归因 |

### Differentiators (Competitive Advantage)

真正拉开差距的不是“有订单管理”，而是是否围绕天气温区 + asymmetry trade 结构，把执行、仿真、风控和数据质量做成一套专门系统。

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 双策略资金路由器（低价 YES / 高价 NO 分腿） | 把“高赔率命中”和“高胜率小利”拆成两套资金与报价逻辑，避免互相污染 | HIGH | 需要独立的 entry band、size curve、max exposure、撤单规则、胜率阈值 |
| 温区分布感知定价，而非单点温度定价 | 天气市场按窄 band 结算，直接用点预测会系统性误价 | HIGH | 需要输出 band probability mass，而不是只给一个 expected high |
| forecast disagreement-aware quoting | 当多源预测分歧变大时自动缩 size、放宽价格、甚至只挂单不追单 | MEDIUM | 这是天气市场特有 alpha 保护层，不是通用 MM 功能 |
| 不对称赔率 sizing 曲线 | 0.1–2¢ YES 与 80–99¢ NO 的收益分布完全不同，不能共用同一 sizing 公式 | HIGH | 应支持 piecewise sizing、floor/ceiling、convexity-aware size cap |
| 队列质量/成交质量评分 | 不只看“挂了没”，而是衡量 quote 在 book 中的位置、等待时间、被触价未成交率 | HIGH | 能直接暴露 simulation 假设是否过于乐观，是 serious execution bot 的关键分水岭 |
| 盘口-天气联合撤单逻辑 | 当 forecast 更新和盘口跳变方向一致时优先撤单，避免被“信息更快的人”挑走坏单 | MEDIUM | 比纯时间刷新更聪明，适合天气市场这种信息逐步收敛场景 |
| 场景化仿真（forecast drift / liquidity drought / late update） | 验证策略不是只靠历史重放，而是靠 adversarial stress 才知道执行边界 | HIGH | 应内置悲观情景：延迟、book thinning、最后时段 forecast 跳变、市场 close 前失真 |
| 规则/结算源自动校验 | 自动检查市场 title、rules、resolution source、单位与本地天气源是否一致 | MEDIUM | 对天气市场尤其重要，能减少“模型对，但市场映射错”的低级亏损 |
| Alpha 保留型不成交容忍机制 | 好的低价 YES 策略必须接受“很多单挂而不成”，而不是为了提高 fill rate 去吃 taker | MEDIUM | 体现为 fill rate 不是主目标，EV after fill-quality 才是主目标 |
| 研究-执行统一日志模型 | 同一事件模型同时服务扫描、报价、paper fill、PnL 归因，方便后续接实盘 | MEDIUM | 这是 brownfield 演进时最值钱的基础设施差异点 |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| “先加真钱，paper 以后再说” | 看起来更快验证赚钱能力 | 会把 execution bug、规则映射错、fill 假设错直接变成真钱损失；与项目目标冲突 | 先做高保真 paper execution，再用小额 shadow/live-readiness 检验 |
| 自动追成交的 taker fallback | 表面上能提高 fill rate | 天气市场 taker fee 存在，且策略 edge 很多来自便宜被动单；追单会吃掉全部边际 | 默认不追单；只在明确定义的 inventory unwind 场景允许 FAK/FOK |
| 单一“fair value = forecast mean”模块 | 实现简单 | 窄温区市场结算按 band，不按均值；会错杀低价 YES 和高价 NO | 用 band probability / CDF 差分做定价 |
| 全市场通用化扩展（体育/政治一起做） | 看起来能扩大机会集 | 不同市场规则、信息结构、fee 行为差异大，v1 会失焦 | 先把天气温度市场做深，再抽象通用层 |
| 黑盒 ML 自动定价器 | 听起来更先进 | 当前数据量、标签质量、执行噪音不足；先上会掩盖数据/执行问题 | 先做可解释概率模型 + rule-based quote policy，后续再做 residual ML |
| 只看最终 PnL，不看成交质量 | 汇报简单 | 会把“信号有用但执行差”与“执行好但信号烂”混成一团 | 强制拆解 candidate quality、quote quality、fill quality、settlement PnL |

## Feature Dependencies

```text
[市场扫描与市场元数据解析]
    └──requires──> [weather market / token / condition 映射]
                           └──requires──> [规则与单位校验]

[候选打分]
    └──requires──> [天气概率分布建模]
                           └──requires──> [多源天气抓取与质量控制]

[被动报价与下单]
    └──requires──> [tick size / min order size / fee 感知]
                           └──requires──> [实时 orderbook + market metadata]

[订单生命周期状态机]
    └──requires──> [market WS + user WS 事件归并]
                           └──requires──> [本地持久化 order ledger]

[高保真 paper execution]
    └──requires──> [订单生命周期状态机]
                           └──requires──> [queue / latency / partial-fill 模型]

[双策略资金路由器]
    ├──requires──> [候选打分]
    ├──requires──> [风险预算与相关暴露控制]
    └──enhances──> [被动报价与下单]

[场景化仿真]
    └──enhances──> [高保真 paper execution]

[自动追成交 taker fallback] ──conflicts──> [alpha 保留型不成交容忍机制]
```

### Dependency Notes

- **候选打分 requires 天气概率分布建模：** 低价 YES / 高价 NO 都依赖 band-level probability，而不是简单方向判断。
- **被动报价与下单 requires tick size / fee 感知：** Polymarket 订单价格不符合 tick size 会被拒；天气类 taker fee 也会改变边际收益。
- **订单生命周期状态机 requires market WS + user WS 事件归并：** 只看 REST open orders 不足以解释 partial fill、cancel acknowledgment 和 market-resolved。
- **高保真 paper execution requires queue / latency / partial-fill 模型：** 否则回测只是在重放想象中的成交，不是在验证执行能力。
- **双策略资金路由器 requires 风险预算：** YES 猎杀和 NO 稳赚会争夺同一资金池，不拆账本就无法评估真实资本效率。
- **自动追成交 taker fallback conflicts with alpha 保留型不成交容忍机制：** 这个项目的核心不是成交率最大化，而是保留不对称赔率 edge。

## MVP Definition

### Launch With (v1)

最小可用版本必须验证“自动扫描 → 候选筛选 → 被动挂单 → 订单管理 → paper fill → 风险/日志复盘”闭环。

- [ ] 天气温度市场扫描 + market/token/condition 映射 — 没有这个就没有可交易 universe
- [ ] band 概率驱动的候选打分（低价 YES / 高价 NO 两套阈值） — 这是策略本体
- [ ] tick-size-aware 被动下单/撤单引擎（GTC/GTD 为主） — 这是从研究走向执行的核心跃迁
- [ ] 订单生命周期状态机 + 本地持久化 ledger — 没有状态闭环就无法做仿真与复盘
- [ ] 保守 paper execution（延迟、部分成交、touch-not-fill） — v1 必须验证成交现实性
- [ ] 风险预算（单市场/单城市/单日/总资金） — 防止相关暴露失控
- [ ] 数据质量防线（时效、单位、源间分歧、规则映射） — 天气 bot 最容易死在这里
- [ ] 结构化 observability（candidate / quote / fill / cancel / PnL） — 否则无法调策略

### Add After Validation (v1.x)

- [ ] 双策略独立资金池与绩效归因 — 当基础 paper execution 与风控稳定后再拆更细
- [ ] forecast disagreement-aware 动态调价/缩量 — 当基础信号稳定后加入 alpha 保护层
- [ ] 场景化压力测试（forecast drift / book thinning / close-window shocks） — 当历史回放结果可解释后加入
- [ ] 队列质量指标面板（估计排队位置、未成交原因分解） — 当基础 fill 模型已跑通后加入
- [ ] 市场关闭前自适应 GTD 过期管理 — 当 bot 已能稳定运行整天后加入 |

### Future Consideration (v2+)

- [ ] 小额真钱 shadow/live mode — 只有 paper 与实际行为误差已知后才值得做
- [ ] 更细的 L3-like book replay / 插拔式仿真内核 — 当前 Polymarket 公开 feed 更偏 L2，等确有瓶颈再升级
- [ ] 组合级资本优化器（跨城市/跨日期 sleeve allocation） — 先验证单 sleeve edge，再做全局最优
- [ ] residual ML 排价器 — 先把可解释系统跑顺，再让模型学残差
- [ ] 扩展到 precipitation / broader weather verticals — 当前先把 temperature 这一类做透 |

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 市场扫描与映射 | HIGH | MEDIUM | P1 |
| band 概率候选打分 | HIGH | MEDIUM | P1 |
| 被动限价单执行引擎 | HIGH | HIGH | P1 |
| 订单生命周期状态机 | HIGH | HIGH | P1 |
| 保守 paper execution | HIGH | HIGH | P1 |
| 风险预算与暴露限制 | HIGH | MEDIUM | P1 |
| 数据质量控制 | HIGH | MEDIUM | P1 |
| 结构化 observability | HIGH | MEDIUM | P1 |
| 双策略资金路由器 | HIGH | HIGH | P2 |
| forecast disagreement-aware 调价 | MEDIUM | MEDIUM | P2 |
| 队列质量评分 | MEDIUM | HIGH | P2 |
| 场景化压力测试 | MEDIUM | HIGH | P2 |
| 小额真钱模式 | MEDIUM | HIGH | P3 |
| 黑盒 ML 排价器 | LOW | HIGH | P3 |

**Priority key:**
- P1: 必须有，否则无法验证 simulation-first 被动执行闭环
- P2: 核心闭环稳定后应补齐，直接提升 edge 质量或研究质量
- P3: 未来项，当前会分散注意力

## Competitor Feature Analysis

这里不把“通用交易平台功能”当对标对象，而是对比三类最接近的实现形态：当前仓库的 threshold bot、通用 Polymarket market maker、以及本项目目标形态。

| Feature | 当前 `weatherbot` 形态 | 典型通用 Polymarket MM | Our Approach |
|---------|----------------------|------------------------|--------------|
| 候选逻辑 | 方向性阈值入场 | 通常围绕中间价做双边挂单 | 围绕低价 YES asymmetry + 高价 NO high-win-rate 双腿 |
| 订单管理 | 较弱，未围绕挂单生命周期建模 | 强，偏泛化 market making | 强，但专门针对天气 band + asymmetry 执行 |
| 成交仿真 | 基础模拟 | 往往偏 live-first，不强调 weather-specific paper validation | simulation-first，明确建模 queue/latency/touch-not-fill |
| 数据质量 | 有基础天气抓取 | 通常不做 weather forecast QA | 把 forecast freshness / disagreement / rule mapping 作为一等公民 |
| 风险控制 | 基础仓位与 EV/Kelly | 库存 skew / quote risk 为主 | 除库存外，还做城市/日期/温区相关暴露管理 |
| 可解释性 | CLI/report 为主 | 偏运维与成交日志 | 研究-执行统一事件日志，强调“为什么挂/撤/成/亏” |

## Sources

- HIGH — `.planning/PROJECT.md`：项目边界、当前能力、v1 约束与目标
- HIGH — Polymarket Trading / Orderbook / Fees / Market Maker docs：
  - https://docs.polymarket.com/market-makers/trading
  - https://docs.polymarket.com/trading/orderbook
  - https://docs.polymarket.com/trading/fees
  - https://docs.polymarket.com/api-reference/trade/send-heartbeat
  - https://docs.polymarket.com/developers/CLOB/orders/create-order
- HIGH — Polymarket WebSocket / CLOB docs（通过官方 docs 索引与 API 参考确认）：market channel、user channel、rate limits、cancel endpoints、tick size、order book、price history
- MEDIUM — Polymarket Help Center 规则/结算说明：
  - https://help.polymarket.com/en/articles/13364518-how-are-prediction-markets-resolved
  - https://help.polymarket.com/en/articles/13364548-how-are-markets-clarified
- MEDIUM — `hftbacktest`（开源高频被动单回测框架）：强调 queue position、latency、tick-by-tick 模拟与“backtest 必须接近 live”
  - https://github.com/nkaz001/hftbacktest
- MEDIUM — `lobsim`（开源 LOB simulator）：强调 deterministic replay、L3/L2 区分、fills + diagnostics + event logs
  - https://github.com/kpetridis24/lobsim

---
*Feature research for: Polymarket weather asymmetry execution bot*
*Researched: 2026-04-17*
