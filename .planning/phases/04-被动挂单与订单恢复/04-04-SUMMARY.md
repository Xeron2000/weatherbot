---
phase: 04-被动挂单与订单恢复
plan: 04
subsystem: testing
tags: [reporting, orders, cli, readme, order-state]
requires:
  - phase: 04-被动挂单与订单恢复
    provides: restored order_state, active_order, and order_history facts from 04-03
provides:
  - operator-facing order lifecycle summary in status/report
  - terminal order reason rollups from persisted order history
  - README guidance for Phase 4 regression and stored order facts
affects: [operator-observability, manual-verification, phase-05-paper-execution]
tech-stack:
  added: []
  patterns: [persisted-order reporting, CLI lifecycle sections, phase verification docs]
key-files:
  created: [tests/test_phase4_reporting.py, .planning/phases/04-被动挂单与订单恢复/04-04-SUMMARY.md]
  modified: [bot_v2.py, README.md]
key-decisions:
  - "Order lifecycle summary uses restored status_counts plus persisted active_order/order_history facts, without recomputing lifecycle in the view layer."
  - "README Phase 4 docs stay phase-scoped: one regression command plus the three new order truth sources."
patterns-established:
  - "Order reporting pattern: risk/candidate sections stay separate, then status/report print a dedicated Order lifecycle block before trade details."
  - "Order reason summary pattern: filled/canceled/expired reasons are counted from terminal order_history facts and grouped by terminal status."
requirements-completed: [OBS-02, ORDR-02]
duration: 3 min
completed: 2026-04-17
---

# Phase 04 Plan 04: 被动挂单与订单恢复 Summary

**CLI 现在会直接展示被动订单的 lifecycle counts、active order 明细和 terminal reason summary，并在 README 里给出 Phase 4 回归入口与真相源说明。**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-17T23:39:55+08:00
- **Completed:** 2026-04-17T15:43:24Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `print_status()` / `print_report()` 新增 `Order lifecycle` 小节，直接展示 persisted `status_counts`、unfinished `active_order` 明细和 terminal reason summary。
- `tests/test_phase4_reporting.py` 锁定 operator-facing 合同，覆盖 planned / working / partial / filled / canceled / expired 可见性与 reason summary 文案。
- `README.md` 补齐 Phase 4 Verification、`active_order` / `order_history` / `order_state` 字段说明，并修正遗留 `weatherbet.py` 命令引用。

## Task Commits

Each task was committed atomically:

1. **Task 1: 为 CLI order summary 建立 operator-facing 合同** - `fff0d99` (test)
2. **Task 2: 实现 order reporting 并补 README 验证说明** - `3741599` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `tests/test_phase4_reporting.py` - 覆盖 status/report 的 order lifecycle counts、active order 详情和 terminal reason summary。
- `bot_v2.py` - 新增 `print_order_summary()` 及终态 reason 聚合 helper，并在 status/report 中输出独立订单生命周期段。
- `README.md` - 增加 Phase 4 Verification、订单真相源文档，并统一 CLI 命令到 `bot_v2.py`。

## Decisions Made
- 订单摘要的 counts 读取 `state["order_state"]`，active order 明细与 terminal reasons 读取 `active_order` / `order_history`，避免展示层重算生命周期。
- terminal reasons 按 `filled` / `canceled` / `expired` 三类分组输出，便于操作者区分成交、撤单和失效原因。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

- README 里还残留一处 `weatherbet.py` Phase 2 命令引用；已在本计划内一并修正，保持验证入口与当前仓库脚本一致。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- 操作者已经能在 CLI 中直接观察 working / partial / canceled / expired / filled 轨迹，Phase 5 可继续在此基础上验证保守 paper fill 假设。
- README 已补全 Phase 4 回归入口，后续 replay / execution phase 可以直接复用订单真相源文档。

## Self-Check: PASSED
- Found `.planning/phases/04-被动挂单与订单恢复/04-04-SUMMARY.md`
- Found commits `fff0d99`, `3741599`

---
*Phase: 04-被动挂单与订单恢复*
*Completed: 2026-04-17*
