# Codebase Concerns

**Analysis Date:** 2026-04-17

## Tech Debt

**Monolithic core bot implementation:**
- Issue: Trading logic, API access, calibration, persistence, reporting, and CLI all live inside `bot_v2.py`, which is a 1028-line single-file script. The older `bot_v1.py` keeps a second copy of similar market parsing and state-management logic.
- Files: `bot_v2.py`, `bot_v1.py`
- Impact: Small behavior changes require editing multiple distant sections, make regressions easy to introduce, and keep v1/v2 logic drifting apart.
- Fix approach: Split `bot_v2.py` into modules for forecast clients, Polymarket client, strategy, persistence, reporting, and CLI; either delete `bot_v1.py` or clearly freeze it as archival example code.

**Configuration and filesystem are hard-wired to the current working directory:**
- Issue: Both scripts load config with `open("config.json")`, and `bot_v2.py` writes state directly under relative paths like `Path("data")`, `data/state.json`, and `data/markets/*.json`.
- Files: `bot_v1.py`, `bot_v2.py`
- Impact: Running the bot from another directory, importing it into other Python code, or packaging it as a service can fail immediately or write state into the wrong location.
- Fix approach: Resolve paths from `Path(__file__).resolve().parent`, inject config/state paths through CLI options, and isolate I/O behind a persistence layer.

**Persistence is flat-file JSON with no atomic writes or recovery path:**
- Issue: Market and state records are written directly with `write_text()` and `json.dump()` without temp files, locking, or corruption handling.
- Files: `bot_v1.py`, `bot_v2.py`
- Impact: Interruptions during writes can leave `simulation.json`, `data/state.json`, or `data/markets/*.json` partially written and unreadable.
- Fix approach: Use atomic write-then-rename behavior, add validation on load, and move state to SQLite if the bot is expected to run continuously.

## Known Bugs

**Calibration pipeline cannot produce usable updates:**
- Symptoms: Self-calibration never has valid resolved inputs, and sigma values in `data/calibration.json` do not reflect actual forecast error learning.
- Files: `bot_v2.py:140-168`, `bot_v2.py:516-528`, `bot_v2.py:746-751`
- Trigger: `run_calibration()` filters on `m.get("resolved")` even though market records use `status == "resolved"`, then looks for snapshot keys `source` and `temp` that are never written to `forecast_snapshots`.
- Workaround: None inside the current code path; calibration data must be repaired manually or the function must be fixed.

**Actual resolved temperature is never populated:**
- Symptoms: Reports do not show the real settled temperature, and calibration lacks ground-truth values.
- Files: `bot_v2.py:248-266`, `bot_v2.py:370-389`, `bot_v2.py:696-739`, `bot_v2.py:851`
- Trigger: `get_actual_temp()` exists but is never called during the resolution flow, so `actual_temp` stays `None` for every market record.
- Workaround: None in runtime; the only option is manual backfill of market JSON files after resolution.

**Win/loss statistics ignore early exits:**
- Symptoms: `status` output can show closed profitable or losing trades while `wins` / `losses` counters remain unchanged.
- Files: `bot_v2.py:562-572`, `bot_v2.py:591-599`, `bot_v2.py:925-947`, `bot_v2.py:730-733`, `bot_v2.py:759-809`
- Trigger: Stop-loss, trailing-stop, take-profit, and forecast-change exits close positions and update balance, but only the auto-resolution branch increments `state["wins"]` and `state["losses"]`.
- Workaround: Derive performance from per-market PnL in `data/markets/*.json` instead of the summary counters.

**README usage points to a non-existent entrypoint:**
- Symptoms: Setup instructions tell operators to run `python weatherbet.py ...`, but the repository only contains `bot_v2.py` and `bot_v1.py`.
- Files: `README.md:16-25`, `README.md:95-97`, `bot_v2.py`
- Trigger: Following the README exactly on a fresh clone.
- Workaround: Run `python bot_v2.py`, `python bot_v2.py status`, or `python bot_v2.py report` instead.

## Security Considerations

**API key is stored in tracked plaintext config:**
- Risk: `config.json` contains `vc_key`, and `.gitignore` ignores `.env` files but does not ignore `config.json`. Replacing the placeholder with a real key makes accidental secret commits likely.
- Files: `config.json`, `.gitignore`
- Current mitigation: The committed sample currently uses a placeholder value rather than a real credential.
- Recommendations: Move secrets to environment variables, load them at runtime, and either ignore local config overrides or provide a separate `config.example.json` template.

**Remote API responses are trusted without status or schema validation:**
- Risk: The bot calls Open-Meteo, Aviation Weather, Visual Crossing, and Polymarket, then immediately parses JSON and uses fields for trading decisions. Most call sites do not use `raise_for_status()` or strict schema checks.
- Files: `bot_v1.py:119-176`, `bot_v2.py:174-266`, `bot_v2.py:268-313`, `bot_v2.py:656-675`, `bot_v2.py:877-886`
- Current mitigation: Broad `try/except` blocks prevent crashes in many places.
- Recommendations: Validate HTTP status codes, reject malformed payloads explicitly, log structured errors, and fail closed when required pricing fields are missing.

## Performance Bottlenecks

**Full scans are highly serial and network-bound:**
- Problem: `scan_and_update()` loops through all 20 cities and up to 4 dates each, performs blocking HTTP requests for forecasts and markets, and inserts deliberate sleeps between calls.
- Files: `bot_v2.py:414-441`, `bot_v2.py:443-753`
- Cause: The implementation uses plain `requests.get()` everywhere, re-fetches event/market data per market, and sleeps `0.3s`, `0.1s`, and `0.3s` in hot paths.
- Improvement path: Reuse a session, batch or cache Polymarket lookups, remove fixed sleeps where unnecessary, and move I/O to async or threaded workers.

**Open-position monitoring scales linearly with the number of trades:**
- Problem: Every monitor pass fetches Polymarket data one market at a time for each open position.
- Files: `bot_v2.py:862-949`
- Cause: `monitor_positions()` performs a separate `requests.get()` per position and falls back to stale cached prices if the call fails.
- Improvement path: Batch market queries if the API permits it, cache best bid data across monitor cycles, or centralize quote refresh in a shared market-data store.

**State reloads and directory scans re-read the full market set repeatedly:**
- Problem: The bot repeatedly scans `data/markets/*.json` and loads every file into memory to produce status, reports, auto-resolution input, and calibration input.
- Files: `bot_v2.py:361-368`, `bot_v2.py:696-751`, `bot_v2.py:759-854`, `bot_v2.py:862-949`
- Cause: Flat-file persistence with `load_all_markets()` forces O(number of market files) work for operations that often need only open or recently changed records.
- Improvement path: Index market state, persist summarized metadata, or move to SQLite so open/resolved subsets can be queried directly.

## Fragile Areas

**Bucket matching depends on Polymarket question wording staying stable:**
- Files: `bot_v1.py:182-194`, `bot_v2.py:314-329`, `bot_v2.py:487-513`, `bot_v2.py:606-614`
- Why fragile: Range extraction relies on regular expressions over market question text. A copy change like different separators, symbols, or wording can silently prevent matching or attach the wrong bucket.
- Safe modification: Add fixture-driven parsing tests for representative market strings before touching `parse_temp_range()` or the bucket-selection logic.
- Test coverage: No automated parser tests are present anywhere in the repository.

**Price semantics are inconsistent across the codebase:**
- Files: `bot_v1.py:349-350`, `bot_v2.py:497-510`, `bot_v2.py:623-629`, `bot_v2.py:656-673`
- Why fragile: `bot_v1.py` treats `outcomePrices[0]` as the YES price, while `bot_v2.py` initially interprets `outcomePrices[0]` / `[1]` as bid/ask before later replacing them with `bestBid` / `bestAsk` from a second API call. This mixes outcome prices with order-book prices inside filtering, EV calculation, spread checks, and market snapshots.
- Safe modification: Normalize one explicit market-price model, document which API fields represent YES price versus executable bid/ask, and update all filters to use the same data source.
- Test coverage: No regression tests exercise pricing interpretation or EV calculations.

**Long-running process state can drift silently behind broad exception handling:**
- Files: `bot_v1.py:131-176`, `bot_v1.py:220-276`, `bot_v2.py:187-200`, `bot_v2.py:215-228`, `bot_v2.py:273-289`, `bot_v2.py:297-304`, `bot_v2.py:879-886`, `bot_v2.py:986-1003`
- Why fragile: Many network and parsing failures are swallowed or reduced to a single print line, then the bot continues with partial data.
- Safe modification: Replace broad exception swallowing with targeted exceptions, structured logs, and explicit skip reasons recorded in state.
- Test coverage: No failure-injection tests verify behavior during partial API outages.

## Scaling Limits

**Market storage and reporting are limited by local JSON fan-out:**
- Current capacity: One JSON file per city/date under `data/markets/{city}_{date}.json`, with every report and calibration pass reloading the full directory.
- Limit: As historical market files accumulate, startup, status, reporting, and calibration cost grows linearly and eventually turns routine operations into full-history scans.
- Scaling path: Store markets in SQLite/Postgres with indexes on `status`, `city`, and `date`, and archive old snapshots separately from hot state.

## Dependencies at Risk

**Unpinned runtime dependency footprint:**
- Risk: The repository has no `pyproject.toml`, `requirements.txt`, or lockfile, even though both scripts depend on `requests`.
- Impact: Fresh environments can pull different `requests` versions or miss the dependency entirely, causing inconsistent behavior across machines.
- Migration plan: Add a minimal `pyproject.toml` or `requirements.txt` with pinned versions and a reproducible install command.

**Strategy depends on free/public external APIs with no abstraction boundary:**
- Risk: Open-Meteo, Aviation Weather, Polymarket Gamma, and Visual Crossing are called directly from the trading loop.
- Impact: API field changes, rate limits, downtime, or auth changes immediately affect trading decisions and reporting.
- Migration plan: Wrap each provider behind a client interface, add cached fallback behavior, and record provider-specific health metrics.

## Missing Critical Features

**No automated validation before trading logic changes:**
- Problem: The repository contains executable scripts and documentation only; there are no tests, no lint config, no type checks, and no CI entrypoints.
- Blocks: Safe refactors of pricing, resolution, parsing, and calibration logic.

**No startup validation for required runtime configuration:**
- Problem: `bot_v2.py` reads `vc_key` and other thresholds from `config.json`, but there is no explicit startup validation that required keys are present and usable before the infinite loop begins.
- Blocks: Predictable deployment and fast failure when configuration is incomplete or invalid.

## Test Coverage Gaps

**Core strategy logic is untested:**
- What's not tested: `bucket_prob()`, `calc_ev()`, `calc_kelly()`, `in_bucket()`, and the buy/close decision branches in `scan_and_update()`.
- Files: `bot_v2.py:97-121`, `bot_v2.py:542-685`
- Risk: Small edits to pricing or probability math can change position entry behavior without detection.
- Priority: High

**Parsing and resolution workflows are untested:**
- What's not tested: `parse_temp_range()`, `hours_to_resolution()`, `check_market_resolved()`, and the auto-resolution branch.
- Files: `bot_v1.py:182-204`, `bot_v2.py:268-341`, `bot_v2.py:696-739`
- Risk: Upstream API or market-copy changes can silently stop market matching or mis-score winners.
- Priority: High

**Persistence and reporting paths are untested:**
- What's not tested: `load_state()`, `save_state()`, `load_market()`, `save_market()`, `load_all_markets()`, `print_status()`, and `print_report()`.
- Files: `bot_v1.py:87-113`, `bot_v2.py:348-408`, `bot_v2.py:759-854`
- Risk: Corrupted JSON, schema drift, or state-counter bugs can go unnoticed until after long bot runs.
- Priority: Medium

---

*Concerns audit: 2026-04-17*
