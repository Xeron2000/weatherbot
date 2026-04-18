---
phase: quick-260418-tcf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config.json
  - docs/strategy-profile-playbook.md
  - README.md
autonomous: true
requirements:
  - QUICK-260418-TCF
must_haves:
  truths:
    - "运行时选择 `strategy_profile = 100` 时，YES 预算重新成为主力，NO 预算退回稀有机会腿。"
    - "100 档 NO 过滤比当前更挑剔：只接受更高概率、更高价格、但更低 ask 且 edge 更大的机会。"
    - "本次不引入 depth filter，也不改变 100 档无关字段与 env-first VC 语义。"
    - "至少有一次自动化 smoke 校验，证明 merge 后 100 档值正确，且 `status` / `report` 入口仍可运行。"
  artifacts:
    - path: "config.json"
      provides: "仅更新 `strategy_profiles[\"100\"]` 的 YES/NO 预算与 NO 过滤参数"
      min_lines: 200
    - path: "docs/strategy-profile-playbook.md"
      provides: "与当前 100 档真实参数一致的操作手册说明"
      min_lines: 120
    - path: "README.md"
      provides: "与当前默认 100 档一致的核心配置说明，不再保留 1000 默认档位表述"
      min_lines: 120
  key_links:
    - from: "config.json"
      to: "weatherbot/config.py"
      via: "`load_config()` 按 `strategy_profile` 深度 merge `strategy_profiles[\"100\"]`"
      pattern: "strategy_profile|strategy_profiles|_deep_merge_dicts|load_config"
    - from: "docs/strategy-profile-playbook.md"
      to: "config.json"
      via: "100 档预算与 NO 阈值说明必须引用已提交配置真实值"
      pattern: "yes_budget_pct|no_budget_pct|min_price|max_ask|min_probability|min_edge"
    - from: "README.md"
      to: "config.json"
      via: "README 中默认档位与 100 档关键说明必须镜像当前提交态 profile 100"
      pattern: "strategy_profile|100|yes_budget_pct|no_budget_pct|min_price|max_ask|min_probability|min_edge"
---

<objective>
把当前活跃的 `strategy_profiles["100"]` 调整成“YES 主力、NO 稀有机会腿”，并把 NO 过滤收紧到用户指定阈值；不做 depth filter。

Purpose: 用户已经明确接受“NO 不是主力腿”，这次只做最小配置收口，让 100 档的预算分配与 NO 候选标准直接反映这个交易意图。
Output: 更新后的 `config.json` 100 档 preset，以及与之同步的 `docs/strategy-profile-playbook.md`
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
@docs/strategy-profile-playbook.md
@weatherbot/config.py

<interfaces>
From `weatherbot/config.py`:
```python
def load_config(config_path=None):
    with open(config_path, encoding="utf-8") as handle:
        loaded = json.load(handle)

    profile_name = loaded.get("strategy_profile")
    if profile_name is not None:
        profiles = loaded.get("strategy_profiles")
        loaded = _deep_merge_dicts(loaded, profiles[profile_name])

    env_vc_key = os.environ.get("VISUAL_CROSSING_KEY")
    if env_vc_key is not None:
        loaded["vc_key"] = env_vc_key
    return loaded
```

当前已知事实：
- 当前默认 runtime 走 `strategy_profiles["100"]`。
- 本次只改活跃 100 档，不重设计 1000 / 10000，也不新增 depth filter。
- 用户给出的最小目标值是：YES/NO 预算 `0.65/0.35`、YES/NO leg cap `0.65/0.35`，NO 过滤改成 `min_price 0.80`、`max_ask 0.90`、`min_probability 0.95`、`min_edge 0.05`。
- 若文档里继续写旧的 100 档参数，会误导操作者判断候选覆盖面与预期行为。
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: 只调整 100 档 preset 的 YES/NO 预算与 NO 过滤</name>
  <files>config.json</files>
  <action>仅修改 `config.json` 中 `strategy_profiles["100"]` 的目标字段：`risk_router.yes_budget_pct = 0.65`、`risk_router.no_budget_pct = 0.35`、`risk_router.yes_leg_cap_pct = 0.65`、`risk_router.no_leg_cap_pct = 0.35`，以及 `no_strategy.min_price = 0.80`、`no_strategy.max_ask = 0.90`、`no_strategy.min_probability = 0.95`、`no_strategy.min_edge = 0.05`。其余 100 档字段保持原样；不要顺手改顶层 `risk_router` / `no_strategy`，不要碰 `1000` / `10000`，不要新增任何 depth filter、extra guardrail 或代码逻辑改动。保留现有 env-first `vc_key` 语义与 loader 行为不变。</action>
  <verify>
    <automated>python - &lt;&lt;'PY'
import json
from pathlib import Path
cfg = json.loads(Path('config.json').read_text(encoding='utf-8'))
profile = cfg['strategy_profiles']['100']
top_risk = cfg['risk_router']
top_no = cfg['no_strategy']
profile_1000 = cfg['strategy_profiles']['1000']
profile_10000 = cfg['strategy_profiles']['10000']
assert profile['risk_router']['yes_budget_pct'] == 0.65
assert profile['risk_router']['no_budget_pct'] == 0.35
assert profile['risk_router']['yes_leg_cap_pct'] == 0.65
assert profile['risk_router']['no_leg_cap_pct'] == 0.35
assert profile['no_strategy']['min_price'] == 0.80
assert profile['no_strategy']['max_ask'] == 0.90
assert profile['no_strategy']['min_probability'] == 0.95
assert profile['no_strategy']['min_edge'] == 0.05
assert top_risk['yes_budget_pct'] == 0.3 and top_risk['no_budget_pct'] == 0.7
assert top_no['min_price'] == 0.78 and top_no['max_ask'] == 0.95
assert profile_1000['risk_router']['yes_budget_pct'] == 0.3 and profile_1000['no_strategy']['max_ask'] == 0.95
assert profile_10000['risk_router']['yes_budget_pct'] == 0.2 and profile_10000['no_strategy']['max_ask'] == 0.93
print('ok')
PY</automated>
  </verify>
  <done>`strategy_profiles["100"]` 已切到 YES 主力 / NO 稀有机会腿配置，且无关字段与其他档位未被误改。</done>
</task>

<task type="auto">
  <name>Task 2: 同步更新 100 档操作手册中的预算与 NO 阈值说明</name>
  <files>docs/strategy-profile-playbook.md, README.md</files>
  <action>对 `docs/strategy-profile-playbook.md` 做**全文范围内所有 100 档引用**的最小必要更新，使其与新的 100 档真实配置一致：把 100 档描述统一改成“YES 成主力、NO 为更稀有且更挑剔的机会腿”，并同步表格、默认推荐/适用场景、快速核对值、观察说明、切档后检查项中所有旧的 100 档数值与语义。文档必须明确 100 档现在看重 `yes_budget_pct 0.65 / no_budget_pct 0.35`，以及 NO 过滤 `0.80 / 0.90 / 0.95 / 0.05`；同时点明这次没有引入 depth filter。并最小更新 `README.md` 中默认档位/100 档说明，使仓库核心配置文档不再保留与当前 100 档行为冲突的旧预算与 NO 阈值描述；不要扩写成新理论，只修正直接镜像当前 operator 认知的段落。</action>
  <verify>
    <automated>python - &lt;&lt;'PY'
import json
from pathlib import Path
import re
cfg = json.loads(Path('config.json').read_text(encoding='utf-8'))
p = cfg['strategy_profiles']['100']
playbook = Path('docs/strategy-profile-playbook.md').read_text(encoding='utf-8')
readme = Path('README.md').read_text(encoding='utf-8')
required = [
    str(p['risk_router']['yes_budget_pct']),
    str(p['risk_router']['no_budget_pct']),
    str(p['no_strategy']['min_price']),
    str(p['no_strategy']['max_ask']),
    str(p['no_strategy']['min_probability']),
    str(p['no_strategy']['min_edge']),
]
for item in required:
    assert item in playbook, f'missing in playbook: {item}'
assert 'depth filter' in playbook
lines = playbook.splitlines()
table_line = next(line for line in lines if line.startswith('| `100` |'))
assert '0.65' in table_line and '0.35' in table_line
assert '0.80 / 0.90 / 0.95 / 0.05' in table_line
section_100 = re.search(r'### 100：.*?(?=### 1000：|## 从 100 升到 1000)', playbook, re.S)
assert section_100, '100 section missing'
section_text = section_100.group(0)
for new_val in ['0.65', '0.35', '0.80', '0.90', '0.95', '0.05']:
    assert new_val in section_text or new_val in table_line, f'missing 100-profile value {new_val}'
for old_val in ['0.4', '0.6', '0.72', '0.97', '0.82', '0.025']:
    assert old_val not in section_text, f'stale 100-profile value still present: {old_val}'
quick_span = re.search(r'100 档的快速核对值.*?(?=## 注意事项|\Z)', playbook, re.S)
assert quick_span, '100 quick-check block missing'
quick_text = quick_span.group(0)
for new_val in ['0.65', '0.35', '0.80', '0.90', '0.95', '0.05']:
    assert new_val in quick_text, f'missing quick-check value {new_val}'
for old_val in ['0.4', '0.6', '0.72', '0.97', '0.82', '0.025']:
    assert old_val not in quick_text, f'stale quick-check value still present: {old_val}'
assert 'strategy_profile' in readme and '100' in readme
assert '`1000`：中间档，作为默认档位' not in readme
assert '默认档位' in readme and '`100`' in readme
for item in required:
    assert item in readme, f'missing in README: {item}'
assert 'depth filter' in readme
print('ok')
PY</automated>
  </verify>
  <done>手册和 README 已反映 100 档新的预算与 NO 过滤现实，不再继续把旧的 0.4/0.6 与宽松 NO 阈值当作当前 100 档说明。</done>
</task>

<task type="auto">
  <name>Task 3: 做 merge smoke 校验并确认 status/report 入口仍可运行</name>
  <files>config.json, docs/strategy-profile-playbook.md</files>
  <action>使用 `weatherbot.config.load_config('config.json')` 对当前默认 `strategy_profile = 100` 做一次 merge 后 smoke 校验，断言 runtime 实际消费到的关键值已变成新的 100 档预算与 NO 阈值，而不是顶层散装默认值；随后运行 `uv run python bot_v2.py status` 与 `uv run python bot_v2.py report` 做入口级 spot check，确认本次仍是纯配置/文档改动，没有破坏现有 CLI 行为。不要新增测试文件，也不要改代码来“适配”这次配置变化。</action>
  <verify>
    <automated>python - &lt;&lt;'PY'
from weatherbot.config import load_config
cfg = load_config('config.json')
assert cfg['strategy_profile'] == '100'
assert cfg['risk_router']['yes_budget_pct'] == 0.65
assert cfg['risk_router']['no_budget_pct'] == 0.35
assert cfg['risk_router']['yes_leg_cap_pct'] == 0.65
assert cfg['risk_router']['no_leg_cap_pct'] == 0.35
assert cfg['no_strategy']['min_price'] == 0.80
assert cfg['no_strategy']['max_ask'] == 0.90
assert cfg['no_strategy']['min_probability'] == 0.95
assert cfg['no_strategy']['min_edge'] == 0.05
print('merge-ok')
PY
uv run python bot_v2.py status
uv run python bot_v2.py report</automated>
  </verify>
  <done>已证明 merge 后 runtime 看到的是新的 100 档值，且 `status` / `report` 命令仍能正常跑通。</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `config.json` → runtime merge | 100 档 preset 的预算与过滤值会直接改变扫描、分配与挂单决策 |
| `docs/strategy-profile-playbook.md` → operator interpretation | 操作者会依据文档判断 100 档为什么 YES 变多、NO 变少，以及是否属于预期行为 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260418-tcf-01 | T | `config.json` | mitigate | 只改 `strategy_profiles["100"]` 指定字段，并用 JSON 断言锁定目标值，避免误改顶层或其他档位。 |
| T-quick-260418-tcf-02 | T | `weatherbot/config.py` merge result | mitigate | 用 `load_config('config.json')` 断言 merge 后 runtime 结果，而不是只看静态文件片段。 |
| T-quick-260418-tcf-03 | R | `docs/strategy-profile-playbook.md` | mitigate | 文档仅引用当前已提交配置真实值，并显式写明本次“不做 depth filter”，避免操作者事后误记。 |
| T-quick-260418-tcf-04 | D | `bot_v2.py status/report` | mitigate | 执行 `status` / `report` 入口 spot check，确保这次配置收口没有破坏现有 CLI 可用性。 |
| T-quick-260418-tcf-05 | I | VC key handling | accept | 本次不触碰 `VISUAL_CROSSING_KEY` / `vc_key` 读取路径，不新增任何 secret 暴露面。 |
</threat_model>

<verification>
- `strategy_profiles["100"]` 的 YES/NO 预算与 NO 过滤值已更新为用户指定目标。
- `docs/strategy-profile-playbook.md` 已与 100 档真实参数一致，并明确这次不做 depth filter。
- `load_config('config.json')` merge 结果命中新值。
- `uv run python bot_v2.py status` 与 `uv run python bot_v2.py report` 仍可运行。
</verification>

<success_criteria>
- 默认活跃的 100 档现在把 YES 作为主力腿、NO 作为更稀有且更挑剔的机会腿。
- 代码行为保持配置驱动，没有新增 depth filter 或其他逻辑改动。
- 操作者从手册与 smoke 结果都能看到同一组新参数，不会再按旧 100 档理解系统行为。
</success_criteria>

<output>
After completion, create `.planning/quick/260418-tcf-yes-no-no-depth-filter/260418-tcf-SUMMARY.md`
</output>
