# Quick Task 260418-he3 Summary

## Objective

修复 `weatherbot/strategy.py` 里 NO 候选的取价语义，避免 `no.bid` 极低时把本应基于可成交 NO 入场价判断的候选误判为 `price_below_min`。

## Completed Work

### Task 1 — RED
- 在 `tests/test_phase2_strategies.py` 增加低 `no.bid` / 高 `no.ask` 回归测试。
- 在 `tests/test_strategy_paper_execution.py` 增加跨层护栏，锁定 `build_candidate_assessments()` 产出的 `NO_CARRY` assessment 仍可被执行层消费。
- 先跑 `uv run pytest -q tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py`，得到预期失败，证明旧逻辑仍在按 `no.bid` 判价。
- Commit: `16edb9a` — `test(quick-260418-he3-01): add failing no ask regression coverage`

### Task 2 — GREEN
- 在 `weatherbot/strategy.py` 的 `evaluate_no_candidate()` 中把：
  - `missing_quote_price` 判定从 `no.bid` 改为 `no.ask`
  - `price_below_min` 判定从 `no.bid < min_price` 改为 `no.ask < min_price`
  - `edge` 计算从 `no.bid - fair_no` 改为 `fair_no - no.ask`
- 保留 `quote_context` 原始 bid/ask，不改快照结构，不改 routing / paper execution。
- 同步把既有测试样例的 NO ask 调整到与新 edge 语义一致，确保 accepted / reprice 断言仍表达真实可成交语义。
- `uv run pytest -q tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py` 的功能断言已全部通过，但被仓库全局 coverage 门槛（75%）拦下；随后用 `uv run pytest -q --no-cov ...` 验证目标测试集，结果 `16 passed`。
- Commit: `709d509` — `fix(quick-260418-he3-01): use no ask for candidate price checks`

### Task 3 — Real Scan Verification
- 执行单次真实扫描：`uv run python -c "import bot_v2; bot_v2.scan_and_update()"`
- 复查状态：`uv run python bot_v2.py status`
- 结果显示 NO 候选不再因旧 `no.bid` 语义批量落成 `price_below_min`：
  - 例如 `New York City 2026-04-18 | NO_CARRY | 64.0-65.0 | status=rejected | reasons=probability_below_min | fair=0.803 | quote=ask=0.99 bid=0.01`
  - 例如 `Chicago 2026-04-18 | NO_CARRY | 64.0-65.0 | status=rejected | reasons=probability_below_min | fair=0.673 | quote=ask=0.99 bid=0.01`
- 额外用 `rg -n 'price_below_min|NO_CARRY' data/markets` 复查，结果只匹配到 `NO_CARRY`，未出现落盘的 `price_below_min` 记录，说明旧 bug 没再污染 persisted `candidate_assessments`。
- 本轮扫描里 NO 侧主要真实约束已变成：
  - `probability_below_min`
  - `missing_quote_price`
  - `orderbook_empty`

## Files Changed

- `weatherbot/strategy.py`
- `tests/test_phase2_strategies.py`
- `tests/test_strategy_paper_execution.py`

## Commits

- `16edb9a` — `test(quick-260418-he3-01): add failing no ask regression coverage`
- `709d509` — `fix(quick-260418-he3-01): use no ask for candidate price checks`

## Deviations / Notes

- 未修改或暂存用户明确禁止触碰的脏文件：
  - `.planning/config.json`
  - `.planning/phases/04-执行paper订单生命周期与状态恢复/04-VERIFICATION.md`
- 未提交 docs artifacts；本 SUMMARY 保持未提交状态。
- 真实扫描生成了 `data/` 运行期文件，未暂存、未提交。
- 精确按计划执行的 pytest 命令会被仓库现有 coverage gate 拦截，这属于本 quick task 范围外的全局测试配置问题；目标回归本身已通过 `--no-cov` 验证。

## Result

NO 候选现在按 `no.ask` 这一可成交入场价做价格门槛和 edge 判断；低 `no.bid` 不再单独把候选错误打成 `price_below_min`。
