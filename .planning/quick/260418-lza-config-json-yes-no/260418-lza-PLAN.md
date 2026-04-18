---
phase: quick-260418-lza-config-json-yes-no
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config.json
  - .planning/quick/260418-lza-config-json-yes-no/260418-lza-SUMMARY.md
autonomous: true
requirements:
  - QUICK-260418-LZA
must_haves:
  truths:
    - "仓库默认 `config.json` 收紧到高不对称回报参数面：YES 只保留超低价窄温区猎杀，NO 保持高确定性筛选。"
    - "`vc_key` env-first 语义、`no_strategy.max_ask=0.95`、`no_kelly_fraction=1.5` 与其他已验证配置边界保持不变。"
    - "更新后的配置仍可被运行时解析，且 `status` / `report` CLI smoke check 不因本次参数收紧而崩溃。"
  artifacts:
    - path: "config.json"
      provides: "提交态 YES/NO 正式策略参数"
      contains: '"yes_strategy"'
    - path: ".planning/quick/260418-lza-config-json-yes-no/260418-lza-SUMMARY.md"
      provides: "参数调整结果与 CLI smoke check 记录"
      contains: "yes_strategy"
  key_links:
    - from: "config.json"
      to: "weatherbot/config.py"
      via: "load_config() 解析 yes_strategy/no_strategy 配置"
      pattern: "yes_strategy|no_strategy|vc_key"
    - from: "config.json"
      to: "weatherbot/strategy.py"
      via: "扫描候选读取 YES/NO 阈值进行筛选"
      pattern: "min_probability|min_edge|max_size|min_price|max_ask"
    - from: "config.json"
      to: "bot_v2.py status/report"
      via: "CLI 启动时加载默认配置并输出状态/报告"
      pattern: "status|report|load_config"
---

<objective>
只修改 `config.json` 中的 YES/NO 策略参数，把仓库默认配置收紧到“低价 YES 窄温区猎杀 + 高价 NO 稳赚小利”的当前目标参数面，同时保持现有代码结构、env-first VC 配置和执行逻辑完全不变。

Purpose: 用最小改动把已验证的配置面继续朝高不对称回报策略收口，避免再做代码结构或执行语义变更。
Output: 更新后的 `config.json`、配置/CLI smoke check 结果、quick summary。
</objective>

<execution_context>
@$HOME/.config/opencode/get-shit-done/workflows/execute-plan.md
@$HOME/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@AGENTS.md
@config.json
@README.md
@.planning/quick/260418-j1b-no-strategy-min-probability-0-95-0-90-no/260418-j1b-SUMMARY.md
@.planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md
@.planning/quick/260418-l91-visual-crossing-key-env-example-no-strat/260418-l91-SUMMARY.md

<interfaces>
Current committed config baseline:

```json
"yes_strategy": {
  "max_price": 0.02,
  "min_probability": 0.08,
  "min_edge": 0.03,
  "max_size": 20.0
},
"no_strategy": {
  "min_price": 0.80,
  "max_ask": 0.95,
  "min_probability": 0.90,
  "min_edge": 0.03,
  "max_size": 30.0
},
"no_kelly_fraction": 1.5,
"vc_key": ""
```

User-locked target for this quick task (config only, no code shape changes):

```json
"yes_strategy": {
  "max_price": 0.02,
  "min_probability": 0.005,
  "min_edge": 0.05,
  "max_size": 200.0
},
"no_strategy": {
  "min_price": 0.80,
  "max_ask": 0.95,
  "min_probability": 0.92
}
```

Protected invariants from prior quick tasks:

```text
- `vc_key` stays env-first with committed-safe empty fallback (`260418-l91`)
- `no_strategy.max_ask = 0.95` stays committed (`260418-kgq` + `260418-l91`)
- `no_kelly_fraction = 1.5` stays committed (`260418-gk9` + `260418-l91`)
- This task must NOT change strategy code structure or execution logic
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: 仅调整 config.json 的 YES/NO 正式参数面</name>
  <files>config.json</files>
  <action>只修改 `config.json` 中直接被用户点名的策略参数，不改任何 Python 代码、测试逻辑、模块结构或 README 文案。将 `yes_strategy` 收紧到窄温区高赔率猎杀：保持 `max_price=0.02` 不变，并把 `min_probability` 改为 `0.005`、`min_edge` 改为 `0.05`、`max_size` 改为 `200.0`；将 `no_strategy` 保持高确定性 regime：保持 `min_price=0.80`、`max_ask=0.95`、`min_edge=0.03`、`max_size=30.0`、`min_size=1.0` 不变，仅把 `min_probability` 改为 `0.92`。同时保留 `no_kelly_fraction=1.5`、顶层安全 `vc_key` 占位和其余已验证字段原样，避免顺手整理其他配置项。</action>
  <verify>
    <automated>uv run python -c "import json; from pathlib import Path; cfg=json.loads(Path('config.json').read_text(encoding='utf-8')); yes=cfg['yes_strategy']; no=cfg['no_strategy']; assert yes['max_price']==0.02 and yes['min_probability']==0.005 and yes['min_edge']==0.05 and yes['max_size']==200.0; assert no['min_price']==0.80 and no['max_ask']==0.95 and no['min_probability']==0.92 and no['min_edge']==0.03 and no['max_size']==30.0 and no['min_size']==1.0; assert cfg['no_kelly_fraction']==1.5; assert cfg.get('vc_key','')==''"</automated>
  </verify>
  <done>`config.json` 只发生目标参数收紧，YES/NO 新阈值与既有保护字段同时满足，且没有夹带代码结构或 secret 相关改动。</done>
</task>

<task type="auto">
  <name>Task 2: 做配置解析与 CLI smoke check，并记录 quick summary</name>
  <files>.planning/quick/260418-lza-config-json-yes-no/260418-lza-SUMMARY.md</files>
  <action>运行最小验证闭环并把结果写入 summary：先验证 `weatherbot.config.load_config()` / 兼容入口都能正常读到新的 YES/NO 参数，再执行 `uv run python bot_v2.py status` 与 `uv run python bot_v2.py report` 作为 CLI smoke check，确认本次仅参数收紧不会把状态/报告命令跑崩。summary 必须明确写清：这次 quick 只改 `config.json` 参数面；沿用 env-first `vc_key`，保留 `no_strategy.max_ask=0.95` 与 `no_kelly_fraction=1.5`；没有改策略代码结构、执行逻辑、README 或其他文档。</action>
  <verify>
    <automated>uv run python -c "from weatherbot.config import load_config; cfg=load_config(); assert cfg['yes_strategy']['min_probability']==0.005 and cfg['yes_strategy']['min_edge']==0.05 and cfg['yes_strategy']['max_size']==200.0; assert cfg['no_strategy']['min_probability']==0.92 and cfg['no_strategy']['max_ask']==0.95 and cfg['no_kelly_fraction']==1.5" && uv run python bot_v2.py status && uv run python bot_v2.py report && uv run python -c "from pathlib import Path; text=Path('.planning/quick/260418-lza-config-json-yes-no/260418-lza-SUMMARY.md').read_text(encoding='utf-8'); assert 'config.json' in text and '0.005' in text and '0.92' in text and 'max_ask=0.95' in text and 'no_kelly_fraction=1.5' in text and '未改策略代码结构' in text"</automated>
  </verify>
  <done>配置解析、`status`、`report` 均通过 smoke check，且 summary 已记录本次只做参数面收紧与保持不变的边界。</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| committed `config.json` → runtime loader | 仓库默认策略参数直接进入扫描与候选筛选逻辑 |
| runtime config → `status` / `report` CLI | CLI 启动会消费默认配置并渲染当前状态/报告 |
| prior validated config invariants → new commit | 新参数收紧不能破坏已验证的 env-first secret 与 NO quote-quality 边界 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-lza-01 | T | `config.json` | mitigate | 只改用户指定字段，验证 YES/NO 精确值，避免误改其他风险参数或 execution 配置。 |
| T-quick-lza-02 | D | `bot_v2.py status/report` | mitigate | 执行 `status` 和 `report` smoke check，确认更激进的参数不会导致配置解析或 CLI 输出崩溃。 |
| T-quick-lza-03 | I | `vc_key` / committed config surface | mitigate | 保持 env-first `vc_key` 安全面不变，并在验证中断言 `config.json` 仍为空占位而非真实 secret。 |
| T-quick-lza-04 | R | quick summary | mitigate | summary 明确记录“仅改参数、不改代码结构/执行逻辑”的边界，便于后续审计和回滚判断。 |
</threat_model>

<verification>
- `uv run python -c "...assert config.json target values..."`
- `uv run python -c "from weatherbot.config import load_config; ..."`
- `uv run python bot_v2.py status`
- `uv run python bot_v2.py report`
- summary 文本检查，确认记录了本次参数面与不变边界
</verification>

<success_criteria>
- `config.json` 的 YES/NO 参数面与用户目标完全一致：YES 更窄更狠，NO 更高确定性
- `no_strategy.max_ask=0.95`、`no_kelly_fraction=1.5`、env-first `vc_key` 保持不变
- 本次 quick 没有改任何策略代码结构或执行逻辑
- 配置解析与 `status` / `report` smoke check 全部通过，summary 留下可审计记录
</success_criteria>

<output>
After completion, create `.planning/quick/260418-lza-config-json-yes-no/260418-lza-SUMMARY.md`
</output>
