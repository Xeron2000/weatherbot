---
phase: quick-260418-ehf-bot
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - bot_v2.py
  - bot_v1.py
  - sim_dashboard_repost.html
  - README.md
  - weatherbot/__init__.py
  - weatherbot/config.py
  - weatherbot/paths.py
  - weatherbot/domain.py
  - weatherbot/forecasts.py
  - weatherbot/polymarket.py
  - weatherbot/persistence.py
  - weatherbot/strategy.py
  - weatherbot/reporting.py
  - weatherbot/paper_execution.py
  - weatherbot/cli.py
  - tests/test_modular_entrypoint.py
autonomous: true
requirements:
  - QUICK-260418-EHF
must_haves:
  truths:
    - "操作者仍可继续使用 `python bot_v2.py`、`python bot_v2.py status`、`python bot_v2.py report` 运行当前机器人。"
    - "`config.json` 与 `data/` 现有格式继续可读可写，重构后不会要求迁移已有状态文件。"
    - "旧版/死代码会被明确删除或标记不再属于主运行链路，不再与当前实现并存漂移。"
    - "核心逻辑不再继续堆在单个巨型脚本内，配置、持久化、外部数据、策略扫描、报告与 CLI 有清晰模块边界。"
  artifacts:
    - path: "weatherbot/config.py"
      provides: "配置加载与默认值兼容层"
    - path: "weatherbot/persistence.py"
      provides: "state/market/calibration JSON 读写与路径边界"
    - path: "weatherbot/strategy.py"
      provides: "扫描、候选、订单/持仓主编排逻辑"
    - path: "weatherbot/reporting.py"
      provides: "status/report 输出逻辑"
    - path: "weatherbot/cli.py"
      provides: "主 CLI 入口与命令分发"
    - path: "bot_v2.py"
      provides: "兼容 shim，继续暴露现有 import/CLI 表面"
    - path: "tests/test_modular_entrypoint.py"
      provides: "模块化后兼容性回归验证"
  key_links:
    - from: "bot_v2.py"
      to: "weatherbot/cli.py"
      via: "兼容导出 + CLI 委托"
      pattern: "from weatherbot\\.cli import|def main|if __name__ == '__main__'"
    - from: "weatherbot/config.py"
      to: "config.json"
      via: "默认配置加载"
      pattern: "config\\.json"
    - from: "weatherbot/persistence.py"
      to: "data/state.json,data/markets/*.json,data/calibration.json"
      via: "默认路径与 JSON schema 兼容"
      pattern: "state\\.json|markets|calibration\\.json"
    - from: "tests/test_modular_entrypoint.py"
      to: "bot_v2.py"
      via: "公开 API/CLI 兼容断言"
      pattern: "import bot_v2|scan_and_update|print_status|run_loop"
---

<objective>
在不重写项目的前提下，激进清理旧版/死代码，并把当前 `bot_v2.py` 拆成轻量模块化结构。

Purpose: 降低单文件膨胀与双实现漂移，给后续 Phase 6 和后续维护留出稳定边界。
Output: 一个 `weatherbot/` 模块目录、保留兼容表面的 `bot_v2.py` shim、删除后的遗留文件清单与更新后的 README。
</objective>

<execution_context>
@$HOME/.config/opencode/get-shit-done/workflows/execute-plan.md
@$HOME/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/quick/260418-ehf-bot/260418-ehf-CONTEXT.md
@.planning/codebase/CONCERNS.md
@.planning/codebase/ARCHITECTURE.md
@.planning/codebase/STACK.md
@bot_v2.py
@bot_v1.py
@README.md
@tests/conftest.py

<decisions>
- D-01: 允许激进清理旧版本、旧 dashboard、历史脚本等遗留内容；不要为了“也许以后有用”继续保留双实现。
- D-02: 轻量模块化；保留一个主 CLI 入口，把配置、持久化、天气/市场数据、策略/扫描、报告拆到独立模块。
- D-03: 尽量保持当前 CLI 命令、`config.json`、`data/` 持久化格式和主要运行方式兼容。
</decisions>

<interfaces>
当前兼容面必须继续存在，避免执行器自己猜：

From `bot_v2.py` current public surface:
```python
def new_market(city_slug, date_str, event, hours):
def load_state():
def save_state(state):
def scan_and_update():
def print_status():
def print_report():
def monitor_positions():
def run_loop():
```

Current CLI contract from `README.md`:
```bash
python bot_v2.py
python bot_v2.py status
python bot_v2.py report
```

Current test contract from `tests/*.py`:
```python
import bot_v2
```
模块化后仍必须让测试通过这个入口访问核心函数；不要把测试强行改成深层模块 import 来掩盖兼容破坏。
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: 建立模块边界与兼容测试护栏</name>
  <files>weatherbot/__init__.py, weatherbot/config.py, weatherbot/paths.py, weatherbot/domain.py, weatherbot/cli.py, tests/test_modular_entrypoint.py</files>
  <action>按 D-02 先定义轻量模块骨架与导出边界：把配置加载、默认路径、城市/时区常量、CLI 分发从 `bot_v2.py` 中抽成独立模块，但不要在这一步改业务语义。按 D-03 新增兼容回归测试，明确要求 `import bot_v2` 后仍可访问 `scan_and_update`、`monitor_positions`、`print_status`、`print_report`、`run_loop`、`load_state`、`save_state`、`new_market`，且默认仍从仓库根目录的 `config.json` 与 `data/` 工作。这样后续清理和迁移有可执行护栏，而不是边拆边猜。</action>
  <verify>
    <automated>uv run pytest tests/test_modular_entrypoint.py -q</automated>
  </verify>
  <done>模块骨架已建立；兼容测试先落地并能证明主入口、默认路径与关键公开函数合同被锁住。</done>
</task>

<task type="auto">
  <name>Task 2: 把 bot_v2 核心逻辑迁入模块并收缩为兼容 shim</name>
  <files>bot_v2.py, weatherbot/forecasts.py, weatherbot/polymarket.py, weatherbot/persistence.py, weatherbot/strategy.py, weatherbot/reporting.py, weatherbot/paper_execution.py, weatherbot/cli.py</files>
  <action>按 D-02 将 `bot_v2.py` 的真实实现拆到独立模块：天气/市场数据访问进入 `forecasts.py` 与 `polymarket.py`，JSON 状态/market/calibration 进入 `persistence.py`，扫描/候选/订单/持仓主流程进入 `strategy.py`，status/report 进入 `reporting.py`，paper execution 相关 helper 进入 `paper_execution.py`。`bot_v2.py` 自身收缩成薄兼容层，只做 import/re-export 与 CLI 启动。按 D-03 保持现有 JSON schema、命令行行为、测试 monkeypatch 点与输出语义，不要借机改策略、改字段名、改 state 结构，也不要把兼容破坏伪装成“新模块 API”。</action>
  <verify>
    <automated>uv run pytest -q</automated>
  </verify>
  <done>`bot_v2.py` 不再承载主体实现；完整回归套件通过；现有 CLI 与 `import bot_v2` 兼容表面仍可用。</done>
</task>

<task type="auto">
  <name>Task 3: 删除确认无用的旧文件/死代码并同步文档</name>
  <files>bot_v1.py, sim_dashboard_repost.html, README.md</files>
  <action>按 D-01 基于代码证据执行激进清理：删除已不在当前主运行链路、也不被测试或 README 需要的遗留文件与死代码，优先目标包括 `bot_v1.py` 与旧 dashboard。删除前先确认没有活动引用；若某文件仍承担兼容职责，则保留并在 README 中明确其用途，禁止“半删除半保留”。同时更新 `README.md`：去掉旧版本叙述，改写为当前模块布局、保留的 `bot_v2.py` 入口、以及 `uv run pytest -q` 级别回归验证方式，确保文档不再把操作者带回旧实现。</action>
  <verify>
    <automated>uv run pytest -q && uv run python bot_v2.py status</automated>
  </verify>
  <done>无用旧文件已删除或有明确保留理由；README 只描述当前主结构；执行 `bot_v2.py status` 仍能跑通。</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI → modular runtime | 用户命令进入重构后的导出/分发层，兼容破坏会直接导致不可用 |
| config/data JSON → runtime modules | 现有 `config.json` 与 `data/*.json` 是不可信历史输入，重构时最容易被路径或 schema 漂移破坏 |
| cleanup decisions → shipped repo | 删除旧文件是不可逆代码改动，误删仍被主链路依赖的文件会造成运行时 DoS |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | T | `weatherbot/config.py`, `weatherbot/persistence.py` | mitigate | 保持 `config.json`、`data/state.json`、`data/markets/*.json`、`data/calibration.json` 默认路径与字段兼容；用兼容测试 + 全量 pytest 防止 schema/path 被重构篡改 |
| T-quick-02 | D | `bot_v2.py`, `weatherbot/cli.py` | mitigate | 让 `bot_v2.py` 仅做 shim 但继续暴露既有函数与 CLI 命令；新增 `tests/test_modular_entrypoint.py` 锁定公开表面，防止入口失效 |
| T-quick-03 | D | `bot_v1.py`, `sim_dashboard_repost.html`, `README.md` | mitigate | 删除前先以测试、README、代码引用为依据确认无活动依赖；删除后执行 `uv run pytest -q && uv run python bot_v2.py status` 验证主链路未被切断 |
| T-quick-04 | R | cleanup decisions | accept | 删除遗留文件本身不引入新的外部审计面；只需在 SUMMARY 中记录删除了哪些文件及依据，作为后续追溯证据 |
</threat_model>

<verification>
- `uv run pytest tests/test_modular_entrypoint.py -q`
- `uv run pytest -q`
- `uv run python bot_v2.py status`
- 手工 spot check：`bot_v2.py` 变为薄入口，主体实现落在 `weatherbot/` 模块目录下；仓库不再同时维护旧 bot/dashboard 双实现。
</verification>

<success_criteria>
- `bot_v2.py` 仍是唯一主入口，但主体逻辑已拆到模块文件。
- 当前回归测试继续通过，且无需迁移 `config.json` 或 `data/` 历史文件。
- `bot_v1.py`、旧 dashboard、以及确认无活动引用的死代码已被删除。
- README 不再宣传旧版本路线，而是描述当前模块结构与兼容运行方式。
</success_criteria>

<output>
After completion, create `.planning/quick/260418-ehf-bot/260418-ehf-SUMMARY.md`
</output>
