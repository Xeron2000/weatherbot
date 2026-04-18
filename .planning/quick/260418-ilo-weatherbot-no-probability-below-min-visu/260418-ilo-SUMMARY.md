# Quick Task 260418-ilo Summary

## Objective

确认 weatherbot 中 NO 候选频繁落入 `probability_below_min` 的真实原因，并把 Visual Crossing key 只做本地配置、不进入 git。

## Current Status

- Task 1 已完成。
- Task 2 已完成：已本地配置 secret，未提交 git。

## Conclusion: `probability_below_min` 的主因不是旧取价 bug

`weatherbot/strategy.py:293-352` 里 `evaluate_no_candidate()` 当前逻辑非常直接：

- `price_below_min` 取决于 `no.ask < no_strategy.min_price`
- `probability_below_min` 取决于 `fair_no < no_strategy.min_probability`

也就是说，`probability_below_min` 和 260418-he3 已修复的 `no.ask/no.bid` 取价问题是两条不同判断链路。旧 bug 修的是 NO 价格侧判定，不会改变 `fair_no < 0.95` 这条概率阈值判断。

## Persisted Evidence

基于当前 `data/markets/*.json` 中 `candidate_assessments` 的 persisted 样本，筛出 `strategy_leg == "NO_CARRY"` 且 `reasons` 包含 `probability_below_min` 的记录后，得到：

- 样本数：72
- `fair_no` 最小值：约 `0.0007`
- `fair_no` 最大值：约 `0.9453`
- `fair_no` 均值：约 `0.7609`
- 这些样本全部仍低于当前 `config.json` 中 `no_strategy.min_probability = 0.95`

代表样本：

- `nyc_2026-04-18`，桶 `64.0-65.0`，`fair_no=0.8138`，`reasons=["probability_below_min"]`
- `miami_2026-04-20`，桶 `78.0-79.0`，`fair_no=0.8075`，`reasons=["probability_below_min"]`
- `chicago_2026-04-20`，桶 `(-999.0, 55.0)`，`fair_no=0.2988`，`reasons=["probability_below_min"]`
- `seattle_2026-04-19`，桶 `(62.0, 999.0)`，`fair_no=0.0007`，`reasons=["probability_below_min"]`
- 高位边界样本 `nyc_2026-04-18`，桶 `62.0-63.0`，`fair_no=0.9453`，依然因为低于 `0.95` 被拒绝

因此，本轮 persisted 事实支持的结论是：当前 `NO_CARRY` 常见 `probability_below_min`，主因是策略阈值 `0.95` 高于现有 `fair_no` 分布；多数样本落在约 `0.6~0.9` 区间，均值约 `0.7609`，而不是又回到了旧的 `no.bid` 取价 bug。

## Relation To 260418-he3

前一个 quick task 260418-he3 已确认：NO 侧价格门槛与 edge 现在按 `no.ask` 判断，低 `no.bid` 不再把候选错误打成 `price_below_min`。本次继续看 persisted `candidate_assessments`，被拒原因已稳定转向 `probability_below_min`，与前次修复后的观察一致。

## Recommendation

- 现阶段只下结论，不直接改 `no_strategy.min_probability`。
- 先继续观察更多扫描样本。
- 下一步应按城市 / 日期 / 温度桶做分层统计，再决定是否下调阈值。
- 如果后续要调参，应把“阈值放宽后候选数量、报价质量、成交后回撤”一起看，不要只看候选通过率。

## Secret Handling

- 已本地配置 secret，未提交 git。
- 本次只修改了 `config.json` 的 `vc_key`，未改动 `no_strategy.min_probability` 等策略参数。
- 无关脏文件 `.planning/config.json` 与 `.planning/phases/04-执行paper订单生命周期与状态恢复/04-VERIFICATION.md` 未触碰。
