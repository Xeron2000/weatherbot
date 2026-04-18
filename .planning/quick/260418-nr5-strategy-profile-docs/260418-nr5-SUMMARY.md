---
phase: quick-260418-nr5
plan: 01
subsystem: docs
tags: [strategy-profile, config-json, operator-playbook, docs]
requires:
  - phase: quick-260418-n5y
    provides: config-driven 100/1000/10000 strategy profile presets in committed config.json
provides:
  - docs/strategy-profile-playbook.md with current 1000 recommendation and committed profile thresholds
  - operator guidance for comparing 100/1000/10000, upgrading, and switching safely
affects: [docs/strategy-profile-playbook.md, config.json, operator decision flow]
tech-stack:
  added: []
  patterns: [docs quote committed strategy_profiles values directly, docs explain switching through strategy_profile only]
key-files:
  created:
    - docs/strategy-profile-playbook.md
    - .planning/quick/260418-nr5-strategy-profile-docs/260418-nr5-SUMMARY.md
  modified: []
key-decisions:
  - "手册只引用当前已提交 config.json 的真实 preset 数值，不补充 README 重复内容。"
  - "当前默认推荐明确写成 1000，因为它在仓库现阶段的风险、容量和执行耐心之间最平衡。"
patterns-established:
  - "Operator docs should explain strategy_profile switching via committed merge semantics, not generic bankroll advice."
requirements-completed: [QUICK-260418-NR5]
duration: 13min
completed: 2026-04-18
---

# Phase quick-260418-nr5 Plan 01: strategy profile docs Summary

**基于已提交的 `config.json` 三档 preset，补齐一份明确推荐 `1000` 的实盘选档与切换手册。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-18T09:00:00Z
- **Completed:** 2026-04-18T09:12:58Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- 新建 `docs/strategy-profile-playbook.md`，开头直接说明当前推荐档位是 `1000`，并解释原因。
- 用当前提交态 `strategy_profiles` 的真实数值对比 `100` / `1000` / `10000` 三档差异，覆盖资金、YES/NO 阈值、`max_size`、风控 cap、`order_policy`、`paper_execution`。
- 补齐升级时机、切换方式和切换后立即检查项，避免操作者只改顶层字段却忘了 profile merge 语义。

## Task Commits

1. **Task 1: 写出 strategy profile 实盘手册主体** - `72bfb18` (docs)
2. **Task 2: 交叉校对文档与当前配置一致** - `585ec85` (docs)

## Files Created/Modified
- `docs/strategy-profile-playbook.md` - 实盘使用手册，明确 `1000` 推荐档位、三档真实差异、升级判断、切换方式与检查项。

## Decisions Made
- 手册不扩写 `README.md`，避免同一套 profile 说明分散到两个文档重复维护。
- 文档结论严格绑定已提交的 `config.json`，重点写清为什么当前推荐是 `1000`，而不是给通用资金管理口号。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 补上“适用场景”显式章节名以通过完整性校验**
- **Found during:** Task 1（写出 strategy profile 实盘手册主体）
- **Issue:** 初版文档已有三档场景说明，但缺少精确的“适用场景”字样，导致计划里的自动检查失败。
- **Fix:** 把章节标题改成“适用场景与三档怎么理解”，保留原内容并让校验和人工阅读都更直观。
- **Files modified:** `docs/strategy-profile-playbook.md`
- **Verification:** 重新运行计划中的完整性检查，结果 `ok`。
- **Committed in:** `72bfb18`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** 仅为满足文档完整性校验的最小修正，没有扩大范围。

## Issues Encountered
- None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Next Phase Readiness
- 操作者现在无需反复打开 `config.json` 推断三档差异，可以直接按文档判断是否继续用 `1000`、何时升档、以及切换后该核对什么。
- 后续如果 `strategy_profiles` 再调值，这份手册需要同步更新，否则会重新产生 docs → operator decision 的误导风险。

## Self-Check: PASSED

- FOUND: `docs/strategy-profile-playbook.md`
- FOUND: `.planning/quick/260418-nr5-strategy-profile-docs/260418-nr5-SUMMARY.md`
- FOUND: `72bfb18`
- FOUND: `585ec85`
