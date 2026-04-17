# Phase 3: 资金路由与暴露控制 - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段只定义双策略资金路由与暴露控制口径：如何在低价 YES 与高价 NO 两条腿之间独立分配预算、如何统计和限制暴露、冲突候选如何被拒绝、以及资金预留何时占用/释放。

本阶段不进入真实下单、订单生命周期或成交仿真；这些仍属于后续阶段。

</domain>

<decisions>
## Implementation Decisions

### 资金池结构
- **D-01:** YES / NO 使用**独立资金池**，不是共享单池。
- **D-02:** 两条腿预算以**总 bankroll 百分比**定义，而不是固定金额。
- **D-03:** 预算可用额度按**每轮扫描刷新**。
- **D-04:** YES / NO 之间**不能互相借预算**。
- **D-05:** 默认初始配比为 **YES 30 / NO 70**。

### 暴露统计与上限口径
- **D-06:** 所有 cap 统一按**最坏损失**统计，不按名义 notional 或入场成本统计。
- **D-07:** 单市场、单城市、单日期、单 city+date event、单策略腿、总资金使用率都应**可配置且任一命中即生效**。
- **D-08:** 单策略腿采用**双保险**：既有独立资金池，也有单腿 hard cap。
- **D-09:** 总资金使用率触顶时，router **直接拒单**，不自动替换已有占用。
- **D-10:** 默认 cap 风格采用**保守模板**，先优先保命，再在后续验证中放宽。

### 冲突与相关性处理
- **D-11:** 同一 city+date event 的多温区暴露按**最坏路径聚合**，默认不做净额化。
- **D-12:** 同一个 bucket 上，**不允许同时存在 YES 和 NO** 暴露。
- **D-13:** 同一 event 下所有 bucket 默认视为**同一相关簇**；相邻/重叠 bucket 优先触发冲突拦截。
- **D-14:** 新候选若与已有暴露冲突，默认**拒绝新候选**，保留已有暴露一致性。

### 路由优先级
- **D-15:** 先按**分腿独立路由**，再受全局 cap 二次拦截；不做全候选统一竞争。
- **D-16:** 同一条腿内部候选按 **edge** 从高到低排序。
- **D-17:** 分数接近时，tie-breaker 先看**流动性**。
- **D-18:** 被预算或 cap 拒绝的候选必须**保留 reject reason**，不能静默丢弃。
- **D-19:** 当全局 cap 不足时，**不做跨腿重排**；保持 YES 30 / NO 70 的分腿设计。

### 预留与释放时机
- **D-20:** 资金在**候选通过 router、准备进入后续下单意图**时开始视为已占用，而不是在 candidate 阶段或成交后才占用。
- **D-21:** 预留资金在**失效即释放**：候选被淘汰、订单取消/过期、或仓位关闭时立即回收。
- **D-22:** 预留金额按**最坏损失全额**记账，和 cap 口径保持一致。
- **D-23:** 重新扫描后若原候选降级或消失，预留应**立即释放并记录原因**。

### the agent's Discretion
- 保守模板下单市场 / 单城市 / 单日期 / 单 event / 单腿 / 全局 cap 的**具体默认百分比**，由 researcher + planner 基于现有策略结构给出初值。
- `state.json` / market JSON 中新增字段的**精确命名**与数据结构，可以由 planner 决定，但必须保持现有 JSON 持久化风格。
- router 是否在未来支持“自动缩量后再试一次”只保留为 seam；Phase 3 首版按硬拒绝落地。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria, and dependency boundary.
- `.planning/REQUIREMENTS.md` — `STRAT-04`, `RISK-01`, `RISK-02` formal requirement text.
- `.planning/PROJECT.md` — project constraints: v1 simulated only, weather-only scope, brownfield evolution.
- `.planning/STATE.md` — locked carry-forward decisions from Phase 1 and Phase 2.

### Existing architecture and conventions
- `.planning/codebase/ARCHITECTURE.md` — current scan loop, persistence model, and CLI/reporting integration points.
- `.planning/codebase/CONVENTIONS.md` — existing single-file, JSON-first, helper-in-`bot_v2.py` implementation style.
- `.planning/codebase/STACK.md` — runtime/config/persistence environment constraints.

### Current runtime contract
- `README.md` — current config shape, persisted JSON facts, and operator-facing verification expectations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `bot_v2.py::load_state()` / `save_state()` — 现有 bankroll 汇总状态入口，适合扩展 per-leg budget / reserved / exposure counters。
- `bot_v2.py::new_market()` / `load_market()` / `save_market()` / `load_all_markets()` — 现有 market JSON 账本入口，适合挂接 per-market exposure / reserve facts。
- `bot_v2.py::build_candidate_assessments()` + `evaluate_yes_candidate()` / `evaluate_no_candidate()` — 已有双腿候选事实源，适合作为 router 输入。
- `bot_v2.py::print_status()` / `print_report()` / `print_candidate_assessments()` — 已有 CLI 汇总出口，适合展示 per-leg budget 与 exposure rollup。

### Established Patterns
- 配置通过 `config.json` 顶层读取并展开为模块常量；新风险参数应继续走同一路径。
- 运行时事实优先落盘到本地 JSON，再由 CLI 直接读取展示；不要在展示层重算风险事实。
- `bot_v2.py` 继续采用单文件 section 分区与纯函数 helper 风格，不在本阶段提前做包级重构。
- skipped / rejected 场景强调显式 reason code，而不是静默失败。

### Integration Points
- `bot_v2.py::scan_and_update()` 中 candidate 评估之后、实际扣减 `balance` 或创建 `position` 之前，是 Phase 3 router 的主插入点。
- `data/state.json` 需要增加双腿预算、全局已占用额度、以及可能的 city/date/event 聚合视图。
- `data/markets/*.json` 适合增加 exposure / reserve / route decision facts，供后续 Phase 4 订单层继续复用。

</code_context>

<specifics>
## Specific Ideas

- 高价 NO 作为稳定现金流主腿，因此默认资金配比偏向 **NO 70 / YES 30**。
- 风控优先于资金利用率：默认先保守、先拒绝，不做自动组合优化器。
- 路由与暴露统计都应该保留明确 reject / release reasons，方便后续复盘和订单层接入。

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-资金路由与暴露控制*
*Context gathered: 2026-04-17*
