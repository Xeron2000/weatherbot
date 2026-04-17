---
phase: 01-市场语义与扫描基线
plan: 01
subsystem: testing
tags: [pytest, uv, polymarket, weatherbot, guardrails]

# Dependency graph
requires: []
provides:
  - pytest/uv 驱动的 Phase 1 市场语义回归入口
  - Gamma event / weather snapshot fixtures
  - 可复用的 resolution metadata、contract identifiers、guardrail helpers
affects: [phase-1-scan-loop, phase-2-pricing, observability]

# Tech tracking
tech-stack:
  added: [pytest, uv]
  patterns: [fixture-driven helper contracts, structured skip reasons]

key-files:
  created: [pyproject.toml, tests/conftest.py, tests/fixtures/phase1_gamma_event.json, tests/fixtures/phase1_weather_snapshot.json, tests/test_phase1_market_semantics.py]
  modified: [bot_v2.py]

key-decisions:
  - "保持 helper 留在 bot_v2.py 内，但必须做成纯函数接口，避免在 Phase 1 提前做包级重构。"
  - "测试通过 fixture + 运行期断言暴露缺 helper 问题，避免 import/setup error 掩盖真实 RED 状态。"

patterns-established:
  - "Pattern 1: 外部 Gamma/weather payload 先经 helper 合同归一化，再进入扫描主循环。"
  - "Pattern 2: 坏 market 用 skip reason code 拒绝，而不是匿名 continue。"

requirements-completed: [MKT-02, MKT-03]

# Metrics
duration: 3 min
completed: 2026-04-17
---

# Phase 01 Plan 01: 建立 Phase 1 测试底座与市场语义 helper 合同 Summary

**用 pytest fixtures 固化 Gamma 市场语义合同，并在 `bot_v2.py` 中补齐 resolution metadata / contract identifiers / stale weather guardrail helpers。**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-17T09:41:25Z
- **Completed:** 2026-04-17T09:44:23Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- 为 Phase 1 引入最小 `uv + pytest` 测试底座，并补齐固定 fixtures。
- 用 RED→GREEN 方式把市场语义 helper 合同落到自动测试里。
- 在 `bot_v2.py` 中新增可复用的 metadata / contracts / guardrails 纯 helper，为后续接扫描主循环做准备。

## Task Commits

Each task was committed atomically:

1. **Task 1: 建立 Phase 1 测试底座与固定 fixtures** - `e412fb6` (chore)
2. **Task 2 (RED): 在测试中收紧 helper 合同断言** - `4eb7066` (test)
3. **Task 2 (GREEN): 在 bot_v2.py 中补齐市场语义与 guardrail helper** - `8a5ac28` (feat)

**Plan metadata:** pending

_Note: Task 2 followed TDD and therefore produced RED + GREEN commits._

## Files Created/Modified
- `pyproject.toml` - 声明 uv 管理的 Python 项目与 pytest 依赖。
- `tests/conftest.py` - 提供 fixture loader，并修正 pytest 运行时导入路径。
- `tests/fixtures/phase1_gamma_event.json` - 固定的可解析 Gamma weather event 样本。
- `tests/fixtures/phase1_weather_snapshot.json` - fresh / stale / missing 三类天气快照样本。
- `tests/test_phase1_market_semantics.py` - 覆盖温区解析、contract identifiers、unit mismatch、weather stale 的 helper 合同测试。
- `bot_v2.py` - 新增 resolution metadata、market contracts、guardrail evaluation 纯 helper。

## Decisions Made
- 保持 helper 仍在 `bot_v2.py` 中，避免在 brownfield 阶段为单个 plan 提前拆包。
- 用结构化 `skip_reasons` 作为坏 market 的统一拒绝接口，后续 phase 直接复用。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 修正 pytest 在 uv 环境下的仓库根导入路径**
- **Found during:** Task 1 (建立 Phase 1 测试底座与固定 fixtures)
- **Issue:** `uv run pytest` 初次执行时无法导入 `bot_v2.py`，报 `ModuleNotFoundError: No module named 'bot_v2'`。
- **Fix:** 在 `tests/conftest.py` 中显式把仓库根目录加入 `sys.path`，让测试进入真实 RED/ GREEN 循环，而不是死在环境导入阶段。
- **Files modified:** `tests/conftest.py`
- **Verification:** `uv run pytest tests/test_phase1_market_semantics.py -q` 从 import error 变为可预期的 failing tests，随后全量转绿。
- **Committed in:** `e412fb6` (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** 仅修正测试执行环境，不改变 plan 目标或实现边界。

## Issues Encountered
- `uv run pytest` 初次执行时没有把仓库根目录放进 `sys.path`；已在 `tests/conftest.py` 收口处理。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- 已具备可重复运行的 Phase 1 helper 回归测试，后续可以把这些 helper 接入 `scan_and_update()`。
- `skip_reasons` 合同已落地，01-02 可以直接围绕 accepted/skipped market 语义接线。

## Self-Check: PASSED
- FOUND: `.planning/phases/01-市场语义与扫描基线/01-01-SUMMARY.md`
- FOUND: `e412fb6`
- FOUND: `4eb7066`
- FOUND: `8a5ac28`
