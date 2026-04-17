# Roadmap: Polymarket Weather Asymmetry Bot

## Overview

这个里程碑不是把现有 weatherbot 继续堆成更大的信号脚本，而是把它演进成一个面向天气市场的模拟执行系统：先保证市场语义正确、候选定价可解释、双策略资金路由可控，再把被动挂单、订单恢复、保守 paper fill 与复盘报告串成闭环。v1 完成时，操作者应能稳定跑自动扫描 + 被动限价挂单工作流，并用模拟结果判断这套低价 YES / 高价 NO 策略是否值得进入后续实盘准备。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: 市场语义与扫描基线** - 先把天气市场对象、规则映射和停单防线做正确。
- [ ] **Phase 2: 候选定价与双策略筛选** - 把 band probability 和可执行盘口评估转成可解释候选。
- [ ] **Phase 3: 资金路由与暴露控制** - 按策略腿和事件暴露把资金分配收口。
- [ ] **Phase 4: 被动挂单与订单恢复** - 建立限价单生命周期、刷新撤单和重启恢复能力。
- [ ] **Phase 5: 保守 paper execution 与回放验证** - 用保守仿真验证挂单假设和成交真实性。
- [ ] **Phase 6: 执行复盘与 readiness 报告** - 提供聚合视图、结构化导出和上线前审计依据。

## Phase Details

### Phase 1: 市场语义与扫描基线
**Goal**: 操作者可以持续扫描天气市场，并且机器人只在市场语义、规则映射和基础数据完整时把市场纳入可交易 universe。
**Depends on**: Nothing (first phase)
**Requirements**: MKT-01, MKT-02, MKT-03
**Success Criteria** (what must be TRUE):
  1. 操作者可以让机器人持续扫描配置好的城市与日期范围，并稳定产出候选市场快照。
  2. 每个被纳入扫描结果的市场都能显示正确的机场站点、温区、结算规则和 condition/token 标识。
  3. 当规则映射缺失、单位不一致或天气数据过期时，机器人会明确跳过该市场而不是继续交易。
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — 建立 Phase 1 测试底座与市场语义 helper 合同
- [x] 01-02-PLAN.md — 将语义 schema 和 guardrail 接入扫描主循环与 market JSON
- [x] 01-03-PLAN.md — 在状态/报告中展示 accepted/skipped market 语义并补文档
- [x] 01-04-PLAN.md — 补齐 accepted summary 的结算规则与 contract identifiers 可见性

### Phase 2: 候选定价与双策略筛选
**Goal**: 操作者可以基于 band probability 和当前可执行盘口，为低价 YES 与高价 NO 两条策略腿分别筛出值得挂单的机会。
**Depends on**: Phase 1
**Requirements**: MKT-04, STRAT-01, STRAT-02, STRAT-03, RISK-03, OBS-01
**Success Criteria** (what must be TRUE):
  1. 操作者可以看到每个温区按多源天气预测计算出的 band probability，而不是单点温度猜测。
  2. 操作者可以分别配置低价 YES 与高价 NO 的价格、概率、时间窗和仓位阈值，并看到两类候选独立筛选结果。
  3. 机器人会结合 bid/ask、tick size、市场状态等可执行盘口信息判断某个候选是否值得挂单。
  4. 当缺少关键市场元数据、规则映射或实时行情时，机器人会自动停单并说明候选被拒绝、缩量或降价的原因。
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — 建立 band probability 真相源并把 bucket probability 表持久化到 market JSON
- [x] 02-02-PLAN.md — 用 CLOB token-level quote snapshot 替换 Gamma 执行近似并补 execution stop reasons
- [x] 02-03-PLAN.md — 增加 YES/NO 分腿配置与 candidate_assessments 持久化
- [x] 02-04-PLAN.md — 在 status/report 中展示候选解释并补 README 验证说明

### Phase 3: 资金路由与暴露控制
**Goal**: 操作者可以让机器人在低价 YES 与高价 NO 之间独立分配资金，并把集中暴露限制在可接受范围内。
**Depends on**: Phase 2
**Requirements**: STRAT-04, RISK-01, RISK-02
**Success Criteria** (what must be TRUE):
  1. 操作者可以为低价 YES 和高价 NO 两条策略腿设置独立资金预算，并看到每条腿当前占用的风险额度。
  2. 机器人会在单市场、单城市、单日期、单策略腿和总资金使用率触达上限时停止继续分配新单。
  3. 当多个温区高度相关或 YES/NO 暴露互相冲突时，机器人会拒绝继续加仓并保留已有暴露的一致性。
**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md — 建立 risk router 配置与最坏损失纯函数合同
- [x] 03-02-PLAN.md — 将路由账本接入 scan loop 并持久化 state/market 风险事实
- [x] 03-03-PLAN.md — 补齐 reservation release 与 event conflict reconciliation
- [x] 03-04-PLAN.md — 在 status/report 中展示预算与暴露并补 README 验证说明

### Phase 4: 被动挂单与订单恢复
**Goal**: 操作者可以把候选机会转成可恢复的被动限价单工作流，并在市场变化后自动管理订单生命周期。
**Depends on**: Phase 3
**Requirements**: ORDR-01, ORDR-02, ORDR-03, ORDR-04, OBS-02
**Success Criteria** (what must be TRUE):
  1. 操作者可以让机器人为候选机会生成 GTC 或 GTD 的被动限价单意图，并查看计划挂单价格与过期设置。
  2. 每笔订单都能被查看为 planned、working、partial、filled、canceled 或 expired 之一，且状态变化连续可追踪。
  3. 当天气预测或盘口变化让原报价变差时，机器人会自动刷新、撤销或放弃挂单，并说明原因。
  4. 机器人重启后可以恢复未完成订单、持仓和事件账本，操作者不会因为重启失去订单一致性。
**Plans**: TBD

### Phase 5: 保守 paper execution 与回放验证
**Goal**: 操作者可以在不使用真实资金的前提下运行完整模拟执行，并检验被动挂单假设是否足够保守。
**Depends on**: Phase 4
**Requirements**: SIM-01, SIM-02, SIM-03
**Success Criteria** (what must be TRUE):
  1. 操作者可以运行完整 paper trading 模式，从候选、挂单、成交到持仓变化都不触发真实下单。
  2. 模拟结果会显式体现下单延迟、排队、部分成交、touch-not-fill 与撤单延迟，而不是把挂单直接视为成交。
  3. 操作者可以回放订单与成交事件，检查仿真成交是否过于乐观，并定位哪些 fill 假设需要调参。
**Plans**: TBD

### Phase 6: 执行复盘与 readiness 报告
**Goal**: 操作者可以从策略腿、城市、日期和市场维度复盘执行质量，并导出进入后续 live readiness 判断所需证据。
**Depends on**: Phase 5
**Requirements**: OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. 操作者可以查看按策略腿、城市、日期和市场聚合的风险、PnL、fill quality 与未成交统计。
  2. 操作者可以导出结构化执行日志，用于复盘、调参与后续 live readiness 审核。
  3. 操作者可以基于聚合报告区分问题更可能来自候选质量、资金路由、订单管理还是仿真成交假设。
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 1.1 → 2 → 2.1 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 市场语义与扫描基线 | 4/4 | Complete | 2026-04-17 |
| 2. 候选定价与双策略筛选 | 0/TBD | Not started | - |
| 3. 资金路由与暴露控制 | 0/4 | Planned | - |
| 4. 被动挂单与订单恢复 | 0/TBD | Not started | - |
| 5. 保守 paper execution 与回放验证 | 0/TBD | Not started | - |
| 6. 执行复盘与 readiness 报告 | 0/TBD | Not started | - |
