<!-- GSD:project-start source:PROJECT.md -->
## Project

**Polymarket Weather Asymmetry Bot**

这是一个基于现有 `weatherbot` 代码库继续演进的 Polymarket 天气市场自动交易项目，目标是在天气温度区间市场里执行一套高不对称回报策略：低价 YES 窄温区猎杀 + 高价 NO 稳赚小利。v1 先做模拟交易，但要把自动扫描、候选筛选、被动挂单、订单生命周期和持仓管理链路完整跑通，为后续实盘接入留好执行边界。

**Core Value:** 在天气市场里稳定抓住“概率对、价格错”的盘口，并用可验证的自动化执行把高赔率机会变成可重复策略。

### Constraints

- **Codebase**: 在现有 `weatherbot` 代码上演进 — 用户明确选择 brownfield 演进而不是重写
- **Trading Mode**: v1 先做模拟交易 — 先验证策略与执行链路，避免真实资金风险
- **Market Scope**: 仅覆盖 Polymarket 天气温度市场 — 与当前仓库能力和给定策略完全对齐
- **Execution Goal**: 完成标准优先“自动扫描 + 挂单” — 先保证候选发现与订单管理闭环
- **Runtime**: 延续 Python CLI + 本地 JSON 持久化 — 现有项目已具备这套运行方式，改造成本最低
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3 (version not pinned) - CLI bot logic in `bot_v1.py` and `bot_v2.py`
- JSON - runtime configuration in `config.json` and persisted bot state in files declared in `bot_v2.py:47-52`
- HTML/CSS/JavaScript - local simulation dashboard in `sim_dashboard_repost.html`
## Runtime
- Python 3 via script shebangs in `bot_v1.py:1` and `bot_v2.py:1`
- Browser runtime for the optional dashboard in `sim_dashboard_repost.html`
- pip implied by installation instructions in `README.md:64-69`
- Lockfile: missing (`requirements.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock`, and `uv.lock` are not present in the repository root)
## Frameworks
- Standard library modules (`json`, `math`, `time`, `pathlib`, `datetime`, `argparse`, `sys`, `re`) - application logic in `bot_v1.py` and `bot_v2.py`
- `requests` (version not pinned) - all HTTP integrations in `bot_v1.py:16`, `bot_v2.py:20`, and installation guidance in `README.md:64-69`
- Not detected - no test framework config or test files are present at the repository root
- No dedicated build system detected - scripts run directly with `python` from `bot_v1.py` and `bot_v2.py`
- Chart.js 4.4.0 via CDN - dashboard chart rendering in `sim_dashboard_repost.html:7`
## Key Dependencies
- `requests` - required for every external API call to weather sources, Polymarket, and Visual Crossing in `bot_v1.py:133-170` and `bot_v2.py:189-308`
- Python standard library `pathlib.Path` - manages persistent data directories and files in `bot_v2.py:22` and `bot_v2.py:47-52`
- Local filesystem - persistent state stored under `data/` in `bot_v2.py:47-52`, `bot_v2.py:348-408`, and described in `README.md:102-110`
- Chart.js CDN - optional local dashboard visualization in `sim_dashboard_repost.html:7` and `sim_dashboard_repost.html:157-162`
- Google Fonts CDN - dashboard typography in `sim_dashboard_repost.html:6`
## Configuration
- Runtime settings are loaded from `config.json` in `bot_v1.py:23-29` and `bot_v2.py:28-42`
- Required config keys currently used by `bot_v2.py` are `balance`, `max_bet`, `min_ev`, `max_price`, `min_volume`, `min_hours`, `max_hours`, `kelly_fraction`, `max_slippage`, `scan_interval`, `calibration_min`, and `vc_key` from `config.json:1-14`
- `vc_key` is a plain JSON config value, not an environment variable, in `config.json:12` and `bot_v2.py:42`
- No build config files detected
- Runtime behavior is controlled directly inside script constants and CLI entrypoints in `bot_v1.py:245-454` and `bot_v2.py:952-1028`
## Platform Requirements
- Python 3 with the `requests` package installed, per `README.md:64-69`
- Writable local filesystem for `data/state.json`, `data/calibration.json`, and `data/markets/*.json` created by `bot_v2.py:47-52` and `bot_v2.py:348-408`
- Optional local HTTP server for the dashboard because `sim_dashboard_repost.html` fetches JSON over HTTP in `sim_dashboard_repost.html:237-300`
- Local long-running Python process using `run_loop()` in `bot_v2.py:952-1012`
- No container, process manager, cloud deployment config, or CI/CD pipeline detected in the repository root
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Root-level executable scripts use snake_case versioned filenames: `bot_v1.py`, `bot_v2.py`.
- JSON configuration/state files use lowercase snake_case names: `config.json`, `simulation.json` in `bot_v1.py`, `data/state.json` and `data/calibration.json` in `bot_v2.py`.
- Use snake_case for all functions and helpers, including I/O, parsing, math, and CLI entry points: `load_sim()` and `show_positions()` in `bot_v1.py`; `get_ecmwf()`, `scan_and_update()`, `print_report()`, and `run_loop()` in `bot_v2.py`.
- Verb-led names are the default for side-effecting functions: `load_state()`, `save_state()`, `take_forecast_snapshot()`, `monitor_positions()` in `bot_v2.py`.
- Module-level configuration constants use UPPER_SNAKE_CASE: `ENTRY_THRESHOLD`, `EXIT_THRESHOLD`, `SIM_FILE` in `bot_v1.py`; `BALANCE`, `MAX_BET`, `SCAN_INTERVAL`, `MONITOR_INTERVAL` in `bot_v2.py`.
- Local working variables use short snake_case names, often domain-specific abbreviations: `mkt`, `pos`, `pnl`, `rng`, `mid`, `snap` in `bot_v2.py`.
- Private module globals are prefixed with `_`: `_cfg` in both `bot_v1.py` and `bot_v2.py`, `_cal` in `bot_v2.py`.
- Type hints are sparse and selective rather than comprehensive.
- Simple built-in return annotations are used in `bot_v1.py`, such as `load_sim() -> dict`, `get_forecast(city_slug: str) -> dict`, and `hours_until_resolution(event: dict) -> float`.
- `bot_v2.py` mostly omits annotations except for `_cal: dict = {}`.
## Code Style
- No formatter config is present: no `pyproject.toml`, `ruff.toml`, `setup.cfg`, `.flake8`, `mypy.ini`, `pytest.ini`, or `tox.ini` were detected in `/home/xeron/Coding/weatherbot`.
- Formatting is hand-maintained inside the scripts `bot_v1.py` and `bot_v2.py`.
- Section dividers use long comment banners with repeated `=` characters, for example `# =============================================================================` throughout `bot_v1.py` and `bot_v2.py`.
- Inline dictionary literals are vertically aligned for readability in large constant maps such as `LOCATIONS` and `TIMEZONES` in `bot_v2.py`.
- Assignment alignment is used for configuration blocks, e.g. `BALANCE          = ...` through `VC_KEY           = ...` in `bot_v2.py:31-42`.
- No lint configuration is detected in `/home/xeron/Coding/weatherbot`.
- There is no evidence of Ruff, Flake8, Pylint, Black, isort, or mypy configuration files.
- The effective standard is “match the existing file-local style” in `bot_v1.py` and `bot_v2.py`.
## Import Organization
- Not used. The code imports only standard library modules and `requests`.
## Error Handling
- Use `try`/`except` around almost every network call and file read/write boundary rather than raising domain-specific exceptions.
- Prefer graceful fallback values over hard failures:
- Broad `except Exception` blocks are common for API integrations and runtime loops, for example in `get_forecast()` and `get_polymarket_event()` in `bot_v1.py`, and `get_ecmwf()`, `get_hrrr()`, `get_metar()`, `get_actual_temp()`, `scan_and_update()`, and `run_loop()` in `bot_v2.py`.
- Runtime recovery is usually implemented with logging plus `continue`, `break`, or fallback defaults instead of exception propagation.
- User-visible warnings are emitted inline via `warn()` in `bot_v1.py` and bracketed `print()` messages in `bot_v2.py`.
## Logging
- `bot_v1.py` wraps console output in helper functions `ok()`, `warn()`, `info()`, and `skip()` plus ANSI color constants in class `C`.
- `bot_v2.py` prints structured status markers directly, such as `[BUY]`, `[SKIP]`, `[WARN]`, `[STOP]`, `[TRAILING]`, `[WIN]`, and `[LOSS]` in `scan_and_update()` and `monitor_positions()`.
- There is no `logging` module setup, log level abstraction, or log sink configuration in the repository root or in `bot_v1.py`/`bot_v2.py`.
## Comments
- Use comments heavily to separate phases of execution and explain trading rules.
- Major control-flow regions are labeled with banner comments, such as `# CONFIG`, `# FORECASTS`, `# CORE LOGIC`, `# REPORT`, and `# CLI` in `bot_v2.py`.
- Short explanatory comments clarify non-obvious business rules, for example:
- Not applicable.
- Python docstrings are used selectively for user-facing modules and non-trivial functions, including the module docstrings in `bot_v1.py` and `bot_v2.py`, plus function docstrings such as `get_forecast()` in `bot_v1.py` and `get_actual_temp()` and `monitor_positions()` in `bot_v2.py`.
## Function Design
- Helper functions are small and single-purpose (`calc_ev()` in `bot_v2.py`, `parse_temp_range()` in both scripts).
- Orchestration functions are large and procedural:
- Most helpers accept primitive values and domain strings rather than objects or classes, e.g. `get_polymarket_event(city_slug, month, day, year)` and `market_path(city_slug, date_str)`.
- Shared mutable state is often read from module globals instead of being injected, such as `LOCATIONS`, `MAX_BET`, `MARKETS_DIR`, and `_cal` in `bot_v2.py`.
- Simple computed values are returned as primitives or plain dictionaries.
- Multi-part state is represented with JSON-serializable dictionaries/lists instead of dataclasses or custom classes, for example market records from `new_market()` in `bot_v2.py` and simulation state from `load_sim()` in `bot_v1.py`.
- Batch/orchestration functions return summary tuples where useful, e.g. `scan_and_update()` returns `(new_pos, closed, resolved)` in `bot_v2.py:753`.
## Module Design
- There is no package export surface. Both `bot_v1.py` and `bot_v2.py` are standalone executable modules with CLI guards at `bot_v1.py:442-454` and `bot_v2.py:1017-1028`.
- Internal helpers are defined in the same file as the CLI entry point and called directly.
- Not used.
- The repository does not have a package directory, `__init__.py`, or re-export modules; all executable behavior lives in `bot_v1.py` and `bot_v2.py`.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Keep executable logic in top-level Python entrypoint files: `bot_v1.py` and `bot_v2.py`.
- Group behavior by section comments inside each script instead of splitting into packages or modules, for example `# CONFIG`, `# FORECASTS`, `# POLYMARKET`, `# STATE`, and `# CORE LOGIC` in `bot_v2.py`.
- Persist runtime state to JSON files on disk instead of a database, using `simulation.json` in `bot_v1.py` and `data/state.json`, `data/calibration.json`, and `data/markets/*.json` in `bot_v2.py`.
## Layers
- Purpose: Parse command selection and start the requested execution mode.
- Location: `bot_v1.py:442`, `bot_v2.py:1017`, `sim_dashboard_repost.html:149`.
- Contains: argparse-based CLI in `bot_v1.py`, argv command dispatch in `bot_v2.py`, browser polling logic in `sim_dashboard_repost.html`.
- Depends on: Core orchestration functions such as `run()` in `bot_v1.py:245`, `run_loop()` in `bot_v2.py:952`, and `loadData()` in `sim_dashboard_repost.html:237`.
- Used by: Shell execution (`python bot_v1.py`, `python bot_v2.py`) and browser execution of `sim_dashboard_repost.html`.
- Purpose: Load thresholds, bankroll settings, scan intervals, and API configuration.
- Location: `config.json`, `bot_v1.py:23-31`, `bot_v2.py:28-52`.
- Contains: Static JSON config file plus module-level constants derived from `_cfg`.
- Depends on: Local file access through `open()` in `bot_v1.py:23` and `open(..., encoding="utf-8")` in `bot_v2.py:28`.
- Used by: All downstream logic, especially position sizing, filtering, scan cadence, and Visual Crossing access.
- Purpose: Define supported cities, station mappings, timezones, and month naming for market slug construction.
- Location: `bot_v1.py:34-63`, `bot_v2.py:54-91`.
- Contains: `LOCATIONS`, `NWS_ENDPOINTS`, `STATION_IDS`, `TIMEZONES`, `MONTHS`, and active location selection in `bot_v1.py:59-60`.
- Depends on: Hard-coded dictionaries embedded in the scripts.
- Used by: Forecast fetchers, Polymarket lookup, reporting, and market record creation.
- Purpose: Pull weather forecasts and observations from external services.
- Location: `bot_v1.py:119-159`, `bot_v2.py:174-266`.
- Contains: `get_forecast()` in `bot_v1.py`, plus `get_ecmwf()`, `get_hrrr()`, `get_metar()`, and `get_actual_temp()` in `bot_v2.py`.
- Depends on: `requests.get(...)`, `LOCATIONS`, `TIMEZONES`, and API-specific URL construction.
- Used by: Snapshot generation in `bot_v2.py:414-441` and market scanning in `bot_v1.py:308-327` / `bot_v2.py:458-540`.
- Purpose: Read Polymarket event and market pricing data and translate text buckets into numeric ranges.
- Location: `bot_v1.py:165-204`, `bot_v2.py:268-341`.
- Contains: `get_polymarket_event()`, `get_market_price()`, `check_market_resolved()`, `parse_temp_range()`, `hours_until_resolution()` / `hours_to_resolution()`, and `in_bucket()`.
- Depends on: Polymarket Gamma endpoints and regular-expression parsing.
- Used by: Entry selection, exit management, auto-resolution, and reporting.
- Purpose: Save and reload simulation state, per-market history, and calibration data.
- Location: `bot_v1.py:87-113`, `bot_v2.py:127-168`, `bot_v2.py:348-408`.
- Contains: `load_sim()` / `save_sim()` in `bot_v1.py`, and `load_cal()`, `run_calibration()`, `market_path()`, `load_market()`, `save_market()`, `load_all_markets()`, `load_state()`, `save_state()` in `bot_v2.py`.
- Depends on: Local JSON files under project root and runtime-created `data/` directories via `Path("data")` in `bot_v2.py:47-52`.
- Used by: All long-running behavior, reporting, and dashboard data consumption.
- Purpose: Combine forecasts, market data, filters, sizing, and position lifecycle rules.
- Location: `bot_v1.py:245-454`, `bot_v2.py:414-753`, `bot_v2.py:862-1012`.
- Contains: One-pass scan in `run()` for v1, full-cycle orchestration in `scan_and_update()`, quick monitoring in `monitor_positions()`, and continuous scheduling in `run_loop()` for v2.
- Depends on: Every lower layer.
- Used by: CLI commands and status/report commands.
- Purpose: Render terminal reports and browser-based dashboards.
- Location: `bot_v1.py:69-81`, `bot_v1.py:210-239`, `bot_v2.py:759-854`, `sim_dashboard_repost.html`.
- Contains: ANSI color helpers in `bot_v1.py`, text status/report functions in `bot_v2.py`, and Chart.js dashboard rendering in `sim_dashboard_repost.html:157-300`.
- Depends on: Persisted JSON state and market records.
- Used by: CLI users and browser users.
## Data Flow
- Treat process state as JSON documents on disk, not as in-memory services or database records.
- Use one summary state file for bankroll counters (`simulation.json` in `bot_v1.py`, `data/state.json` in `bot_v2.py`) and one file per market in `data/markets/*.json` through `market_path()` in `bot_v2.py:348-359`.
- Keep calibration state in `data/calibration.json` and refresh it via `run_calibration()` in `bot_v2.py:140-168`.
## Key Abstractions
- Purpose: Represent one city/date market lifecycle with forecast history, price history, optional position, and final resolution.
- Examples: `bot_v2.py:370-389`, `bot_v2.py:477-691`, `bot_v2.py:697-739`.
- Pattern: Plain Python dictionary persisted to `data/markets/{city}_{date}.json`.
- Purpose: Represent one simulated trade with entry price, share count, stop state, and close metadata.
- Examples: `bot_v1.py:395-404`, `bot_v2.py:631-653`, `bot_v2.py:542-599`, `bot_v2.py:925-943`.
- Pattern: Embedded dictionary nested under state or market records.
- Purpose: Freeze what each forecast source said at a specific timestamp for one target date.
- Examples: `bot_v2.py:421-441`, `bot_v2.py:516-528`.
- Pattern: Timestamped dictionary appended to `forecast_snapshots`.
- Purpose: Normalize one Polymarket outcome into numeric bounds plus price and liquidity fields.
- Examples: `bot_v2.py:487-514`, `bot_v1.py:342-359`.
- Pattern: Parsed dictionary with `range`, `bid`, `ask`, `price`, `spread`, and `volume`.
- Purpose: Track bankroll-level counters across runs.
- Examples: `bot_v1.py:89-107`, `bot_v2.py:395-408`.
- Pattern: JSON-backed summary document.
## Entry Points
- Location: `bot_v1.py:442-454`
- Triggers: `python bot_v1.py`, `python bot_v1.py --live`, `python bot_v1.py --positions`, `python bot_v1.py --reset`
- Responsibilities: Select one-shot scan mode, show positions, or reset the simulation file.
- Location: `bot_v2.py:1017-1028`
- Triggers: `python bot_v2.py`, `python bot_v2.py status`, `python bot_v2.py report`
- Responsibilities: Start the long-running trading loop or print persisted summaries.
- Location: `sim_dashboard_repost.html:149-300`
- Triggers: Opening the HTML file over a local HTTP server.
- Responsibilities: Poll `simulation.json`, render live stats, and visualize open positions and trade history.
## Error Handling
- Return empty dictionaries or `None` on upstream failures, for example `get_hrrr()` in `bot_v2.py:202-228`, `get_market_price()` in `bot_v2.py:306-312`, and `get_polymarket_event()` in both scripts.
- Continue processing the remaining cities or markets after per-call failures, for example `scan_and_update()` in `bot_v2.py:458-464` and `run_loop()` in `bot_v2.py:986-993`.
- Use broad exception handling for external requests and parsing, for example `bot_v1.py:131-157`, `bot_v2.py:187-200`, and `bot_v2.py:657-675`.
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
