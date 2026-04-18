---
phase: quick-260418-ilo-weatherbot-no-probability-below-min-visu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260418-ilo-weatherbot-no-probability-below-min-visu/260418-ilo-SUMMARY.md
  - config.json
autonomous: true
requirements:
  - QUICK-260418-ILO
must_haves:
  truths:
    - "能明确证明 NO_CARRY 常见 probability_below_min 不是旧 no.bid 取价 bug，而是 fair_no 普遍低于当前 no_strategy.min_probability=0.95。"
    - "Visual Crossing key 已本地写入 config.json，可被 weatherbot 配置加载。"
    - "secret 只做本地配置，不进入 git 提交，也不波及无关脏文件。"
  artifacts:
    - path: ".planning/quick/260418-ilo-weatherbot-no-probability-below-min-visu/260418-ilo-SUMMARY.md"
      provides: "本次 quick task 的结论、证据与后续建议"
    - path: "config.json"
      provides: "本地 Visual Crossing key 配置"
      contains: "vc_key"
  key_links:
    - from: "weatherbot/strategy.py"
      to: "config.json"
      via: "NO_STRATEGY.min_probability 与 vc_key 配置加载"
      pattern: "load_config|evaluate_no_candidate|probability_below_min"
    - from: "config.json"
      to: "weatherbot/strategy.py"
      via: "load_config() 读取本地配置"
      pattern: "vc_key|no_strategy"
---

<objective>
确认 weatherbot 中 NO 候选频繁落入 `probability_below_min` 的真实原因，并把 Visual Crossing key 只在本地配置完成。

Purpose: 区分“策略阈值过严”与“代码取价 bug”这两类原因，避免误改策略；同时补齐天气源 key，让后续扫描不再卡在占位配置。
Output: 一份 quick 结论摘要 + 本地可用的 `config.json`。
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
@.planning/quick/260418-he3-weatherbot-no-no-bid-price-below-min/260418-he3-SUMMARY.md

<interfaces>
From `weatherbot/strategy.py`:

```python
def evaluate_no_candidate(bucket_probability, quote_snapshot, hours):
    ...
    if ask is not None and ask < NO_STRATEGY.get("min_price", 0.0):
        reasons.append("price_below_min")
    if bucket_probability.get("fair_no", 0.0) < NO_STRATEGY.get("min_probability", 0.0):
        reasons.append("probability_below_min")
```

From `config.json`:

```json
"vc_key": "YOUR_KEY_HERE",
"no_strategy": {
  "min_price": 0.80,
  "min_probability": 0.95
}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: 固化 NO 候选被 probability_below_min 拒绝的真实结论</name>
  <files>.planning/quick/260418-ilo-weatherbot-no-probability-below-min-visu/260418-ilo-SUMMARY.md</files>
  <action>先基于 persisted 事实做一次显式统计，再创建 quick summary。统计来源限定为当前 `data/markets/*.json` 中的 `candidate_assessments`：筛出 `strategy_leg == "NO_CARRY"` 且 `reasons` 包含 `probability_below_min` 的样本，提取 `fair_no` 的区间、均值或近似均值、代表城市/日期/桶样本；然后在 summary 中明确写出：`evaluate_no_candidate()` 当前的 `probability_below_min` 触发条件就是 `fair_no &lt; no_strategy.min_probability`；结合 persisted 样本说明当前 `no_strategy.min_probability=0.95`，而 `fair_no` 多数在 `0.6~0.9`、均值约 `0.7609`，所以主因是策略阈值高于当前市场概率分布，而不是 260418-he3 已修复的 `no.ask/no.bid` 取价问题。结论里只能给建议，不得直接改 `no_strategy.min_probability`；建议至少包含“先继续观察更多扫描样本/分城市分日期分桶统计，再决定是否下调阈值”。</action>
  <verify>
    <automated>python -c "import json; from pathlib import Path; vals=[]; files=list(Path('data').glob('markets/*.json')); assert files; 
for p in files:
    data=json.loads(p.read_text(encoding='utf-8'))
    for item in data.get('candidate_assessments', []) or []:
        if item.get('strategy_leg')=='NO_CARRY' and 'probability_below_min' in (item.get('reasons') or []):
            vals.append(float(item.get('fair_no') or 0.0))
assert vals and min(vals) < 0.95 and sum(vals)/len(vals) < 0.95" && python -c "from pathlib import Path; p=Path('.planning/quick/260418-ilo-weatherbot-no-probability-below-min-visu/260418-ilo-SUMMARY.md'); text=p.read_text(encoding='utf-8'); assert '0.95' in text and '0.7609' in text and 'probability_below_min' in text and '不直接改' in text"</automated>
  </verify>
  <done>summary 明确区分了旧取价 bug 与当前阈值约束，并给出只读结论与后续建议，没有擅自改策略参数。</done>
</task>

<task type="auto">
  <name>Task 2: 本地写入 Visual Crossing key 并验证不进入 git</name>
  <files>config.json</files>
  <action>先记录无关脏文件的基线状态，再把 `config.json` 中的 `vc_key` 从占位值改成用户提供的 secret，仅做本地配置，不修改其他策略参数。执行后验证配置可被 `weatherbot` 正常读取。严格避免暂存或提交 `config.json`，并且不要编辑或暂存无关脏文件 `.planning/config.json` 与 `.planning/phases/04-执行paper订单生命周期与状态恢复/04-VERIFICATION.md`。如需在 summary 记录此事，只写“已本地配置 secret，未提交 git”，不要明文展开 key。</action>
  <verify>
    <automated>python -c "import json; from pathlib import Path; cfg=json.loads(Path('config.json').read_text()); assert cfg['vc_key'] != 'YOUR_KEY_HERE' and cfg['no_strategy']['min_probability']==0.95" && python -c "from weatherbot.config import load_config; cfg=load_config(); assert cfg.get('vc_key') and cfg['vc_key']!='YOUR_KEY_HERE'" && test -z "$(git diff --cached --name-only -- config.json)" && test -z "$(git diff --cached --name-only -- .planning/config.json)" && test -z "$(git diff --cached --name-only -- '.planning/phases/04-执行paper订单生命周期与状态恢复/04-VERIFICATION.md')" && test -z "$(git diff --name-only -- .planning/config.json)" && test -z "$(git diff --name-only -- '.planning/phases/04-执行paper订单生命周期与状态恢复/04-VERIFICATION.md')"</automated>
  </verify>
  <done>`config.json` 已可本地供 Visual Crossing 使用，策略参数保持原样，且执行记录明确说明 secret 不提交 git、无关脏文件未被触碰。</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local config → git history | `vc_key` 是 secret，若误提交会造成凭据泄露 |
| local config → external weather API | weatherbot 会用本地 `vc_key` 发起外部请求 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-260418-ilo-01 | I | `config.json` | mitigate | 仅本地写入 `vc_key`，验证后不 `git add`/不提交；summary 中不重复明文 secret。 |
| T-quick-260418-ilo-02 | T | `config.json` / `no_strategy` | mitigate | 只修改 `vc_key`，校验 `no_strategy.min_probability` 仍为 `0.95`，避免顺手改策略参数。 |
| T-quick-260418-ilo-03 | R | quick investigation summary | mitigate | 在 `260418-ilo-SUMMARY.md` 中记录证据链：策略代码条件、当前阈值、persisted 样本分布、前一个 quick 修复结论。 |
| T-quick-260418-ilo-04 | T | unrelated dirty files | mitigate | 明确禁止编辑/暂存 `.planning/config.json` 与 `04-VERIFICATION.md`，并用 `git status --short -- ...` 定点核验。 |
</threat_model>

<verification>
- `260418-ilo-SUMMARY.md` 包含阈值结论、样本分布、非改参建议。
- `config.json` 的 `vc_key` 已替换为本地 secret，`weatherbot.config.load_config()` 能读到。
- `git status` 只用于核验，不进行暂存/提交；无关脏文件保持原状。
</verification>

<success_criteria>
- NO 候选频繁 `probability_below_min` 的原因被归因为“当前 `fair_no` 分布低于 0.95 阈值”，而不是旧价格取值 bug。
- Visual Crossing key 完成本地配置，后续运行不再依赖 `YOUR_KEY_HERE`。
- 本次 quick task 没有改动 `no_strategy.min_probability`，也没有把 secret 提交进 git。
</success_criteria>

<output>
After completion, create `.planning/quick/260418-ilo-weatherbot-no-probability-below-min-visu/260418-ilo-SUMMARY.md`
</output>
