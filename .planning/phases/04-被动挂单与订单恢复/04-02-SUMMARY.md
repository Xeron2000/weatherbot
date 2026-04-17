---
phase: 04-被动挂单与订单恢复
plan: 02
subsystem: api
tags: [orders, scan-loop, passive-execution, lifecycle, pytest]
requires:
  - phase: 04-被动挂单与订单恢复
    provides: passive order intents, transitions, and loader backfill from 04-01
provides:
  - scan loop wiring that creates working passive orders from accepted reservations
  - deterministic refresh/cancel/expire/fill handling driven by persisted market facts
  - regression coverage for active_order, order_history, and filled-to-position flow
affects: [phase-04-order-restore, phase-04-reporting, phase-05-paper-execution]
tech-stack:
  added: []
  patterns: [order-first scan loop, persisted-facts-only lifecycle decisions, append-only terminal order archive]
key-files:
  created: []
  modified: [bot_v2.py, tests/test_phase4_scan_loop.py]
key-decisions:
  - "scan_and_update 先调用 sync_market_order，再让既有 stop/forecast/resolution 逻辑继续消费 filled 后生成的 position。"
  - "refresh/cancel/expire 只读取 reserved_exposure、candidate_assessments、route_decisions 和 quote_snapshot，不在 wiring 层重算候选。"
  - "terminal 订单统一写入 order_history，partial 保持 active_order，filled/canceled/expired 则清空 active_order。"
patterns-established:
  - "Order sync pattern: ready market + reservation + persisted quote snapshot -> working/partial/filled/canceled/expired。"
  - "Release pattern: candidate_downgraded、market_no_longer_ready、expired 等终态在 cancel/expire 时同步释放 reservation。"
requirements-completed: [ORDR-01, ORDR-02, ORDR-03]
duration: 4 min
completed: 2026-04-17
---

# Phase 04 Plan 02: 被动挂单与订单恢复 Summary

**scan loop 现在会把 accepted reservation 落成真实 passive order，并在报价、候选和 guardrail 变化下自动 refresh、cancel、expire、partial fill、filled。**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-17T15:22:21Z
- **Completed:** 2026-04-17T15:26:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `bot_v2.py` 新增 `sync_market_order()` 及相关 helper，把 accepted route 从“直接开仓”改成“先挂单，再由订单生命周期推进”。
- scan loop 现在会把 `candidate_downgraded`、`market_no_longer_ready`、`quote_repriced`、`expired` 等原因稳定写入终态订单 history。
- `tests/test_phase4_scan_loop.py` 锁定 working / partial / filled / canceled / expired / refresh 合同，并验证 reservation 释放语义。

## Task Commits

Each task was committed atomically:

1. **Task 1: 为 scan loop 订单生命周期建立回归合同** - `8c7fb85` (test)
2. **Task 2: 把 passive order lifecycle 接入 scan_and_update()** - `dbe52bb` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `bot_v2.py` - 新增订单同步 helper，接管 refresh/cancel/expire/fill，并移除 scan loop 里的直接 `best_signal` 开仓路径。
- `tests/test_phase4_scan_loop.py` - 增加 scan lifecycle 回归，覆盖 active_order、order_history、partial/fill、refresh 和 reservation release。

## Decisions Made
- 用 `sync_market_order()` 作为唯一 wiring seam，把订单生成、替换、成交和终态归档集中处理，避免 scan loop 分支继续膨胀。
- filled 订单直接转换为现有 `position` schema，让 stop-loss、forecast_changed 和 resolution 路径无需重写。
- quote 缺失时不猜测成交；只有 `ask <= limit_price` 且 `ask_size` 可用时才推进 partial/filled。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

- 新测试夹具最初把 `get_polymarket_event()` 的月份参数按数字比较，导致 market 未创建；已在测试内修正为按 month slug 匹配。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `active_order` / `order_history` 已成为 scan loop 的运行时事实源，Phase 04-03 可以继续做 restart restore/resume。
- filled 订单已复用现有 position 管理链路，Phase 05 可直接在此基础上加入更保守的 paper execution 假设。

## Self-Check: PASSED
- Found `.planning/phases/04-被动挂单与订单恢复/04-02-SUMMARY.md`
- Found commits `8c7fb85`, `dbe52bb`
