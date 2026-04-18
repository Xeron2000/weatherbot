---
phase: 05-保守 paper execution 与回放验证
plan: 02
subsystem: api
tags: [paper-execution, scan-loop, monitor, persistence, pytest]
requires:
  - phase: 05-保守 paper execution 与回放验证
    provides: paper execution config, event schema, and pure helper contracts from 05-01
provides:
  - conservative paper execution wired into scan_and_update and monitor_active_orders
  - append-only execution evidence persisted across fill and cancel terminal states
  - restart-safe integration regressions for touch-not-fill, partial fill, cancel latency, and resume
affects: [phase-05-replay, operator-observability, runtime-simulation]
tech-stack:
  added: []
  patterns: [paper-engine-only order progression, terminal-only reservation release, persisted execution ledger resume]
key-files:
  created: [.planning/phases/05-保守 paper execution 与回放验证/05-02-SUMMARY.md]
  modified: [bot_v2.py, tests/test_phase5_scan_loop.py]
key-decisions:
  - "scan loop 与 monitor 分支都只通过 simulate_paper_execution_step() 推进订单，不再走 ask<=limit 直接成交捷径。"
  - "candidate downgrade / market_no_longer_ready 只触发 cancel_pending，请求后的 reservation 释放延后到 terminal cancel/fill/expire。"
patterns-established:
  - "Runtime wiring pattern: active_order + quote_snapshot + paper_execution_state -> sync_active_order_with_paper_engine() -> order_history/position/execution_events。"
  - "Resume pattern: load_market()/monitor_active_orders() 直接续跑 persisted paper_execution_state 与 execution_events，不重置排队进度。"
requirements-completed: [SIM-01, SIM-02]
duration: 9 min
completed: 2026-04-18
---

# Phase 05 Plan 02: 把保守 paper execution 接入 scan loop、monitor 与持久化账本 Summary

**scan loop 和 monitor 现在都只通过保守 paper engine 推进 passive order，并把 touch、partial、fill、cancel 延迟证据持续写入持久化 execution ledger。**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-18T00:56:56Z
- **Completed:** 2026-04-18T01:05:55Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `tests/test_phase5_scan_loop.py` 新增 Phase 5 集成回归，覆盖 full scan、monitor、cancel latency 和 restart resume。
- `bot_v2.py` 新增 `sync_active_order_with_paper_engine()`，把 `sync_market_order()` 的 fill/cancel 统一改为消费 persisted paper execution facts。
- terminal fill/cancel 现在会分别建立 position / 释放 reservation，并保留 `execution_events`、`paper_execution_state`、`execution_metrics` 作为 append-only 账本。

## Task Commits

Each task was committed atomically:

1. **Task 1: 为保守 paper scan/monitor wiring 建立集成回归** - `8c06c06` (test)
2. **Task 2: 把 paper execution engine 接入 scan loop、monitor 与持久化账本** - `b575108` (feat)

**Plan metadata:** None - 按用户要求未更新 `.planning/STATE.md` / `.planning/ROADMAP.md`，摘要仅落盘到 SUMMARY 文件。

## Files Created/Modified
- `tests/test_phase5_scan_loop.py` - 锁定 conservative paper execution 的 touch-not-fill、partial→filled、cancel_pending→canceled、restart resume 集成链路。
- `bot_v2.py` - 用 paper engine 接管 scan/monitor fill/cancel wiring，并把 simulated fill price 与 cancel reason 写入持久化 execution facts。

## Decisions Made
- 使用 `sync_active_order_with_paper_engine()` 作为运行时唯一 execution seam，避免 `sync_market_order()` 再次分叉出直接成交逻辑。
- unfinished order 的 reservation 不在 candidate downgrade 时立刻释放，而是在 paper cancel terminal 后释放，防止 cancel latency 期间风险账本提前归零。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

- `reconcile_market_reservation()` 初版会在 candidate downgrade 时立即释放 reservation，破坏 cancel latency 合同；已改为 unfinished order 先进入 `cancel_pending`，terminal 后再释放。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- replay 现在可直接消费 `execution_events`、`execution_metrics` 和 `paper_execution_state` 做 fill quality / latency 回放。
- scan/monitor wiring 已经满足“只读 persisted candidate/order/quote/execution facts”约束，后续 phase 可在此基础上做回放验证与报告扩展。

## Self-Check: PASSED
- Found `.planning/phases/05-保守 paper execution 与回放验证/05-02-SUMMARY.md`
- Found commits `8c06c06`, `b575108`
