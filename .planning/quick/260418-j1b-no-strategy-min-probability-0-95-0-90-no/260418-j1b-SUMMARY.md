---
phase: quick-260418-j1b-no-strategy-min-probability-0-95-0-90-no
plan: 01
subsystem: strategy
tags: [weatherbot, no-carry, config, local-only, probability]
requires: []
provides:
  - baseline vs post-scan NO comparison
  - local-only no_strategy.min_probability experiment result
affects: [config.json, candidate_assessments, NO_CARRY]
tech-stack:
  added: []
  patterns: [local-only config experiment, persisted candidate_assessments comparison]
key-files:
  created:
    - .planning/quick/260418-j1b-no-strategy-min-probability-0-95-0-90-no/260418-j1b-SUMMARY.md
  modified:
    - config.json
key-decisions:
  - "只做 local-only 配置实验，不改代码逻辑，不暂存 secret。"
  - "对比口径固定为 persisted data/markets/*.json 中 strategy_leg=NO_CARRY 的 candidate_assessments。"
requirements-completed: [QUICK-260418-J1B]
duration: 7min
completed: 2026-04-18
---

# Quick Task 260418-j1b Summary

**把本地 `no_strategy.min_probability` 从 0.95 下调到 0.90，并用一次单次扫描验证 NO_CARRY 的 `probability_below_min` 是否明显松动。**

## Performance

- **Started:** 2026-04-18T05:50:00Z
- **Completed:** 2026-04-18T05:57:26Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- 固化了 0.95 baseline：基于现有 persisted `candidate_assessments` 统计 NO_CARRY 的 status / reasons 分布。
- 把本地 `config.json` 中 `no_strategy.min_probability` 改到 `0.90`，其余策略参数与 secret 保持原样，仅作 local-only experiment。
- 执行一次 `uv run python -c "import bot_v2; bot_v2.scan_and_update()"`，并完成 baseline vs post-scan NO comparison。

## Baseline (0.95)

Baseline 口径：改配置前，读取 `data/markets/*.json` 中 persisted `candidate_assessments`，仅统计 `strategy_leg == "NO_CARRY"` 的记录。上个 quick 已证明 `probability_below_min` 的主因是 `fair_no` 分布低于阈值，而不是旧 `no.bid` bug；`weatherbot/strategy.py:293-322` 当前判断也明确把 `price_below_min` 与 `probability_below_min` 分开。

- `config.json` baseline 阈值：`no_strategy.min_probability = 0.95`
- NO 记录总数：198
- status：`accepted=0`，`size_down=0`，`reprice=0`，`rejected=198`
- key reasons：`probability_below_min=72`，`price_below_min=0`，`orderbook_empty=19`，`missing_quote_price=19`
- `fair_no`：min `0.0007`，max `1.0000`，整体均值约 `0.9091`

代表 baseline bucket：

- `seattle_2026-04-19` `62.0-999.0`：`fair_no=0.0007`，`reasons=["probability_below_min"]`
- `nyc_2026-04-20` `50.0-51.0`：`fair_no=0.7167`，`reasons=["probability_below_min"]`
- `dallas_2026-04-18` `78.0-79.0`：`fair_no=0.8095`，`reasons=["probability_below_min"]`
- `miami_2026-04-19` `88.0-89.0`：`fair_no=0.8916`，`reasons=["probability_below_min"]`
- `nyc_2026-04-18` `62.0-63.0`：`fair_no=0.9453`，仍因低于 `0.95` 被拒绝

## Local-only Config Change

- `config.json:21-24` 中 `no_strategy.min_probability` 已从 `0.95` 改为 `0.90`
- 未改其他策略参数
- secret 只保留在本地，summary 不回显明文
- 未触碰 `.planning/config.json` 与 `.planning/phases/04-执行paper订单生命周期与状态恢复/04-VERIFICATION.md`
- 未暂存 `config.json`

## Post-scan (0.90)

执行了一次且仅一次扫描：`uv run python -c "import bot_v2; bot_v2.scan_and_update()"`。随后运行 `uv run python bot_v2.py status` 复查。扫描对 `data/` 的变化仅是运行时副作用，不属于手工编辑。

- `config.json` 当前阈值：`no_strategy.min_probability = 0.90`
- NO 记录总数：198
- status：`accepted=0`，`size_down=0`，`reprice=0`，`rejected=198`
- key reasons：`probability_below_min=56`，`price_below_min=0`，`orderbook_empty=21`，`missing_quote_price=21`
- `fair_no`：min `0.0007`，max `1.0000`，整体均值约 `0.9091`

仍被 `probability_below_min` 拒绝的代表 bucket：

- `seattle_2026-04-19` `62.0-999.0`：`fair_no=0.0007`，`ask=0.999`
- `seattle_2026-04-20` `62.0-999.0`：`fair_no=0.0012`，`ask=0.99`
- `seattle_2026-04-18` `50.0-999.0`：`fair_no=0.0737`，`ask=0.999`
- `dallas_2026-04-19` `-999.0-71.0`：`fair_no=0.0938`，`ask=0.99`
- `chicago_2026-04-20` `-999.0-55.0`：`fair_no=0.2536`，`ask=0.99`

被 0.90 阈值“释放”出 `probability_below_min` 的代表 bucket：

- `chicago_2026-04-20` `58.0-59.0`：`fair_no=0.9029`，`reasons=[]`，但 `edge=-0.0871`
- `atlanta_2026-04-18` `88.0-89.0`：`fair_no=0.9073`，`reasons=[]`，但 `edge=-0.0827`
- `miami_2026-04-20` `76.0-77.0`：`fair_no=0.9081`，`reasons=[]`，但 `edge=-0.0909`
- `nyc_2026-04-18` `56.0-57.0`：`fair_no=0.9430`，`reasons=[]`，但 `edge=-0.0560`
- `dallas_2026-04-18` `80.0-81.0`：`fair_no=0.9486`，`reasons=[]`，但 `edge=-0.0504`

## Baseline vs Post-scan NO comparison

| Metric | Baseline 0.95 | Post-scan 0.90 | Delta |
|---|---:|---:|---:|
| accepted | 0 | 0 | 0 |
| size_down | 0 | 0 | 0 |
| reprice | 0 | 0 | 0 |
| rejected | 198 | 198 | 0 |
| probability_below_min | 72 | 56 | -16 |
| price_below_min | 0 | 0 | 0 |
| orderbook_empty | 19 | 21 | +2 |
| missing_quote_price | 19 | 21 | +2 |

## Conclusion

`0.95 -> 0.90` 确实让一部分 NO bucket 脱离了 `probability_below_min`：从 72 降到 56，说明阈值放宽是有效的。但 accepted / size_down / reprice 完全没有增长，说明 **0.90 仍不足以显著放行可交易 NO 候选**。

当前主导原因不是旧 `no.bid` bug，也不是 `price_below_min`；而是更现实的一点：即使 `fair_no` 已超过 0.90，盘口 `ask` 仍普遍在 `0.99~1.00`，导致 edge 继续为负，所以 status 仍停留在 `rejected`。换句话说，这次实验只释放了“概率门槛”，没有释放“价格/边际”约束。

## Deviations from Plan

None - plan executed exactly as written。

## Verification

- 通过：`uv run python -c "import json; from pathlib import Path; cfg=json.loads(Path('config.json').read_text(encoding='utf-8')); assert cfg['no_strategy']['min_probability']==0.90; assert cfg.get('vc_key') and cfg['vc_key']!='YOUR_KEY_HERE'"`
- 通过：`uv run python -c "from weatherbot.config import load_config; cfg=load_config(); assert cfg['no_strategy']['min_probability']==0.90 and cfg.get('vc_key')"`
- 通过：`uv run python -c "import bot_v2; bot_v2.scan_and_update()"`（仅执行一次）
- 通过：`uv run python bot_v2.py status`
- 通过：未暂存 `config.json`，且无关脏文件保持未触碰

## Known Stubs

None.
