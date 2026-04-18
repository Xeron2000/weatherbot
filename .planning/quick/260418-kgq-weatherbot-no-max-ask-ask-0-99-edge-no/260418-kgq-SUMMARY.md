---
phase: quick-260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no
plan: 01
subsystem: strategy
tags: [weatherbot, no-carry, quote-quality, max-ask, local-only]
requires: []
provides:
  - NO max_ask quote-quality guard
  - ask_above_max wrapper and modular regressions
  - persisted ask_above_max scan evidence
affects: [weatherbot/strategy.py, weatherbot/__init__.py, candidate_assessments, NO_CARRY]
tech-stack:
  added: []
  patterns: [explicit NO quote-quality rejection, local-only config experiment, persisted candidate_assessments verification]
key-files:
  created:
    - .planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md
  modified:
    - weatherbot/strategy.py
    - weatherbot/__init__.py
    - tests/test_phase2_strategies.py
    - tests/test_strategy_paper_execution.py
    - config.json
key-decisions:
  - "NO 路径继续只消费 no.ask；max_ask 只作为 quote-quality guard，不回退到 no.bid。"
  - "ask_above_max 单独命中时走 reprice/non-executable；叠加其他原因时保持 rejected。"
  - "config.json 只做 local-only 实验，secret 不回显、不暂存、不提交。"
patterns-established:
  - "NO quote guard: 价格下限与 ask 上限都先给出显式 reason，再决定 reprice/rejected。"
  - "Scan verification: 直接读取 persisted candidate_assessments，而不是在 summary 里重算候选逻辑。"
requirements-completed: [QUICK-260418-KGQ]
duration: 19min
completed: 2026-04-18
---

# Quick Task 260418-kgq Summary

**为 NO_CARRY 增加 `max_ask` 守卫，把 `ask≈0.99` 的坏报价从“负 edge 隐式淘汰”升级成显式 `ask_above_max` 拒绝。**

## Performance

- **Started:** 2026-04-18T06:46:00Z
- **Completed:** 2026-04-18T07:05:12Z
- **Tasks:** 3
- **Files modified:** 5 code/local files + 1 summary

## Accomplishments

- 在 `weatherbot/strategy.py` 的 NO evaluator 中加入 `max_ask`/`ask_above_max`，并同步 `weatherbot/__init__.py` 默认 mirror。
- 补齐 wrapper 路径与模块化 strategy 路径回归测试，锁定超限 NO ask 的 non-executable 语义。
- 做了一次 local-only `config.json` 实验和单次扫描，确认 persisted `NO_CARRY` assessments 已出现大批 `ask_above_max` 命中。

## Task Commits

1. **Task 1 RED: 为 NO evaluator 增加 failing 回归** - `2aa7106` (`test`)
2. **Task 1 GREEN: 为 NO evaluator 增加 max_ask quote guard** - `9690e6e` (`fix`)
3. **Task 2: 补齐模块化回归测试** - `e2ebd47` (`test`)

_Note: 本 quick task 按 TDD 执行了 test → fix → test；docs summary 未提交。_

## Files Created/Modified

- `weatherbot/strategy.py` - 为 NO evaluator 增加 `max_ask` 默认值与 `ask_above_max` reason，纯 quote-quality 命中时返回 `reprice`。
- `weatherbot/__init__.py` - 同步 `NO_STRATEGY` 默认 mirror，确保 wrapper/runtime 与 strategy 合同一致。
- `tests/test_phase2_strategies.py` - 新增 wrapper 级 `ask_above_max` 回归和缺省兼容性回归。
- `tests/test_strategy_paper_execution.py` - 新增 `build_candidate_assessments()` 对坏 NO ask 的显式拦截测试。
- `config.json` - local-only 加入 `no_strategy.max_ask = 0.95` 用于单次扫描验证；未暂存、未提交。

## Baseline Observation

上一个 quick (`260418-j1b`) 已证明：把 `no_strategy.min_probability` 从 `0.95` 放宽到 `0.90` 后，部分 NO bucket 已经不再带 `probability_below_min`，但仍因 `ask` 普遍落在 `0.99~1.00`、`edge` 为负而停留在 rejected。也就是说，问题已经从“概率门槛”收敛到“坏报价缺少显式 quote-quality guard”。

## Local-only Scan Evidence

本次仅在本地 `config.json` 增加 `no_strategy.max_ask = 0.95`，随后执行一次且仅一次：

- `uv run python -c "import bot_v2; bot_v2.scan_and_update()"`

扫描后直接读取 `data/markets/*.json` 里的 persisted `candidate_assessments`，统计 `strategy_leg == "NO_CARRY"` 且 `reasons` 包含 `ask_above_max` 的记录：

- `ask_above_max` 命中数：**167**
- 其中 `status = reprice`：**116**
- 其中 `status = rejected`：**51**（说明有一部分同时叠加了 `probability_below_min` 等其他原因）
- `reasons == ["ask_above_max"]` 的纯 quote-quality 命中：**116**
- 命中样本的 `ask` 区间：**0.99 ~ 0.999**
- 命中样本里 `edge < 0` 的记录：**97**

代表样本（均来自 persisted facts，而非 summary 层重算）：

| Market file | Range | Ask | Fair NO | Edge | Status | Reasons |
|---|---|---:|---:|---:|---|---|
| `nyc_2026-04-18.json` | `56.0-57.0` | `0.999` | `0.903241` | `-0.095759` | `reprice` | `ask_above_max` |
| `nyc_2026-04-18.json` | `62.0-63.0` | `0.99` | `0.912153` | `-0.077847` | `reprice` | `ask_above_max` |
| `nyc_2026-04-18.json` | `64.0-65.0` | `0.99` | `0.779684` | `-0.210316` | `rejected` | `ask_above_max, probability_below_min` |

这说明 `ask≈0.99` 的 NO 坏报价现在已经被 `ask_above_max` 明确接管：

- 纯报价问题不再只是靠负 edge 静默变成 `rejected`，而是进入可解释的 `reprice`。
- 若同时还有别的硬原因（如 `probability_below_min`），则仍保持 `rejected`，没有放宽原有风险约束。

## Decisions Made

- `max_ask` 只作用于 NO quote-quality，不改 route、order intent、持久化结构。
- 对旧配置保持兼容：若运行时 `NO_STRATEGY` 未配置 `max_ask`，就不新增 `ask_above_max` reason。
- 默认值选 `0.95`，因为本轮坏报价主要集中在 `0.99~1.00`，足以把问题报价与正常 NO ask 分开。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 子集 pytest 校验被全局 coverage 门槛误伤**
- **Found during:** Task 1 / Task 2 verification
- **Issue:** 计划里的 `pytest -k ...` 子集命令逻辑上通过，但仓库级 `pytest-cov` 75% fail-under 会让任意子集验证失败。
- **Fix:** 保留原始子集命令结果作为证据后，追加使用 `--no-cov` 跑最近似任务级验证；最后再跑一遍两份 touched test 文件的完整回归。
- **Files modified:** None
- **Verification:** `uv run pytest --no-cov tests/test_phase2_strategies.py -k "no_evaluator" -x`、`uv run pytest --no-cov tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py -x`
- **Committed in:** not applicable (verification-only deviation)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** 仅影响验证命令形态，不影响实现范围或运行结果。

## Issues Encountered

- 子集测试选择表达式只命中了模块化用例，因此最后补跑了两份 touched 测试文件的完整回归，确保 wrapper 与模块化路径都实际验证到。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- NO evaluator 现在已经能把超限 ask 与纯负 edge 区分开，后续如果要继续调 NO 策略，可直接基于 persisted `ask_above_max` 命中分布做参数决策。
- `config.json` 仍是 local-only 脏变更；如需保留实验值，应由后续明确的配置任务处理，不能直接提交。

## Verification

- 通过：`uv run pytest --no-cov tests/test_phase2_strategies.py -k "no_evaluator" -x`
- 通过：`uv run pytest --no-cov tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py -k "ask_above_max or no_assessment" -x`
- 通过：`uv run pytest --no-cov tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py -x`
- 通过：`uv run python -c "import json; from pathlib import Path; cfg=json.loads(Path('config.json').read_text(encoding='utf-8')); assert cfg['no_strategy']['max_ask'] < 0.99 and cfg.get('vc_key') and cfg['vc_key'] != 'YOUR_KEY_HERE'"`
- 通过：`uv run python -c "import bot_v2; bot_v2.scan_and_update()"`（仅执行一次）
- 通过：persisted `NO_CARRY` assessments 中出现 `ask_above_max` 命中 167 条
- 通过：`config.json` 未暂存；`.planning/config.json` 与 `.planning/phases/04-被动挂单与订单恢复/04-VERIFICATION.md` 未被本 quick task 改动

## Known Stubs

None.
