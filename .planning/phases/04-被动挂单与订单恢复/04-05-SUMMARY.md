---
phase: 04-被动挂单与订单恢复
plan: 05
subsystem: testing
tags: [orders, reporting, observability, cli, pytest]
requires:
  - phase: 04-被动挂单与订单恢复
    provides: active_order/order_history persistence and order lifecycle reporting from 04-04
provides:
  - explicit unfinished order status in CLI lifecycle details
  - recent terminal orders rendered per entry from persisted order facts
  - OBS-02 regression coverage for per-order reporting visibility
affects: [operator-observability, phase-05-paper-execution, verification]
tech-stack:
  added: []
  patterns: [persisted-order lifecycle reporting, per-order terminal audit rows, pytest reporting contracts]
key-files:
  created: [.planning/phases/04-被动挂单与订单恢复/04-05-SUMMARY.md]
  modified: [bot_v2.py, tests/test_phase4_reporting.py]
key-decisions:
  - "Recent terminal orders are rendered directly from markets[*].order_history before grouped reason rollups, so report output stays tied to persisted facts."
  - "Active order detail lines now print explicit status alongside status_reason, limit, tif, expiry, and fill progress to satisfy OBS-02 without changing execution semantics."
patterns-established:
  - "Per-order reporting pattern: print unfinished active_order facts first, then recent terminal order rows, then grouped terminal reason counts."
  - "OBS-02 regression pattern: reporting tests assert concrete order_ids and status/reason fields, not just grouped summaries."
requirements-completed: [OBS-02]
duration: 2 min
completed: 2026-04-17
---

# Phase 04 Plan 05: 被动挂单与订单恢复 Summary

**CLI 现在会逐笔展示 unfinished active order 与 recent terminal orders 的 status/reason/price/fill 事实，补齐 OBS-02 最后可观测性缺口。**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-17T16:04:02Z
- **Completed:** 2026-04-17T16:06:31Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `tests/test_phase4_reporting.py` 先锁死 active order 必须输出显式 `status=`，且 report 必须逐笔打印 `Recent terminal orders`。
- `bot_v2.py` 新增 recent terminal order 收集与逐笔渲染逻辑，直接读取 persisted `active_order` / `order_history` 字段。
- grouped `Recent terminal reasons` 继续保留，但被降级为逐笔明细后的补充汇总，不能再替代 per-order visibility。

## Task Commits

Each task was committed atomically:

1. **Task 1: 锁定逐笔 unfinished / terminal order 可见性的回归合同** - `21cf890` (test)
2. **Task 2: 在 print_order_summary() 中输出逐笔 active/terminal order lifecycle** - `8e4c393` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `tests/test_phase4_reporting.py` - 增加对 `status=partial`、`Recent terminal orders`、具体 terminal order ids 与逐笔 lifecycle 字段的断言。
- `bot_v2.py` - 新增 `collect_recent_terminal_orders()`，并在 `print_order_summary()` 中输出 active order 显式 status 与逐笔 terminal order 明细。
- `.planning/phases/04-被动挂单与订单恢复/04-05-SUMMARY.md` - 记录 gap closure 执行结果。

## Decisions Made
- 逐笔 terminal order 列表按 `updated_at` 倒序直接读取 `order_history`，避免展示层重新推导 lifecycle 或 reason。
- active order 明细只补可观测性字段，不改 scan loop、restore 或订单状态机语义，确保这是纯 reporting gap fix。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

- Python LSP diagnostics 在本地不可用（缺少 `ty`），因此改用精确 pytest 回归作为本计划的完成验证；未影响交付正确性。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 4 的 OBS-02 现在由逐笔 active/terminal order 输出和 pytest 合同共同覆盖，Phase 5 可以直接复用这些事实源验证保守 paper execution 假设。
- 若后续需要更强复盘能力，可在 Phase 6 基于这些逐笔 order rows 做更高层聚合，而无需回填订单原因真相源。

## Self-Check: PASSED
- Found `.planning/phases/04-被动挂单与订单恢复/04-05-SUMMARY.md`
- Found commits `21cf890`, `8e4c393`

---
*Phase: 04-被动挂单与订单恢复*
*Completed: 2026-04-17*
