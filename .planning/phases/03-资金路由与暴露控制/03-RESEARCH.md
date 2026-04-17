# Phase 3: 资金路由与暴露控制 - Research

**Researched:** 2026-04-17
**Domain:** 双策略资金池、最坏损失暴露聚合、router reject/release 生命周期
**Confidence:** MEDIUM

## User Constraints

### Locked Decisions
- YES / NO 必须使用独立资金池，预算按总 bankroll 百分比定义，每轮扫描刷新，且不能互借预算。[VERIFIED: `.planning/phases/03-资金路由与暴露控制/03-CONTEXT.md` D-01~D-05]
- 所有 cap 与预留一律按最坏损失统计，不按 notional / entry cost；单市场、单城市、单日期、单 event、单腿、全局资金使用率都要可配置，任一命中即拦截。[VERIFIED: `03-CONTEXT.md` D-06~D-10]
- 同一 city+date event 的多 bucket 默认按最坏路径聚合；同 bucket 禁止 YES/NO 对冲；同 event bucket 默认视为同相关簇，新冲突候选默认拒绝，保留已有暴露。[VERIFIED: `03-CONTEXT.md` D-11~D-14]
- 路由顺序必须先分腿、后全局；腿内按 edge 排序，接近时再看流动性；被拒候选必须持久化 reject reason，不做跨腿重排。[VERIFIED: `03-CONTEXT.md` D-15~D-19]
- 预留从“candidate 通过 router、准备进入后续下单意图”时开始，占用/释放都按最坏损失全额，候选失效时立即释放并记录原因。[VERIFIED: `03-CONTEXT.md` D-20~D-23]

### the agent's Discretion
- 保守模板的具体 cap 默认值尚未锁定，可在不违背 D-06~D-10 的前提下给出初值，并保留配置入口。[VERIFIED: `03-CONTEXT.md`]
- 状态与 market JSON 新字段命名可沿用现有 JSON 风格自行设计，但必须成为后续 Phase 4 订单层可复用的事实源。[VERIFIED: `03-CONTEXT.md`; VERIFIED: `bot_v2.py:1128-1194`]

### Deferred Ideas (OUT OF SCOPE)
- 真实下单、订单状态机、paper fill realism、自动缩量重试都不在本 phase 交付范围内。[VERIFIED: `.planning/ROADMAP.md`; VERIFIED: `03-CONTEXT.md`]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STRAT-04 | YES/NO 两腿独立分配资金并限制每腿最大风险暴露 | 需要从当前 `yes_strategy` / `no_strategy` 再扩出 `risk_router` 配置与 per-leg budget ledger，并把 `candidate_assessments` 升级为可路由输入而非仅解释输出。[VERIFIED: `config.json`; VERIFIED: `bot_v2.py:951-1085`; VERIFIED: `.planning/REQUIREMENTS.md`] |
| RISK-01 | 单市场、单城市、单日期、单策略腿、总资金使用率可配置上限 | 适合在 `load_state()` / `save_state()` 增加全局 risk ledger，同时在 market JSON 写入 route decision 与 exposure facts，避免展示层重算。[VERIFIED: `bot_v2.py:1128-1194`; VERIFIED: `03-CONTEXT.md`] |
| RISK-02 | 阻止高相关 bucket 或冲突 YES/NO 暴露继续加仓 | 需要 event 级聚合 helper，基于已持久化 `candidate_assessments`、`position` 和新 `route_decisions` / `reserved_exposure` 字段做最坏路径冲突拦截。[VERIFIED: `bot_v2.py:1431-1655`; VERIFIED: `03-CONTEXT.md`] |
</phase_requirements>

## Summary

Phase 3 不是“再给 candidate 打一个 size multiplier”，而是把 Phase 2 的 `candidate_assessments` 升级成 **资金路由真相源**：哪些候选通过、为什么被拒、占用了哪条腿多少最坏损失、冲突来自哪里、何时释放预留，都必须落盘且可在 CLI 里直接看到。[VERIFIED: `.planning/phases/02-候选定价与双策略筛选/02-03-SUMMARY.md`; VERIFIED: `.planning/phases/02-候选定价与双策略筛选/02-04-SUMMARY.md`]

当前代码的主要缺口有三处：
1. `state.json` 只有 balance / win-loss 汇总，没有 per-leg budget 或暴露账本。[VERIFIED: `bot_v2.py:1178-1188`]
2. `scan_and_update()` 仍然把 candidate 直接走向旧的 YES 单腿开仓逻辑，没有“router -> reserve -> intent seam”。[VERIFIED: `bot_v2.py:1506-1595`]
3. market JSON 只有 `candidate_assessments`，还没有 route decision、reserved exposure、release reason 这类后续订单层要复用的事实字段。[VERIFIED: `bot_v2.py:1128-1169`]

**Primary recommendation:** 保持 `bot_v2.py` 单文件 + 本地 JSON 的 brownfield 形态，在本 phase 内新增三层事实：
- `risk_router` 配置（预算比例 + cap 模板）
- state 级 ledger（per-leg / global usage 与 event exposure rollup）
- market 级 route ledger（route decision、reserved worst loss、release reason）

不要在本 phase 提前引入订单对象、数据库或自动净额优化器。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`; VERIFIED: `.planning/PROJECT.md`]

## Project Constraints (from AGENTS.md / PROJECT)

- brownfield 演进，不重写、不拆包，继续以 `bot_v2.py` 为主战场。[VERIFIED: `/home/xeron/Coding/weatherbot/AGENTS.md`; VERIFIED: `.planning/PROJECT.md`]
- v1 仍是模拟交易；Phase 3 只建立资金占用和暴露控制 seam，不生成真实订单副作用。[VERIFIED: `.planning/PROJECT.md`; VERIFIED: `.planning/ROADMAP.md`]
- 运行时继续使用 Python CLI + 本地 JSON 持久化，不引入数据库或额外服务。[VERIFIED: `.planning/codebase/STACK.md`; VERIFIED: `.planning/PROJECT.md`]
- 现有测试已经采用 pytest + monkeypatch + tmp_path 文件系统隔离；Phase 3 应沿用同一模式增加 router/scan/reporting 回归。[VERIFIED: `tests/conftest.py`; VERIFIED: `tests/test_phase2_strategies.py`; VERIFIED: `.planning/codebase/TESTING.md`]

## Recommended Architecture Patterns

### Pattern 1: Candidate assessment → route decision → reservation

**What:** Phase 2 的 `candidate_assessments[]` 保持原样作为输入；Phase 3 新增 `route_candidate()` / `route_market_candidates()` 之类纯 helper，对每条 assessment 产出 `route_decision`，至少包含：
- `strategy_leg`
- `status` (`accepted`, `rejected`, `released`)
- `reserved_worst_loss`
- `reasons[]`
- `conflict_keys[]`
- `budget_bucket`（yes/no/global）

**Why:** 这样后续 Phase 4 可以直接消费 route 通过的候选生成 order intent，而不用重新推断风控边界。[VERIFIED: `02-03-SUMMARY.md`; VERIFIED: `03-CONTEXT.md`]

### Pattern 2: State ledger is global truth; market ledger is trace truth

**What:**
- `data/state.json` 持久化聚合后的 budget / exposure counters
- `data/markets/*.json` 持久化单 market 的 route decision、reserved exposure、release reason

**Why:** 这与当前项目“运行时事实先落盘，再由 CLI 直接读取展示”的模式一致，也避免 reporting 层重算暴露。[VERIFIED: `.planning/codebase/ARCHITECTURE.md`; VERIFIED: `03-CONTEXT.md`]

### Pattern 3: Worst-path event clustering, no netting

**What:** 同一 `city+date` event 内，把 bucket 暴露视为相关簇；新候选命中同簇时，只要会提高最坏路径损失，就直接拒绝。不要把 YES/NO 做净额化，不要做 bucket 组合优化。[VERIFIED: `03-CONTEXT.md` D-11~D-14]

**Why:** 这是本 phase 的核心锁定决策；任何“看起来能对冲所以放行”的实现都会违背上下文。

## Proposed Data Shape

### `config.json`

```json
{
  "risk_router": {
    "yes_budget_pct": 0.30,
    "no_budget_pct": 0.70,
    "global_usage_cap_pct": 0.85,
    "per_leg_hard_cap_pct": 0.35,
    "per_market_cap_pct": 0.08,
    "per_city_cap_pct": 0.20,
    "per_date_cap_pct": 0.20,
    "per_event_cap_pct": 0.20
  }
}
```

> 百分比具体值可由 planner 调整，但结构应支持 D-01~D-10 需要的独立预算与多层 cap。[ASSUMED]

### `data/state.json`

```json
{
  "risk_state": {
    "bankroll": 10000.0,
    "global_reserved_worst_loss": 0.0,
    "legs": {
      "YES_SNIPER": {"budget": 3000.0, "reserved": 0.0},
      "NO_CARRY": {"budget": 7000.0, "reserved": 0.0}
    },
    "city_exposure": {},
    "date_exposure": {},
    "event_exposure": {}
  }
}
```

### `data/markets/*.json`

```json
{
  "route_decisions": [],
  "reserved_exposure": {
    "strategy_leg": "YES_SNIPER",
    "reserved_worst_loss": 0.0,
    "reserved_at": null,
    "release_reason": null
  }
}
```

## Anti-Patterns to Avoid

- 继续用 `balance -= cost` 代表风险占用：这只适合旧的单腿直接开仓，不满足 D-06 / D-22 的 worst-loss 口径。[VERIFIED: `bot_v2.py:1585-1587`]
- 在 reporting 层重算 per-leg budget 与 event exposure：会重复踩“数据已存但展示层另算一套”的坑。[VERIFIED: `02-04-SUMMARY.md`]
- 新候选冲突时自动替换旧候选或跨腿挪预算：违背 D-09 / D-14 / D-19。[VERIFIED: `03-CONTEXT.md`]
- 把 release 放到订单取消后再说：Phase 3 明确要求 candidate 降级/消失即释放，为 Phase 4 留 seam，不可拖后实现。[VERIFIED: `03-CONTEXT.md` D-21~D-23]

## Validation Architecture

- **Unit/TDD layer:** 先给 router helper 建 pytest 合同，覆盖独立预算、multi-cap 拒绝、event 冲突、same-bucket YES/NO 互斥、release reason。
- **Scan integration layer:** 用 tmp_path + monkeypatch 运行 `scan_and_update()`，断言 state.json / market JSON 中的 risk ledger、route decisions、reserved exposure 写入正确。
- **Reporting layer:** `print_status()` / `print_report()` 直接读取持久化 risk facts，展示 per-leg budget usage、event/city/date exposure 与 reject/release reasons。
- **Quick command:** `uv run pytest tests/test_phase3_router.py -q`
- **Full command:** `uv run pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py tests/test_phase2_reporting.py tests/test_phase3_router.py tests/test_phase3_scan_loop.py tests/test_phase3_reporting.py -q`

## Assumptions Log

| # | Claim | Risk if Wrong |
|---|-------|---------------|
| A1 | `risk_router` 适合新增为顶层配置块，而不是塞回 `yes_strategy` / `no_strategy` | 若用户更想所有 cap 分散在腿配置里，计划中的 config 结构需要调整。 |
| A2 | Phase 3 可以把“候选通过 router”视为 reserved seam，而不必真的创建 order intent 对象 | 若用户要求本 phase 就显式生成 planned order artifact，则 Phase 4 边界会前移。 |
| A3 | per-city / per-date / per-event 聚合用 state-level JSON ledger 足够，不需要额外索引文件 | 若后续 reporting 需要高频查询，Phase 6 可能再演进结构。 |

## Open Questions

1. 保守模板的默认 cap 百分比取值应多保守？
   - 建议：先让 planner 选一组能明显小于 budget 的默认值，并全部可配置。
2. reserved exposure 是否只保留单条通过的 route，还是保留全部 rejected 路由记录？
   - 建议：market JSON 保留全部 `route_decisions[]`，另设一个 `reserved_exposure` 指向当前生效预留，兼顾审计与后续消费。
