---
phase: quick-260418-o5m
plan: 01
subsystem: config-docs
tags: [strategy-profile, config-json, operator-playbook, smoke-check]
requires:
  - phase: quick-260418-n5y
    provides: config-driven 100/1000/10000 strategy profile presets in committed config.json
  - phase: quick-260418-nr5
    provides: strategy profile operator playbook
provides:
  - config.json defaults to strategy_profile 100 for 100 USD operation
  - docs/strategy-profile-playbook.md aligned with 100-profile default and observation checklist
  - smoke-verified merged config baseline for status/report runs
affects: [config.json, docs/strategy-profile-playbook.md, operator verification flow]
tech-stack:
  added: []
  patterns: [change only top-level strategy_profile default, verify runtime via weatherbot.config.load_config]
key-files:
  created:
    - .planning/quick/260418-o5m-strategy-profile-100-bot/260418-o5m-SUMMARY.md
  modified:
    - config.json
    - docs/strategy-profile-playbook.md
key-decisions:
  - "默认切档只改顶层 strategy_profile，不重写 preset 内容，继续依赖 load_config() 深度 merge。"
  - "手册只做最小改动：把默认说明改成 100，并补一份面向 100 档的观察清单。"
patterns-established:
  - "Quick profile changes must ship with one merged-config smoke check plus status/report baseline output."
requirements-completed: [QUICK-260418-O5M]
duration: 15min
completed: 2026-04-18
---

# Phase quick-260418-o5m Plan 01: strategy profile 100 bot Summary

**把默认 `strategy_profile` 切到 `100`，并用一次 merge smoke 校验和简明观察清单固定小资金运行基线。**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-18T09:13:00Z
- **Completed:** 2026-04-18T09:28:19Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- 修改 `config.json` 顶层默认 `strategy_profile`，从 `1000` 切到 `100`，没有改动任何 `strategy_profiles` preset 本体。
- 最小更新 `docs/strategy-profile-playbook.md`：把默认说明改成 `100`，并加入一份面向 YES/NO、容量 cap、挂单节奏与异常排查的简明检查清单。
- 运行 `weatherbot.config.load_config('config.json')` smoke 校验，确认运行时 merge 后代表值落在 `100` 档；随后执行 `python bot_v2.py status` 与 `python bot_v2.py report` 固化观察基线。

## Task Commits

1. **Task 1: 切换默认 strategy profile 到 100** - `c3e8af6` (chore)
2. **Task 2: 最小更新手册中的默认说明与观察清单** - `8d0ddfc` (docs)
3. **Task 3: 做一次 merge 后 smoke 校验并固化观察基准** - no commit (verification-only)

## Files Created/Modified
- `config.json` - 顶层 `strategy_profile` 默认值改为 `100`，其余 preset 保持原样。
- `docs/strategy-profile-playbook.md` - 默认说明切到 `100`，增加“切到 100 后观察 bot 行为的检查清单”。

## Verification
- `python - <<'PY' ... json.loads(Path('config.json').read_text()) ... PY` → `ok`
- `python - <<'PY' ... from weatherbot.config import load_config ... PY` → `ok`
- `python bot_v2.py status` → 成功输出状态；当前基线显示 `Route decisions: accepted=0 rejected=396 released=0`，`active_orders=0`。
- `python bot_v2.py report` → 成功输出报告；当前没有 terminal orders，也没有 resolved markets。

## Operator Checklist
- 确认 merge 后关键值：`balance 100.0`、YES `max_price 0.08`、NO `min_price 0.72`、`global_usage_cap_pct 0.92`、`max_order_hours_open 36.0`。
- YES 候选应比 `1000` 档更宽，NO 候选也应更容易进池；若表现仍像 `1000` 档，先查 profile 是否切错。
- 因为总资金只有 `100`，单市场 / 单事件占用会更快碰到绝对金额上限。
- 订单等待与取消节奏应更短；若仍像 72 小时慢节奏，优先排查 merge 是否没生效。
- 行为异常先查 `strategy_profile = 100` 与 merge 结果，再判断是否是策略问题。

## Decisions Made
- 这次只做默认档位切换，不扩写或重构三档 preset 设计。
- 观察基准直接引用 smoke 校验过的代表值，避免文档和运行时再次漂移。

## Deviations from Plan

None - plan executed as written.

## Issues Encountered
- None.

## User Setup Required

None.

## Known Stubs

None.

## Next Phase Readiness
- 操作者现在直接按默认配置启动时，会落到 `100` 档小资金参数，不再默认沿用 `1000` 档。
- 后续若继续调整 `strategy_profiles[100]` 的代表值，需要同步更新 playbook 检查清单，否则会重新出现 docs/runtime 漂移。

## Self-Check: PASSED

- FOUND: `.planning/quick/260418-o5m-strategy-profile-100-bot/260418-o5m-SUMMARY.md`
- FOUND: `c3e8af6`
- FOUND: `8d0ddfc`
