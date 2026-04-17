---
phase: 03-资金路由与暴露控制
plan: 03
subsystem: api
tags: [reconciliation, release, conflicts, reservations, pytest]
requires:
  - phase: 03-资金路由与暴露控制
    provides: persisted risk_state plus route_decisions/reserved_exposure seam
provides:
  - reservation release reasons for downgraded and missing candidates
  - market reconciliation that preserves existing exposure on conflicts
  - skip-path release for `market_no_longer_ready`
affects: [phase-03-reporting, phase-04-order-intents, audit-traceability]
tech-stack:
  added: []
  patterns: [reservation reconciliation, explicit release_reason tracing, preserve-existing-on-conflict]
key-files:
  created: []
  modified: [bot_v2.py, tests/test_phase3_scan_loop.py]
key-decisions:
  - "当前 market 的旧 reservation 先从 risk_state 摘出，再按 keep/release 结果重建，避免自冲突和双记账。"
  - "已有 reservation 仍然可接受时直接保留，不因为新候选或外部 cap 重新排序而被替换。"
patterns-established:
  - "Release pattern: candidate_downgraded / candidate_missing / market_no_longer_ready 都成为 deterministic release_reason。"
  - "Conflict pattern: 保留已有 reservation，再让新候选吃 same_bucket_conflict / event_cluster_conflict。"
requirements-completed: [RISK-01, RISK-02]
duration: 14 min
completed: 2026-04-17
---

# Phase 03 Plan 03: 资金路由与暴露控制 Summary

**连续扫描下的 reservation 现在会按 `candidate_downgraded`、`candidate_missing` 和 `market_no_longer_ready` 立即释放，并保留已有冲突暴露。**

## Performance

- **Duration:** 14 min
- **Started:** 2026-04-17T14:37:00Z
- **Completed:** 2026-04-17T14:51:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- 新增 reservation reconciliation helper，解决连续扫描下的自冲突、双记账和 stale reservation 问题。
- 旧 reservation 若仍然可接受，会优先被保留并重新写回 risk ledger；新冲突候选会被明确拒绝。
- release path 现在会保留 `release_reason`，为后续报告和订单层提供可追踪审计事实。

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: 为释放与冲突回收建立连续扫描回归** - `25b725b` (test)
2. **Task 2: 在 scan loop 中实现 reservation reconciliation** - `1b6d458` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `bot_v2.py` - 增加 reservation release / reconcile helper，并在 skipped path 与 reroute path 写入 `release_reason`。
- `tests/test_phase3_scan_loop.py` - 增加 downgrade/missing/conflict 的连续扫描回归。

## Decisions Made
- release 后保留 `reserved_exposure` 审计对象，但把 `reserved_worst_loss` 归零，确保账本和审计同时成立。
- 旧 reservation 若仍是 accepted/size_down，不再走“重新竞争”路径，而是直接保留并让新候选在其上被判断冲突。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- release 后若直接把 `reserved_exposure` 清空，会让 CLI/reporting 丢失 release 原因；最终改为保留 released record 并从 risk ledger 中减掉占用。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- route audit 现在同时包含 reject 和 release 原因，reporting 可以直接消费而无需补逻辑。
- stale reservation 风险已经收口，后续 phase 可安全引入 order intent / order lifecycle。

## Self-Check: PASSED
- Found `.planning/phases/03-资金路由与暴露控制/03-03-SUMMARY.md`
- Found commits `25b725b`, `1b6d458`

---
*Phase: 03-资金路由与暴露控制*
*Completed: 2026-04-17*
