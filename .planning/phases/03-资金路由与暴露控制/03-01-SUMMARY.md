---
phase: 03-资金路由与暴露控制
plan: 01
subsystem: testing
tags: [risk-router, exposures, routing, pytest, config]
requires:
  - phase: 02-候选定价与双策略筛选
    provides: candidate_assessments with YES_SNIPER / NO_CARRY truth
provides:
  - conservative `risk_router` config defaults
  - pure worst-loss routing helpers in `bot_v2.py`
  - router regression coverage for caps, conflicts, and sorting
affects: [phase-03-scan-routing, phase-03-reporting, future-order-routing]
tech-stack:
  added: []
  patterns: [worst-loss routing helpers, per-leg budget config, deterministic reason codes]
key-files:
  created: [tests/test_phase3_router.py]
  modified: [config.json, bot_v2.py]
key-decisions:
  - "risk_router 作为独立顶层配置块落地，不把腿级 budget/cap 混回 yes_strategy/no_strategy。"
  - "router 先产出 deterministic reason codes，再由后续 scan/reporting 直接复用，不在展示层重算。"
patterns-established:
  - "Pure router pattern: candidate_worst_loss / route_candidate_assessment / sort_leg_candidates 都可脱离 scan loop 单测。"
  - "Conflict pattern: same bucket opposite side 直接 same_bucket_conflict，同 event 其他 bucket 直接 event_cluster_conflict。"
requirements-completed: [STRAT-04, RISK-01, RISK-02]
duration: 12 min
completed: 2026-04-17
---

# Phase 03 Plan 01: 资金路由与暴露控制 Summary

**独立 YES/NO 预算、最坏损失记账和冲突 reason code 现已在 `bot_v2.py` 中成为可复用的纯函数合同。**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-17T14:10:00Z
- **Completed:** 2026-04-17T14:22:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 在 `config.json` 增加 conservative `risk_router` 配置，显式区分 YES/NO budget 与 leg cap。
- 在 `bot_v2.py` 中新增 worst-loss、cap、冲突和排序 helper，形成 Phase 3 的纯函数路由核心。
- 用 `tests/test_phase3_router.py` 锁定 same-bucket / event-cluster conflict、multi-cap reject 和腿内排序合同。

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: 建立 risk router 配置与纯函数测试合同** - `9de5477` (test)
2. **Task 1 GREEN: 建立 risk router 配置与纯函数测试合同** - `baebd35` (feat)
3. **Task 2: 在 bot_v2.py 实现最坏损失路由 helper** - `f982789` (test)

**Plan metadata:** pending

_Note: Task 2 的补充合同在 Task 1 的实现基础上直接变绿，说明最小 helper 设计已覆盖后续 worst-loss/status 归一化要求。_

## Files Created/Modified
- `config.json` - 新增 `risk_router` conservative defaults。
- `bot_v2.py` - 新增 risk router loader、worst-loss 计算、冲突判断和腿内排序 helper。
- `tests/test_phase3_router.py` - 覆盖 cap、冲突、排序和 status normalization 的 Phase 3 单测合同。

## Decisions Made
- 将 worst-loss 口径定义为腿级策略 size contract，而不是 quote price / entry cost 的函数，确保 budget 和记账维度稳定。
- `route_candidate_assessment()` 只输出 `accepted` 或 `rejected` 两种 route status，保留输入 assessment status 供审计。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Task 2 的新增测试在第一次运行时已直接通过，说明 Task 1 helper 设计覆盖范围比计划基线更完整，因此没有额外 GREEN 代码提交。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `scan_and_update()` 已可直接消费 routing helpers，不必再把风险规则写回过程逻辑里。
- `risk_router` defaults 和 reason codes 已稳定，后续 plan 可专注持久化与 release 生命周期。

## Self-Check: PASSED
- Found `.planning/phases/03-资金路由与暴露控制/03-01-SUMMARY.md`
- Found commits `9de5477`, `baebd35`, `f982789`

---
*Phase: 03-资金路由与暴露控制*
*Completed: 2026-04-17*
