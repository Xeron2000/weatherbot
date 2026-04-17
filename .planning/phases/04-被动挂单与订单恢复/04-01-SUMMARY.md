---
phase: 04-被动挂单与订单恢复
plan: 01
subsystem: api
tags: [orders, order-policy, state-machine, pytest, json]
requires:
  - phase: 03-资金路由与暴露控制
    provides: stable reserved_exposure, route_decisions, candidate_assessments facts
provides:
  - passive order policy defaults for YES/NO time in force
  - pure helpers for building passive order intents and order transitions
  - market loader backfill for active_order and order_history fields
affects: [phase-04-scan-wiring, phase-04-order-restore, operator-observability]
tech-stack:
  added: []
  patterns: [single-file pure order helpers, append-only order history, config-driven tif defaults]
key-files:
  created: [tests/test_phase4_orders.py]
  modified: [config.json, bot_v2.py]
key-decisions:
  - "build_passive_order_intent 返回 {order, reason} 包装，既保留纯函数合同，也能给 wiring 层稳定失败原因。"
  - "旧 market JSON 通过 loader/backfill 自动补 active_order 与 order_history，避免 Phase 4 恢复逻辑因缺字段崩溃。"
patterns-established:
  - "Passive order pattern: route reservation + assessment + quote snapshot -> deterministic order/reason result。"
  - "Order transition pattern: history append-only，状态原因和 fill delta 全量留痕。"
requirements-completed: [ORDR-01, ORDR-02]
duration: 4 min
completed: 2026-04-17
---

# Phase 04 Plan 01: 被动挂单与订单恢复 Summary

**Phase 4 现在具备 config-driven 被动挂单合同、限价单意图构建 helper，以及可追溯的订单状态流转 history。**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-17T15:12:01Z
- **Completed:** 2026-04-17T15:16:19Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `config.json` 新增 `order_policy`，显式定义 YES/NO 的 `time_in_force`、GTD buffer 和 reprice buffer 默认值。
- `bot_v2.py` 新增 `load_order_policy_config()`、`build_passive_order_intent()`、`apply_order_transition()`、`is_order_terminal()` 等 Phase 4 纯函数 helper。
- `new_market()`、`load_market()`、`load_all_markets()` 现在会稳定补齐 `active_order` / `order_history`，并由 `tests/test_phase4_orders.py` 锁定回归合同。

## Task Commits

Each task was committed atomically:

1. **Task 1: 建立被动订单 helper 的 RED 合同** - `c117b43` (test)
2. **Task 2: 在 bot_v2.py 落地订单配置、意图与状态机 helper** - `b806409` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `config.json` - 增加 `order_policy` 顶层配置块。
- `bot_v2.py` - 增加订单策略加载、限价意图生成、状态机流转和 market 默认补齐 helper。
- `tests/test_phase4_orders.py` - 覆盖 order policy、intent schema、transition history 与 loader backfill 合同。

## Decisions Made
- `build_passive_order_intent()` 采用返回 `{order, reason}` 的纯函数接口，避免 scan loop 在失败场景里自行拼凑 reason。
- GTD 订单过期时间直接按 `now_ts + gtd_buffer_hours` 计算，GTC 则明确保持 `expires_at = None`。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- scan loop 已经可以直接消费 `ORDER_POLICY`、`build_passive_order_intent()` 和 `apply_order_transition()`，后续只需接生命周期 wiring。
- 旧 market JSON 的订单字段兼容已打底，Phase 04-03 可在此基础上继续做 restart restore。

## Self-Check: PASSED
- Found `.planning/phases/04-被动挂单与订单恢复/04-01-SUMMARY.md`
- Found commits `c117b43`, `b806409`

---
*Phase: 04-被动挂单与订单恢复*
*Completed: 2026-04-17*
