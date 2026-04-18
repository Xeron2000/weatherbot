---
phase: 05-保守 paper execution 与回放验证
verified: 2026-04-18T02:08:37Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 5: 保守 paper execution 与回放验证 Verification Report

**Phase Goal:** 操作者可以在不使用真实资金的前提下运行完整模拟执行，并检验被动挂单假设是否足够保守。
**Verified:** 2026-04-18T02:08:37Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 操作者可以运行完整 paper trading 模式，从候选、挂单、成交到持仓变化都不触发真实下单。 | ✓ VERIFIED | `scan_and_update()` 走候选→`sync_market_order()`→`sync_active_order_with_paper_engine()`→`build_position_from_order()` 链路，且订单推进只调用 `simulate_paper_execution_step()`，见 `bot_v2.py:2399-2455`, `bot_v2.py:2882-3095`；搜索 `requests.post|submit_order|place_order|cancel_order` 无匹配。 |
| 2 | 模拟结果会显式体现下单延迟、排队、部分成交、touch-not-fill 与撤单延迟，而不是把挂单直接视为成交。 | ✓ VERIFIED | `simulate_paper_execution_step()` 明确处理 `submission_pending` / `submission_released` / `touch_not_fill` / `partial_fill` / `filled` / `cancel_requested` / `cancel_confirmed`，见 `bot_v2.py:1966-2192`。 |
| 3 | 操作者可以回放订单与成交事件，检查仿真成交是否过于乐观，并定位哪些 fill 假设需要调参。 | ✓ VERIFIED | `print_replay()` 直接读取持久化事件并输出 fill quality 摘要，见 `bot_v2.py:3486-3696`；CLI 入口见 `bot_v2.py:4164-4206`；README 给出命令见 `README.md:215-238`。 |
| 4 | paper 模式的执行假设来自显式配置，而不是散落在运行时硬编码。 | ✓ VERIFIED | `config.json:48-55` 定义 `paper_execution`；`load_paper_execution_config()` 强制校验字段，见 `bot_v2.py:136-165`。 |
| 5 | execution event / paper state 合同是统一且可恢复的事实源。 | ✓ VERIFIED | market 默认 schema 包含 `paper_execution_state`、`execution_events`、`execution_metrics`，见 `bot_v2.py:1838-1877`, `bot_v2.py:2725-2804`；`load_market()` / `load_all_markets()` 会回填默认值，见 `bot_v2.py:2725-2746`。 |
| 6 | full scan 与 monitor 分支都会继续推进未完成订单，而不是只在首轮 scan 中模拟。 | ✓ VERIFIED | `scan_and_update()` 与 `monitor_active_orders()` 都调用 `sync_market_order()`，后者统一走 paper engine，见 `bot_v2.py:3093-3097`, `bot_v2.py:4042-4079`。 |
| 7 | replay 输出会指出 touch-not-fill、queue delay、partial fill、cancel delay、adverse fill 等保守假设证据。 | ✓ VERIFIED | `build_replay_fill_quality()` 汇总 `touch_not_fill_count`、`queue_wait_ms`、`partial_fill_slices`、`cancel_delay_ms`、`adverse_buffer_hits` 与 `tune_hints`，见 `bot_v2.py:3559-3608`。 |
| 8 | README 提供本地回归命令与 replay 真相源说明，操作者可自助复查假设。 | ✓ VERIFIED | `README.md:217-238` 明确给出 pytest 回归命令、`python bot_v2.py replay` 用法和三类 truth sources。 |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `config.json` | `paper_execution` 顶层配置块 | ✓ VERIFIED | 存在完整 7 个保守参数，见 `config.json:48-55`。 |
| `bot_v2.py` | paper execution helper、runtime wiring、replay CLI | ✓ VERIFIED | 配置加载、事件录入、单步仿真、scan/monitor 接线、replay 全在同文件落地，见 `bot_v2.py:136-168`, `bot_v2.py:1838-2192`, `bot_v2.py:2371-2606`, `bot_v2.py:3486-3696`, `bot_v2.py:4164-4206`。 |
| `tests/test_phase5_paper_execution.py` | Phase 5 纯函数合同测试 | ✓ VERIFIED | 覆盖 submission latency、queue、partial、filled、cancel latency，见 `tests/test_phase5_paper_execution.py:86-317`。 |
| `tests/test_phase5_scan_loop.py` | scan/monitor 集成回归 | ✓ VERIFIED | 覆盖 touch-not-fill、partial→filled、cancel_pending→canceled、restart resume，见 `tests/test_phase5_scan_loop.py:51-563`。 |
| `tests/test_phase5_replay.py` | operator-facing replay 回归 | ✓ VERIFIED | 覆盖时间线展示、fill quality 摘要、market/order 精确过滤，见 `tests/test_phase5_replay.py:69-316`。 |
| `README.md` | Phase 5 验证与 replay 使用说明 | ✓ VERIFIED | 存在独立 “Phase 5 Verification” 段落，见 `README.md:215-238`。 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `config.json` | `bot_v2.py` | `load_paper_execution_config()` | ✓ WIRED | `bot_v2.py:136-168` 在模块加载时读取并校验 `config.json.paper_execution`。 |
| `bot_v2.py` | `tests/test_phase5_paper_execution.py` | pure helper contracts | ✓ WIRED | 测试直接调用 `load_paper_execution_config()` / `simulate_paper_execution_step()`，见 `tests/test_phase5_paper_execution.py:86-317`。 |
| `sync_market_order()` | `market["execution_events"]` | paper execution step persistence | ✓ WIRED | `sync_market_order()` → `sync_active_order_with_paper_engine()` → `simulate_paper_execution_step()`，随后把 `execution_events` / `paper_execution_state` / `execution_metrics` 回写到 market，见 `bot_v2.py:2399-2410`, `bot_v2.py:2458-2606`。 |
| `monitor_active_orders()` | `paper_execution_state` | resume unfinished order simulation | ✓ WIRED | `monitor_active_orders()` 读取未完成订单，刷新 quote 后继续调用 `sync_market_order()`，并 `save_market()` 持久化续跑结果，见 `bot_v2.py:4042-4079`。 |
| `bot_v2.py` | `execution_events` | replay renderer | ✓ WIRED | `events_for_order()` 与 `print_replay()` 只读取持久化 `execution_events`，见 `bot_v2.py:3509-3515`, `bot_v2.py:3643-3696`。 |
| `README.md` | `python bot_v2.py replay` | verification instructions | ✓ WIRED | README 直接给出 replay CLI 命令，见 `README.md:229-235`。 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `sync_active_order_with_paper_engine()` | `market["execution_events"]` / `market["paper_execution_state"]` | `simulate_paper_execution_step()` 内部通过 `record_execution_event()` 追加事件，再由 `sync_active_order_with_paper_engine()` 回写，见 `bot_v2.py:1988-2192`, `bot_v2.py:2399-2410` | Yes | ✓ FLOWING |
| `build_position_from_order()` | `entry_price` | `average_order_fill_price(order.history[*].fill_price)`；`fill_price` 来自 paper event 的 `simulated_fill_price`，见 `bot_v2.py:2417-2434`, `bot_v2.py:2281-2331` | Yes | ✓ FLOWING |
| `print_replay()` | `events`, `quality` | `events_for_order(market, order_id)` + `build_replay_fill_quality(order, events, paper_state)`，直接消费持久化 market JSON，见 `bot_v2.py:3509-3608`, `bot_v2.py:3643-3696` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 5 regression suite passes | `uv run pytest tests/test_phase5_paper_execution.py tests/test_phase5_scan_loop.py tests/test_phase5_replay.py -q` | `14 passed in 0.08s` | ✓ PASS |
| Replay CLI runs without rescanning | `python bot_v2.py replay --limit 1` | 正常输出 `Replay orders` 和空结果提示，无异常退出 | ✓ PASS |
| New market schema includes paper execution defaults | `python -c "import bot_v2; ..."` | 输出 `idle 0 [...]`，确认默认 state/events/metrics 就绪 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `SIM-01` | `05-01-PLAN.md`, `05-02-PLAN.md` | 操作者可以在不发送真实订单的前提下运行完整的 paper trading 模式 | ✓ SATISFIED | runtime 只走 paper engine，`scan_and_update()`/`monitor_active_orders()` 可完成候选→挂单→成交→持仓链路；相关回归见 `tests/test_phase5_scan_loop.py:51-563`。 |
| `SIM-02` | `05-01-PLAN.md`, `05-02-PLAN.md` | 操作者可以让 paper 模式保守建模下单延迟、排队、部分成交、touch-not-fill 与撤单延迟 | ✓ SATISFIED | `simulate_paper_execution_step()` 覆盖全部保守阶段，配置来自 `config.json.paper_execution`；回归见 `tests/test_phase5_paper_execution.py:105-317`。 |
| `SIM-03` | `05-03-PLAN.md` | 操作者可以回放订单和成交事件，用来检验成交假设是否过于乐观 | ✓ SATISFIED | `print_replay()` + `build_replay_fill_quality()` + README 验证入口，回归见 `tests/test_phase5_replay.py:69-316`, `README.md:215-238`。 |

**Orphaned requirements:** None. `REQUIREMENTS.md` 中映射到 Phase 5 的仅有 `SIM-01`、`SIM-02`、`SIM-03`，且都已在计划 frontmatter 中声明并被验证。

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | — | 未在 Phase 5 相关文件中发现 TODO/FIXME/placeholder stub；检出的空列表/空字典均为初始化容器、默认 schema 或测试夹具，不构成用户可见空实现。 | ℹ️ Info | 无阻塞影响 |

### Human Verification Required

None.

### Gaps Summary

未发现阻塞 Phase 05 目标达成的缺口。代码已同时满足：

- 完整 paper execution 链路只走本地仿真事实源；
- 保守成交假设以显式配置和 append-only 事件账本表达；
- replay CLI 可以直接复盘逐笔订单时间线并暴露需要调参的保守假设。

---

_Verified: 2026-04-18T02:08:37Z_
_Verifier: the agent (gsd-verifier)_
