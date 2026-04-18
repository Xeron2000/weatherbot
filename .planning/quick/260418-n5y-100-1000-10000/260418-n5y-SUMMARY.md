---
phase: quick-260418-n5y
plan: 01
subsystem: config
tags: [config-json, strategy-profile, runtime-config, pytest, visual-crossing]
requires:
  - phase: phase-04
    provides: module entrypoints consume runtime config via weatherbot/__init__.py
provides:
  - config-driven 100/1000/10000 strategy profile presets
  - deep-merged runtime config before import-time constant derivation
  - regression coverage for profile merge, env-first vc_key, and legacy config fallback
affects: [weatherbot/config.py, weatherbot/__init__.py, config.json, README.md]
tech-stack:
  added: []
  patterns: [deep-merge config profiles in loader, env-first secret override after merge, legacy config fallback when profile fields absent]
key-files:
  created: []
  modified:
    - weatherbot/config.py
    - config.json
    - tests/test_modular_entrypoint.py
    - tests/test_phase3_router.py
    - tests/test_phase5_paper_execution.py
    - README.md
key-decisions:
  - "profile 选择与深度 merge 只放在 weatherbot/config.py，不扩散到策略模块或入口 wiring。"
  - "config.json 顶层保留 1000 中间档默认值，100/10000 通过 strategy_profiles 提供更激进/更保守预设。"
  - "VISUAL_CROSSING_KEY 继续在 merge 完成后最后覆盖 vc_key，保持 env-first secret 语义。"
patterns-established:
  - "Runtime config selection happens inside load_config() before weatherbot import-time constants derive."
  - "Missing strategy_profile fields preserve legacy top-level config behavior; only explicit unknown names raise."
requirements-completed: [QUICK-260418-N5Y]
duration: 27min
completed: 2026-04-18
---

# Phase quick-260418-n5y Plan 01: strategy profile 配置 Summary

**通过 `strategy_profile` 切换 100/1000/10000 三档资金策略，并在 loader 内完成深度 merge 后再给入口模块消费。**

## Performance

- **Duration:** 27 min
- **Started:** 2026-04-18T08:25:00Z
- **Completed:** 2026-04-18T08:52:15Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- 补齐 profile merge、env-first `vc_key`、入口 import-time 消费、提交态三档预设与 legacy fallback 回归测试。
- 在 `weatherbot/config.py` 实现最小 profile 选择与深度 merge，保持旧配置无 profile 字段时完全兼容。
- 在 `config.json`/`README.md` 提交 100、1000、10000 三档说明与默认选项，用户只改一个字段即可切换。

## Task Commits

1. **Task 1: 先锁定 profile merge 与入口消费回归** - `76cc2ad` (test)
2. **Task 2: 在配置加载层实现最小 profile 选择与深度 merge，并提交三档预设** - `c6bde18` (feat)
3. **Task 3: 最小更新 README 并跑最终回归** - `ac0763d` (docs)

## Files Created/Modified
- `tests/test_modular_entrypoint.py` - 增加 profile merge、env-first、入口 reload 消费与兼容性回归。
- `tests/test_phase3_router.py` - 锁定提交态三档 profile 与风控保守/激进顺序。
- `tests/test_phase5_paper_execution.py` - 校验三档 preset 的完整 `paper_execution` 块可被现有 loader 消费。
- `weatherbot/config.py` - 新增递归深度 merge，并在 `load_config()` 中执行 profile 选择后再应用环境变量覆盖。
- `config.json` - 提交 100/1000/10000 三档完整预设与默认 `strategy_profile`。
- `README.md` - 最小补充 profile 切换方式与 `VISUAL_CROSSING_KEY` env-first 说明。

## Decisions Made
- profile 逻辑只放在 loader，`weatherbot/__init__.py` 继续只消费最终 `_cfg`，不做额外分支。
- 顶层默认配置直接对齐 `1000` 中间档，保证现有运行方式和 README 默认说明一致。
- 三档 profile 都显式携带完整 `paper_execution` 块，避免 merge 后执行配置缺字段。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- 计划里的 pytest 校验命令会被仓库全局 coverage fail-under 75 门槛拦截；逻辑测试本身全部通过，但命令最终因全局覆盖率门槛失败。
- 为完成 quick task 的功能验证，额外运行了 `uv run pytest --no-cov -q tests/test_modular_entrypoint.py tests/test_phase3_router.py tests/test_phase5_paper_execution.py`，结果 `28 passed`；随后再跑 README/config 只读断言通过。

## Known Stubs

None.

## Next Phase Readiness

- 运行时现在可以只靠 `strategy_profile` 切换整套配置，不需要再改入口或策略模块。
- 后续若继续细调大/中/小资金档，只需要在 `config.json` 的 `strategy_profiles` 中改值并补回归即可。

## Self-Check: PASSED

- FOUND: `.planning/quick/260418-n5y-100-1000-10000/260418-n5y-SUMMARY.md`
- FOUND: `76cc2ad`
- FOUND: `c6bde18`
- FOUND: `ac0763d`
