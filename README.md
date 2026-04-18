# 🌤 WeatherBet — Polymarket Weather Trading Bot

当前主入口仍然是 `bot_v2.py`，但主体实现已经拆到 `weatherbot/` 包里。

目标不变：扫描 Polymarket 天气温度市场，基于多源天气数据做 **YES-only** 模拟交易、被动挂单、订单生命周期管理和回放分析。

## 运行方式

兼容入口保持不变：

```bash
python bot_v2.py
python bot_v2.py status
python bot_v2.py report
python bot_v2.py replay
```

`config.json` 与 `data/` 现有格式保持兼容，不需要迁移历史文件。

## 当前模块结构

```text
bot_v2.py                 # 兼容 shim
weatherbot/__init__.py    # 兼容导出层 + 运行时同步
weatherbot/config.py      # config.json 加载与策略/执行配置解析
weatherbot/paths.py       # 仓库根目录、config/data 默认路径
weatherbot/domain.py      # 城市、时区、月份常量
weatherbot/forecasts.py   # 天气与结算温度数据访问
weatherbot/polymarket.py  # Polymarket/Gamma/CLOB 解析与行情辅助
weatherbot/persistence.py # state / market / calibration JSON 读写
weatherbot/strategy.py    # 扫描、候选、风控、主循环、监控
weatherbot/paper_execution.py # 被动订单与 paper execution 生命周期
weatherbot/reporting.py   # status / report / replay 输出
weatherbot/cli.py         # CLI 命令分发
```

## 安装

```bash
git clone https://github.com/alteregoeth-ai/weatherbot
cd weatherbot
uv sync
```

如果你只想跑测试，确保环境里至少有 `requests`、`pytest` 和 `pytest-cov`，然后直接使用 `uv run ...`。

## 配置

项目默认从仓库根目录读取 `config.json`，核心字段包括：

- 资金档位选择：`strategy_profile`（可选 `100` / `1000` / `10000`）
- 顶层资金与扫描参数：`balance`、`min_volume`、`min_hours`、`max_hours`、`scan_interval`
- 策略块：`yes_strategy`
- 风控块：`risk_router`
- 订单策略：`order_policy`
- Paper execution：`paper_execution`
- 结算温度拉取：`vc_key`

提交态 `config.json` 已经内置三档 **YES-only** 可运行预设，当前默认档位是 `100`：

- `100`：当前默认档，小资金观察用；YES 入场更宽、挂单等待更短，适合先把 YES-only 链路跑顺
- `1000`：中间档；YES 过滤、风险占用和等待节奏更均衡
- `10000`：更保守；YES 更便宜、cap 更紧、等待更耐心

切换方式只需要改一个字段：

```json
{
  "strategy_profile": "100"
}
```

运行时会先按所选 profile 深度 merge 出最终配置，然后 `weatherbot` / `bot_v2` 入口直接消费这份 merge 后结果；如果旧配置没有 `strategy_profile` / `strategy_profiles` 字段，则继续按原来的顶层配置运行。

当前默认 `100` 档的直觉应该是：优先让更多低价 YES 样本进入观察和挂单流程，同时保持更快的取消/替换节奏，方便小资金先验证 YES-only 执行链路。

历史说明：仓库早期文档曾讨论过 NO 腿 / `no_strategy`，但该路径已移除；当前提交态与运行时只支持 YES-only 活跃语义。

Visual Crossing key 现在走**环境变量优先**：运行时会先读取 `VISUAL_CROSSING_KEY`，只有未设置该环境变量时才回退到 `config.json` 里的 `vc_key`。

推荐本地配置方式：

```bash
cp .env.example .env
```

然后把真实 key 写进你本地 `.env`：

```bash
VISUAL_CROSSING_KEY=your_real_key_here
```

仓库里的 `config.json` 会保留空的 `vc_key` 作为安全占位，避免把真实 secret 提交进 git。

## 数据持久化

运行时仍然写入：

- `data/state.json`
- `data/calibration.json`
- `data/markets/*.json`

这些 JSON schema 保持现有测试覆盖下的兼容行为，包括：

- `bucket_probabilities`
- `quote_snapshot`
- `candidate_assessments`
- `route_decisions`
- `reserved_exposure`
- `active_order`
- `order_history`
- `paper_execution_state`
- `execution_events`

## 回归验证

默认回归（同时执行 `weatherbot` 包 coverage gate，低于 75% 直接失败）：

```bash
uv run pytest -q
```

这条命令已经内置 `--cov=weatherbot --cov-report=term-missing --cov-fail-under=75`，不需要额外手动拼 coverage 参数。

兼容入口 spot check：

```bash
uv run python bot_v2.py status
```

## 说明

- 已删除旧的 `bot_v1.py` 与历史 dashboard 文件，避免双实现继续漂移。
- `bot_v2.py` 现在只负责兼容导入与 CLI 启动，不再承载主体实现。
- `import bot_v2` 的现有测试/脚本调用方式继续可用。

## 外部数据源

| API | Auth | Purpose |
|-----|------|---------|
| Open-Meteo | None | ECMWF + HRRR forecasts |
| Aviation Weather (METAR) | None | Real-time station observations |
| Polymarket Gamma / CLOB | None | Market data |
| Visual Crossing | Free key | Historical temps for resolution |

## Disclaimer

这不是投资建议。当前仓库只提供 YES-only 模拟执行与回放语义；先在模拟模式下完整验证，再考虑任何真实资金行为。
