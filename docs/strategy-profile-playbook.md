# Strategy Profile 使用手册

## 当前状态

当前仓库已经收口为 **YES-only**。`strategy_profile` 的三档预设只用于调节低价 YES 的入场宽度、资金占用上限和挂单耐心，不再代表不同策略腿。

历史说明：更早的文档里出现过 NO 腿的说法，那是已移除路径，当前操作者不应再按那套语义理解或执行。

## 当前默认档位：100

当前提交态 `config.json` 的 `strategy_profile` 是 `100`。默认先用它，不是因为更刺激，而是因为它最贴近小资金下验证 **YES-only** 扫描、挂单和回放链路的目标。

`100` 档的核心直觉：

- `balance = 100.0`，先按小账户真实容量观察行为。
- YES 入场更宽：`max_price = 0.08`、`min_probability = 0.005`、`min_edge = 0.04`、`max_size = 25.0`。
- 总体 cap 更宽：`global_usage_cap_pct = 0.92`、`per_market_cap_pct = 0.15`、`per_city_cap_pct = 0.3`、`per_date_cap_pct = 0.3`、`per_event_cap_pct = 0.3`。
- 挂单更快：`gtd_buffer_hours = 4.0`、`max_order_hours_open = 36.0`、`submission_latency_ms = 2500`、`cancel_latency_ms = 2000`。

一句话：**默认 `100` 是为了让 YES-only 主链先稳定跑起来，并尽快看到真实样本。**

## 三档真实差异

下表只保留当前仍然活跃的 YES/shared 语义。

| 档位 | balance | YES max_price / min_probability / min_edge / max_size | 风控与容量 | 挂单与 paper execution |
| --- | ---: | --- | --- | --- |
| `100` | `100.0` | `0.08 / 0.005 / 0.04 / 25.0` | `global_usage_cap_pct 0.92`，`per_market_cap_pct 0.15`，`per_city_cap_pct 0.3`，`per_date_cap_pct 0.3`，`per_event_cap_pct 0.3` | `gtd_buffer_hours 4.0`，`max_order_hours_open 36.0`，`submission_latency_ms 2500`，`cancel_latency_ms 2000` |
| `1000` | `1000.0` | `0.05 / 0.01 / 0.05 / 18.0` | `global_usage_cap_pct 0.85`，`per_market_cap_pct 0.08`，`per_city_cap_pct 0.18`，`per_date_cap_pct 0.18`，`per_event_cap_pct 0.18` | `gtd_buffer_hours 6.0`，`max_order_hours_open 72.0`，`submission_latency_ms 3500`，`cancel_latency_ms 3000` |
| `10000` | `10000.0` | `0.02 / 0.015 / 0.06 / 12.0` | `global_usage_cap_pct 0.72`，`per_market_cap_pct 0.04`，`per_city_cap_pct 0.1`，`per_date_cap_pct 0.1`，`per_event_cap_pct 0.1` | `gtd_buffer_hours 8.0`，`max_order_hours_open 96.0`，`submission_latency_ms 5000`，`cancel_latency_ms 4500` |

## 三档怎么理解

### 100：小资金试跑档

- YES 候选最宽，便于快速积累样本。
- 单市场和总资金限制相对宽，更容易触碰真实容量边界。
- 挂单等待时间最短，适合先观察取消、替换和回放节奏。

适合：你现在的主要任务是确认 YES-only 链路是否稳定，而不是追求最保守的资金效率。

### 1000：中档平衡档

- YES 价格和概率门槛开始收紧。
- 单市场、单城市、单日期的占用明显下降。
- 挂单等待更长，更接近“等合适成交”而不是频繁换价。

适合：你已经确认 `100` 能稳定跑，开始更重视容量控制和执行质量。

### 10000：大资金保护档

- YES 只接受更便宜、edge 更高的机会。
- 总体与单市场 cap 最紧，优先防集中曝险。
- 挂单最耐心，paper execution 也最保守。

适合：你的问题已经不是“能不能跑起来”，而是“更大资金下怎样控制容量与执行质量”。

## 什么时候升级档位

### 从 100 升到 1000

满足下面几条再升更合理：

1. `100` 档已经能稳定产出 YES 候选样本。
2. 你对更大的绝对金额波动有心理预期。
3. 你开始持续复盘单市场占用，而不是只看有没有单。
4. 你能接受从 `36h` 延长到 `72h` 的等待节奏。

不该升级的典型信号：

- 你还在频繁手改阈值或手动干预挂单。
- 你还需要 `100` 档更宽的 YES 条件才能看清候选质量。
- 你没有持续看容量、等待和回放，只是想把金额放大。

### 从 1000 升到 10000

更适合这些情况：

1. 单市场和组合集中度已经成为真实问题。
2. 你更在意执行质量，愿意接受更慢的成交节奏。
3. 复盘表明真正有效的单子本来就集中在更便宜、更高 edge 的 YES。
4. 账户变大后，你更关心绝对金额控制而不是扩大出手频率。

不该升级的典型信号：

- 切到 `10000` 后几乎没有候选，但你并没有遇到容量问题。
- 你还没把 `1000` 档的等待和占用行为看清。
- 你只是因为余额变大，就机械地想切到最大档位。

## 切换方式

只改 `config.json` 里的 `strategy_profile`：

```json
{
  "strategy_profile": "100"
}
```

可选值只有 `100`、`1000`、`10000`。

运行时要记住两点：

1. loader 会先按 `strategy_profile` 从 `strategy_profiles` 深度 merge 出最终配置。
2. `weatherbot` / `bot_v2.py` 消费的是 merge 后结果，不是你肉眼看到的局部片段。

所以正常切换时只改 `strategy_profile`，不要手工拼半套 preset。

## 切到 100 后的检查清单

切到 `100` 后，先确认下面这些代表值：

- `strategy_profile = 100`
- YES：`max_price 0.08`、`min_probability 0.005`、`min_edge 0.04`、`max_size 25.0`
- `risk_router.global_usage_cap_pct = 0.92`
- `risk_router.per_market_cap_pct = 0.15`
- `order_policy.max_order_hours_open = 36.0`
- `paper_execution.submission_latency_ms = 2500`

观察 bot 行为时，重点看这几件事：

1. YES 候选是否比 `1000` 档更宽，而不是还停留在中档门槛。
2. 单市场占用是否更快触到小资金上限。
3. 挂单是否更快进入取消/替换节奏，而不是继续表现成长等待模式。
4. 行为异常时先查 profile merge 结果，再判断是不是策略问题。

## 注意事项

- 当前文档描述的是 **YES-only** 现状，不再包含已移除的 NO 活跃路径。
- `100` 更适合先跑通；`10000` 更适合在容量与执行质量成为第一约束后再用。
- 这份手册依据当前提交态 preset；只要 `strategy_profiles` 变了，这份文档也要同步更新。
