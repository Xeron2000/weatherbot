---
phase: 01-市场语义与扫描基线
plan: 02
subsystem: testing
tags: [polymarket, weather, scan-loop, pytest, json]
requires:
  - phase: 01-市场语义与扫描基线
    provides: Phase 01 helper contracts for market semantics and guardrails
provides:
  - Market JSON semantic fields for event identity, resolution metadata, and scan guardrails
  - Scan loop skip behavior that persists explicit reasons and continues processing later markets
  - Regression coverage for schema defaults and mixed good/bad scan survivability
affects: [phase-01-reporting, phase-02-candidate-selection, persisted-market-json]
tech-stack:
  added: []
  patterns: [json-backed semantic market records, explicit guardrail skip statuses, fixture-driven scan loop tests]
key-files:
  created: [tests/test_phase1_scan_loop.py]
  modified: [bot_v2.py, tests/test_phase1_guardrails.py]
key-decisions:
  - "将 event_slug/event_id、resolution_metadata、market_contracts、scan_guardrails 直接持久化到 market JSON，而不是额外拆存储层。"
  - "guardrail 失败时先写入 skipped 状态并保存，再 continue 到下一个 city/date，避免坏 market 污染候选 universe。"
patterns-established:
  - "Scan guardrail pattern: 先抽取 resolution metadata/contract ids，再统一生成 admissible + skip_reasons。"
  - "Persist-before-trade pattern: 语义字段和 last_scan_status 在任何开仓逻辑前落盘。"
requirements-completed: [MKT-01, MKT-02, MKT-03]
duration: 4 min
completed: 2026-04-17
---

# Phase 01 Plan 02: 将语义 schema 和 guardrail 接入扫描主循环与 market JSON Summary

**市场 JSON 现已持久化 resolution metadata、contract identifiers 与 skipped/ready 扫描状态，scan loop 会在坏 market 上显式跳过并继续处理后续市场。**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-17T10:03:32Z
- **Completed:** 2026-04-17T10:08:15Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 复用现有未提交的 `tests/test_phase1_guardrails.py` 作为 Task 1 RED 基础，没有重做半成品。
- 扩展 `new_market()` 和旧 market record 回填逻辑，使持久化 JSON 自带事件语义、guardrail 状态与最近扫描结论。
- 把 helper 接入 `scan_and_update()`，让 inadmissible market 明确写 `skipped` 并不中断同轮其他 city/date 的扫描。

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: semantic market schema tests** - `73cc45f` (test)
2. **Task 1 GREEN: persisted semantic scan fields** - `e1b7fa4` (feat)
3. **Task 2 RED: scan loop survivability tests** - `4cc159d` (test)
4. **Task 2 GREEN: scan loop semantic integration** - `d859289` (feat)

**Plan metadata:** pending

_Note: This plan used TDD, so each task produced RED/GREEN commits._

## Files Created/Modified
- `bot_v2.py` - 扩展 market record schema，并在 scan loop 中持久化语义字段、skip 状态与 contract-aware outcomes。
- `tests/test_phase1_guardrails.py` - 验证 schema 默认值、skip reason 持久化和 admissible market 语义字段。
- `tests/test_phase1_scan_loop.py` - 验证 skipped market 明确落盘、admissible market 语义完整，以及 mixed good/bad scan 不会中断。

## Decisions Made
- 语义字段继续保留在 `bot_v2.py` 与本地 JSON 中，遵守 brownfield + JSON 持久化约束，不提前做 package/SQLite 重构。
- `all_outcomes` 在 admissible 情况下改为基于 `market_contracts` 组装，这样后续入场逻辑读取的是已带 condition/token 标识的 outcome。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正 market unit 解析误判**
- **Found during:** Task 1 (扩展 market record schema，持久化市场语义与扫描防线)
- **Issue:** `parse_market_unit()` 会把普通文本里的字母误识别成 `F/C`，导致 `°C` 规则文本没有触发 `unit_mismatch`。
- **Fix:** 收紧 unit 正则，只接受 `°F` / `°C` / 独立 unit token / Fahrenheit/Celsius 文本。
- **Files modified:** `bot_v2.py`
- **Verification:** `uv run pytest tests/test_phase1_market_semantics.py tests/test_phase1_guardrails.py -q`
- **Committed in:** `e1b7fa4`

**2. [Rule 2 - Missing Critical] 为已存在 market JSON 回填新语义字段默认值**
- **Found during:** Task 2 (改造 scan_and_update()，输出合格 universe 并对坏 market 明确跳过)
- **Issue:** 旧 market record 重新加载后可能缺少 `market_contracts` / `scan_guardrails` / `last_scan_status`，会让 scan loop 行为不一致。
- **Fix:** 在 `scan_and_update()` 对已加载 record 使用 `setdefault()` 回填新字段，再执行语义评估与持久化。
- **Files modified:** `bot_v2.py`
- **Verification:** `uv run pytest tests/test_phase1_guardrails.py tests/test_phase1_scan_loop.py -q` and `uv run pytest -q`
- **Committed in:** `d859289`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** 两处修复都直接影响 guardrail 正确性与历史 market record 兼容性，没有引入额外架构扩张。

## Issues Encountered
- 发现工作树里已有未提交的 `tests/test_phase1_guardrails.py` 半成品；本次直接复用为 Task 1 RED，而不是重新生成测试。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `data/markets/*.json` 现在能区分 accepted/skipped market，并给 Phase 01 Plan 03 的状态/报告展示提供直接输入。
- Phase 02 可以基于 `market_contracts` 与 `scan_guardrails` 做候选定价和停单解释，而不用重新猜测市场语义。

## Self-Check: PASSED
- Found `.planning/phases/01-市场语义与扫描基线/01-02-SUMMARY.md`
- Found commits `73cc45f`, `e1b7fa4`, `4cc159d`, `d859289`
