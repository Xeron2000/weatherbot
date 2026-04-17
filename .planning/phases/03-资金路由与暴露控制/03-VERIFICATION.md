---
phase: 03-资金路由与暴露控制
verified: 2026-04-17T14:55:21Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 3: 资金路由与暴露控制 Verification Report

**Phase Goal:** 操作者可以让机器人在低价 YES 与高价 NO 之间独立分配资金，并把集中暴露限制在可接受范围内。
**Verified:** 2026-04-17T14:55:21Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 操作者可以为低价 YES 和高价 NO 两条策略腿设置独立资金预算，并看到每条腿当前占用的风险额度。 | ✓ VERIFIED | `config.json:29-39` 定义独立 `risk_router` 预算；`bot_v2.py:1322-1347` 构建分腿 `risk_state`；`bot_v2.py:2321-2340` 在 CLI 输出 YES/NO budget/reserved/available；`python bot_v2.py status` 实际输出了两条腿预算与 `global_reserved_worst_loss`。 |
| 2 | 路由按最坏损失而不是名义成本做预算占用和 cap 判断。 | ✓ VERIFIED | `bot_v2.py:1140-1152` 用 `candidate_worst_loss()` 计算 worst-loss；`bot_v2.py:1209-1318` 全部 cap 判断都基于 `reserved_worst_loss`；`tests/test_phase3_router.py:214-256` 覆盖 YES/NO worst-loss 口径。 |
| 3 | pure router 合同覆盖同 bucket YES/NO 冲突、同 event 最坏路径冲突，以及 edge/liquidity 排序。 | ✓ VERIFIED | `bot_v2.py:1167-1174` 实现 `sort_leg_candidates()`；`bot_v2.py:1225-1238` 实现 `same_bucket_conflict` / `event_cluster_conflict`；`tests/test_phase3_router.py:146-212` 明确断言冲突与排序。 |
| 4 | scan loop 会在 `candidate_assessments` 之后、旧开仓逻辑之前完成 per-leg routing。 | ✓ VERIFIED | `bot_v2.py:1934-1941` 先生成 `candidate_assessments` 再调用 `reconcile_market_reservation()`；`bot_v2.py:2047-2077` 旧 entry seam 只有命中 accepted YES route 才允许继续。 |
| 5 | 机器人会在单市场、单城市、单日期、单策略腿和总资金使用率触达上限时停止继续分配新单。 | ✓ VERIFIED | `bot_v2.py:1240-1314` 逐项拒绝 `leg_budget_exceeded`、`leg_cap_exceeded`、`global_cap_exceeded`、`market/city/date/event_cap_exceeded`；`tests/test_phase3_router.py:91-144` 全部 reason code 有回归覆盖。 |
| 6 | `state.json` / state truth 与 market JSON 会记录 `risk_state`、`route_decisions`、`reserved_exposure`。 | ✓ VERIFIED | `bot_v2.py:1677-1679` 给 market 新增 `route_decisions` / `reserved_exposure`；`bot_v2.py:1707-1709` 从 market reservations 重建 `risk_state`；`bot_v2.py:1542-1544`、`2208-2211` 将 route/risk 写回 market/state；`tests/test_phase3_scan_loop.py:107-143` 验证持久化字段。 |
| 7 | 已有 reservation 在候选降级、消失或 market 不再 ready 时会释放。 | ✓ VERIFIED | `bot_v2.py:1450-1459` 实现 `release_reserved_exposure()`；`bot_v2.py:1562-1568` 处理 `candidate_missing` / `candidate_downgraded`；`bot_v2.py:1865-1874` 处理 `market_no_longer_ready`；`tests/test_phase3_scan_loop.py:190-242` 覆盖 downgrade/missing。 |
| 8 | 当多个温区高度相关或 YES/NO 暴露互相冲突时，机器人会拒绝继续加仓并保留已有暴露的一致性。 | ✓ VERIFIED | `bot_v2.py:1547-1602` 先 reconcile 旧 reservation 再 reroute；`bot_v2.py:1225-1238` 按 event/bucket 拒绝冲突；`tests/test_phase3_scan_loop.py:245-276` 断言冲突时保留已有 reservation。 |
| 9 | 操作者可以在 `status` / `report` 中看到 route reject / release reasons、风险汇总和 exposure rollups。 | ✓ VERIFIED | `bot_v2.py:2344-2393` 输出 city/date/event exposure 与 reject/release reason summary；`bot_v2.py:2396-2481` 在 `print_status()` / `print_report()` 接线；`tests/test_phase3_reporting.py:52-107` 覆盖 operator-facing 文案；`python bot_v2.py report` 实际输出 risk/exposure/route summary。 |
| 10 | README 提供 Phase 3 回归命令与新增风险字段说明。 | ✓ VERIFIED | `README.md:170-184` 包含完整 Phase 2+3 回归命令与 `risk_state` / `route_decisions` / `reserved_exposure` 字段说明。 |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `config.json` | risk router conservative defaults | ✓ VERIFIED | 存在且含 `risk_router`、YES/NO budgets、各级 cap，见 `config.json:29-39`。 |
| `bot_v2.py` | 风险路由、reconciliation、reporting 主实现 | ✓ VERIFIED | 纯函数、scan loop 接线、risk ledger、reporting 全部存在且非 stub，见 `bot_v2.py:67-92`, `1140-1602`, `1689-2211`, `2321-2481`。 |
| `tests/test_phase3_router.py` | 路由纯函数回归 | ✓ VERIFIED | 覆盖 budgets/caps/conflicts/sorting/worst-loss，`uv run pytest ...` 通过。 |
| `tests/test_phase3_scan_loop.py` | scan loop 路由与释放回归 | ✓ VERIFIED | 覆盖 route persistence、global cap、downgrade/missing/conflict release。 |
| `tests/test_phase3_reporting.py` | operator-facing reporting 回归 | ✓ VERIFIED | 覆盖 status/report 风险摘要与 release reason 输出。 |
| `README.md` | Phase 3 验证与字段说明 | ✓ VERIFIED | 含回归命令和字段说明，见 `README.md:170-184`。 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `config.json` | `bot_v2.py` | `RISK_ROUTER` config loader | ✓ WIRED | `bot_v2.py:67-92` 读取 `risk_router` 并生成 `RISK_ROUTER`。 |
| `candidate_assessments` | `route_decisions` | `scan_and_update()` | ✓ WIRED | `bot_v2.py:1934-1941` 生成 candidate 后立即进入 `reconcile_market_reservation()`；`bot_v2.py:1503-1544` 产出并写回 `route_decisions`。 |
| prior reservation | refreshed candidate set | `reconcile_market_reservation()` | ✓ WIRED | `bot_v2.py:1547-1602` 会在 reroute 前释放/保留旧 reservation。 |
| event exposure / active reservations | route rejection | `same_bucket_conflict` / `event_cluster_conflict` | ✓ WIRED | `bot_v2.py:1225-1238` 按 event/bucket 冲突直接拒绝新候选。 |
| state risk ledger | `status` / `report` output | risk summary | ✓ WIRED | `bot_v2.py:1689-1709` 载入 risk ledger，`2396-2481` 输出 risk summary/exposure。 |
| market `route_decisions` / `reserved_exposure` | terminal output | reject/release explanation summary | ✓ WIRED | `bot_v2.py:2363-2393` 聚合 rejected 与 released reasons。 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `bot_v2.py` reporting | `risk_state` | `load_state()` → `restore_risk_state_from_markets()` / `scan_and_update()` persistence (`bot_v2.py:1707-1709`, `2208-2211`) | Yes — budget/reserved/exposure 由 reservations 回放或 scan 结果生成 | ✓ FLOWING |
| `bot_v2.py` route summary | `route_decisions` | `reconcile_market_reservation()` → `route_market_candidates()` → `save_market()` (`bot_v2.py:1503-1602`, `2155`) | Yes — accepted/rejected routes 从 candidate routing 真实生成 | ✓ FLOWING |
| `bot_v2.py` release summary | `reserved_exposure.release_reason` | `release_reserved_exposure()` / skip-path release (`bot_v2.py:1450-1459`, `1865-1874`) | Yes — downgrade/missing/market_not_ready 直接写入 persisted reservation audit trail | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 3 regression suite passes | `uv run pytest tests/test_phase3_router.py tests/test_phase3_scan_loop.py tests/test_phase3_reporting.py -q` | `14 passed in 0.06s` | ✓ PASS |
| Phase 2 + 3 combined suite passes | `uv run pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py tests/test_phase2_reporting.py tests/test_phase3_router.py tests/test_phase3_scan_loop.py tests/test_phase3_reporting.py -q` | `31 passed in 0.09s` | ✓ PASS |
| CLI status exposes leg/global risk usage | `python bot_v2.py status` | 输出 `YES_SNIPER` / `NO_CARRY` budgets 和 `global_reserved_worst_loss=...` | ✓ PASS |
| CLI report exposes risk/exposure summaries | `python bot_v2.py report` | 输出 `Risk usage`、`City/Date/Event exposure`、`Route decisions` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| STRAT-04 | 03-01, 03-02, 03-04 | 低价 YES / 高价 NO 两条腿独立分配资金，并限制每条腿最大风险暴露 | ✓ SATISFIED | `config.json:29-39`, `bot_v2.py:1322-1347`, `2321-2340`, `tests/test_phase3_router.py:82-144`, `tests/test_phase3_scan_loop.py:107-143` |
| RISK-01 | 03-01, 03-02, 03-03, 03-04 | 单市场/城市/日期/策略腿/总资金使用率暴露上限 | ✓ SATISFIED | `bot_v2.py:1240-1314`, `1350-1438`, `tests/test_phase3_router.py:91-144`, `tests/test_phase3_scan_loop.py:146-188` |
| RISK-02 | 03-01, 03-03, 03-04 | 阻止相关性过高温区或冲突 YES/NO 暴露继续加仓 | ✓ SATISFIED | `bot_v2.py:1225-1238`, `1547-1602`, `tests/test_phase3_router.py:146-186`, `tests/test_phase3_scan_loop.py:245-276` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `README.md` | 166, 184 | 文档示例仍引用不存在的 `weatherbet.py` CLI (`python weatherbet.py status/report`) | ⚠️ Warning | Phase 3 README 主体已补齐回归命令和字段说明，但操作者若照这两行执行会失败；已通过 `python weatherbet.py status` 实测报 “No such file”。 |
| `tests/test_phase3_scan_loop.py` | - | `market_no_longer_ready` 释放路径没有专门回归用例 | ⚠️ Warning | 代码在 `bot_v2.py:1865-1874` 已实现 skipped-market release，但当前 Phase 3 测试仅覆盖 `candidate_downgraded` / `candidate_missing` / conflict。 |

### Human Verification Required

None.

### Gaps Summary

没有发现会阻断 Phase 3 目标达成的缺口。资金路由、worst-loss 风险账本、冲突拒绝、reservation release、以及 operator-facing risk/report 输出都已在代码、持久化路径和回归测试中闭环验证。

存在两项非阻断性警告：README 里仍有旧 CLI 文件名 `weatherbet.py`，以及 `market_no_longer_ready` 缺少专门测试覆盖。这两项不影响本 phase 目标是否达成，但建议后续修正。

---

_Verified: 2026-04-17T14:55:21Z_
_Verifier: the agent (gsd-verifier)_
