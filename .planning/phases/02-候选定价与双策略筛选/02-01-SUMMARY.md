---
phase: 02-候选定价与双策略筛选
plan: 01
subsystem: testing
tags: [polymarket, weather, probability, pytest, json]
requires:
  - phase: 01-市场语义与扫描基线
    provides: market_contracts、scan_guardrails 与 persist-before-trade 扫描骨架
provides:
  - 全 bucket `per_source_probability` 与 `aggregate_probability` 真相表
  - admissible market 的 `bucket_probabilities` 持久化字段
  - skipped rescan 会清空陈旧概率表的回归保护
affects: [phase-02-yes-no-selection, persisted-market-json, candidate-screening]
tech-stack:
  added: []
  patterns: [fixture-driven probability contracts, normalized band probability table, scan-time probability persistence]
key-files:
  created: [tests/fixtures/phase2_gamma_event.json, tests/fixtures/phase2_weather_snapshot.json, tests/test_phase2_probability.py]
  modified: [bot_v2.py, tests/conftest.py]
key-decisions:
  - "继续把 probability helper 留在 bot_v2.py 内，用纯函数输出完整 bucket probability records，而不是提前拆模块。"
  - "scan loop 先持久化 bucket_probabilities，再进入后续策略逻辑；skipped market 必须主动清空旧表。"
patterns-established:
  - "Probability truth pattern: 所有 bucket 统一输出 per-source/aggregate/fair YES/fair NO。"
  - "Persistence guard pattern: admissible market 写入概率表，inadmissible rescan 立即清空陈旧概率事实。"
requirements-completed: [STRAT-01]
duration: 3 min
completed: 2026-04-17
---

# Phase 02 Plan 01: 候选定价与双策略筛选 Summary

**多源天气预测现已为每个温区生成归一化 band probability 表，并在 admissible market JSON 中持久化为 `bucket_probabilities`。**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-17T11:48:38Z
- **Completed:** 2026-04-17T11:51:50Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- 为 Phase 2 新增 weather/gamma fixtures 与 `tests/test_phase2_probability.py`，锁定连续概率质量、per-source 输出和持久化合同。
- 把 `bucket_prob()` 从中间 bucket 的 one-hot 命中逻辑升级为连续概率质量计算，并新增 `aggregate_probability()` 输出完整概率表。
- 在 `scan_and_update()` 中接入 `bucket_probabilities` 持久化，并确保 skipped rescan 会清空旧概率表，避免污染后续 YES/NO 策略。

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: 建立 Phase 2 概率 fixtures 与 bucket probability 合同** - `4f7a9d3` (test)
2. **Task 1 GREEN: 建立 Phase 2 概率 fixtures 与 bucket probability 合同** - `da0e8fc` (feat)
3. **Task 2 RED: 把 bucket probability 表接入 scan loop 与 market JSON** - `6515922` (test)
4. **Task 2 GREEN: 把 bucket probability 表接入 scan loop 与 market JSON** - `beb6af4` (feat)

**Plan metadata:** pending

_Note: This plan used TDD, so each task produced RED/GREEN commits._

## Files Created/Modified
- `bot_v2.py` - 新增连续 bucket probability helper，并在 scan loop 落盘/清空 `bucket_probabilities`。
- `tests/conftest.py` - 注册 Phase 2 fixtures loader。
- `tests/fixtures/phase2_gamma_event.json` - 提供稳定的 weather event fixture。
- `tests/fixtures/phase2_weather_snapshot.json` - 提供多源 forecast/sigma fixture。
- `tests/test_phase2_probability.py` - 覆盖概率合同与 scan loop 持久化回归。

## Decisions Made
- 保持 brownfield 单文件脚本约束，概率 helper 继续放在 `bot_v2.py`，避免 Phase 2 提前拆包。
- aggregate bucket probability 先按可用 source 的平均值聚合，再归一化到整组 bucket，总和稳定接近 1，便于后续 YES/NO 共用。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Phase 2 fixture 初版 bucket 文本不符合现有 `parse_temp_range()` 合同，改为现有解析器可识别的 weather market wording 后恢复稳定回归。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `data/markets/*.json` 现在可直接为每个 admissible market 提供 `bucket_probabilities`，后续 YES/NO evaluator 不必再重算 band probability。
- skipped market 的陈旧概率表已被清理，后续候选筛选不会误读旧扫描结果。

## Self-Check: PASSED
- Found `.planning/phases/02-候选定价与双策略筛选/02-01-SUMMARY.md`
- Found commits `4f7a9d3`, `da0e8fc`, `6515922`, `beb6af4`
