# Requirements: Polymarket Weather Asymmetry Bot

**Defined:** 2026-04-17
**Core Value:** 在天气市场里稳定抓住“概率对、价格错”的盘口，并用可验证的自动化执行把高赔率机会变成可重复策略。

## v1 Requirements

### Market Universe

- [x] **MKT-01**: 操作者可以让机器人持续扫描配置好的城市与日期范围内的 Polymarket 天气温度市场
- [x] **MKT-02**: 操作者可以让机器人为每个候选市场保存正确的机场站点、温区、结算规则、condition/token 标识
- [x] **MKT-03**: 操作者可以让机器人在市场缺少规则映射、单位不一致或天气数据过期时拒绝交易该市场
- [x] **MKT-04**: 操作者可以让机器人基于当前可执行盘口信息（bid/ask、tick size、市场状态）评估是否值得挂单

### Probability & Strategy

- [x] **STRAT-01**: 操作者可以让机器人根据多源天气预测为每个温区计算 band probability，而不是只看单点温度预测
- [ ] **STRAT-02**: 操作者可以为低价 YES 策略配置独立的价格、概率、时间窗与仓位阈值
- [ ] **STRAT-03**: 操作者可以为高价 NO 策略配置独立的价格、概率、时间窗与仓位阈值
- [ ] **STRAT-04**: 操作者可以让机器人在低价 YES 和高价 NO 两个策略腿之间独立分配资金，并限制每条腿的最大风险暴露

### Order Lifecycle

- [ ] **ORDR-01**: 操作者可以让机器人为候选机会生成被动限价单意图，并支持 GTC 或带过期时间的 GTD 挂单
- [ ] **ORDR-02**: 操作者可以查看每笔订单的完整生命周期状态：planned、working、partial、filled、canceled、expired
- [ ] **ORDR-03**: 操作者可以让机器人在天气预测或盘口变化后自动刷新、撤销或放弃已经变差的挂单
- [ ] **ORDR-04**: 操作者可以在机器人重启后恢复未完成订单、持仓和事件账本，而不会丢失状态一致性

### Simulation & Validation

- [ ] **SIM-01**: 操作者可以在不发送真实订单的前提下运行完整的 paper trading 模式
- [ ] **SIM-02**: 操作者可以让 paper 模式保守建模下单延迟、排队、部分成交、touch-not-fill 与撤单延迟
- [ ] **SIM-03**: 操作者可以回放订单和成交事件，用来检验成交假设是否过于乐观

### Risk Controls

- [ ] **RISK-01**: 操作者可以为单市场、单城市、单日期、单策略腿和总资金使用率设置暴露上限
- [ ] **RISK-02**: 操作者可以阻止机器人在相关性过高的温区或相互冲突的 YES/NO 暴露上继续加仓
- [x] **RISK-03**: 操作者可以要求机器人在缺少关键市场元数据、规则映射或实时行情时自动停单

### Observability

- [ ] **OBS-01**: 操作者可以查看每个候选机会为何被接受、拒绝、缩量或降价
- [ ] **OBS-02**: 操作者可以查看每笔订单为何被挂出、刷新、撤销、部分成交或完全成交
- [ ] **OBS-03**: 操作者可以查看按策略腿、城市、日期和市场维度聚合的风险、PnL、fill quality 与未成交统计
- [ ] **OBS-04**: 操作者可以导出结构化执行日志，用于后续复盘、调参与 live readiness 审核

## v2 Requirements

### Live Trading

- **LIVE-01**: 操作者可以在通过上线闸门后切换到小额真钱 shadow/live 模式
- **LIVE-02**: 操作者可以完成 Polymarket 真实下单所需的认证、allowance、heartbeat 与健康检查

### Advanced Validation

- **VAL-01**: 操作者可以运行 forecast drift、流动性抽干、临近结算冲击等场景化压力测试
- **VAL-02**: 操作者可以获得更细粒度的 queue quality / fill quality 评分与误差校准

### Expansion

- **EXP-01**: 操作者可以在天气温度市场跑稳后扩展到更多天气子品类或其他 Polymarket 市场

## Out of Scope

| Feature | Reason |
|---------|--------|
| v1 真实自动下单 | 当前阶段先验证策略、执行和仿真闭环，避免真钱放大执行错误 |
| 默认 taker 追单成交 | 会直接侵蚀低价 YES / 高价 NO 的不对称收益结构 |
| 非天气类通用市场支持 | 会让首个里程碑失焦，削弱天气场景专用优化 |
| 多用户 Web SaaS 界面 | 当前系统只服务单个操作者，优先做执行与风控而不是产品化 |
| 黑盒 ML 自动定价器 | 当前更需要可解释概率与执行日志，避免模型掩盖数据/执行问题 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MKT-01 | Phase 1 | Complete |
| MKT-02 | Phase 1 | Complete |
| MKT-03 | Phase 1 | Complete |
| MKT-04 | Phase 2 | Complete |
| STRAT-01 | Phase 2 | Complete |
| STRAT-02 | Phase 2 | Pending |
| STRAT-03 | Phase 2 | Pending |
| STRAT-04 | Phase 3 | Pending |
| ORDR-01 | Phase 4 | Pending |
| ORDR-02 | Phase 4 | Pending |
| ORDR-03 | Phase 4 | Pending |
| ORDR-04 | Phase 4 | Pending |
| SIM-01 | Phase 5 | Pending |
| SIM-02 | Phase 5 | Pending |
| SIM-03 | Phase 5 | Pending |
| RISK-01 | Phase 3 | Pending |
| RISK-02 | Phase 3 | Pending |
| RISK-03 | Phase 2 | Complete |
| OBS-01 | Phase 2 | Pending |
| OBS-02 | Phase 4 | Pending |
| OBS-03 | Phase 6 | Pending |
| OBS-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-17*
*Last updated: 2026-04-17 after roadmap creation*
