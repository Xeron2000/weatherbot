---
phase: 02-候选定价与双策略筛选
plan: 03
subsystem: testing
tags: [polymarket, strategy, config, candidates, pytest]
requires:
  - phase: 02-候选定价与双策略筛选
    provides: bucket_probabilities and quote_snapshot execution truth
provides:
  - independent `yes_strategy` and `no_strategy` config blocks
  - dual strategy evaluators for YES_SNIPER and NO_CARRY
  - persisted `candidate_assessments` for each ready market bucket
affects: [phase-02-reporting, candidate-selection, phase-03-order-routing]
tech-stack:
  added: []
  patterns: [dual-strategy config blocks, candidate_assessment persistence, reprice-vs-reject strategy outcomes]
key-files:
  created: [tests/test_phase2_strategies.py]
  modified: [bot_v2.py, config.json]
key-decisions:
  - "策略配置拆成 yes_strategy/no_strategy 两个独立块，不再让单一 max_price/min_ev 统治所有腿。"
  - "candidate_assessments 直接持久化到 market JSON，作为后续报告与订单层共用事实源。"
patterns-established:
  - "Dual evaluator pattern: 每个 bucket 同时产出 YES_SNIPER 与 NO_CARRY 两条 assessment。"
  - "Assessment status pattern: price 不满足时标为 reprice，执行面/配置面失败时标为 rejected。"
requirements-completed: [STRAT-02, STRAT-03]
duration: 1 min
completed: 2026-04-17
---

# Phase 02 Plan 03: 候选定价与双策略筛选 Summary

**扫描主循环现已为每个 ready bucket 同时生成 YES_SNIPER 与 NO_CARRY 的 `candidate_assessments`，并从独立策略配置读取各自阈值。**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-17T12:04:52Z
- **Completed:** 2026-04-17T12:05:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 将 `config.json` 从单组全局入场阈值升级为 `yes_strategy` / `no_strategy` 两个独立配置块。
- 在 `bot_v2.py` 中新增 YES/NO evaluator helper，并区分 accepted / size_down / reprice / rejected 四类候选状态。
- scan loop 现会持久化 `candidate_assessments`，对同一 bucket 同时保留 YES/NO 两条策略腿的结论与理由。

## Task Commits

Each task was committed atomically:

1. **Task 1/2 RED: 增加 YES/NO 分腿配置与 dual strategy 回归合同** - `dd8dc2e` (test)
2. **Task 1/2 GREEN: 持久化双策略 candidate assessments** - `6c1613a` (feat)

**Plan metadata:** pending

_Note: 本计划的 Task 1/Task 2 共享同一回归文件，最终在一个实现提交中完成 evaluator 与 scan wiring。_

## Files Created/Modified
- `config.json` - 新增 `yes_strategy` 与 `no_strategy` 配置块。
- `bot_v2.py` - 加载双策略配置，新增 evaluator helper，并持久化 `candidate_assessments`。
- `tests/test_phase2_strategies.py` - 覆盖独立阈值、同 bucket 双腿分叉结果与 assessment 持久化合同。

## Decisions Made
- price 不满足但 execution/probability 仍有意义时用 `reprice`，避免把可继续观察的 bucket 混同为纯 reject。
- `candidate_assessments` 至少包含 `strategy_leg`、`token_side`、`range`、`aggregate_probability`、`fair_price`、`quote_context`、`status`、`reasons`、`size_multiplier`，为后续报告和订单层保留稳定字段。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 为双策略 evaluator 增加配置缺字段检测**
- **Found during:** Task 1 (增加 YES/NO 分腿配置与 evaluator 合同)
- **Issue:** 若 `yes_strategy` / `no_strategy` 缺关键阈值字段，旧逻辑会静默回退默认值，违背 plan threat model 对显式配置错误的要求。
- **Fix:** 新增 `missing_strategy_fields()`，让 evaluator 产出 `config_missing_*` reason 并走 rejected，而不是悄悄回退旧全局阈值。
- **Files modified:** `bot_v2.py`
- **Verification:** `uv run pytest tests/test_phase2_strategies.py -q` and `uv run pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py -q`
- **Committed in:** `6c1613a`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** 修复收紧了策略配置边界，保证后续 candidate truth 不会被静默默认值污染；无额外架构扩张。

## Issues Encountered
- `fair_yes - ask` 与 `bid - fair_no` 的 edge 更贴近双腿逻辑，因此测试夹具需要按策略腿分别校准价格，才能稳定覆盖 accepted / reprice 场景。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `candidate_assessments` 已成为 Phase 2 候选真相源，后续报告层可直接解释 accept / reject / size_down / reprice。
- Phase 03 可以开始接入订单意图、资金路由或更细的 execution recommendation，而无需再拆策略配置。

## Self-Check: PASSED
- Found `.planning/phases/02-候选定价与双策略筛选/02-03-SUMMARY.md`
- Found commits `dd8dc2e`, `6c1613a`
