# Architecture

**Analysis Date:** 2026-04-17

## Pattern Overview

**Overall:** Flat script-based architecture with function-grouped sections, synchronous API orchestration, and file-backed persistence.

**Key Characteristics:**
- Keep executable logic in top-level Python entrypoint files: `bot_v1.py` and `bot_v2.py`.
- Group behavior by section comments inside each script instead of splitting into packages or modules, for example `# CONFIG`, `# FORECASTS`, `# POLYMARKET`, `# STATE`, and `# CORE LOGIC` in `bot_v2.py`.
- Persist runtime state to JSON files on disk instead of a database, using `simulation.json` in `bot_v1.py` and `data/state.json`, `data/calibration.json`, and `data/markets/*.json` in `bot_v2.py`.

## Layers

**CLI / Entry Layer:**
- Purpose: Parse command selection and start the requested execution mode.
- Location: `bot_v1.py:442`, `bot_v2.py:1017`, `sim_dashboard_repost.html:149`.
- Contains: argparse-based CLI in `bot_v1.py`, argv command dispatch in `bot_v2.py`, browser polling logic in `sim_dashboard_repost.html`.
- Depends on: Core orchestration functions such as `run()` in `bot_v1.py:245`, `run_loop()` in `bot_v2.py:952`, and `loadData()` in `sim_dashboard_repost.html:237`.
- Used by: Shell execution (`python bot_v1.py`, `python bot_v2.py`) and browser execution of `sim_dashboard_repost.html`.

**Configuration Layer:**
- Purpose: Load thresholds, bankroll settings, scan intervals, and API configuration.
- Location: `config.json`, `bot_v1.py:23-31`, `bot_v2.py:28-52`.
- Contains: Static JSON config file plus module-level constants derived from `_cfg`.
- Depends on: Local file access through `open()` in `bot_v1.py:23` and `open(..., encoding="utf-8")` in `bot_v2.py:28`.
- Used by: All downstream logic, especially position sizing, filtering, scan cadence, and Visual Crossing access.

**Domain Data Layer:**
- Purpose: Define supported cities, station mappings, timezones, and month naming for market slug construction.
- Location: `bot_v1.py:34-63`, `bot_v2.py:54-91`.
- Contains: `LOCATIONS`, `NWS_ENDPOINTS`, `STATION_IDS`, `TIMEZONES`, `MONTHS`, and active location selection in `bot_v1.py:59-60`.
- Depends on: Hard-coded dictionaries embedded in the scripts.
- Used by: Forecast fetchers, Polymarket lookup, reporting, and market record creation.

**Forecast / External Data Layer:**
- Purpose: Pull weather forecasts and observations from external services.
- Location: `bot_v1.py:119-159`, `bot_v2.py:174-266`.
- Contains: `get_forecast()` in `bot_v1.py`, plus `get_ecmwf()`, `get_hrrr()`, `get_metar()`, and `get_actual_temp()` in `bot_v2.py`.
- Depends on: `requests.get(...)`, `LOCATIONS`, `TIMEZONES`, and API-specific URL construction.
- Used by: Snapshot generation in `bot_v2.py:414-441` and market scanning in `bot_v1.py:308-327` / `bot_v2.py:458-540`.

**Market Access Layer:**
- Purpose: Read Polymarket event and market pricing data and translate text buckets into numeric ranges.
- Location: `bot_v1.py:165-204`, `bot_v2.py:268-341`.
- Contains: `get_polymarket_event()`, `get_market_price()`, `check_market_resolved()`, `parse_temp_range()`, `hours_until_resolution()` / `hours_to_resolution()`, and `in_bucket()`.
- Depends on: Polymarket Gamma endpoints and regular-expression parsing.
- Used by: Entry selection, exit management, auto-resolution, and reporting.

**Persistence Layer:**
- Purpose: Save and reload simulation state, per-market history, and calibration data.
- Location: `bot_v1.py:87-113`, `bot_v2.py:127-168`, `bot_v2.py:348-408`.
- Contains: `load_sim()` / `save_sim()` in `bot_v1.py`, and `load_cal()`, `run_calibration()`, `market_path()`, `load_market()`, `save_market()`, `load_all_markets()`, `load_state()`, `save_state()` in `bot_v2.py`.
- Depends on: Local JSON files under project root and runtime-created `data/` directories via `Path("data")` in `bot_v2.py:47-52`.
- Used by: All long-running behavior, reporting, and dashboard data consumption.

**Strategy / Orchestration Layer:**
- Purpose: Combine forecasts, market data, filters, sizing, and position lifecycle rules.
- Location: `bot_v1.py:245-454`, `bot_v2.py:414-753`, `bot_v2.py:862-1012`.
- Contains: One-pass scan in `run()` for v1, full-cycle orchestration in `scan_and_update()`, quick monitoring in `monitor_positions()`, and continuous scheduling in `run_loop()` for v2.
- Depends on: Every lower layer.
- Used by: CLI commands and status/report commands.

**Presentation Layer:**
- Purpose: Render terminal reports and browser-based dashboards.
- Location: `bot_v1.py:69-81`, `bot_v1.py:210-239`, `bot_v2.py:759-854`, `sim_dashboard_repost.html`.
- Contains: ANSI color helpers in `bot_v1.py`, text status/report functions in `bot_v2.py`, and Chart.js dashboard rendering in `sim_dashboard_repost.html:157-300`.
- Depends on: Persisted JSON state and market records.
- Used by: CLI users and browser users.

## Data Flow

**v1 scan-to-trade flow:**

1. `bot_v1.py:442-454` dispatches CLI options into `run()`, `show_positions()`, or `reset_sim()`.
2. `run()` in `bot_v1.py:245-327` loads `simulation.json` through `load_sim()` and fetches forecast data per active city using `get_forecast()`.
3. `run()` in `bot_v1.py:329-370` resolves the target Polymarket event with `get_polymarket_event()` and matches one bucket using `parse_temp_range()`.
4. `run()` in `bot_v1.py:372-417` applies threshold filters and optionally opens a simulated position in memory.
5. `run()` in `bot_v1.py:420-425` writes the updated state back to `simulation.json` through `save_sim()`.

**v2 full-cycle trading flow:**

1. `bot_v2.py:1017-1028` dispatches `run`, `status`, or `report` commands.
2. `run_loop()` in `bot_v2.py:952-1012` alternates between hourly `scan_and_update()` calls and 10-minute `monitor_positions()` calls.
3. `scan_and_update()` in `bot_v2.py:443-540` builds a four-day date horizon, fetches forecast snapshots with `take_forecast_snapshot()`, loads or creates market files with `load_market()` / `new_market()`, and stores `forecast_snapshots` plus `market_snapshots`.
4. `scan_and_update()` in `bot_v2.py:542-685` manages open positions, checks stop/trailing rules, computes probability/EV/Kelly on the matched bucket, and opens a position when all filters pass.
5. `scan_and_update()` in `bot_v2.py:696-753` checks Polymarket closure through `check_market_resolved()`, settles winning or losing positions, updates state, and reruns calibration when enough resolved markets exist.

**Dashboard read flow:**

1. `sim_dashboard_repost.html:237-243` polls `simulation.json` via `fetch()` every 10 seconds.
2. `sim_dashboard_repost.html:247-286` derives balance, PnL, open positions, trade list, and chart history from the JSON payload.
3. `sim_dashboard_repost.html:288-300` falls back to an instructional offline state when the file cannot be fetched over HTTP.

**State Management:**
- Treat process state as JSON documents on disk, not as in-memory services or database records.
- Use one summary state file for bankroll counters (`simulation.json` in `bot_v1.py`, `data/state.json` in `bot_v2.py`) and one file per market in `data/markets/*.json` through `market_path()` in `bot_v2.py:348-359`.
- Keep calibration state in `data/calibration.json` and refresh it via `run_calibration()` in `bot_v2.py:140-168`.

## Key Abstractions

**Market Record:**
- Purpose: Represent one city/date market lifecycle with forecast history, price history, optional position, and final resolution.
- Examples: `bot_v2.py:370-389`, `bot_v2.py:477-691`, `bot_v2.py:697-739`.
- Pattern: Plain Python dictionary persisted to `data/markets/{city}_{date}.json`.

**Position Object:**
- Purpose: Represent one simulated trade with entry price, share count, stop state, and close metadata.
- Examples: `bot_v1.py:395-404`, `bot_v2.py:631-653`, `bot_v2.py:542-599`, `bot_v2.py:925-943`.
- Pattern: Embedded dictionary nested under state or market records.

**Forecast Snapshot:**
- Purpose: Freeze what each forecast source said at a specific timestamp for one target date.
- Examples: `bot_v2.py:421-441`, `bot_v2.py:516-528`.
- Pattern: Timestamped dictionary appended to `forecast_snapshots`.

**Outcome Bucket:**
- Purpose: Normalize one Polymarket outcome into numeric bounds plus price and liquidity fields.
- Examples: `bot_v2.py:487-514`, `bot_v1.py:342-359`.
- Pattern: Parsed dictionary with `range`, `bid`, `ask`, `price`, `spread`, and `volume`.

**State Snapshot:**
- Purpose: Track bankroll-level counters across runs.
- Examples: `bot_v1.py:89-107`, `bot_v2.py:395-408`.
- Pattern: JSON-backed summary document.

## Entry Points

**Base bot CLI:**
- Location: `bot_v1.py:442-454`
- Triggers: `python bot_v1.py`, `python bot_v1.py --live`, `python bot_v1.py --positions`, `python bot_v1.py --reset`
- Responsibilities: Select one-shot scan mode, show positions, or reset the simulation file.

**Full bot CLI:**
- Location: `bot_v2.py:1017-1028`
- Triggers: `python bot_v2.py`, `python bot_v2.py status`, `python bot_v2.py report`
- Responsibilities: Start the long-running trading loop or print persisted summaries.

**Browser dashboard:**
- Location: `sim_dashboard_repost.html:149-300`
- Triggers: Opening the HTML file over a local HTTP server.
- Responsibilities: Poll `simulation.json`, render live stats, and visualize open positions and trade history.

## Error Handling

**Strategy:** Local try/except guards around network and file operations, with fallback defaults and console logging instead of propagated exceptions.

**Patterns:**
- Return empty dictionaries or `None` on upstream failures, for example `get_hrrr()` in `bot_v2.py:202-228`, `get_market_price()` in `bot_v2.py:306-312`, and `get_polymarket_event()` in both scripts.
- Continue processing the remaining cities or markets after per-call failures, for example `scan_and_update()` in `bot_v2.py:458-464` and `run_loop()` in `bot_v2.py:986-993`.
- Use broad exception handling for external requests and parsing, for example `bot_v1.py:131-157`, `bot_v2.py:187-200`, and `bot_v2.py:657-675`.

## Cross-Cutting Concerns

**Logging:** Terminal-first logging with `print()` everywhere and ANSI helper wrappers in `bot_v1.py:69-81`; `bot_v2.py` prints lifecycle tags such as `[BUY]`, `[SKIP]`, `[WIN]`, and `[TRAILING]` directly.

**Validation:** Filter-driven validation inside trading orchestration rather than dedicated validator modules; examples include volume, EV, slippage, price, horizon, and bucket checks in `bot_v2.py:602-677` and threshold checks in `bot_v1.py:338-390`.

**Authentication:** API access is mostly anonymous; only Visual Crossing uses a configured key via `VC_KEY` in `bot_v2.py:42` and `get_actual_temp()` in `bot_v2.py:248-266`.

---

*Architecture analysis: 2026-04-17*
