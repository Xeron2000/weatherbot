---
phase: 02-候选定价与双策略筛选
verified: 2026-04-17T12:23:51Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
human_verification:
  - test: "运行一次真实 scan，并检查生成的 market JSON"
    expected: "admissible market 会写入 bucket_probabilities、quote_snapshot、candidate_assessments，且 execution_stop_reasons 与候选拒绝/缩量/降价原因一致"
    why_human: "依赖真实 Polymarket Gamma/CLOB 与天气源返回；自动化回归只覆盖 fixture 合同，无法证明线上 payload 没有漂移"
  - test: "运行 `python bot_v2.py status` 与 `python bot_v2.py report` 评估候选解释可读性"
    expected: "操作者能直接看懂 strategy_leg、bucket、status、reasons、fair 与 quote 字段，不需要回头翻 JSON"
    why_human: "字段存在和字符串断言已自动验证，但“是否真正好读”仍属于人工 UX 判断"
---

# Phase 2: 候选定价与双策略筛选 Verification Report

**Phase Goal:** 操作者可以基于 band probability 和当前可执行盘口，为低价 YES 与高价 NO 两条策略腿分别筛出值得挂单的机会。
**Verified:** 2026-04-17T12:23:51Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 操作者可以看到每个温区按多源天气预测计算出的 band probability，而不是单点温度猜测。 | ✓ VERIFIED | `aggregate_probability()` 为每个 contract 生成 `per_source_probability`、`aggregate_probability`、`fair_yes`、`fair_no`，见 `bot_v2.py:316-358`；回归见 `tests/test_phase2_probability.py:91-127`。 |
| 2 | 同一 market 的所有 bucket 概率表都基于 Phase 1 的 `market_contracts` 全量生成。 | ✓ VERIFIED | `scan_and_update()` 先写入 `market_contracts`，再基于该字段生成 `bucket_probabilities`，见 `bot_v2.py:1321-1323, 1387-1395`。 |
| 3 | scan loop 会把概率表持久化到 market JSON，供后续 YES/NO evaluator 直接消费。 | ✓ VERIFIED | `new_market()` 预置 `bucket_probabilities`，ready market 写入、skipped market 清空，见 `bot_v2.py:1166, 1341, 1387-1401`；回归见 `tests/test_phase2_probability.py:130-227`。 |
| 4 | 操作者可以分别配置低价 YES 与高价 NO 的价格、概率、时间窗和仓位阈值，并看到两类候选独立筛选结果。 | ✓ VERIFIED | `config.json:11-28` 定义 `yes_strategy`/`no_strategy`；`bot_v2.py:41-68` 加载独立配置；YES/NO 分腿回归见 `tests/test_phase2_strategies.py:101-210`。 |
| 5 | scan loop 会对同一 bucket 同时跑 YES_SNIPER 与 NO_CARRY evaluator，并得到独立候选结论。 | ✓ VERIFIED | `build_candidate_assessments()` 对每个 bucket 同时调用 `evaluate_yes_candidate()` 与 `evaluate_no_candidate()`，见 `bot_v2.py:1077-1085`；回归见 `tests/test_phase2_strategies.py:212-327`。 |
| 6 | 候选评估会把 accept / reject / size_down / reprice 结构化写入 market JSON，而不是只打印。 | ✓ VERIFIED | evaluator 输出 `status`、`reasons`、`size_multiplier`、`quote_context`，并由 `scan_and_update()` 持久化 `candidate_assessments`，见 `bot_v2.py:951-1074, 1397-1401`。 |
| 7 | 机器人会结合 bid/ask、tick size、市场状态等可执行盘口信息判断某个候选是否值得挂单。 | ✓ VERIFIED | `get_token_quote_snapshot()` 读取 token-level bid/ask、tick size、book 状态，见 `bot_v2.py:847-905`；回归见 `tests/test_phase2_quotes.py:59-138`。 |
| 8 | 缺少实时 quote、tick size、open orderbook 或 market state 不可执行时，候选会被停单并写明原因。 | ✓ VERIFIED | quote helper 产出 `missing_quote_book`、`orderbook_empty`、`market_closed`、`tick_size_missing`，evaluator 继续把这些原因写入 `reasons`，见 `bot_v2.py:852-903, 973-997, 1037-1059`；回归见 `tests/test_phase2_quotes.py:93-212` 与 `tests/test_phase2_strategies.py:318-327`。 |
| 9 | YES 与 NO 两侧 quote 真相来自各自 token_id，而不是 `1 - yes_price` 或 Gamma convenience price。 | ✓ VERIFIED | `build_quote_snapshot()` 分别读取 `token_id_yes` / `token_id_no`，见 `bot_v2.py:907-926`；NO 独立 quote 回归见 `tests/test_phase2_quotes.py:59-91`。 |
| 10 | 操作者可以在 status/report 中看见每个候选为何 accepted、rejected、size_down 或 reprice。 | ✓ VERIFIED | `print_candidate_assessments()` 直接输出 `status` 与 `reasons`，并由 `print_scan_summary()` 接到 `print_status()` / `print_report()`，见 `bot_v2.py:1701-1765, 1834-1848`；回归见 `tests/test_phase2_reporting.py:39-149`。 |
| 11 | 候选解释同时展示 strategy_leg、bucket、fair price 与 quote context，而不是只有 free-form print 文本。 | ✓ VERIFIED | 输出格式直接包含 `strategy_leg`、bucket、`fair=`、`quote=`，见 `bot_v2.py:1711-1727`；字符串断言见 `tests/test_phase2_reporting.py:68-76`。 |
| 12 | Phase 2 的本地验证命令和候选 JSON 字段在 README 中有最小说明。 | ✓ VERIFIED | `README.md:149-163` 记录 Phase 2 回归命令与 `bucket_probabilities`、`quote_snapshot`、`candidate_assessments` 字段说明。 |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `bot_v2.py` | 概率、quote、双策略、reporting 主实现 | ✓ VERIFIED | gsd-tools 对 4 个 plan artifact 检查均通过；实现见 `bot_v2.py:316-358, 847-1085, 1128-1401, 1701-1848`。 |
| `config.json` | YES/NO 分腿配置块 | ✓ VERIFIED | `config.json:11-28` 存在独立 `yes_strategy` 与 `no_strategy`。 |
| `tests/test_phase2_probability.py` | STRAT-01 回归 | ✓ VERIFIED | 覆盖概率质量、持久化、stale clear，见 `tests/test_phase2_probability.py:91-227`。 |
| `tests/test_phase2_quotes.py` | MKT-04 / RISK-03 回归 | ✓ VERIFIED | 覆盖 token quote、reason code、scan 持久化、monitor execution truth，见 `tests/test_phase2_quotes.py:59-263`。 |
| `tests/test_phase2_strategies.py` | STRAT-02 / STRAT-03 回归 | ✓ VERIFIED | 覆盖独立阈值、同 bucket 双腿分叉、assessment 持久化，见 `tests/test_phase2_strategies.py:101-327`。 |
| `tests/test_phase2_reporting.py` | OBS-01 回归 | ✓ VERIFIED | 覆盖 status/report 输出合同，见 `tests/test_phase2_reporting.py:39-149`。 |
| `tests/fixtures/phase2_gamma_event.json` | 稳定 weather event fixture | ✓ VERIFIED | gsd-tools artifact check passed。 |
| `tests/fixtures/phase2_clob_book_yes.json` | YES token orderbook fixture | ✓ VERIFIED | gsd-tools artifact check passed。 |
| `README.md` | Phase 2 验证与字段说明 | ✓ VERIFIED | gsd-tools artifact check passed；说明见 `README.md:149-163`。 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `bot_v2.py` | `tests/test_phase2_probability.py` | probability helper contract | ✓ WIRED | gsd-tools verified=true。 |
| `bot_v2.py` | `data/markets/*.json` | scan_and_update persistence | ✓ WIRED | gsd-tools verified=true；`scan_and_update()` 写入 `bucket_probabilities`。 |
| `bot_v2.py` | `tests/test_phase2_quotes.py` | quote snapshot guardrail contract | ✓ WIRED | gsd-tools verified=true。 |
| `bot_v2.py` | market JSON | token-side quote persistence | ✓ WIRED | gsd-tools verified=true；`scan_and_update()` 写入 `quote_snapshot`。 |
| `config.json` | `bot_v2.py` | strategy config loader | ✓ WIRED | gsd-tools verified=true；`bot_v2.py:41-68` 加载 yes/no 配置。 |
| `bot_v2.py` | market JSON | candidate_assessments persistence | ✓ WIRED | gsd-tools verified=true；`bot_v2.py:1397-1401` 写入。 |
| `bot_v2.py` | `tests/test_phase2_reporting.py` | operator-facing reporting contract | ✓ WIRED | gsd-tools verified=true。 |
| market JSON | `print_status()` / `print_report()` | `candidate_assessments` | ✓ WIRED | 人工核查 `load_all_markets()` → `print_scan_summary()` → `print_candidate_assessments()` 直接读取 `m.get("candidate_assessments")`，见 `bot_v2.py:1118-1125, 1701-1765, 1834-1848`。 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `bot_v2.py` probability pipeline | `bucket_probabilities` | `market_contracts` + `take_forecast_snapshot()` → `aggregate_probability()` | Yes | ✓ FLOWING |
| `bot_v2.py` quote pipeline | `quote_snapshot` | `get_clob_book()` + `get_clob_tick_size()` → `get_token_quote_snapshot()` | Yes | ✓ FLOWING |
| `bot_v2.py` strategy pipeline | `candidate_assessments` | `bucket_probabilities` + `quote_snapshot` → `build_candidate_assessments()` | Yes | ✓ FLOWING |
| reporting pipeline | candidate lines | `load_all_markets()` persisted `candidate_assessments` → `print_candidate_assessments()` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 2 regression suite | `uv run pytest tests/test_phase2_probability.py tests/test_phase2_quotes.py tests/test_phase2_strategies.py tests/test_phase2_reporting.py -q` | `17 passed in 0.08s` | ✓ PASS |
| Strategy config and market defaults load | `python -c "import bot_v2; ..."` | `True True True True True` | ✓ PASS |
| CLI status command runs | `python bot_v2.py status` | 正常输出状态页，并展示 accepted/skipped 与 candidate assessments 摘要 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `MKT-04` | `02-02-PLAN.md` | 基于可执行盘口信息评估是否值得挂单 | ✓ SATISFIED | `get_token_quote_snapshot()` + `build_quote_snapshot()` + quotes 回归，见 `bot_v2.py:847-926`、`tests/test_phase2_quotes.py:59-212`。 |
| `STRAT-01` | `02-01-PLAN.md` | 为每个温区计算 band probability | ✓ SATISFIED | `aggregate_probability()` 与回归见 `bot_v2.py:316-358`、`tests/test_phase2_probability.py:91-127`。 |
| `STRAT-02` | `02-03-PLAN.md` | 低价 YES 独立阈值 | ✓ SATISFIED | `YES_STRATEGY` + `evaluate_yes_candidate()`，见 `config.json:11-19`、`bot_v2.py:951-1013`。 |
| `STRAT-03` | `02-03-PLAN.md` | 高价 NO 独立阈值 | ✓ SATISFIED | `NO_STRATEGY` + `evaluate_no_candidate()`，见 `config.json:20-28`、`bot_v2.py:1015-1074`。 |
| `RISK-03` | `02-02-PLAN.md` | 缺少关键元数据/实时行情时自动停单 | ✓ SATISFIED | execution stop reasons 从 quote helper 传到 candidate reasons，见 `bot_v2.py:852-903, 973-997, 1037-1059`。 |
| `OBS-01` | `02-04-PLAN.md` | 查看候选为何被接受/拒绝/缩量/降价 | ✓ SATISFIED | `print_candidate_assessments()` 与 reporting 回归，见 `bot_v2.py:1701-1727`、`tests/test_phase2_reporting.py:39-149`。 |

Orphaned requirements for Phase 2: none.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `README.md` | 16, 112-114, 163 | 文档仍引用不存在的 `weatherbet.py` 入口 | ⚠️ Warning | Phase 2 回归命令正确，但 README 基础 CLI 示例会误导操作者使用错误入口；实际可执行脚本是 `bot_v2.py`。 |

### Human Verification Required

### 1. 真实外部数据链路抽查

**Test:** 在网络正常时运行一次真实扫描，检查新生成的 `data/markets/*.json`。
**Expected:** admissible market 含 `bucket_probabilities`、`quote_snapshot`、`candidate_assessments`；若盘口缺 tick size / 空簿 / closed，`candidate_assessments[].reasons` 与 `quote_snapshot[].execution_stop_reasons` 一致。
**Why human:** 依赖真实天气源与 Polymarket Gamma/CLOB payload；当前自动化只覆盖本地 fixture 合同，无法证明线上 schema 没有漂移。

### 2. CLI 候选解释可读性抽查

**Test:** 在存在候选数据的前提下运行 `python bot_v2.py status` 与 `python bot_v2.py report`。
**Expected:** 操作者能直接读懂每条候选的 `strategy_leg`、bucket、`status`、`reasons`、`fair`、`quote`，无需再翻 JSON。
**Why human:** 自动化已经验证字段存在和命令可运行，但“够不够清晰”仍是 operator-facing 文本质量判断。

### Gaps Summary

无阻塞性代码缺口。Phase 2 的 must-haves、artifacts、key links 与数据流均已落地并通过自动化回归；剩余工作是外部服务实链路与 CLI 可读性的人工验收。

---

_Verified: 2026-04-17T12:23:51Z_
_Verifier: the agent (gsd-verifier)_
