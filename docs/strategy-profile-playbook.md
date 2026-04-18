# Strategy Profile 实盘使用手册

## 当前推荐档位：1000

当前提交态 `config.json` 的 `strategy_profile` 是 `1000`，现阶段推荐继续用 `1000` 作为默认实盘档位。

原因不是“中间档看起来顺眼”，而是它正好落在当前策略阶段最平衡的位置：

- 资金规模是 `1000.0`，够让单笔挂单、单市场容量和候选覆盖面有实用意义，但还没有大到必须把每个 cap 都收得很死。
- `kelly_fraction = 0.22`、`no_kelly_fraction = 1.5`，比 `100` 档明显收敛，不会因为小资金心态把 YES/NO 仓位打得过猛；又比 `10000` 档更愿意出手，不会过度保守到大量候选都被自己挡掉。
- YES 侧 `max_price = 0.05`、NO 侧 `min_price = 0.78` / `max_ask = 0.95`，既保留低价 YES 窄温区猎杀，也保留高价 NO 稳赚小利，两条腿都还能正常工作。
- 风控上 `global_usage_cap_pct = 0.85`、`per_market_cap_pct = 0.08`、`per_city_cap_pct = 0.18`，已经开始限制单市场和单城市集中，但还没紧到像 `10000` 档那样经常先碰容量上限。
- 订单与 paper execution 也更接近当前项目节奏：`GTC/GTD` 组合不变，但 `gtd_buffer_hours = 6.0`、`max_order_hours_open = 72.0`、`submission_latency_ms = 3500`、`cancel_latency_ms = 3000` 都比 `100` 档更有耐心，又没有 `10000` 档那么慢和苛刻。

一句话判断：**`1000` 是当前“还能持续成交、又不会把风险和执行压力放大到失控”的默认档位。**

## 三档真实参数差异

下表全部来自当前提交态 `config.json` 的 `strategy_profiles`，不是通用建议，也不是额外假设。

| 档位 | balance | kelly_fraction | no_kelly_fraction | YES max_price / min_probability / min_edge / max_size | NO min_price / max_ask / min_probability / min_edge / max_size | risk_router 关键 cap | order_policy | paper_execution |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `100` | `100.0` | `0.35` | `1.8` | `0.08 / 0.005 / 0.04 / 25.0` | `0.72 / 0.97 / 0.82 / 0.025 / 20.0` | `yes_budget_pct 0.4`，`no_budget_pct 0.6`，`global_usage_cap_pct 0.92`，`per_market_cap_pct 0.15`，`per_city_cap_pct 0.3`，`per_date_cap_pct 0.3`，`per_event_cap_pct 0.3` | `yes_time_in_force GTC`，`no_time_in_force GTD`，`gtd_buffer_hours 4.0`，`replace_edge_buffer 0.015`，`max_order_hours_open 36.0` | `submission_latency_ms 2500`，`queue_ahead_shares 60.0`，`queue_ahead_ratio 0.2`，`touch_not_fill_min_touches 1`，`partial_fill_slice_ratio 0.6`，`cancel_latency_ms 2000` |
| `1000` | `1000.0` | `0.22` | `1.5` | `0.05 / 0.01 / 0.05 / 18.0` | `0.78 / 0.95 / 0.88 / 0.03 / 30.0` | `yes_budget_pct 0.3`，`no_budget_pct 0.7`，`global_usage_cap_pct 0.85`，`per_market_cap_pct 0.08`，`per_city_cap_pct 0.18`，`per_date_cap_pct 0.18`，`per_event_cap_pct 0.18` | `yes_time_in_force GTC`，`no_time_in_force GTD`，`gtd_buffer_hours 6.0`，`replace_edge_buffer 0.02`，`max_order_hours_open 72.0` | `submission_latency_ms 3500`，`queue_ahead_shares 70.0`，`queue_ahead_ratio 0.22`，`touch_not_fill_min_touches 1`，`partial_fill_slice_ratio 0.55`，`cancel_latency_ms 3000` |
| `10000` | `10000.0` | `0.12` | `1.2` | `0.02 / 0.015 / 0.06 / 12.0` | `0.84 / 0.93 / 0.94 / 0.04 / 16.0` | `yes_budget_pct 0.2`，`no_budget_pct 0.8`，`global_usage_cap_pct 0.72`，`per_market_cap_pct 0.04`，`per_city_cap_pct 0.1`，`per_date_cap_pct 0.1`，`per_event_cap_pct 0.1` | `yes_time_in_force GTC`，`no_time_in_force GTD`，`gtd_buffer_hours 8.0`，`replace_edge_buffer 0.03`，`max_order_hours_open 96.0` | `submission_latency_ms 5000`，`queue_ahead_shares 100.0`，`queue_ahead_ratio 0.3`，`touch_not_fill_min_touches 2`，`partial_fill_slice_ratio 0.4`，`cancel_latency_ms 4500` |

## 适用场景与三档怎么理解

### 100：小资金试跑档，最激进

- YES 更宽：`max_price 0.08`，允许更贵的低价票；`min_probability 0.005` 也更低。
- NO 更宽：`min_price 0.72`、`max_ask 0.97`、`min_probability 0.82`，说明它愿意接更多“没那么完美”的高价 NO。
- 仓位更猛：`kelly_fraction 0.35`、`no_kelly_fraction 1.8`，并且 `global_usage_cap_pct 0.92`、`per_market_cap_pct 0.15` 都很宽。
- 执行更快：挂单更短，`max_order_hours_open 36.0`；paper execution 延迟也更低。

适合场景：你还在验证自己会不会持续按规则执行，账户小，主要目标是快速建立样本和操作手感，而不是追求绝对稳健。

### 1000：当前默认档，最平衡

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

1. **候选质量稳定**：你连续一段时间观察到，`100` 档放出来的候选里，真正值得留单的并不是靠极宽阈值硬凑出来的；更严格一点的 YES/NO 阈值不会让候选池直接干掉。
2. **你能承受更真实的回撤节奏**：`1000` 档虽然更保守，但绝对资金变大了。你需要能接受单次浮亏金额变大，而不是只适应百分比概念。
3. **单市场容量开始有意义，但还不是硬瓶颈**：如果 `100` 档常出现“其实还能多下，但账户太小/仓位太散，统计意义不够”，说明可以升到 `1000`；如果你还远没到这个程度，没必要急着升。
4. **你愿意接受更慢的成交节奏**：从 `36h` 到 `72h` 的挂单容忍度变化不小；如果你总是因为等待不耐烦手动干预，先别升。

不该升级的典型信号：

- 你还在频繁手改挂单、手改阈值。
- 你仍然需要靠 `100` 档更宽的 `YES 0.08` 或 `NO 0.72/0.97` 才看得到足够多候选。
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
  "strategy_profile": "1000"
}
```

可选值只有当前提交态预设里的三个名字：`100`、`1000`、`10000`。

运行时语义要记住两点：

1. loader 会先按 `strategy_profile` 从 `strategy_profiles` 深度 merge 出最终配置。
2. `weatherbot` / `bot_v2.py` 消费的是 merge 后结果，不是你肉眼看到的顶层片段拼凑判断。

所以，**正常切换时只改 `strategy_profile`，不要手工把顶层 `yes_strategy`、`no_strategy`、`risk_router` 改成半套新档位。**

## 切换后立即检查项

切换完不要直接跑，先确认：

1. `strategy_profile` 字段已经是目标值，例如 `1000`。
2. 你理解当前运行会使用该 profile 深度 merge 后的结果，而不是只看顶层已有默认值。
3. 不要只改单个顶层字段，例如只把顶层 `balance` 改成 `10000`，却忘了 profile 里的 YES/NO 阈值、cap、order policy、paper execution 仍应该整体切换。
4. 如果你确实需要自定义某个档位，应该改对应的 `strategy_profiles[profile_name]` 内容，而不是造成“顶层一套、profile 一套”的错觉。
5. 切换后重新对照本手册中的关键数字，至少确认 YES 价格阈值、NO 价格/概率阈值、`max_size` 和 `global_usage_cap_pct` 符合预期。

### 当前默认 `1000` 档的快速核对值

如果你现在就是按推荐档位运行，至少应确认这些代表值和 `1000` preset 一致：

- `strategy_profile = 1000`
- YES：`max_price 0.05`、`min_probability 0.01`、`max_size 18.0`
- NO：`min_price 0.78`、`max_ask 0.95`、`min_probability 0.88`、`max_size 30.0`
- `risk_router.global_usage_cap_pct = 0.85`
- `order_policy.max_order_hours_open = 72.0`
- `paper_execution.submission_latency_ms = 3500`

如果这些值对不上，先不要继续把结果解释成策略问题，先确认是不是档位没切对，或者你手工改了顶层字段却没同步 profile 本体。

## 注意事项

- 当前推荐就是 `1000`，不是因为它“折中”，而是因为它最符合这个仓库现在要验证的目标：自动扫描、候选筛选、被动挂单、订单生命周期和持仓管理都要完整跑通，同时不把风险放大到 `100` 那么激进，也不把机会收缩到 `10000` 那么保守。
- `100` 更激进，适合小资金试跑；`10000` 更保守，适合容量、集中度和执行质量已经成为第一约束时再上。
- 如果你在实操里还经常靠主观判断临时改阈值，那先别升级档位；先把执行纪律稳定下来。
- 如果你切档后感觉“机会变少/变多很多”，先回看是不是配置逻辑生效了，而不是马上下结论说策略坏了。三档本来就故意在 YES/NO 阈值、cap 和执行耐心上拉开差距。
- 文档依据的是**当前已提交配置值**。后面只要 `config.json` 里的 `strategy_profiles` 改了，这份手册也必须一起更新，不能继续沿用旧结论。
