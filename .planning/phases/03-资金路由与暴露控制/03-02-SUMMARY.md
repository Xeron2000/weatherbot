---
phase: 03-资金路由与暴露控制
plan: 02
subsystem: api
tags: [scan-loop, risk-ledger, reservations, routing, pytest]
requires:
  - phase: 03-资金路由与暴露控制
    provides: pure routing helpers and conservative risk_router defaults
provides:
  - persisted `risk_state` in `data/state.json`
  - persisted `route_decisions` and `reserved_exposure` in market JSON
  - scan loop routing gate before legacy entry seam
affects: [phase-03-reconciliation, phase-03-reporting, phase-04-order-intents]
tech-stack:
  added: []
  patterns: [state-ledger rebuild from markets, route-decision persistence, router-gated entry seam]
key-files:
  created: [tests/test_phase3_scan_loop.py]
  modified: [bot_v2.py]
key-decisions:
  - "risk_state 每轮由已持久化 reservations 重建，避免 budget/accounting 只留在内存。"
  - "旧的直接开仓 seam 保留，但必须先命中 accepted YES route 才允许继续。"
patterns-established:
  - "Ledger pattern: state.json 聚合 bankroll 级 risk_state，market JSON 保留 route_decisions 和 reserved_exposure 审计轨迹。"
  - "Routing seam pattern: candidate_assessments → route_decisions → reserved_exposure → legacy best_signal gate。"
requirements-completed: [STRAT-04, RISK-01]
duration: 15 min
completed: 2026-04-17
---

# Phase 03 Plan 02: 资金路由与暴露控制 Summary

**scan loop 现在会把每轮候选先路由成 `route_decisions`，并把 reserved worst-loss 同步写入 `risk_state` 与 market JSON。**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-17T14:22:00Z
- **Completed:** 2026-04-17T14:37:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `load_state()` 现在补齐并恢复 `risk_state`，含 YES/NO budget、global reserved worst-loss 与 city/date/event exposure。
- `scan_and_update()` 在 candidate 阶段后新增 routing seam，持久化 `route_decisions` 和 `reserved_exposure`。
- 旧的 `best_signal` 开仓路径被 router gate 约束，没有 accepted YES route 时不会再偷偷进入 legacy entry。

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: 为 scan loop 风险路由持久化建立集成合同** - `c3effb0` (test)
2. **Task 2: 将 risk ledger 与 route decisions 接入 scan_and_update** - `03a68ce` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `bot_v2.py` - 增加 `risk_state`、`route_decisions`、`reserved_exposure` 和 scan loop routing gate。
- `tests/test_phase3_scan_loop.py` - 覆盖 route persistence、per-leg budget ledger 和 leg-order-before-cap 集成回归。

## Decisions Made
- `risk_state` 的 source of truth 采用“从 market reservations 回放重建”，而不是只在 scan 过程中增量修改临时值。
- `reserved_exposure` 保持 singular current reservation，审计细节统一放到 `route_decisions[]`。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- 同一 market 内多个候选的约束顺序需要同时满足腿内排序、冲突与 global cap；最终通过集成测试把顺序钉死在 routing seam 上。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- reservation 已有持久化总账和 per-market trace，后续可以直接在连续扫描里做 release/reconcile。
- reporting 层已经有稳定事实源，不需要在 Phase 4/6 再反推 risk usage。

## Self-Check: PASSED
- Found `.planning/phases/03-资金路由与暴露控制/03-02-SUMMARY.md`
- Found commits `c3effb0`, `03a68ce`

---
*Phase: 03-资金路由与暴露控制*
*Completed: 2026-04-17*
