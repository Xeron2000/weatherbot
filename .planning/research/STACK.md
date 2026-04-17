# Stack Research

**Domain:** brownfield Polymarket 天气市场执行机器人（simulation-first，后续可接实盘）
**Researched:** 2026-04-17
**Confidence:** MEDIUM-HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | 主运行时 | 对现有脚本迁移成本最低；生态稳定；`py-clob-client` 支持 Python 3.9+，3.12 是 2026 年最稳妥的工程默认版本。 |
| uv | latest stable | 包管理、虚拟环境、锁文件、运行命令 | 2026 年 Python 项目默认优先选项；用 `pyproject.toml` + `uv.lock` 解决当前仓库无锁文件、无依赖边界的问题。 |
| `uv_build` | `>=0.11.7,<0.12` | 纯 Python 打包后端 | 适合这个纯 Python CLI bot；比 `setuptools`/Poetry 更轻，且与 uv 原生配合最好。 |
| `py-clob-client` | `>=0.34,<0.35` | Polymarket CLOB 读写、签名、下单、撤单 | Polymarket 官方 Python SDK；能直接覆盖认证、签名、下单、撤单、订单查询，避免自己碰 EIP-712 / HMAC 细节。 |
| `httpx` | `>=0.28,<0.29` | 天气源、Gamma/Data API、非交易 HTTP 调用 | 比现有 `requests` 更适合新代码：默认超时模型更严格，sync/async 双栈一致，且和测试桩工具 `respx` 配套很好。 |
| SQLite (`sqlite3`) | stdlib | 订单生命周期、fills、position ledger、simulation event log | 这是我对现有“全 JSON 持久化”的唯一建议升级。订单/撤单/部分成交/重启恢复一旦引入，JSON 文件很快会失控；SQLite 仍然是本地、单文件、零额外服务，但事务和查询能力强很多。 |
| `pydantic` | `>=2.13,<2.14` | 边界数据模型、输入校验、配置/状态 schema | 用在配置、外部 API 响应清洗、CLI 输入和持久化记录 schema，能显著降低脚本继续膨胀时的脆弱性。 |
| `pydantic-settings` | `>=2.13,<2.14` | 环境变量与 `.env` 配置加载 | 当前 `config.json` 里直接放 key，不适合后续接 Polymarket 密钥；这个包是最轻的升级路径。 |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tenacity` | `>=9.1,<10` | 对天气 API、Gamma API、非幂等外的读请求做有限重试 | 只用于读取类请求和安全幂等调用；不要包住真实下单，避免重复执行风险。 |
| `orjson` | `>=3.11,<4` | 高速序列化快照、导出回测/报告数据 | 可选；当 snapshot / ledger 体量变大时再加。不是首批必需依赖。 |
| `pytest` | `>=9,<10` | 单元测试与集成测试 | 必加；这是当前仓库最缺的基础设施。 |
| `respx` | `>=0.22,<0.23` | mock `httpx` 请求 | 用于天气源、Gamma/Data API、回放固定 orderbook / price 响应。 |
| `pytest-xdist` | `>=3.8,<4` | 并行测试 | 可选；当回放场景和仿真矩阵变多时再开。 |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `ruff` | lint + format | 用一个工具替代 Flake8 + isort + Black；符合“保持简单”的目标。 |
| `uv run` | 统一运行入口 | 用 `uv run pytest`、`uv run python -m weatherbot.cli`，不要再混用系统 Python。 |
| stdlib `logging` | 结构化执行日志 | 不建议一开始引入 `structlog`；先把 `print()` 收口为标准 logging，并给 order_id / market_id / city 打字段。 |

## Recommended Dependency Strategy

### 1. 先把仓库变成一个“可安装应用”，不要直接上 workspace

这个项目现在还是单 bot、单操作者、单进程。**不要一开始拆 monorepo/workspace。**

推荐结构：

```text
weatherbot/
  pyproject.toml
  uv.lock
  src/weatherbot/
    cli.py
    config.py
    domains/
    forecasts/
    polymarket/
    strategy/
    execution/
    simulation/
    storage/
```

原因：
- 比继续把逻辑堆在 `bot_v2.py` 里更稳。
- 比拆多个 package/workspace 简单得多。
- `src/` 布局能避免“测试时从仓库根目录误 import 成功”的假象。

**保留 `bot_v2.py` 作为过渡 shim 即可**，内部逐步委托到 `weatherbot.cli`。

### 2. 用“双边界”策略控依赖

依赖只放在两类边界：

1. **外部边界**：Polymarket、天气 API、配置、CLI
2. **持久化边界**：SQLite / JSON 导入导出

核心策略与 simulation 引擎里尽量只用：
- `dataclasses`
- `decimal.Decimal`
- `enum`
- `typing`
- 纯 Python 业务代码

这很重要：
**Pydantic 用在边界，核心撮合/定价/资金路由不要全靠 Pydantic model 跑。**
否则执行环节会变成“到处是 schema，真正策略逻辑反而更难改”。

### 3. execution 抽象只做一层，不做交易所通用框架

推荐接口：

```python
class ExecutionVenue(Protocol):
    def place_limit_order(self, intent: OrderIntent) -> PlacedOrder: ...
    def cancel_order(self, order_id: str) -> CancelResult: ...
    def get_open_orders(self) -> list[OpenOrder]: ...
    def get_order_status(self, order_id: str) -> OrderStatus: ...
```

只实现两个 adapter：
- `PaperVenue`：simulation-first
- `PolymarketVenue`：后续实盘

不要做：
- 通用 exchange adapter 框架
- ccxt 风格统一接口
- “先支持多交易所以后再说”

这个项目是 **Polymarket weather bot**，不是通用 trading platform。

### 4. 持久化策略：配置继续文本化，执行状态改 SQLite

推荐分层：

- `.env`：密钥、账户、运行模式
- `config.toml` 或 `config.json`：非敏感策略参数
- `state.db`（SQLite）：订单、挂单队列、候选、fills、positions、simulation events
- `exports/*.json`：调试导出、dashboard 喂数、人工审计快照

这样既保留“本地文件可控”，又解决：
- 订单生命周期难追踪
- 重启恢复脆弱
- JSON 被并发/中断写坏
- 报表查询太痛苦

### 5. simulation-first 的正确依赖边界

simulation 层不要依赖真实 SDK 的响应格式。

做法：
- `OrderIntent` / `PlacedOrder` / `FillEvent` / `PositionLot` 自定义域模型
- `PaperVenue` 与 `PolymarketVenue` 都映射到这套域模型
- 所有策略测试都只喂域模型，不直接喂 SDK 原始 dict

这样后续从 paper 切 live，不会把整个策略层重写一遍。

## Installation

```bash
# 初始化 Python 版本
uv python install 3.12

# 核心依赖
uv add "py-clob-client>=0.34,<0.35" \
  "httpx>=0.28,<0.29" \
  "pydantic>=2.13,<2.14" \
  "pydantic-settings>=2.13,<2.14" \
  "tenacity>=9.1,<10"

# 可选性能依赖
uv add "orjson>=3.11,<4"

# 开发依赖
uv add --dev "pytest>=9,<10" \
  "respx>=0.22,<0.23" \
  "pytest-xdist>=3.8,<4" \
  "ruff>=0.15,<0.16"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `py-clob-client` | 直接打 CLOB REST + 自己做签名 | 只有在官方 SDK 缺关键能力、或你要做极细粒度底层优化时才值得；v1/v2 阶段不值得。 |
| `httpx` | `requests` | 仅在保留旧模块、不想立刻迁移时继续容忍；所有新模块应统一到 `httpx`。 |
| SQLite | 继续全 JSON 持久化 | 只有在你仍停留在“单次扫描、几乎没有订单生命周期”时才够用；一旦引入挂单/撤单/部分成交，就不够了。 |
| 单 package app | uv workspace / 多 package monorepo | 只有当 `simulation engine`、`CLI`、`dashboard feeder` 已经明显要独立发布/测试时再拆。 |
| `pydantic-settings` + `.env` | 纯 `config.json` | 只适合没有任何敏感密钥、没有环境切换的脚本；不适合要接 Polymarket 认证的 bot。 |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Poetry / Pipenv / `requirements.txt` 作为主依赖源 | 会让 brownfield 迁移多一层工具切换成本；还会继续保持“无锁、无统一运行入口” | `uv` + `pyproject.toml` + `uv.lock` |
| 新代码继续用 `requests` | timeout、连接池、测试替身、未来 async 迁移都不如 `httpx` | `httpx.Client` |
| 一开始就上 asyncio / websocket / actor 架构 | 这个 bot 的核心节奏是分钟级/小时级扫描与挂单管理，不是高频撮合；复杂度收益比太差 | 单进程同步 loop + 明确的 polling interval |
| Postgres / Redis / Celery | 对单操作者本地 bot 过重，部署和恢复复杂度不值当 | SQLite + 单进程调度 |
| pandas / backtrader / 通用量化框架 | 这里不是大规模 K 线研究，也不是券商回测框架；会把项目带离“执行机器人”主线 | 轻量域模型 + SQLite + 自定义 simulation engine |
| 自己写 EIP-712 / HMAC 签名栈 | 容易踩 Polymarket 认证和代理钱包细节坑 | `py-clob-client` |
| 过早引入 generic exchange abstraction | Polymarket 的 CLOB、neg-risk、heartbeat、funder/signature_type 都很特化 | 只做 `PaperVenue` / `PolymarketVenue` 两个 adapter |

## Stack Patterns by Variant

**If 目标仍然是 simulation-first（当前推荐）：**
- 用 `py-clob-client` 只做 read-only market data 校验或预留 live adapter
- 核心执行走 `PaperVenue`
- 重点建设 SQLite ledger、order queue、fill simulator、恢复逻辑

**Because：**
先把“候选发现 → 下单意图 → 排队 → 部分成交 → 取消/超时 → 持仓退出”链路跑稳，比提早接真钱更重要。

**If 准备进入有限实盘：**
- 保持相同的策略层和 order domain model
- 新增 `PolymarketVenue`
- 增加 geoblock / heartbeat / allowance / auth health checks

**Because：**
Polymarket live 复杂度主要在执行边界，不该污染策略和 simulation 核心。

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.12 | `py-clob-client>=0.34,<0.35` | 官方包要求 Python 3.9+，3.12 是稳妥生产版本。 |
| `httpx>=0.28,<0.29` | `respx>=0.22,<0.23` | RESPX 官方说明要求 HTTPX 0.25+；这组组合安全。 |
| `pydantic>=2.13,<2.14` | `pydantic-settings>=2.13,<2.14` | 同代版本最省心，避免 settings/source API 小差异。 |
| `uv_build>=0.11.7,<0.12` | uv latest stable | Astral 官方文档明确建议对 `uv_build` 加上上界。 |
| `orjson>=3.11,<4` | Python 3.12 | `orjson` 3.11.x 需要 Python 3.10+，与本项目选择一致。 |

## Final Recommendation

**最优 2026 方案不是“重写成更复杂的系统”，而是：**

1. **Python 3.12 + uv** 把仓库先变成可安装、可锁版本、可测试的项目。
2. **`py-clob-client` 作为唯一 Polymarket 交易 SDK**，不要自写签名与下单协议。
3. **新 HTTP 代码统一 `httpx`**，旧 `requests` 模块逐步迁移，不强行一次性重写。
4. **配置走 `pydantic-settings`，执行状态走 SQLite**；JSON 只留给导出与人工查看。
5. **simulation/live 共用一套 order domain model + execution interface**，只分 `PaperVenue` 与 `PolymarketVenue`。
6. **测试只上 pytest + respx + ruff**，先把基础打稳，不引入多余框架。

这套组合最符合这个仓库的现实：**brownfield、单操作者、本地运行、先模拟后实盘、以被动挂单和订单生命周期为核心。**

## Sources

- Polymarket Docs — https://docs.polymarket.com/api-reference/introduction — 验证 Gamma / Data / CLOB 三类 API 边界（HIGH）
- Polymarket Docs — https://docs.polymarket.com/api-reference/clients-sdks — 验证官方 Python SDK 存在且覆盖交易能力（HIGH）
- Polymarket Docs — https://docs.polymarket.com/api-reference/authentication — 验证 L1/L2 认证、signature type、funder、heartbeat、geoblock 等执行约束（HIGH）
- PyPI — https://pypi.org/project/py-clob-client/ — 验证 `py-clob-client` 当前版本 `0.34.6`、Python 3.9+、limit/market order 示例（HIGH）
- uv Docs — https://docs.astral.sh/uv/concepts/projects/dependencies/ — 验证 `pyproject.toml`、dependency groups、lockfile 工作流（HIGH）
- uv Docs — https://docs.astral.sh/uv/concepts/projects/workspaces/ — 验证 workspace 适用场景与“不必过早拆分”的依据（HIGH）
- uv Docs — https://docs.astral.sh/uv/concepts/build-backend/ — 验证 `uv_build>=0.11.7,<0.12` 建议（HIGH）
- HTTPX Docs — https://www.python-httpx.org/ — 验证 sync/async、HTTP/2、严格 timeout、测试友好特性（HIGH）
- pytest Docs — https://docs.pytest.org/en/stable/ — 验证 pytest 9.x 稳定文档与 Python 3.10+ 支持（HIGH）
- RESPX Docs / PyPI — https://lundberg.github.io/respx/ 、https://pypi.org/project/respx/ — 验证其与 HTTPX 的兼容范围（MEDIUM-HIGH）
- Pydantic Settings Docs — https://docs.pydantic.dev/latest/concepts/pydantic_settings/ （通过官方跳转与文档摘录验证）— 验证 `BaseSettings` / `.env` 能力（MEDIUM）
- Pydantic Releases / PyPI — https://github.com/pydantic/pydantic/releases 、https://pypi.python.org/pypi/pydantic — 验证 2.13 系列为当前代版本（MEDIUM）
- pydantic-settings Releases / PyPI — https://github.com/pydantic/pydantic-settings/releases 、https://pypi.python.org/pypi/pydantic-settings — 验证 2.13 系列为当前代版本（MEDIUM）
- Tenacity Docs / PyPI — https://tenacity.readthedocs.io/en/latest/ 、https://pypi.python.org/pypi/tenacity — 验证 retry 能力与 9.1.x 版本线（MEDIUM）
- pytest-xdist Docs — https://pytest-xdist.readthedocs.io/en/latest/ — 验证并行测试可选方案（MEDIUM）
- orjson PyPI — https://pypi.org/project/orjson/3.11.7/ — 验证 Python 3.10+ 与 3.x 版本约束（MEDIUM)

---
*Stack research for: Polymarket weather execution bot*
*Researched: 2026-04-17*
