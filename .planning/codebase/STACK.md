# Technology Stack

**Analysis Date:** 2026-04-17

## Languages

**Primary:**
- Python 3 (version not pinned) - CLI bot logic in `bot_v1.py` and `bot_v2.py`

**Secondary:**
- JSON - runtime configuration in `config.json` and persisted bot state in files declared in `bot_v2.py:47-52`
- HTML/CSS/JavaScript - local simulation dashboard in `sim_dashboard_repost.html`

## Runtime

**Environment:**
- Python 3 via script shebangs in `bot_v1.py:1` and `bot_v2.py:1`
- Browser runtime for the optional dashboard in `sim_dashboard_repost.html`

**Package Manager:**
- pip implied by installation instructions in `README.md:64-69`
- Lockfile: missing (`requirements.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock`, and `uv.lock` are not present in the repository root)

## Frameworks

**Core:**
- Standard library modules (`json`, `math`, `time`, `pathlib`, `datetime`, `argparse`, `sys`, `re`) - application logic in `bot_v1.py` and `bot_v2.py`
- `requests` (version not pinned) - all HTTP integrations in `bot_v1.py:16`, `bot_v2.py:20`, and installation guidance in `README.md:64-69`

**Testing:**
- Not detected - no test framework config or test files are present at the repository root

**Build/Dev:**
- No dedicated build system detected - scripts run directly with `python` from `bot_v1.py` and `bot_v2.py`
- Chart.js 4.4.0 via CDN - dashboard chart rendering in `sim_dashboard_repost.html:7`

## Key Dependencies

**Critical:**
- `requests` - required for every external API call to weather sources, Polymarket, and Visual Crossing in `bot_v1.py:133-170` and `bot_v2.py:189-308`
- Python standard library `pathlib.Path` - manages persistent data directories and files in `bot_v2.py:22` and `bot_v2.py:47-52`

**Infrastructure:**
- Local filesystem - persistent state stored under `data/` in `bot_v2.py:47-52`, `bot_v2.py:348-408`, and described in `README.md:102-110`
- Chart.js CDN - optional local dashboard visualization in `sim_dashboard_repost.html:7` and `sim_dashboard_repost.html:157-162`
- Google Fonts CDN - dashboard typography in `sim_dashboard_repost.html:6`

## Configuration

**Environment:**
- Runtime settings are loaded from `config.json` in `bot_v1.py:23-29` and `bot_v2.py:28-42`
- Required config keys currently used by `bot_v2.py` are `balance`, `max_bet`, `min_ev`, `max_price`, `min_volume`, `min_hours`, `max_hours`, `kelly_fraction`, `max_slippage`, `scan_interval`, `calibration_min`, and `vc_key` from `config.json:1-14`
- `vc_key` is a plain JSON config value, not an environment variable, in `config.json:12` and `bot_v2.py:42`

**Build:**
- No build config files detected
- Runtime behavior is controlled directly inside script constants and CLI entrypoints in `bot_v1.py:245-454` and `bot_v2.py:952-1028`

## Platform Requirements

**Development:**
- Python 3 with the `requests` package installed, per `README.md:64-69`
- Writable local filesystem for `data/state.json`, `data/calibration.json`, and `data/markets/*.json` created by `bot_v2.py:47-52` and `bot_v2.py:348-408`
- Optional local HTTP server for the dashboard because `sim_dashboard_repost.html` fetches JSON over HTTP in `sim_dashboard_repost.html:237-300`

**Production:**
- Local long-running Python process using `run_loop()` in `bot_v2.py:952-1012`
- No container, process manager, cloud deployment config, or CI/CD pipeline detected in the repository root

---

*Stack analysis: 2026-04-17*
