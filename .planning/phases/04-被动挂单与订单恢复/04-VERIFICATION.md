---
phase: 04-被动挂单与订单恢复
verified: 2026-04-17T15:55:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "操作者可以查看每笔订单为何被挂出、刷新、撤销、部分成交或完全成交。"
    status: partial
    reason: "运行时订单事实与恢复账本已落地，但 CLI/report 只展示聚合计数与 terminal reason rollup，未逐笔展示 active/terminal 订单的明确 status 与 reason 轨迹。"
    artifacts:
      - path: "bot_v2.py"
        issue: "`print_order_summary()` 只输出 aggregate counts、active order 明细和 grouped terminal reasons；active order 行缺少显式 `status`，recent terminal orders 也未逐笔列出。"
      - path: "tests/test_phase4_reporting.py"
        issue: "回归只断言 `Recent terminal reasons` 聚合文案，未覆盖逐笔 terminal lifecycle 可见性，也未约束 active order 详情必须打印 `status`。"
    missing:
      - "在 status/report 中逐笔展示 unfinished active orders 的 `status`、`status_reason`、limit/tif/expires/fill progress。"
      - "在 report 中逐笔展示 recent terminal orders（至少含 order_id/status/reason/updated_at/limit_price 或 fill progress），而不只是 grouped reason counts。"
      - "补充 pytest，锁定逐笔订单 lifecycle 可见性，避免仅靠聚合 summary 通过回归。"
---

# Phase 4: 被动挂单与订单恢复 Verification Report

**Phase Goal:** 操作者可以把候选机会转成可恢复的被动限价单工作流，并在市场变化后自动管理订单生命周期。
**Verified:** 2026-04-17T15:55:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 操作者可以让机器人为候选机会生成 GTC 或 GTD 的被动限价单意图，并查看计划挂单价格与过期设置。 | ✓ VERIFIED | `bot_v2.py:1603-1665` 实现 `build_passive_order_intent()`；`config.json:40-47` 提供 `order_policy`；`tests/test_phase4_orders.py:98-193` 覆盖 GTC/GTD、limit price、expires_at。Spot-check: `uv run python -c ...build_passive_order_intent...` 输出 `planned 0.1 GTC None`。 |
| 2 | 每笔订单都能被查看为 planned、working、partial、filled、canceled 或 expired 之一，且状态变化连续可追踪。 | ✓ VERIFIED | `bot_v2.py:1668-1707` 统一状态机并 append-only 写 history；`bot_v2.py:1749-1787` 恢复 `status_counts`；`tests/test_phase4_orders.py:228-274` 与 `tests/test_phase4_scan_loop.py:178-250` 覆盖 planned→working→partial→filled / canceled / expired。 |
| 3 | 当天气预测或盘口变化让原报价变差时，机器人会自动刷新、撤销或放弃挂单，并说明原因。 | ✓ VERIFIED | `bot_v2.py:1900-2152` 的 `sync_market_order()` 处理 `candidate_downgraded`、`market_no_longer_ready`、`route_not_accepted`、`quote_repriced`、`expired`；`tests/test_phase4_scan_loop.py:253-324,327-499` 覆盖降级、refresh、guardrail 失效、GTD 过期。 |
| 4 | 机器人重启后可以恢复未完成订单、持仓和事件账本，操作者不会因为重启失去订单一致性。 | ✓ VERIFIED | `bot_v2.py:2267-2288,2345-2365,3312-3349` 通过 market JSON 恢复 `active_order/order_history`、重建 `order_state` 并在 monitor 分支 resume unfinished order；`tests/test_phase4_restore.py:65-265` 覆盖 partial resume、no duplicate order、terminal isolation。 |
| 5 | 操作者可以查看每笔订单为何被挂出、刷新、撤销、部分成交或完全成交。 | ✗ FAILED | `bot_v2.py:2993-3046` 的 `print_order_summary()` 仅打印 aggregate counts + grouped terminal reason counts；active order 明细未输出显式 `status`，recent terminal orders 也未逐笔列出。`tests/test_phase4_reporting.py:191-207` 只断言 rollup reasons 出现，未验证逐笔订单 history 可见性。 |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `config.json` | Phase 4 order policy defaults | ✓ VERIFIED | `order_policy` 存在且含 YES/NO TIF、GTD buffer、replace buffer、max open hours。 |
| `bot_v2.py` | order intent / lifecycle / restore / reporting wiring | ⚠️ PARTIAL | 订单意图、scan lifecycle、restore wiring 均成立；但 operator-facing reporting 未达到“逐笔可查看原因”要求。 |
| `tests/test_phase4_orders.py` | order intent/state-machine contracts | ✓ VERIFIED | 覆盖 config、intent、transition、loader backfill。 |
| `tests/test_phase4_scan_loop.py` | scan lifecycle regression | ✓ VERIFIED | 覆盖 active_order、partial/fill、cancel、refresh、expire。 |
| `tests/test_phase4_restore.py` | restart recovery regression | ✓ VERIFIED | 覆盖 `order_state` restore、resume、防重复建单。 |
| `tests/test_phase4_reporting.py` | status/report order visibility regression | ⚠️ PARTIAL | 测到 aggregate summary 与 reason rollup，但未锁定逐笔 status / terminal history 展示。 |
| `README.md` | Phase 4 verification docs | ✓ VERIFIED | `README.md:188-202` 提供 Phase 4 回归命令与 3 个 truth sources。 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `config.json` | `bot_v2.py` | ORDER_POLICY config loader | ✓ WIRED | `ORDER_POLICY = load_order_policy_config(_cfg)` (`bot_v2.py:95-132`)。 |
| `candidate_assessments + route_decisions` | `active_order` | `sync_market_order()` | ✓ WIRED | `bot_v2.py:1932-2099` 直接消费 persisted candidate/routing facts 生成或替换订单。 |
| `active_order/order_history` | `order_state` | `restore_order_state_from_markets()` + `load_state()` | ✓ WIRED | `bot_v2.py:1749-1787,2345-2365`。 |
| `order_state + active_order/order_history` | CLI status/report | `print_order_summary()` | ⚠️ PARTIAL | 数据已接线，但输出只到 aggregate/rollup，未完成 OBS-02 的逐笔可见性。 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `build_passive_order_intent()` | `limit_price/shares/time_in_force/expires_at` | `reservation + assessment + quote_snapshot + ORDER_POLICY` | Yes — `bot_v2.py:1603-1665` 直接从 route/quote/config 计算 | ✓ FLOWING |
| `sync_market_order()` | `active_order/order_history/position` | `candidate_assessments + route_decisions + reserved_exposure + quote_snapshot` | Yes — `bot_v2.py:1900-2152` 使用 persisted market facts 推进生命周期 | ✓ FLOWING |
| `restore_order_state_from_markets()` | `status_counts/active_orders` | `market.active_order + market.order_history` | Yes — `bot_v2.py:1749-1787` 从 market JSON 回放恢复 | ✓ FLOWING |
| `print_order_summary()` | lifecycle summary text | `state.order_state + markets[*].active_order/order_history` | Yes, but only aggregate/rollup | ⚠️ FLOWING BUT INSUFFICIENT |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 4 全量回归通过 | `uv run pytest tests/test_phase4_orders.py tests/test_phase4_scan_loop.py tests/test_phase4_restore.py tests/test_phase4_reporting.py -q` | `19 passed in 0.59s` | ✓ PASS |
| 被动订单意图输出 GTC/GTD 核心字段 | `uv run python -c '...build_passive_order_intent...'` | `planned 0.1 GTC None` | ✓ PASS |
| 重启恢复账本汇总 unfinished + terminal counts | `uv run python -c '...restore_order_state_from_markets...'` | 返回 `active_orders` + `status_counts`，含 `partial=1 filled=1 canceled=1` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ORDR-01 | 04-01, 04-02 | 生成 GTC/GTD 被动限价单意图 | ✓ SATISFIED | `bot_v2.py:1603-1665`；`tests/test_phase4_orders.py:98-193`。 |
| ORDR-02 | 04-01, 04-02, 04-03, 04-04 | 生命周期状态 planned/working/partial/filled/canceled/expired 可查看可追踪 | ✓ SATISFIED | 状态机 `bot_v2.py:1668-1707`、restore `1749-1787`、scan tests `178-250,253-499`。 |
| ORDR-03 | 04-02 | 预测/盘口变差时自动 refresh/cancel/abandon | ✓ SATISFIED | `bot_v2.py:1936-2099`；测试覆盖 `candidate_downgraded` / `quote_repriced` / `market_no_longer_ready` / `expired`。 |
| ORDR-04 | 04-03 | 重启后恢复 unfinished orders/positions/ledger | ✓ SATISFIED | `bot_v2.py:2345-2365,3312-3349`；`tests/test_phase4_restore.py:65-265`。 |
| OBS-02 | 04-04 | 查看每笔订单为何挂出/刷新/撤销/部分成交/完全成交 | ✗ BLOCKED | CLI 仅有 aggregate counts + grouped terminal reason summary（`bot_v2.py:2993-3046`），未逐笔展示 terminal orders，也未在 active order 明细输出显式 status。 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `tests/test_phase4_reporting.py` | 191-207 | 误导性回归：只断言 grouped terminal reason summary，不验证逐笔订单可见性 | ⚠️ Warning | 让 OBS-02 缺口在测试全部通过时仍被遗漏。 |
| `bot_v2.py` | 3026-3045 | reporting 仅输出 aggregate/rollup，不输出 per-order terminal lifecycle entries | 🛑 Blocker | 操作者无法在 CLI/report 中逐笔审计订单为什么被刷新/撤销/成交。 |

### Gaps Summary

Phase 4 的核心执行链路基本已经成立：候选会先变成 passive order，scan loop 会处理 refresh/cancel/partial/fill，重启后也能恢复 unfinished order 与账本。一句话说，**订单工作流本身是真的跑通了**。

但本 phase 映射了 `OBS-02`，而当前 operator-facing 输出还停留在“聚合摘要”层：

- active order 明细没有显式 `status`
- recent terminal orders 没有逐笔列出
- report 只能看到 grouped reason counts，不能直接看到“哪一笔订单因为什么被取消/部分成交/完全成交”

这意味着 Phase 4 还没有完全达到“操作者可查看每笔订单原因”的要求，因此判定为 `gaps_found`，不是 `passed`。

---

_Verified: 2026-04-17T15:55:00Z_
_Verifier: the agent (gsd-verifier)_
