---
phase: 05-保守 paper execution 与回放验证
plan: 01
subsystem: api
tags: [paper-execution, simulation, execution-events, config, pytest]
requires:
  - phase: 04-被动挂单与订单恢复
    provides: passive order lifecycle persistence and restart-safe unfinished order facts
provides:
  - explicit paper execution configuration for conservative simulation assumptions
  - append-only execution event schema and recoverable paper execution state defaults
  - pure helper contracts for submission latency, queueing, partial fills, and cancel latency
affects: [phase-05-scan-wiring, phase-05-replay, operator-observability]
tech-stack:
  added: []
  patterns: [config-validated paper execution assumptions, append-only execution event ledger, pure single-step simulation helper]
key-files:
  created: [tests/test_phase5_paper_execution.py]
  modified: [config.json, bot_v2.py]
key-decisions:
  - "paper execution 参数必须来自显式 config，而不是散落在 scan loop 里的乐观硬编码。"
  - "保守成交仿真先落成 pure helper + append-only event schema，Phase 05-02 再接入运行时 wiring。"
patterns-established:
  - "Simulation step pattern: market facts + order facts + quote snapshot + paper config -> updated paper state + append-only execution event。"
  - "Schema default pattern: market JSON 默认携带 paper_execution_state、execution_events、execution_metrics，便于后续恢复与回放。"
requirements-completed: [SIM-01, SIM-02]
duration: commit-window 7h 42m
completed: 2026-04-18
---

# Phase 05 Plan 01: 建立 paper execution 配置、事件 schema 与纯函数合同 Summary

**paper execution 现在有显式保守配置、append-only execution event schema，以及可复用的单步仿真 pure helper。**

## Performance

- **Duration:** commit window 7h 42m
- **Started:** 2026-04-17T17:09:42Z
- **Completed:** 2026-04-18T00:52:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `tests/test_phase5_paper_execution.py` 锁定 submission latency、queue ahead、touch-not-fill、partial fill、cancel latency 与事件字段合同。
- `config.json` 新增 `paper_execution` 顶层配置块，显式声明保守仿真关键参数。
- `bot_v2.py` 新增 `load_paper_execution_config()`、market schema 默认字段、`record_execution_event()` 与 `simulate_paper_execution_step()` pure helper。

## Task Commits

Each task was committed atomically:

1. **Task 1: 先写 paper execution RED 合同与事件 schema** - `0ce00a1` (test)
2. **Task 2: 实现 paper execution 配置、默认字段与纯函数 helper** - `a288a67` (feat)

**Plan metadata:** None - summary created without additional metadata commit per orchestrator-managed planning files.

## Files Created/Modified
- `tests/test_phase5_paper_execution.py` - Phase 5 RED→GREEN 合同，覆盖配置校验、延迟提交、排队未成、部分成交、终态撤单。
- `config.json` - 新增 `paper_execution` 配置块，集中声明 submission latency、queue ahead、partial fill、cancel delay、adverse buffer 参数。
- `bot_v2.py` - 新增 paper execution config loader、schema backfill、append-only execution events 与单步仿真 helper。

## Decisions Made
- 对 `paper_execution` 关键字段采用显式校验并抛出 deterministic `ValueError`，避免缺字段时静默回退到乐观默认值。
- 不改动 Phase 4 运行时 wiring，先把 schema 与 pure helper 钉死，后续 scan/monitor/replay 统一消费同一合同。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

- 初版 partial fill 逻辑在第二次推进时仍按 slice ratio 截断剩余仓位，导致 `filled` 合同未通过；已调整为 partial 后允许下一步清完剩余数量，回归通过。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `paper_execution_state`、`execution_events`、`execution_metrics` 已成为稳定 schema，Phase 05-02 可以把保守仿真接入 scan loop / monitor 持久化路径。
- replay 所需的 append-only execution event 证据链已存在，Phase 05-03 可以直接在此基础上实现回放与 fill quality 检查。

## Self-Check: PASSED
- Found `.planning/phases/05-保守 paper execution 与回放验证/05-01-SUMMARY.md`
- Found commits `0ce00a1`, `a288a67`
