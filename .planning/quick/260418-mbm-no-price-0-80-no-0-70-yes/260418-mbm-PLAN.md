---
phase: quick-260418-mbm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - weatherbot/strategy.py
  - weatherbot/paper_execution.py
  - tests/test_phase2_quotes.py
  - tests/test_strategy_paper_execution.py
  - tests/test_phase4_restore.py
autonomous: true
requirements:
  - QUICK-NO-LARGE-STOP
must_haves:
  truths:
    - "YES 持仓不再因为旧的通用 stop-loss 规则被提前平仓"
    - "NO 持仓只有在入场价 >= 0.80 且当前 NO 市场价 <= 0.70 时才触发止损"
    - "旧 market JSON 即使缺少 position.entry_side/token_side 也不会因为新规则崩溃或失去兼容性"
  artifacts:
    - path: "weatherbot/paper_execution.py"
      provides: "filled order -> position 的 side 元数据持久化"
    - path: "weatherbot/strategy.py"
      provides: "按 YES/NO 分支的止损判定与旧持仓兼容回退"
    - path: "tests/test_phase2_quotes.py"
      provides: "monitor_positions 的 YES/NO 止损回归测试"
    - path: "tests/test_phase4_restore.py"
      provides: "旧 position 缺 side 元数据的兼容回归测试"
  key_links:
    - from: "weatherbot/paper_execution.py"
      to: "weatherbot/strategy.py"
      via: "position.token_side / position.entry_side"
      pattern: "build_position_from_order"
    - from: "weatherbot/strategy.py"
      to: "quote_snapshot[].yes / quote_snapshot[].no"
      via: "scan_and_update / monitor_positions 读取对应 side 的 exit price"
      pattern: "token_side"
    - from: "tests/test_phase4_restore.py"
      to: "weatherbot/strategy.py"
      via: "legacy market JSON without side metadata"
      pattern: "entry_side"
---

<objective>
把持仓止损语义改成这条单一新规则：YES 不止损；NO 只有大仓位（入场价 >= 0.80）才在 NO 市场价跌到 0.70 时止损，同时保持旧 market JSON 兼容。

Purpose: 这次只收紧高价 NO 的风险，不顺手改 forecast close、take-profit、订单路由或其他策略门槛。
Output: side-aware position metadata、按 YES/NO 分支的止损逻辑、以及覆盖 YES/NO/legacy 三类场景的回归测试。
</objective>

<execution_context>
@/home/xeron/.config/opencode/get-shit-done/workflows/execute-plan.md
@/home/xeron/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@AGENTS.md
@weatherbot/strategy.py
@weatherbot/paper_execution.py
@weatherbot/__init__.py
@tests/test_phase2_quotes.py
@tests/test_strategy_paper_execution.py
@tests/test_phase4_restore.py

<interfaces>
From weatherbot/paper_execution.py:
```python
def build_position_from_order(market, order, assessment, forecast_snap):
    ...
```

Current position payload is missing stable side metadata:
```python
position = {
    "market_id": order.get("market_id"),
    "entry_price": entry_price,
    "shares": filled_shares,
    "cost": round(filled_shares * entry_price, 2),
    "status": "open",
}
```

From weatherbot/strategy.py:
```python
if mkt.get("position") and mkt["position"].get("status") == "open":
    entry = pos["entry_price"]
    stop = pos.get("stop_price", entry * 0.80)
    if current_price <= stop:
        ...
```

This stop branch currently does not distinguish YES vs NO and therefore cannot implement the new rule safely.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: 先补回归测试，锁定 YES/NO/legacy 三种止损语义</name>
  <files>tests/test_phase2_quotes.py, tests/test_strategy_paper_execution.py, tests/test_phase4_restore.py</files>
  <behavior>
    - Test 1: YES 持仓即使价格跌破旧的 20% stop，也不会在 `monitor_positions()` 中被 stop-loss 平仓。
    - Test 2: `token_side/entry_side=no` 且 `entry_price>=0.80` 的持仓，在当前 NO bid <= 0.70 时会被平仓并写入 `stop_loss`。
    - Test 3: `build_position_from_order()` 会把 filled order 的 side 元数据持久化到 position，供后续监控读取。
    - Test 4: 旧 market JSON 缺少 `position.entry_side/token_side` 时，监控逻辑仍可运行并保持兼容回退，不因新字段缺失抛错。
  </behavior>
  <action>在 `tests/test_phase2_quotes.py` 增加监控层回归：一条 YES 场景明确证明旧 stop 已失效；一条 NO 场景明确证明只有高价 NO 会在 0.70 触发止损，并且取价来自 NO 侧 quote 而不是 YES 侧。于 `tests/test_strategy_paper_execution.py` 增加 `build_position_from_order()` 的 position side 持久化断言。于 `tests/test_phase4_restore.py` 增加 legacy market regression，构造缺少 side 元数据的旧 position，要求新逻辑不崩溃并保留兼容行为。不要扩展到 take-profit、forecast shift close、risk router 或订单恢复之外的新语义。</action>
  <verify>
    <automated>uv run pytest -q tests/test_phase2_quotes.py tests/test_strategy_paper_execution.py tests/test_phase4_restore.py</automated>
  </verify>
  <done>测试明确锁定 YES 无止损、NO 高价仓 0.70 止损、以及旧 position 缺 side 字段的兼容路径，并且这些断言在修复前至少有一部分会失败。</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 持久化 position side 元数据并为旧持仓提供兼容回退</name>
  <files>weatherbot/paper_execution.py</files>
  <behavior>
    - Test 1: 新开仓 position 明确写入 `token_side`，并同步写入稳定的 `entry_side` 兼容字段。
    - Test 2: 旧 position 缺少 side 字段时，不要求 migration；运行时允许后续逻辑通过 `None` / 回退路径处理。
  </behavior>
  <action>只在 `weatherbot/paper_execution.py` 最小修改 `build_position_from_order()`：把订单侧的 `token_side` 持久化到 position，并增加等价的 `entry_side` 字段，作为后续策略止损判断的事实源。不要重写 position 结构，不要新增独立 migration 文件，不要把 side 元数据散落到 state 顶层；兼容旧 market JSON 的方式应是“新仓写字段、旧仓运行时回退”，不是一次性改写所有历史文件。</action>
  <verify>
    <automated>uv run pytest -q tests/test_strategy_paper_execution.py tests/test_phase4_restore.py</automated>
  </verify>
  <done>所有新建 position 都带有可读的 side 元数据，而旧 market JSON 仍可被现有 loader/restore 正常读取。</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: 将 scan/monitor 止损逻辑改成 side-aware，仅实现目标规则</name>
  <files>weatherbot/strategy.py</files>
  <behavior>
    - Test 1: YES open position 跳过 stop-loss / trailing stop 分支，但保留既有 take-profit、forecast shift、resolution 流程不变。
    - Test 2: `token_side=no` 且 `entry_price>=0.80` 的仓位，用 NO 侧当前可卖出价格（优先 NO bid）判定 `<=0.70` 时 stop。
    - Test 3: `token_side=no` 但 `entry_price<0.80` 不触发这条新 stop。
    - Test 4: 对缺 side 字段的 legacy position，继续沿用旧 `stop_price` / `entry*0.80` 通用回退，保证 backward compatibility。
  </behavior>
  <action>在 `weatherbot/strategy.py` 把 `scan_and_update()` 与 `monitor_positions()` 的止损读取抽到同一套最小 helper 或内联分支：先解析 position side（优先 `token_side`，再 `entry_side`，缺失则走 legacy 回退）；YES 直接跳过 stop-loss/trailing-stop；NO 仅当 `entry_price>=0.80` 时，使用 NO 侧 quote 的 bid 作为 exit price 判定 `<=0.70` 触发 `stop_loss`。不要改 take-profit 阈值，不要改 forecast-shift close，不要改 order sync，不要引入新配置项，不要让旧 position 因缺字段被静默当成 YES 从而失去历史兼容性。</action>
  <verify>
    <automated>uv run pytest -q tests/test_phase2_quotes.py tests/test_strategy_paper_execution.py tests/test_phase4_restore.py</automated>
  </verify>
  <done>止损语义收敛为：YES 无止损；NO 仅高价仓在 0.70 触发；旧无 side 持仓仍按 legacy 路径可运行。</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| persisted market JSON → runtime stop logic | 旧仓位缺 side 元数据，运行时如果误判为 YES 或 NO 会导致错误平仓或失去保护 |
| quote_snapshot / live token quote → stop evaluator | 止损价必须读取正确 side 的市场价，否则会把 YES 价格误用到 NO，或反之 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-mbm-01 | T | `weatherbot/strategy.py` stop evaluator | mitigate | 以 `position.token_side/entry_side` 决定读取 YES/NO 对应 quote，并用测试锁定 YES skip / NO 0.70 stop |
| T-quick-mbm-02 | D | legacy market restore path | mitigate | 缺 side 字段时走 legacy stop 回退，不允许 KeyError 或把旧仓位静默降级成 “永不止损” |
| T-quick-mbm-03 | I | `weatherbot/paper_execution.py` position payload | mitigate | 在 `build_position_from_order()` 写入稳定 side 元数据，避免后续监控依赖临时推断 |
</threat_model>

<verification>
- `uv run pytest -q tests/test_phase2_quotes.py tests/test_strategy_paper_execution.py tests/test_phase4_restore.py`
</verification>

<success_criteria>
- 新开仓 position 带有 `token_side` 与 `entry_side`，供止损逻辑直接消费。
- YES 持仓不再触发旧 stop-loss；NO 仅 `entry_price>=0.80` 的仓位会在 `no<=0.70` 时触发止损。
- 旧 market JSON 缺少 side 字段时仍能被监控/恢复逻辑处理，不出现崩溃或错误静默降级。
</success_criteria>

<output>
After completion, create `.planning/quick/260418-mbm-no-price-0-80-no-0-70-yes/260418-mbm-SUMMARY.md`
</output>
