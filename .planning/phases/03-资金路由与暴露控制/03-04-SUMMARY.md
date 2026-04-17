---
phase: 03-资金路由与暴露控制
plan: 04
subsystem: testing
tags: [reporting, readme, risk-state, route-decisions, cli]
requires:
  - phase: 03-资金路由与暴露控制
    provides: stable risk_state, route_decisions, reserved_exposure facts
provides:
  - operator-facing risk usage summary in status/report
  - exposure rollup and reject/release reason summaries
  - README guidance for Phase 3 regression and stored facts
affects: [operator-observability, manual-verification, phase-04-execution]
tech-stack:
  added: []
  patterns: [persisted-risk reporting, CLI reason summaries, phase verification docs]
key-files:
  created: [tests/test_phase3_reporting.py]
  modified: [bot_v2.py, README.md]
key-decisions:
  - "reporting 继续只读持久化 risk facts，不在展示层重算 budget、exposure 或 reason。"
  - "README 仅记录 Phase 3 字段和回归命令，不提前扩展到后续订单状态机。"
patterns-established:
  - "Risk reporting pattern: 先输出 Risk usage / exposure，再展示 scan summary 与 route reason summary。"
  - "README verification pattern: phase-specific regression command + persisted fact source bullets。"
requirements-completed: [STRAT-04, RISK-01, RISK-02]
duration: 10 min
completed: 2026-04-17
---

# Phase 03 Plan 04: 资金路由与暴露控制 Summary

**CLI 现在能直接展示 YES/NO budget usage、global worst-loss、city/date/event exposure，以及 reject/release reason 摘要。**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-17T14:51:00Z
- **Completed:** 2026-04-17T15:01:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `print_status()` / `print_report()` 新增 Risk usage、exposure rollup 与 route reason summary 段。
- `tests/test_phase3_reporting.py` 锁定 operator-facing 风险摘要和 release reason 文案合同。
- README 补齐 Phase 3 的完整回归命令以及 `risk_state` / `route_decisions` / `reserved_exposure` 字段说明。

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: 为 Phase 3 风险摘要建立 operator-facing reporting 合同** - `3520538` (test)
2. **Task 1 GREEN: 为 Phase 3 风险摘要建立 operator-facing reporting 合同** - `c949892` (feat)
3. **Task 2: 更新 README 的 Phase 3 风控字段与验证命令** - `51d623a` (chore)

**Plan metadata:** pending

## Files Created/Modified
- `bot_v2.py` - 输出 per-leg budget、global usage、city/date/event exposure 和 route reason 摘要。
- `tests/test_phase3_reporting.py` - 覆盖 status/report 的 risk summary 合同。
- `README.md` - 增加 Phase 3 Verification 与新增 risk fact 说明。

## Decisions Made
- `print_report()` 同样读取 `load_state()`，确保 report 和 status 使用同一份 persisted risk truth。
- route reason summary 同时统计 rejected decision reasons 和 released reservation reasons，避免操作者只能看到一半上下文。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered
- 现有 CLI 输出已经很长，因此新增 risk summary 时采用独立小节而不是把字段塞进 candidate rows，避免可读性退化。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- 操作者已经能直接看懂 budget usage、冲突拒绝和释放原因，后续 phase 可专注 order intent / order state。
- README 已提供完整回归入口，Phase 4 实现后只需追加新增测试，不必再解释 Phase 3 风险字段。

## Self-Check: PASSED
- Found `.planning/phases/03-资金路由与暴露控制/03-04-SUMMARY.md`
- Found commits `3520538`, `c949892`, `51d623a`

---
*Phase: 03-资金路由与暴露控制*
*Completed: 2026-04-17*
