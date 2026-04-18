---
phase: 05-保守 paper execution 与回放验证
plan: 03
subsystem: testing
tags: [replay, cli, paper-execution, observability, pytest]
requires:
  - phase: 05-保守 paper execution 与回放验证
    provides: conservative paper execution wiring and persisted execution ledger from 05-02
provides:
  - replay CLI for per-order paper execution timelines
  - fill quality summary from persisted execution facts
  - Phase 5 README verification entry for replay truth sources
affects: [phase-06-readiness, operator-observability, replay-audit]
tech-stack:
  added: []
  patterns: [persisted execution replay, exact replay filters, fill-quality CLI summary]
key-files:
  created: [.planning/phases/05-保守 paper execution 与回放验证/05-03-SUMMARY.md]
  modified: [bot_v2.py, README.md, tests/test_phase5_replay.py]
key-decisions:
  - "Replay 只读取 execution_events / paper_execution_state / order_history，不在 view 层重跑 paper engine。"
  - "market_id 与 order_id 过滤采用严格精确匹配，未命中时直接提示，避免操作者误看错单。"
patterns-established:
  - "Replay reporting pattern: collect_replay_orders() -> events_for_order() -> build_replay_fill_quality() -> print_replay()."
  - "Operator audit pattern: 逐笔 timeline 先展示事件，再附带可直接映射到 queue/cancel/buffer 参数的 tuning hints。"
requirements-completed: [SIM-03]
duration: 6 min
completed: 2026-04-18
---

# Phase 05 Plan 03: 提供 replay CLI、fill quality 回放与 README 验证说明 Summary

**bot_v2.py 现在可以直接回放单笔 paper order 的 submit/touch/queue/partial/fill/cancel 时间线，并用 fill quality 摘要指出该调哪些保守执行参数。**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-18T09:10:49+08:00
- **Completed:** 2026-04-18T09:17:06+08:00
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `tests/test_phase5_replay.py` 锁定 replay 的 operator-facing 合同，覆盖 filled / canceled 时间线、fill quality 摘要和严格过滤行为。
- `bot_v2.py` 新增 `print_replay()` 与 replay helper，直接从 persisted `execution_events`、`paper_execution_state`、`order_history` 回放订单证据。
- `README.md` 新增 Phase 5 Verification，给出回归命令、replay CLI 入口和三类 replay truth sources。

## Task Commits

Each task was committed atomically:

1. **Task 1: 为 replay 输出建立 operator-facing 合同** - `193c8c3` (test)
2. **Task 2: 实现 replay CLI、fill quality 摘要与 README 验证说明** - `f8bc147` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `tests/test_phase5_replay.py` - 定义 replay 时间线、fill quality 摘要和 market/order 过滤的可见性合同。
- `bot_v2.py` - 增加 replay order 收集、事件过滤、fill quality 计算、timeline 打印和 `python bot_v2.py replay` CLI。
- `README.md` - 补充 Phase 5 验证命令、truth sources 和 replay 使用示例。

## Decisions Made
- 用 `execution_events` 的 `order_id` 精确切分时间线，避免在同一 market 的多笔历史订单之间串台。
- fill quality 摘要直接暴露 `queue_wait_ms`、`partial_fill_slices`、`cancel_delay_ms`、`adverse_buffer_hits`，并把它们映射回具体 paper 参数名，方便操作者调参。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 现在已经具备逐笔 replay 入口，操作者可以直接复查保守成交假设，不必翻 raw JSON。
- Phase 6 可以在这些逐笔 replay / fill quality facts 之上做更高层聚合报告，而不需要回填执行真相源。

## Self-Check: PASSED
- Found `.planning/phases/05-保守 paper execution 与回放验证/05-03-SUMMARY.md`
- Found commits `193c8c3`, `f8bc147`

---
*Phase: 05-保守 paper execution 与回放验证*
*Completed: 2026-04-18*
