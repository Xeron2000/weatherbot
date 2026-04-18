# Strategy Profile 实盘使用手册

## 当前默认档位：100

当前提交态 `config.json` 的 `strategy_profile` 是 `100`，这次默认选择直接对齐 100 刀小资金试跑场景。

原因不是“100 档更刺激”，而是这次账户规模已经明确只有 `100`，默认值就应该先保证运行时 merge 后的阈值、风控和挂单节奏与小资金规模一致：

- 资金规模直接落到 `balance = 100.0`，不会再出现“默认还是 1000 档，但实际只想按 100 刀观察行为”的错位。
- YES 侧继续保留更宽的小资金试跑阈值：`max_price = 0.08`、`min_probability = 0.005`，让低价窄温区票继续作为主力腿进入候选池。
- NO 侧这次改成更挑剔的稀有机会腿：`min_price = 0.80`、`max_ask = 0.90`、`min_probability = 0.95`、`min_edge = 0.05`，只有更高概率、更高价格、但 ask 更低且 edge 更大的机会才会留下。
- 风控与容量 cap 同步放宽到 `global_usage_cap_pct = 0.92`、`per_market_cap_pct = 0.15`，让小账户更快触碰到“一个市场/事件能吃掉多少资金”的真实边界。
- 预算也明确改成 YES 主力、NO 稀有机会腿：`yes_budget_pct = 0.65`、`no_budget_pct = 0.35`，对应 `yes_leg_cap_pct = 0.65`、`no_leg_cap_pct = 0.35`。
- 订单等待也更短：`gtd_buffer_hours = 4.0`、`max_order_hours_open = 36.0`、`cancel_latency_ms = 2000`，更符合小资金先看节奏、快速观察挂单行为的目标。
- 本次只收口 100 档预算与 NO 阈值，**没有引入 depth filter**，也没有改动 1000 / 10000 档或 env-first VC 语义。

一句话判断：**当前默认先用 `100`，目标不是让 NO 成主力，而是让 YES 继续做主力腿、NO 只保留更稀有但更硬的高确定性机会。**

## 三档真实参数差异

下表全部来自当前提交态 `config.json` 的 `strategy_profiles`，不是通用建议，也不是额外假设。

| 档位 | balance | kelly_fraction | no_kelly_fraction | YES max_price / min_probability / min_edge / max_size | NO min_price / max_ask / min_probability / min_edge / max_size | risk_router 关键 cap | order_policy | paper_execution |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `100` | `100.0` | `0.35` | `1.8` | `0.08 / 0.005 / 0.04 / 25.0` | `0.80 / 0.90 / 0.95 / 0.05 / 20.0` | `yes_budget_pct 0.65`，`no_budget_pct 0.35`，`global_usage_cap_pct 0.92`，`per_market_cap_pct 0.15`，`per_city_cap_pct 0.3`，`per_date_cap_pct 0.3`，`per_event_cap_pct 0.3` | `yes_time_in_force GTC`，`no_time_in_force GTD`，`gtd_buffer_hours 4.0`，`replace_edge_buffer 0.015`，`max_order_hours_open 36.0` | `submission_latency_ms 2500`，`queue_ahead_shares 60.0`，`queue_ahead_ratio 0.2`，`touch_not_fill_min_touches 1`，`partial_fill_slice_ratio 0.6`，`cancel_latency_ms 2000` |
| `1000` | `1000.0` | `0.22` | `1.5` | `0.05 / 0.01 / 0.05 / 18.0` | `0.78 / 0.95 / 0.88 / 0.03 / 30.0` | `yes_budget_pct 0.3`，`no_budget_pct 0.7`，`global_usage_cap_pct 0.85`，`per_market_cap_pct 0.08`，`per_city_cap_pct 0.18`，`per_date_cap_pct 0.18`，`per_event_cap_pct 0.18` | `yes_time_in_force GTC`，`no_time_in_force GTD`，`gtd_buffer_hours 6.0`，`replace_edge_buffer 0.02`，`max_order_hours_open 72.0` | `submission_latency_ms 3500`，`queue_ahead_shares 70.0`，`queue_ahead_ratio 0.22`，`touch_not_fill_min_touches 1`，`partial_fill_slice_ratio 0.55`，`cancel_latency_ms 3000` |
| `10000` | `10000.0` | `0.12` | `1.2` | `0.02 / 0.015 / 0.06 / 12.0` | `0.84 / 0.93 / 0.94 / 0.04 / 16.0` | `yes_budget_pct 0.2`，`no_budget_pct 0.8`，`global_usage_cap_pct 0.72`，`per_market_cap_pct 0.04`，`per_city_cap_pct 0.1`，`per_date_cap_pct 0.1`，`per_event_cap_pct 0.1` | `yes_time_in_force GTC`，`no_time_in_force GTD`，`gtd_buffer_hours 8.0`，`replace_edge_buffer 0.03`，`max_order_hours_open 96.0` | `submission_latency_ms 5000`，`queue_ahead_shares 100.0`，`queue_ahead_ratio 0.3`，`touch_not_fill_min_touches 2`，`partial_fill_slice_ratio 0.4`，`cancel_latency_ms 4500` |

## 适用场景与三档怎么理解

### 100：小资金试跑档，YES 主力 / NO 稀有机会腿

- YES 更宽：`max_price 0.08`，允许更贵的低价票；`min_probability 0.005` 也更低。
- NO 更挑剔：`min_price 0.80`、`max_ask 0.90`、`min_probability 0.95`、`min_edge 0.05`，说明它只接更高确定性、价格也更合适的高价 NO。
- 预算明确偏向 YES：`yes_budget_pct 0.65`、`no_budget_pct 0.35`，对应 `yes_leg_cap_pct 0.65`、`no_leg_cap_pct 0.35`。
- 仓位仍然更猛：`kelly_fraction 0.35`、`no_kelly_fraction 1.8`，并且 `global_usage_cap_pct 0.92`、`per_market_cap_pct 0.15` 都很宽。
- 执行更快：挂单更短，`max_order_hours_open 36.0`；paper execution 延迟也更低。
- 本次没有新增 depth filter；100 档行为变化只来自预算切换和 NO 阈值收紧。

适合场景：你还在验证自己会不会持续按规则执行，账户小，主要目标是让低价 YES 持续提供样本，同时把 NO 留给更少但更硬的高确定性机会。

### 1000：中档平衡档

- YES 开始收敛到更便宜的位置：`max_price 0.05`。
- NO 开始要求更确定：`min_price 0.78`、`min_probability 0.88`。
- 单腿与总量 cap 已经明显收紧，但没有紧到严重妨碍策略跑通。
- `max_order_hours_open 72.0` 让被动挂单更像“等合适成交”，不是频繁追着改价。

适合场景：你已经不只是想“跑起来”，而是要开始观察真实候选质量、容量占用、成交等待和回撤感受的平衡。

### 10000：大资金保护档，最保守

- YES 只打极便宜票：`max_price 0.02`，`min_edge 0.06`。
- NO 只收更硬的确定性：`min_price 0.84`、`max_ask 0.93`、`min_probability 0.94`。
- 风控最紧：`global_usage_cap_pct 0.72`，单市场只给 `0.04`，单城/单日/单事件都只给 `0.1`。
- 执行最慢、最耐心：`gtd_buffer_hours 8.0`、`max_order_hours_open 96.0`、`submission_latency_ms 5000`，并且 `touch_not_fill_min_touches 2`。

适合场景：你已经确认策略有效，真正的问题不再是“有没有候选”，而是“怎么避免更大的资金把自己挤进容量和执行质量陷阱里”。

## 从 100 升到 1000

只有下面这些条件大体成立，再升比较合理：

1. **候选质量稳定**：你连续一段时间观察到，`100` 档放出来的候选里，YES 主力腿已经足够提供样本，而 NO 即使收紧到稀有机会腿，也不会让你错过真正该留的高确定性机会。
2. **你能承受更真实的回撤节奏**：`1000` 档虽然更保守，但绝对资金变大了。你需要能接受单次浮亏金额变大，而不是只适应百分比概念。
3. **单市场容量开始有意义，但还不是硬瓶颈**：如果 `100` 档常出现“其实还能多下，但账户太小/仓位太散，统计意义不够”，说明可以升到 `1000`；如果你还远没到这个程度，没必要急着升。
4. **你愿意接受更慢的成交节奏**：从 `36h` 到 `72h` 的挂单容忍度变化不小；如果你总是因为等待不耐烦手动干预，先别升。

不该升级的典型信号：

- 你还在频繁手改挂单、手改阈值。
- 你仍然需要靠 `100` 档更宽的 YES 才看得到足够多候选，但又接受不了 NO 现在 `0.80 / 0.90 / 0.95 / 0.05` 的更挑剔过滤。
- 你对单市场占用和总资金占用没有持续复盘，只是觉得“金额大一点更刺激”。

## 从 1000 升到 10000

升到 `10000` 不是“更高级”，而是“你已经需要更保守的保护层”。常见触发条件：

1. **单市场容量限制开始成为真实瓶颈**：你发现 `1000` 档下，`per_market_cap_pct 0.08` 仍然会让单市场占用过大，或者某些高确定性 NO 常把组合压得太集中，这时 `10000` 的 `0.04` / `0.1` 系列 cap 才有意义。
2. **执行耐心与成交质量要求提升**：你更在意别被短期波动或队列位置拖着走，愿意用更长挂单时间和更慢 paper execution 交换更稳的模拟成交假设。
3. **你已经确认更激进阈值不是优势来源**：如果复盘后发现真正赚钱的单子本来就主要集中在更便宜 YES、更高确定性 NO，那就应该让 `10000` 档替你主动过滤掉边缘候选。
4. **你的回撤承受能力更看重绝对金额控制**：账户变大后，最先要收紧的不是“想不想赚更多”，而是“能不能承受单事件、单城市、单日期集中曝险”。

不该升级的典型信号：

- 你切到 `10000` 后，候选直接少到几乎不成交，但这不是策略进化，只是把自己锁死。
- 你还没有遇到 `1000` 档的容量、等待、组合集中问题。
- 你只是因为账户余额变大，就想机械对应到 `10000`，但执行纪律和复盘密度没有同步升级。

## 切换方式

切换只改 `config.json` 里的 `strategy_profile`：

```json
{
  "strategy_profile": "100"
}
```

可选值只有当前提交态预设里的三个名字：`100`、`1000`、`10000`。

运行时语义要记住两点：

1. loader 会先按 `strategy_profile` 从 `strategy_profiles` 深度 merge 出最终配置。
2. `weatherbot` / `bot_v2.py` 消费的是 merge 后结果，不是你肉眼看到的顶层片段拼凑判断。

所以，**正常切换时只改 `strategy_profile`，不要手工把顶层 `yes_strategy`、`no_strategy`、`risk_router` 改成半套新档位。**

## 切到 100 后观察 bot 行为的检查清单

切到 `100` 后不要只盯着“有没有单子”，先按下面清单看行为是不是和小资金 preset 一致：

1. **先验 merge 结果，不要只看顶层默认值。** 至少确认运行时关键值是：`balance = 100.0`、YES `max_price = 0.08`、NO `min_price = 0.80` / `max_ask = 0.90` / `min_probability = 0.95` / `min_edge = 0.05`、`yes_budget_pct = 0.65` / `no_budget_pct = 0.35`、`risk_router.global_usage_cap_pct = 0.92`、`order_policy.max_order_hours_open = 36.0`。
2. **YES 候选应比 1000 档更宽。** 观察 scan 输出时，低价 YES 不该还被卡在 `max_price 0.05` / `min_probability 0.01` 的中档门槛上；如果表现仍像 1000 档，先查 profile 是否没切对。
3. **NO 候选应明显更少，但质量更高。** `min_price 0.80`、`max_ask 0.90`、`min_probability 0.95`、`min_edge 0.05` 意味着 NO 只会保留更高概率、更高价格、但 ask 更低且 edge 更大的机会；若 NO 仍很多，优先排查 merge 值而不是直接归因策略失效。
4. **单市场 / 单事件占用会更快打到小资金上限。** 因为总资金只有 `100.0`，哪怕 `per_market_cap_pct = 0.15`、`per_event_cap_pct = 0.3` 看上去更宽，绝对金额上也会更快感受到占用上限。
5. **订单等待与取消节奏应更短更快。** 观察 `max_order_hours_open = 36.0`、`gtd_buffer_hours = 4.0`、`cancel_latency_ms = 2000` 这一组值是否让挂单更快进入取消/替换节奏，而不是继续表现成 72 小时慢节奏。
6. **确认这次没有引入 depth filter。** 如果你观察到的是候选深度维度变化，不要先脑补新 guardrail；这次 100 档变化只来自 YES/NO 预算和 NO 阈值收紧。
7. **行为异常先查 profile，再谈策略。** 如果候选、风控、挂单节奏完全不像小资金档，第一步是核对 `strategy_profile = 100` 和 merge 后代表值，而不是马上下结论说策略逻辑坏了。

### 100 档的快速核对值

如果你现在按默认配置运行，至少应确认这些代表值和 `100` preset 一致：

- `strategy_profile = 100`
- YES：`max_price 0.08`、`min_probability 0.005`、`max_size 25.0`
- NO：`min_price 0.80`、`max_ask 0.90`、`min_probability 0.95`、`min_edge 0.05`、`max_size 20.0`
- `risk_router.yes_budget_pct = 0.65`、`risk_router.no_budget_pct = 0.35`
- `risk_router.yes_leg_cap_pct = 0.65`、`risk_router.no_leg_cap_pct = 0.35`
- `risk_router.global_usage_cap_pct = 0.92`
- `order_policy.max_order_hours_open = 36.0`
- `paper_execution.submission_latency_ms = 2500`

如果这些值对不上，先不要继续把结果解释成策略问题，先确认是不是档位没切对，或者你手工改了顶层字段却没同步 profile 本体。

## 注意事项

- 当前默认已经切到 `100`，因为这次目标不是讨论长期最优档位，而是让 100 刀小资金运行时直接落在 YES 主力、NO 稀有机会腿的 preset 上。
- `100` 更激进，适合小资金试跑；`10000` 更保守，适合容量、集中度和执行质量已经成为第一约束时再上。
- 这次没有引入 depth filter；如果你看到 100 档行为变化，优先从 YES/NO 预算和 NO 过滤阈值解释。
- 如果你在实操里还经常靠主观判断临时改阈值，那先别升级档位；先把执行纪律稳定下来。
- 如果你切档后感觉“机会变少/变多很多”，先回看是不是配置逻辑生效了，而不是马上下结论说策略坏了。三档本来就故意在 YES/NO 阈值、cap 和执行耐心上拉开差距。
- 文档依据的是**当前已提交配置值**。后面只要 `config.json` 里的 `strategy_profiles` 改了，这份手册也必须一起更新，不能继续沿用旧结论。
