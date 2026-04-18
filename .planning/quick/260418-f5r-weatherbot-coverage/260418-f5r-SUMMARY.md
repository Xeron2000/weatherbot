---
phase: quick-260418-f5r-weatherbot-coverage
plan: 01
summary_type: execution
status: complete
duration_seconds: 783
completed_at: "2026-04-18T03:14:00Z"
key_files:
  created:
    - tests/test_cli.py
    - tests/test_persistence.py
    - tests/test_strategy_paper_execution.py
  modified:
    - pyproject.toml
    - README.md
    - weatherbot/cli.py
    - weatherbot/persistence.py
    - weatherbot/paper_execution.py
    - weatherbot/strategy.py
    - uv.lock
commits:
  - e0cb655
  - 39235ea
  - c23d56a
  - 67a437c
  - 139aa23
  - 7a50149
---

# Phase quick 260418-f5r Plan 01: coverage gate 与关键直测 Summary

一句话总结：把 `uv run pytest -q` 升级成默认 coverage gate，并给 CLI、persistence、paper execution、strategy 的关键模块边界补上直接测试。

## Completed Tasks

### Task 1: 建立 coverage 门槛与默认回归入口
- 在 `pyproject.toml` 增加 `pytest-cov` dev 依赖。
- 把 `uv run pytest -q` 默认绑定到 `--cov=weatherbot --cov-report=term-missing --cov-fail-under=75`。
- 用 coverage omit 排除 `tests/*`、`.planning/*`、`bot_v2.py` 和 `weatherbot/__init__.py`。
- 在 `README.md` 明确说明默认回归命令自带 coverage gate。
- 代码提交：`e0cb655`

### Task 2: 为 CLI 与 persistence 补直接单元测试
- 新增 `tests/test_cli.py`，直接覆盖 `main(argv, runtime)` 的 `run/status/report/replay` 分发与非法命令分支。
- 新增 `tests/test_persistence.py`，直接覆盖 market backfill、state 默认值补齐、restore helper 调用，以及 `new_market()/save_market()` 的模块化字段。
- 修复 `weatherbot/cli.py` 的 replay 非法参数退出码，让未知 replay 参数与未知命令都统一为非零 `SystemExit`。
- 给 `weatherbot/persistence.py` 补最小默认依赖暴露，允许模块级 direct test 直接 monkeypatch 路径、router 和 restore helper。
- 代码提交：`39235ea`, `c23d56a`

### Task 3: 为策略/订单关键状态转移补直接测试并跑全量 gate
- 新增 `tests/test_strategy_paper_execution.py`，直接覆盖：
  - `build_passive_order_intent()` 的稳定 reason 与确定性订单字段
  - `apply_order_transition()` 的 append-only history 与非法 status 拒绝
  - `determine_size_multiplier()` / `build_candidate_assessments()` 的 accepted / size_down / rejected 语义
  - `build_exposure_keys()` 对 market dict 与 primitive 输入的稳定键
- 给 `weatherbot/paper_execution.py` 和 `weatherbot/strategy.py` 补最小默认运行时配置，避免 direct module tests 只能依赖 package wrapper 注入。
- 同步提交 `uv.lock`，锁定新引入的 `pytest-cov`。
- 代码提交：`67a437c`, `139aa23`, `7a50149`

## Verification

- `uv run pytest tests/test_modular_entrypoint.py -q`
  - 结果：功能通过，但会被新 coverage gate 拦下；这是预期，因为单文件回归不可能单独满足 75%。
- `uv run pytest tests/test_cli.py tests/test_persistence.py -q --no-cov`
  - 结果：通过。
- `uv run pytest tests/test_strategy_paper_execution.py -q --no-cov`
  - 结果：通过。
- `uv run pytest -q`
  - 结果：通过。
  - coverage：`weatherbot` 包总覆盖率 `76.54%`，高于 `75%` gate。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 统一 replay 非法参数退出码**
- **Found during:** Task 2 RED
- **Issue:** `cli.main()` 对未知 replay 参数抛出字符串型 `SystemExit`，和未知命令的 `SystemExit(1)` 语义不一致。
- **Fix:** 改成打印错误后显式 `raise SystemExit(1)`。
- **Files modified:** `weatherbot/cli.py`
- **Commit:** `c23d56a`

**2. [Rule 3 - Blocking issue] direct module tests 缺默认依赖可 monkeypatch 入口**
- **Found during:** Task 2 / Task 3 RED
- **Issue:** `weatherbot.persistence`、`weatherbot.paper_execution`、`weatherbot.strategy` 缺少模块级默认依赖，直接 monkeypatch 时会因为属性不存在而阻塞测试。
- **Fix:** 给相关模块补最小默认 config / path / policy 入口，只覆盖 direct tests 必需的运行时依赖，不重做架构。
- **Files modified:** `weatherbot/persistence.py`, `weatherbot/paper_execution.py`, `weatherbot/strategy.py`
- **Commit:** `c23d56a`, `139aa23`

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- Summary file path 已创建：`.planning/quick/260418-f5r-weatherbot-coverage/260418-f5r-SUMMARY.md`
- 所有本次代码提交均存在：`e0cb655`, `39235ea`, `c23d56a`, `67a437c`, `139aa23`, `7a50149`
- 最终 gate 验证已通过：`uv run pytest -q`
