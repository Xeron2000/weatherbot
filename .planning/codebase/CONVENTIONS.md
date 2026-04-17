# Coding Conventions

**Analysis Date:** 2026-04-17

## Naming Patterns

**Files:**
- Root-level executable scripts use snake_case versioned filenames: `bot_v1.py`, `bot_v2.py`.
- JSON configuration/state files use lowercase snake_case names: `config.json`, `simulation.json` in `bot_v1.py`, `data/state.json` and `data/calibration.json` in `bot_v2.py`.

**Functions:**
- Use snake_case for all functions and helpers, including I/O, parsing, math, and CLI entry points: `load_sim()` and `show_positions()` in `bot_v1.py`; `get_ecmwf()`, `scan_and_update()`, `print_report()`, and `run_loop()` in `bot_v2.py`.
- Verb-led names are the default for side-effecting functions: `load_state()`, `save_state()`, `take_forecast_snapshot()`, `monitor_positions()` in `bot_v2.py`.

**Variables:**
- Module-level configuration constants use UPPER_SNAKE_CASE: `ENTRY_THRESHOLD`, `EXIT_THRESHOLD`, `SIM_FILE` in `bot_v1.py`; `BALANCE`, `MAX_BET`, `SCAN_INTERVAL`, `MONITOR_INTERVAL` in `bot_v2.py`.
- Local working variables use short snake_case names, often domain-specific abbreviations: `mkt`, `pos`, `pnl`, `rng`, `mid`, `snap` in `bot_v2.py`.
- Private module globals are prefixed with `_`: `_cfg` in both `bot_v1.py` and `bot_v2.py`, `_cal` in `bot_v2.py`.

**Types:**
- Type hints are sparse and selective rather than comprehensive.
- Simple built-in return annotations are used in `bot_v1.py`, such as `load_sim() -> dict`, `get_forecast(city_slug: str) -> dict`, and `hours_until_resolution(event: dict) -> float`.
- `bot_v2.py` mostly omits annotations except for `_cal: dict = {}`.

## Code Style

**Formatting:**
- No formatter config is present: no `pyproject.toml`, `ruff.toml`, `setup.cfg`, `.flake8`, `mypy.ini`, `pytest.ini`, or `tox.ini` were detected in `/home/xeron/Coding/weatherbot`.
- Formatting is hand-maintained inside the scripts `bot_v1.py` and `bot_v2.py`.
- Section dividers use long comment banners with repeated `=` characters, for example `# =============================================================================` throughout `bot_v1.py` and `bot_v2.py`.
- Inline dictionary literals are vertically aligned for readability in large constant maps such as `LOCATIONS` and `TIMEZONES` in `bot_v2.py`.
- Assignment alignment is used for configuration blocks, e.g. `BALANCE          = ...` through `VC_KEY           = ...` in `bot_v2.py:31-42`.

**Linting:**
- No lint configuration is detected in `/home/xeron/Coding/weatherbot`.
- There is no evidence of Ruff, Flake8, Pylint, Black, isort, or mypy configuration files.
- The effective standard is “match the existing file-local style” in `bot_v1.py` and `bot_v2.py`.

## Import Organization

**Order:**
1. Python standard library imports first: `re`, `json`, `argparse`, `sys`, `math`, `time`, `datetime`, `pathlib` in `bot_v1.py` and `bot_v2.py`.
2. Third-party imports after stdlib: `requests` in both `bot_v1.py` and `bot_v2.py`.
3. No local package imports exist; the repository is script-based and keeps all logic inside `bot_v1.py` and `bot_v2.py`.

**Path Aliases:**
- Not used. The code imports only standard library modules and `requests`.

## Error Handling

**Patterns:**
- Use `try`/`except` around almost every network call and file read/write boundary rather than raising domain-specific exceptions.
- Prefer graceful fallback values over hard failures:
  - `load_sim()` in `bot_v1.py` returns a default simulation structure on `FileNotFoundError`.
  - `hours_until_resolution()` in `bot_v1.py` returns `999` on parse failure.
  - `get_market_price()` in `bot_v2.py` returns `None` on request failure.
  - `load_market()` and `load_state()` in `bot_v2.py` return `None` or a default state when persisted files are absent.
- Broad `except Exception` blocks are common for API integrations and runtime loops, for example in `get_forecast()` and `get_polymarket_event()` in `bot_v1.py`, and `get_ecmwf()`, `get_hrrr()`, `get_metar()`, `get_actual_temp()`, `scan_and_update()`, and `run_loop()` in `bot_v2.py`.
- Runtime recovery is usually implemented with logging plus `continue`, `break`, or fallback defaults instead of exception propagation.
- User-visible warnings are emitted inline via `warn()` in `bot_v1.py` and bracketed `print()` messages in `bot_v2.py`.

## Logging

**Framework:** console via `print`

**Patterns:**
- `bot_v1.py` wraps console output in helper functions `ok()`, `warn()`, `info()`, and `skip()` plus ANSI color constants in class `C`.
- `bot_v2.py` prints structured status markers directly, such as `[BUY]`, `[SKIP]`, `[WARN]`, `[STOP]`, `[TRAILING]`, `[WIN]`, and `[LOSS]` in `scan_and_update()` and `monitor_positions()`.
- There is no `logging` module setup, log level abstraction, or log sink configuration in the repository root or in `bot_v1.py`/`bot_v2.py`.

## Comments

**When to Comment:**
- Use comments heavily to separate phases of execution and explain trading rules.
- Major control-flow regions are labeled with banner comments, such as `# CONFIG`, `# FORECASTS`, `# CORE LOGIC`, `# REPORT`, and `# CLI` in `bot_v2.py`.
- Short explanatory comments clarify non-obvious business rules, for example:
  - `# Airport coordinates — match the exact stations Polymarket resolves on` in `bot_v1.py`.
  - `# Best forecast: HRRR for US D+0/D+1, otherwise ECMWF` in `bot_v2.py:429-439`.
  - `# 2-degree buffer — avoid closing on small forecast fluctuations` in `bot_v2.py:579`.

**JSDoc/TSDoc:**
- Not applicable.
- Python docstrings are used selectively for user-facing modules and non-trivial functions, including the module docstrings in `bot_v1.py` and `bot_v2.py`, plus function docstrings such as `get_forecast()` in `bot_v1.py` and `get_actual_temp()` and `monitor_positions()` in `bot_v2.py`.

## Function Design

**Size:**
- Helper functions are small and single-purpose (`calc_ev()` in `bot_v2.py`, `parse_temp_range()` in both scripts).
- Orchestration functions are large and procedural:
  - `run()` in `bot_v1.py` owns exit checks, scan logic, execution, and summary output.
  - `scan_and_update()` in `bot_v2.py` owns forecasting, market matching, entry filters, stop logic, resolution handling, persistence, and recalibration.

**Parameters:**
- Most helpers accept primitive values and domain strings rather than objects or classes, e.g. `get_polymarket_event(city_slug, month, day, year)` and `market_path(city_slug, date_str)`.
- Shared mutable state is often read from module globals instead of being injected, such as `LOCATIONS`, `MAX_BET`, `MARKETS_DIR`, and `_cal` in `bot_v2.py`.

**Return Values:**
- Simple computed values are returned as primitives or plain dictionaries.
- Multi-part state is represented with JSON-serializable dictionaries/lists instead of dataclasses or custom classes, for example market records from `new_market()` in `bot_v2.py` and simulation state from `load_sim()` in `bot_v1.py`.
- Batch/orchestration functions return summary tuples where useful, e.g. `scan_and_update()` returns `(new_pos, closed, resolved)` in `bot_v2.py:753`.

## Module Design

**Exports:**
- There is no package export surface. Both `bot_v1.py` and `bot_v2.py` are standalone executable modules with CLI guards at `bot_v1.py:442-454` and `bot_v2.py:1017-1028`.
- Internal helpers are defined in the same file as the CLI entry point and called directly.

**Barrel Files:**
- Not used.
- The repository does not have a package directory, `__init__.py`, or re-export modules; all executable behavior lives in `bot_v1.py` and `bot_v2.py`.

---

*Convention analysis: 2026-04-17*
