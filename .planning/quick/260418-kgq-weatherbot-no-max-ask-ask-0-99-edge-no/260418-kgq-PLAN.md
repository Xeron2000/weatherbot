---
phase: quick-260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - weatherbot/strategy.py
  - weatherbot/__init__.py
  - tests/test_phase2_strategies.py
  - tests/test_strategy_paper_execution.py
  - config.json
  - .planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md
autonomous: true
requirements:
  - QUICK-260418-KGQ
must_haves:
  truths:
    - "NO_CARRY 候选在 no.ask 高于配置上限时会被显式标记为 ask_above_max，且不会继续作为可执行候选。"
    - "配置 no_strategy.max_ask 后，bot_v2 wrapper 与 strategy evaluator 会对同一超限 NO ask 一致返回 ask_above_max / non-executable。"
    - "本地单次扫描可验证 ask≈0.99 的 NO 报价被 quote-quality guard 拦截，且 config.json secret 不提交不暂存。"
  artifacts:
    - path: "weatherbot/strategy.py"
      provides: "NO max_ask 过滤与 ask_above_max reason"
      contains: "evaluate_no_candidate"
    - path: "weatherbot/__init__.py"
      provides: "NO_STRATEGY 默认配置镜像包含 max_ask"
      contains: "NO_STRATEGY"
    - path: "tests/test_phase2_strategies.py"
      provides: "NO ask 超限策略回归测试"
      contains: "ask_above_max"
    - path: "tests/test_strategy_paper_execution.py"
      provides: "模块化 strategy/paper 路径的 NO quote-quality 回归测试"
      contains: "ask_above_max"
    - path: ".planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md"
      provides: "单次扫描后的 ask_above_max 命中证据与 local-only 结果摘要"
      contains: "ask_above_max"
  key_links:
    - from: "config.json"
      to: "weatherbot/strategy.py"
      via: "NO_STRATEGY['max_ask']"
      pattern: "max_ask"
    - from: "weatherbot/strategy.py"
      to: "tests/test_phase2_strategies.py"
      via: "evaluate_no_candidate"
      pattern: "ask_above_max"
    - from: "weatherbot/strategy.py"
      to: "tests/test_strategy_paper_execution.py"
      via: "build_candidate_assessments"
      pattern: "ask_above_max"
    - from: "data/markets/*.json"
      to: ".planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md"
      via: "persisted candidate_assessments -> ask_above_max hit summary"
      pattern: "NO_CARRY|ask_above_max"
---

<objective>
为 NO 策略补一个只针对报价质量的 `max_ask` 守卫，显式拦截 `ask≈0.99` 且 edge 为负的 NO_CARRY 候选，并用一次本地扫描验证该守卫生效。

Purpose: 把当前“靠 edge 自然淘汰”的隐式坏报价，升级成可解释、可配置、可回归测试的显式拒绝原因。
Output: NO `max_ask` 配置合同、`ask_above_max` evaluator 逻辑、两份回归测试、一次 local-only scan 验证记录。
</objective>

<execution_context>
@$HOME/.config/opencode/get-shit-done/workflows/execute-plan.md
@$HOME/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@AGENTS.md
@config.json
@weatherbot/strategy.py
@weatherbot/__init__.py
@tests/test_phase2_strategies.py
@tests/test_strategy_paper_execution.py
@.planning/quick/260418-j1b-no-strategy-min-probability-0-95-0-90-no/260418-j1b-SUMMARY.md

<interfaces>
From `weatherbot/strategy.py`:

```python
NO_STRATEGY = _cfg.get(
    "no_strategy",
    {
        "min_price": 0.65,
        "min_probability": 0.70,
        "min_edge": 0.04,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
        "max_size": 20.0,
        "min_size": 1.0,
    },
)

def evaluate_no_candidate(bucket_probability, quote_snapshot, hours):
    ...
    return {
        "strategy_leg": "NO_CARRY",
        "token_side": "no",
        "status": status,
        "reasons": normalize_skip_reasons(reasons),
        "edge": edge,
    }
```

From `weatherbot/__init__.py`:

```python
NO_STRATEGY = _cfg.get(
    "no_strategy",
    {
        "min_price": 0.65,
        "min_probability": 0.70,
        "min_edge": 0.04,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
        "max_size": 20.0,
        "min_size": 1.0,
    },
)
```

From `tests/test_phase2_strategies.py` current NO pattern:

```python
result = bot_v2.evaluate_no_candidate(...)
assert result["status"] == "accepted"
assert "price_below_min" in result["reasons"]
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: 为 NO evaluator 增加 max_ask quote-quality 守卫</name>
  <files>weatherbot/strategy.py, weatherbot/__init__.py</files>
  <behavior>
    - Test 1: `no.ask` 高于 `NO_STRATEGY.max_ask` 时，结果包含 `ask_above_max`，且不会保持 `accepted` / `size_down`。
    - Test 2: 仅命中 `ask_above_max` 这一类报价约束时，行为与现有价格边界一致，走可解释的 non-executable 状态而不是静默靠负 edge 兜底。
    - Test 3: 未配置 `max_ask` 时保持向后兼容，不改变现有 NO floor / probability / edge 逻辑。
  </behavior>
  <action>在 `weatherbot/strategy.py` 的 `NO_STRATEGY` 默认字典和 `weatherbot/__init__.py` 的 runtime mirror 同步加入 `max_ask` 字段；在 `evaluate_no_candidate()` 中继续只使用 `no.ask`（不要回退到 `no.bid`，延续上一轮 quick 的修复结论），新增 `ask_above_max` reason，并把它当作 NO 专用 quote-quality guard。实现时保持 scope 只在 evaluator/默认配置层：不要改 route、order intent、持久化结构或 unrelated strategy。若 `ask_above_max` 是唯一报价边界原因，按现有 YES `price_above_max` / NO `price_below_min` 模式给出可解释的 non-executable 状态；若叠加其他原因，维持 rejected。为兼容旧配置，`max_ask` 缺省时不得引入新 reason。</action>
  <verify>
    <automated>uv run pytest tests/test_phase2_strategies.py -k "no_evaluator" -x</automated>
  </verify>
  <done>`evaluate_no_candidate()` 能基于 `NO_STRATEGY.max_ask` 显式拦截 `ask≈0.99` 报价；`weatherbot` 顶层 mirror 与 strategy 模块默认合同一致；未配置 `max_ask` 的旧路径不破。</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 补齐模块化回归测试，锁定 ask≈0.99 的 NO 拦截语义</name>
  <files>tests/test_phase2_strategies.py, tests/test_strategy_paper_execution.py</files>
  <behavior>
    - Test 1: `bot_v2.evaluate_no_candidate()` 在 `no.ask=0.99` 且 `max_ask` 更低时返回 `ask_above_max`。
    - Test 2: `strategy.build_candidate_assessments()` 的 NO assessment 在同条件下不再是 executable candidate。
    - Test 3: 合法 `no.ask` 仍保持已有 accepted 路径，避免把所有 NO 高价腿一刀切打坏。
  </behavior>
  <action>在 `tests/test_phase2_strategies.py` 新增最小回归，直接覆盖 `bot_v2` wrapper 下的 `evaluate_no_candidate()`；在 `tests/test_strategy_paper_execution.py` 新增模块化 strategy 路径测试，确保 `build_candidate_assessments()` 产出的 NO assessment 也带上 `ask_above_max` 并失去可执行状态。测试命名沿用现有 `test_no_*` 风格，复用已有 `configure_strategy_runtime()` / `make_quote_snapshot()` helpers，避免新增测试基建。不要改 unrelated paper execution 断言。</action>
  <verify>
    <automated>uv run pytest tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py -k "ask_above_max or no_assessment" -x</automated>
  </verify>
  <done>两条测试路径都能稳定证明：坏 NO 报价被 `ask_above_max` 显式拦截，而正常 NO ask 仍可通过既有 accepted 路径。</done>
</task>

<task type="auto">
  <name>Task 3: 执行 local-only max_ask 配置实验并完成一次扫描验证</name>
  <files>config.json, .planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md</files>
  <action>仅在本地 `config.json` 的 `no_strategy` 中加入 `max_ask`（建议先用 `0.95`，因为本次问题集中在 `0.99~1.00`；若实现时已有更合适证据，可在 summary 中说明调整理由），并保留已有 secret 与本地 `min_probability=0.90` 状态，不回显明文 secret，不提交、不暂存 `config.json`。随后只执行一次扫描：`uv run python -c "import bot_v2; bot_v2.scan_and_update()"`。扫描后用一条只读脚本统计 persisted `candidate_assessments` 中 `strategy_leg == 'NO_CARRY'` 的 `ask_above_max` 命中数，并抽样确认 `ask≈0.99` 负 edge 候选被该新 reason 接管；把 baseline 观察、`ask_above_max` 命中数、代表样本、以及 local-only / unstaged 结论写入 `260418-kgq-SUMMARY.md`。严格不要触碰 `.planning/config.json` 与 `.planning/phases/04-被动挂单与订单恢复/04-VERIFICATION.md`。</action>
  <verify>
    <automated>uv run python -c "import json; from pathlib import Path; cfg=json.loads(Path('config.json').read_text(encoding='utf-8')); assert cfg['no_strategy']['max_ask'] < 0.99 and cfg.get('vc_key') and cfg['vc_key'] != 'YOUR_KEY_HERE'" && uv run python -c "import bot_v2; bot_v2.scan_and_update()" && uv run python -c "import json; from pathlib import Path; hits=[]
for path in Path('data/markets').glob('*.json'):
    data=json.loads(path.read_text(encoding='utf-8'))
    for item in data.get('candidate_assessments', []):
        if item.get('strategy_leg')=='NO_CARRY' and 'ask_above_max' in item.get('reasons', []):
            hits.append((path.name, item.get('range'), item.get('quote_context', {}).get('ask'), item.get('edge')))
assert hits, 'expected ask_above_max hits after scan'" && test -z "$(git diff --cached --name-only -- config.json)" && test -z "$(git diff --cached --name-only -- .planning/config.json)" && test -z "$(git diff --cached --name-only -- '.planning/phases/04-被动挂单与订单恢复/04-VERIFICATION.md')" && test -z "$(git diff --name-only -- .planning/config.json)" && test -z "$(git diff --name-only -- '.planning/phases/04-被动挂单与订单恢复/04-VERIFICATION.md')" && uv run python -c "from pathlib import Path; text=Path('.planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md').read_text(encoding='utf-8'); assert 'ask_above_max' in text and 'local-only' in text and 'NO_CARRY' in text"</automated>
  </verify>
  <done>本地单次扫描完成，`config.json` 仍为 unstaged local-only 变更，且 persisted NO assessments 中能看到 `ask_above_max` 接管 `ask≈0.99` 的坏报价过滤。</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| config.json → strategy evaluator | 本地可编辑配置进入交易候选决策 |
| Polymarket quote snapshot → NO assessment | 外部 orderbook 报价进入候选筛选 |
| local scan → persisted market JSON | 运行时扫描结果写入本地事实源 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-kgq-01 | T | `evaluate_no_candidate()` | mitigate | 仅消费 `quote_for_side(..., "no")` 的 `ask`，新增 `max_ask` 上限，避免被 `ask≈0.99` 的坏报价污染 NO executable candidate。 |
| T-quick-kgq-02 | I | `config.json` / summary output | mitigate | local-only experiment 不回显 `vc_key` 明文，不提交、不暂存 `config.json`。 |
| T-quick-kgq-03 | R | persisted `candidate_assessments` | mitigate | 扫描后通过 persisted `ask_above_max` reason 做验证，不在报告层重算候选原因。 |
| T-quick-kgq-04 | D | unrelated dirty files | mitigate | 明确禁止触碰 `.planning/config.json` 与 `.planning/phases/04-被动挂单与订单恢复/04-VERIFICATION.md`，避免 quick task 扩散。 |
</threat_model>

<verification>
- `uv run pytest tests/test_phase2_strategies.py -k "no_evaluator" -x`
- `uv run pytest tests/test_phase2_strategies.py tests/test_strategy_paper_execution.py -k "ask_above_max or no_assessment" -x`
- `uv run python -c "import bot_v2; bot_v2.scan_and_update()"` 仅执行一次
- 扫描后读取 `data/markets/*.json`，确认 `strategy_leg == 'NO_CARRY'` 的 persisted assessments 出现 `ask_above_max`
- `git status --short config.json .planning/config.json .planning/phases/04-被动挂单与订单恢复/04-VERIFICATION.md` 用于确认只保留 local-only `config.json` 变更、无关脏文件未被动到
</verification>

<success_criteria>
- `weatherbot/strategy.py` 为 NO 路径新增 `max_ask` / `ask_above_max`，且坏报价不再仅靠负 edge 隐式淘汰
- `weatherbot/__init__.py` 的 `NO_STRATEGY` 默认镜像与 strategy 合同一致
- 两份测试稳定覆盖 wrapper 路径与模块化 strategy 路径
- 本地单次扫描后，persisted NO assessments 能证明 `ask≈0.99` 坏报价被新 guard 显式拦截
- `config.json` 保持 local-only，不提交 secret，不触碰指定无关脏文件
</success_criteria>

<output>
After completion, create `.planning/quick/260418-kgq-weatherbot-no-max-ask-ask-0-99-edge-no/260418-kgq-SUMMARY.md`
</output>
