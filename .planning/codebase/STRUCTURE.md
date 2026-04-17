# Codebase Structure

**Analysis Date:** 2026-04-17

## Directory Layout

```text
weatherbot/
├── .planning/                 # Generated planning artifacts for GSD workflows
│   └── codebase/              # Architecture/structure reference documents
├── .gitignore                 # Ignore rules for Python, virtualenvs, caches, and local secrets
├── README.md                  # Project overview, setup, usage, and API summary
├── bot_v1.py                  # Base one-shot trading bot with simple simulation storage
├── bot_v2.py                  # Full trading bot with continuous loop and JSON persistence
├── config.json                # Runtime configuration loaded by both Python bots
├── LICENSE                    # Repository license
└── sim_dashboard_repost.html  # Static dashboard that reads simulation JSON over HTTP
```

## Directory Purposes

**Project root (`/home/xeron/Coding/weatherbot`):**
- Purpose: Keep all source files, configuration, and static assets in a single flat directory.
- Contains: Python executables, one HTML dashboard, project docs, and config.
- Key files: `bot_v1.py`, `bot_v2.py`, `config.json`, `README.md`, `sim_dashboard_repost.html`.

**Planning docs (`/home/xeron/Coding/weatherbot/.planning/codebase`):**
- Purpose: Store generated codebase analysis artifacts.
- Contains: Markdown files such as `ARCHITECTURE.md` and `STRUCTURE.md`.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

**Runtime data directory (`/home/xeron/Coding/weatherbot/data`):**
- Purpose: Hold persisted state for the full bot when `bot_v2.py` runs.
- Contains: `state.json`, `calibration.json`, and `markets/*.json` created by `Path("data")` and `MARKETS_DIR.mkdir(...)` in `bot_v2.py:47-52`.
- Key files: `data/state.json`, `data/calibration.json`, `data/markets/{city}_{date}.json`.

**Runtime market subdirectory (`/home/xeron/Coding/weatherbot/data/markets`):**
- Purpose: Store one JSON record per tracked city/date market.
- Contains: Files created by `market_path()` in `bot_v2.py:348-349`.
- Key files: `data/markets/nyc_YYYY-MM-DD.json` style records.

## Key File Locations

**Entry Points:**
- `bot_v1.py`: Base bot CLI with `argparse` and one-pass scan execution.
- `bot_v2.py`: Full bot CLI with `run`, `status`, and `report` command dispatch.
- `sim_dashboard_repost.html`: Standalone browser UI that polls `simulation.json`.

**Configuration:**
- `config.json`: Shared runtime config for bankroll, filters, cadence, and API key fields.
- `.gitignore`: Ignore policy for Python caches, virtualenvs, `.env`, `.pypirc`, and tooling artifacts.

**Core Logic:**
- `bot_v1.py:119-204`: v1 forecast retrieval, Polymarket lookup, and parsing helpers.
- `bot_v1.py:245-425`: v1 trade scan, position opening, exits, and simulation persistence.
- `bot_v2.py:174-341`: v2 forecast and Polymarket integration helpers.
- `bot_v2.py:414-753`: v2 snapshotting, market updates, entry logic, exit logic, and settlement.
- `bot_v2.py:862-1012`: v2 monitoring loop and scheduler.

**Testing:**
- Not present in the current repository tree. No `tests/`, `test_*.py`, or `*_test.py` files were detected under `/home/xeron/Coding/weatherbot`.

## Naming Conventions

**Files:**
- Root-level executable scripts use snake_case plus version suffixes: `bot_v1.py`, `bot_v2.py`.
- Config and documentation use conventional lowercase names: `config.json`, `README.md`.
- Generated market files use `{city}_{date}.json` via `market_path()` in `bot_v2.py:348-349`.

**Directories:**
- Top-level hidden operational directories use dot-prefixed names: `.git/`, `.planning/`.
- Runtime storage directories use short lowercase nouns: `data/`, `data/markets/` in `bot_v2.py:47-52`.

## Where to Add New Code

**New Feature:**
- Primary code: Add new function sections inside `bot_v2.py` when the feature belongs to the full bot runtime, keeping the same sectioned layout used by `# FORECASTS`, `# POLYMARKET`, `# STATE`, and `# CORE LOGIC`.
- Tests: Not applicable in the current layout because no test directory exists. If tests are added later, introduce a dedicated `tests/` directory at project root rather than mixing test code into `bot_v1.py` or `bot_v2.py`.

**New Component/Module:**
- Implementation: The current codebase does not use a package tree, so new modules should be added at project root as separate `.py` files only when the logic clearly outgrows `bot_v2.py`. Otherwise keep related functions in the existing file.

**Utilities:**
- Shared helpers: Place shared pure helpers near existing helper sections in `bot_v2.py`, for example math helpers in `bot_v2.py:97-122`, parsing helpers in `bot_v2.py:314-341`, or persistence helpers in `bot_v2.py:348-408`.

## Special Directories

**`.planning/`:**
- Purpose: Generated planning and mapping artifacts.
- Generated: Yes.
- Committed: Yes, directory exists in the repository root and is intended for checked-in planning docs.

**`.git/`:**
- Purpose: Git repository metadata.
- Generated: Yes.
- Committed: No.

**`data/`:**
- Purpose: Runtime persistence for `bot_v2.py`.
- Generated: Yes, created at startup by `DATA_DIR.mkdir(exist_ok=True)` in `bot_v2.py:48`.
- Committed: Not currently present in the repository tree; treat as runtime output.

**`data/markets/`:**
- Purpose: Per-market JSON storage for forecast, price, and trade history.
- Generated: Yes, created by `MARKETS_DIR.mkdir(exist_ok=True)` in `bot_v2.py:51`.
- Committed: Not currently present in the repository tree; treat as runtime output.

## Structure Rules for Future Changes

- Keep executable Python files at project root unless a real package split is introduced.
- Keep configuration in `config.json` and load it at process start, matching `bot_v1.py:23-31` and `bot_v2.py:28-52`.
- Keep browser-only assets as standalone HTML files at project root, following `sim_dashboard_repost.html`.
- Persist long-lived bot state under `data/` and per-market history under `data/markets/`, matching `bot_v2.py:47-52` and `bot_v2.py:348-359`.
- Put new GSD reference documents under `.planning/codebase/`.

---

*Structure analysis: 2026-04-17*
