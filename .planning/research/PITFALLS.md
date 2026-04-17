# Pitfalls Research

**Domain:** brownfield Polymarket 天气市场被动执行 / 预测市场自动交易
**Researched:** 2026-04-17
**Confidence:** HIGH

## 建议的路线图阶段命名

为便于下游 roadmap 直接引用，本文统一用以下阶段名：

- **Phase 1 — 市场语义与执行边界建模**
- **Phase 2 — CLOB 接入与实时市场数据**
- **Phase 3 — 仿真/回放与执行真实性**
- **Phase 4 — 订单生命周期与执行引擎**
- **Phase 5 — 组合风控与资金分配**
- **Phase 6 — brownfield 状态一致性与可观测性**
- **Phase 7 — 纸面验证门槛与上线闸门**

## Critical Pitfalls

### Pitfall 1: 把“信号 edge”误当成“可执行 edge”

**What goes wrong:**
天气模型给出正 EV，但真实挂单后根本吃不到这个 EV：要么价差太宽、要么最小 tick/最小下单量不允许、要么成交后变成 taker 并承担费用，最终纸面优势被微观结构成本吃光。

**Why it happens:**
现有 bot 更像“看见错价就模拟入场”，而不是“按 CLOB 规则拿得到这个价格”。Polymarket 订单必须满足 tick size、size、allowance、post-only 等约束；所谓 market order 本质上也是立即成交的 limit order。

**How to avoid:**
- 所有候选单先经过 `executable_edge = model_edge - spread_cost - fee_cost - stale_quote_risk - expected_adverse_fill_cost`。
- 每次报价前实时拉 `tick_size`、best bid/ask、depth、feesEnabled/fee-rate。
- 高价 NO / 低价 YES 分别单独建最小可成交收益门槛，不共用同一 edge 阈值。
- 报价层强制区分：`post-only passive quote`、`FAK/FOK rebalance`、`GTD timed quote`。

**Warning signs:**
- 回测胜率高，但按盘口重放后净收益接近 0 或转负。
- 订单频繁报 `breaks minimum tick size rule`、`size lower than minimum`、`invalid post-only order: order crosses book`。
- 账面 edge 多数只有 1–3¢，但 spread 本身已接近或超过它。

**Phase to address:**
**Phase 2 — CLOB 接入与实时市场数据**

---

### Pitfall 2: 把被动挂单的成交概率当成“迟早会成交”

**What goes wrong:**
模拟里挂单经常成交，实盘里长期排不到、只在坏时候成交，导致 passive execution 变成“只吃 adverse selection，不吃正常成交”。

**Why it happens:**
多数纸面系统默认：挂在 best bid/ask 就有合理 fill rate；但真实成交取决于 queue position、前方挂单量、对手盘冲击、盘口刷新速度。微观结构研究和实盘经验都说明，被动成交与成交后不利价格变动高度相关。

**How to avoid:**
- 仿真里引入**队列位置**、**前方排队量**、**盘口被吃穿概率**、**partial fill**、**成交后 1–5 次 book update 的 adverse move 标记**。
- 把 fill 分成 `adverse fill` / `non-adverse fill`，单独统计。
- 不允许把“挂上去但未成交”当成已开仓；只有成交 portion 才进入持仓与风控。
- 先做 order-book replay paper mode，再谈自动执行。

**Warning signs:**
- 纸面 passive fill rate 异常高。
- 成交后短时间 mark-to-market 经常立刻变差。
- 真实/重放环境里，大量订单一直 live，最终只能撤单或超时。

**Phase to address:**
**Phase 3 — 仿真/回放与执行真实性**

---

### Pitfall 3: 只用轮询快照，不做实时盘口订阅

**What goes wrong:**
你以为自己挂的是被动单，实际上在旧快照上已经穿价；或者 tick size 变了但本地还按旧规则报价，订单不断被拒；或者 market 已 resolved 但本地还在报价。

**Why it happens:**
Polymarket 官方明确建议 live orderbook 用 WebSocket `market` channel，不要靠 polling。`tick_size_change`、`best_bid_ask`、`market_resolved` 都是 bot 级关键事件。

**How to avoid:**
- 盘口层默认 WebSocket，REST 只做冷启动/补快照。
- 订阅 `book`、`price_change`、`last_trade_price`，并启用 `custom_feature_enabled: true` 监听 `best_bid_ask`、`market_resolved`。
- 对 `tick_size_change` 事件即时刷新本地 quoting params。
- 建立“数据陈旧阈值”：超过 N 秒未收到更新则停止挂新单并撤掉易受冲击报价。

**Warning signs:**
- 订单拒绝集中在 tick size 变化或盘口剧烈波动时。
- 本地 mid/bbo 与交易所实时盘口经常不一致。
- resolved 市场、已失效市场仍有活跃订单尝试。

**Phase to address:**
**Phase 2 — CLOB 接入与实时市场数据**

---

### Pitfall 4: 没有把订单生命周期建成显式状态机

**What goes wrong:**
系统无法正确处理 `live / matched / delayed / unmatched / partial fill / retrying / failed / confirmed` 的差异，最终重复下单、错误记仓、撤错单、把未最终确认的成交当成已完成。

**Why it happens:**
从方向性脚本升级到被动执行时，最大的断层不是“怎么算概率”，而是“订单从创建到结算的全过程”。Polymarket 交易是 offchain matching + onchain settlement，成交后还会经历 `MATCHED → MINED → CONFIRMED / FAILED`。

**How to avoid:**
- 用单独的 `Order` 聚合根，不把订单状态散落在 market JSON 里。
- 明确定义状态迁移表与幂等规则，禁止跳跃更新。
- `size_matched` 与剩余量分开存；partial fill 只允许取消未成交余量。
- 扫描线程与监控线程都只能通过状态机 API 改单，不得直接改 JSON 字段。

**Warning signs:**
- 同一 token / 同一价格层出现重复订单。
- `matched` 但仓位没变，或仓位变了但订单仍显示 live。
- 重启后无法恢复哪些订单还在 book 上。

**Phase to address:**
**Phase 4 — 订单生命周期与执行引擎**

---

### Pitfall 5: 忽略 heartbeat、GTD 到期和撤单兜底

**What goes wrong:**
要么因为没发 heartbeat，Polymarket 自动把全部挂单取消；要么因为没有 GTD/超时撤单，老报价一直挂着，等天气模型和盘口都变了还在暴露风险。

**Why it happens:**
Polymarket 文档明确：heartbeat 不按要求发送，所有 open orders 会被取消。另一方面，被动天气单又天然需要“时间失效”——天气更新、临近收盘、resolution 临近时，旧报价会迅速失真。

**How to avoid:**
- 所有自动挂单都绑定 session heartbeat watchdog。
- 默认使用 `GTD`，到期时间与“下一次天气源刷新”“离收盘阈值”“人工 circuit breaker”联动。
- 设计 cancel fallback：API 失败时，进入停止开新单 + 持续重试撤单模式。
- 对每张 live 单记录 `reason_to_live`；理由消失就撤。

**Warning signs:**
- 订单经常“神秘消失”。
- 长时间无人值守后，盘口里还留着早已失真的报价。
- 断网/进程重启后，本地与交易所 open orders 对不上。

**Phase to address:**
**Phase 4 — 订单生命周期与执行引擎**

---

### Pitfall 6: 误读天气市场 resolution 规则

**What goes wrong:**
模型预测的是城市中心、机场 METAR、小时 forecast 或小数温度；市场结算却按**指定机场站点**、**Wunderground 最终定稿值**、**整度**、**当日最高温**来结算。结果信号方向没错，合约却输了。

**Why it happens:**
天气 bot 很容易把“天气”当作泛化概念，但 Polymarket 天气市场的结算对象极其具体。官方市场页已明确：例如 Atlanta 市场按 Hartsfield-Jackson International Airport Station、Wunderground、whole degrees Fahrenheit、数据 finalized 后结算，后续 revision 不再计入。

**How to avoid:**
- 市场发现阶段就解析并持久化每个市场的 resolution text，不允许只靠 slug/城市名推断。
- 数据层统一映射到**结算站点**与**结算精度**。
- 预测分布在下单前先量化为与 market bucket 一致的离散整度概率，而不是连续温度概率直接比较。
- 对“同城不同站”“时区跨日”“最高温 vs 某时点温度”做单元测试与历史回放验证。

**Warning signs:**
- 同城 forecast 与最终结算站点观测偏差长期系统性偏大。
- 预测命中了方向，却总在边界 bucket 输。
- 市场规则文本与本地 city/station 配置不一致。

**Phase to address:**
**Phase 1 — 市场语义与执行边界建模**

---

### Pitfall 7: 把高价 NO / 低价 YES 当作彼此独立仓位

**What goes wrong:**
同一城市同一天的多个 bucket 之间是强相关、互斥、甚至在 event 层面可净额化的；如果只按“单腿 notional”控仓，会错误放大或低估真实风险，尤其是极端温区高价 NO 策略会在同一事件上堆出隐藏集中暴露。

**Why it happens:**
脚本式系统通常以“一个 market 一个仓位”建模，但天气温度市场本质上是一组 mutually exclusive buckets。项目目标中的“双策略框架”更容易在同一 event 内堆积相关头寸。

**How to avoid:**
- 风控以 **event/date/city** 为主维度，不以单合约为主维度。
- 为每个 event 计算 worst-case payout map，而不是简单相加未实现 PnL。
- 允许识别互斥 bucket 的净风险、总 tail loss、总 resolution cashflow。
- 低价 YES 与高价 NO 分开做资金池，但共享 event-level exposure ceiling。

**Warning signs:**
- 单笔仓位都不大，但某一城市/日期事件的总 worst-case loss 很高。
- 组合层看似分散，实则收益几乎由少数温度路径决定。
- 高价 NO 策略在多个尾部 bucket 同时持仓时，capital locked 明显偏大。

**Phase to address:**
**Phase 5 — 组合风控与资金分配**

---

### Pitfall 8: 用未经校准的概率直接做 Kelly / 重仓

**What goes wrong:**
模型只是“会排序”，不代表“会定价”。一旦把未校准概率直接喂给 Kelly，仓位会系统性过大，连续几次边界失误就足以击穿账户。

**Why it happens:**
天气模型很容易输出看似精确的概率，但真实关键在 calibration。社区实盘经验也反复提到：忽略 ensemble spread、只看点预测，会显著高估信心。被动执行又放大了“错得很慢但仓位很重”的问题。

**How to avoid:**
- 先做 bucket-level calibration、Brier score、reliability curve，再谈 Kelly。
- 默认 quarter-Kelly 或更低；在 Phase 7 前禁止 full Kelly。
- 把 ensemble spread、forecast disagreement、距 resolution 时间一起纳入 sizing dampener。
- 分策略维护独立绩效与校准，不允许把低价 YES / 高价 NO 共用同一参数。

**Warning signs:**
- 纸面胜率不低，但回撤异常大。
- 亏损主要来自少量“大信心”仓位。
- 同类边界 bucket 持续偏离预期，说明 calibration 而非 ranking 有问题。

**Phase to address:**
**Phase 5 — 组合风控与资金分配**

---

### Pitfall 9: brownfield JSON 状态让订单与仓位失去一致性

**What goes wrong:**
继续在平面脚本 + JSON 文件上叠加执行逻辑，扫描、监控、结算、dashboard 都读写同一批文件，容易出现重启后状态分叉、重复下单、已撤单仍显示 live、已成交未入账等问题。

**Why it happens:**
当前代码库是单进程、脚本式、文件持久化；这对“看机会”足够，对“管理 open orders + partial fills + retries + reconciliation”则很脆。问题不一定表现为崩溃，更常见是**静默错账**。

**How to avoid:**
- 把“市场快照”“订单日志”“仓位账本”“策略信号”拆成独立持久化对象。
- 所有写操作走 append-only journal，再异步生成当前快照；不要直接覆盖事实。
- 进程启动时做 reconciliation：本地 open orders vs 交易所 open orders vs 本地持仓三方对账。
- 每个外部动作带 idempotency key / client order tag，防止重放下重复单。

**Warning signs:**
- 重启后净仓位、挂单数、现金余额经常对不上。
- dashboard 与 CLI 状态时常矛盾。
- 出现“这个订单我明明撤了/没下过”的情况。

**Phase to address:**
**Phase 6 — brownfield 状态一致性与可观测性**

---

### Pitfall 10: 没有为“从纸面到自动执行”设置专门上线闸门

**What goes wrong:**
系统在 paper mode 看起来可盈利，于是直接切自动执行；结果发现 simulator 高估 fill、低估 stale risk、没覆盖 API 故障与撤单失败，真钱表现与纸面断层。

**Why it happens:**
signal-generation bot 的胜利标准通常是“选对方向”；passive execution system 的胜利标准必须变成“按真实盘口与真实生命周期赚到钱”。两者不是一个问题。

**How to avoid:**
- 上线前单独设置 execution gates：最小样本数、realistic fill attribution、adverse fill 占比、quote cancel ratio、stale-order incidents、peak drawdown、事件级 worst-case loss。
- 先跑“仿真→order-book replay→paper with live book→极小额 live”的分级门槛。
- 每个 gate 必须同时看**信号质量**与**执行质量**，不能只看最终 PnL。

**Warning signs:**
- paper PnL 好，但大部分收益来自“假设成交”。
- 没有任何指标追踪 fill quality、cancel latency、reconciliation drift。
- 团队只能回答“模型好不好”，回答不了“执行好不好”。

**Phase to address:**
**Phase 7 — 纸面验证门槛与上线闸门**

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| 继续把订单状态塞进现有 market JSON | 改动最小 | 很快失去订单/仓位/现金一致性 | 仅限 Phase 1 原型，进入 Phase 4 前必须拆账本 |
| 用 REST 轮询代替 WebSocket | 实现快 | stale quotes、tick size 变更漏接、resolved 市场继续报价 | 仅限离线分析，不可用于自动挂单 |
| 用“命中就算成交”做 paper PnL | 早期演示简单 | 严重高估 passive strategy | never |
| 单策略 Kelly 参数复用于所有 bucket | 配置简单 | 对低价 YES 和高价 NO 同时过拟合/过重仓 | never |
| 直接覆盖 JSON 快照，不保留事件日志 | 文件少、看着干净 | 无法对账、无法回放、无法恢复 | 仅限只读市场缓存，不可用于订单与资金账本 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Polymarket CLOB Auth | 把地址、signatureType、funder 当成“随便填一个钱包地址” | 明确区分 EOA / POLY_PROXY / GNOSIS_SAFE，并使用正确 funder |
| Polymarket Trading | 下单前不查 allowance / balance / nonce | 每次交易前检查余额、allowance、nonce 管理与错误恢复 |
| Polymarket Market Data | 用 Gamma 做发现，却不接 CLOB book | Gamma 只做 market discovery；执行必须接 CLOB 实时盘口 |
| Polymarket WebSocket | 只订阅 book，不监听 tick_size_change / market_resolved | 打开 custom features，并把关键事件接入状态机 |
| Weather Resolution Source | 用 city forecast / point forecast 直接映射 | 按市场规则解析机场站点、单位、整度、finalized source |
| Wunderground / resolution timing | 默认当天结束即可结算 | 把“数据 finalized”建模为独立状态，未 finalized 不视为 resolved |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 20+ 城市全量轮询所有盘口 | 请求量高、延迟上升、扫描结果变旧 | 用 keyset / 增量订阅 / token 白名单，执行层只盯候选市场 | 城市和日期扩到 20+ 后就开始明显恶化 |
| 扫描与监控共用同一串行循环 | 撤单/监控滞后，错过订单状态变化 | 分离 scheduler：scan、quote refresh、order reconciliation、risk checks | 市场数 > 30、open orders > 20 时明显失控 |
| dashboard 直接消费交易主状态文件 | UI 读取影响主流程、文件竞争 | 主流程写 journal，dashboard 读派生只读快照 | 长时间运行 + 高频写入时出现读写冲突 |
| 每次重算全历史 calibration | 运行时间越来越长 | 增量更新 calibration 指标 | resolved markets 积累到数百后开始拖慢 |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| 将 private key / API creds 混在代码或前端可见环境 | 直接资金风险 / 账户接管 | 只放后端 secrets manager / 本地 env，不进仓库、不进 dashboard |
| 自动交易进程与研究脚本共用同一凭据 | 测试脚本误下单、误撤单 | 分离 paper/live 凭据，live 凭据仅执行进程可读 |
| 没有 geoblock 预检 | 订单被拒、策略 silently fail | 在启动和周期性健康检查里调用 geoblock 检查 |
| 没有 kill switch | 异常行情或 bug 持续放大损失 | 提供全局“停止开新单 + 撤所有单 + 仅对账”模式 |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 报告只显示 model edge，不显示 executable edge | 操作者误以为机会很好 | 同时展示 mid、bbo、depth、fees、预计 fill quality |
| open orders 和 filled positions 混在一起 | 误判真实风险暴露 | 明确区分 live orders / partial fills / confirmed positions |
| 不显示 event-level exposure | 操作者以为分散，实际高度集中 | 默认展示按 city/date/event 聚合的最坏损失 |
| 没有 stale quote / heartbeat 告警 | 进程挂了很久才知道 | 增加 freshness、heartbeat、reconciliation drift 告警 |

## "Looks Done But Isn't" Checklist

- [ ] **Passive quoting:** 不只是能下 GTC；还要验证 post-only 拒单、tick size 变更、GTD 到期、heartbeat 失效后的行为。
- [ ] **Paper trading:** 不只是能算 PnL；还要验证 queue position、partial fill、adverse fill、未成交订单超时。
- [ ] **Weather mapping:** 不只是城市名对上；还要验证机场站点、单位、整度、时区、最高温定义。
- [ ] **Risk engine:** 不只是限制单笔下注；还要验证 event-level worst-case exposure 与跨 bucket 相关性。
- [ ] **Reconciliation:** 不只是本地状态能读写；还要验证重启后与交易所 open orders/positions 一致。
- [ ] **Go-live readiness:** 不只是 paper PnL 正；还要验证 execution metrics、drawdown gates、kill switch、手动接管流程。

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| 错误 weather resolution 映射 | HIGH | 停止新单；回查所有 market rules；重建 station mapping；重跑历史 calibration |
| 订单生命周期错账 | HIGH | 冻结执行；拉取交易所 open orders / trades；按 journal 重建账本；修正仓位后再恢复 |
| heartbeat / stale quote 事故 | MEDIUM | 立即 cancel-all；标记受影响时间窗；分析是否有失效报价成交 |
| passive fill 仿真失真 | HIGH | 暂停策略评估；引入 order-book replay；把历史 paper 结果按 realistic fill 重新估值 |
| event-level 暴露过高 | MEDIUM | 停止同事件加仓；按最差路径压降仓位；加入 event ceiling |
| auth / allowance / funder 配置错误 | MEDIUM | 切只读模式；修复凭据和 funder；用小额沙盒级下单验证后再恢复 |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 信号 edge ≠ 可执行 edge | Phase 2 | 每笔候选单都有 executable edge 分解，并能解释为何跳过 |
| passive fill 被高估 | Phase 3 | 回放仿真输出 fill rate、adverse fill rate、未成交率 |
| 只用轮询不做实时盘口 | Phase 2 | WebSocket 断连、tick_size_change、market_resolved 都有测试 |
| 无订单状态机 | Phase 4 | 任一订单都能从创建追到 confirmed/failed，重启不丢状态 |
| 缺 heartbeat / GTD / 撤单兜底 | Phase 4 | 故意断开心跳后，系统能安全停机并对账 |
| 误读天气结算规则 | Phase 1 | 每个 market 都保存解析后的 resolution metadata，并通过样本规则测试 |
| 同事件风险隐藏集中 | Phase 5 | dashboard 默认显示 event-level worst-case loss |
| 未校准概率直接 Kelly | Phase 5 | sizing 依赖 calibration 指标，且支持分策略 dampener |
| brownfield JSON 错账 | Phase 6 | 重启对账测试通过，local vs exchange 漂移可检测 |
| 没有纸面到自动执行闸门 | Phase 7 | 存在明确定义的 go-live checklist，且 execution metrics 达标 |

## Sources

- **HIGH** — Polymarket API Introduction: https://docs.polymarket.com/api-reference/introduction
- **HIGH** — Polymarket Authentication: https://docs.polymarket.com/api-reference/authentication
- **HIGH** — Polymarket Rate Limits: https://docs.polymarket.com/api-reference/rate-limits
- **HIGH** — Polymarket Trading / order lifecycle / order types / heartbeat / errors: https://docs.polymarket.com/trading/overview , https://docs.polymarket.com/trading/orders/create , https://docs.polymarket.com/api-reference/trade/send-heartbeat
- **HIGH** — Polymarket WebSocket market channel: https://docs.polymarket.com/market-data/websocket/market-channel
- **HIGH** — Polymarket market maker trading + inventory docs: https://docs.polymarket.com/market-makers/trading , https://docs.polymarket.com/market-makers/inventory
- **HIGH** — Example live weather market rules (airport station, whole-degree precision, finalized Wunderground source): https://polymarket.com/event/highest-temperature-in-atlanta-on-april-17-2026
- **MEDIUM** — Nick Rae, weather bot postmortem / live gates / spread-calibration lessons: https://nickrae.net/blog/kalshi-weather-bot.html
- **MEDIUM** — sonnyfully/polymarket-bot README on simulator realism and passive fill caveats: https://github.com/sonnyfully/polymarket-bot
- **MEDIUM** — Lalor & Swishchuk, *Market Simulation under Adverse Selection* (2025): https://arxiv.org/html/2409.12721v2
- **MEDIUM** — *The Market Maker’s Dilemma: Navigating the Fill Probability vs. Post-Fill Returns Trade-Off* (2025): https://arxiv.org/html/2502.18625v2

---
*Pitfalls research for: Polymarket weather-market passive execution bot*
*Researched: 2026-04-17*
