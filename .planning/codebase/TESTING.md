# Testing Patterns

**Analysis Date:** 2026-04-17

## Test Framework

**Runner:**
- Not detected.
- Config: No `pytest.ini`, `pyproject.toml`, `tox.ini`, `noxfile.py`, `setup.cfg`, `jest.config.*`, or `vitest.config.*` files were found in `/home/xeron/Coding/weatherbot`.

**Assertion Library:**
- Not detected. No `pytest`, `unittest`, `doctest`, or third-party assertion helpers are referenced in `bot_v1.py` or `bot_v2.py`.

**Run Commands:**
```bash
Not applicable              # No repository-defined test runner command found
Not applicable              # No watch mode command found
Not applicable              # No coverage command found
```

## Test File Organization

**Location:**
- No test directories or test modules were detected under `/home/xeron/Coding/weatherbot`.
- No `tests/`, `test_*.py`, or `*_test.py` files are present alongside `bot_v1.py` or `bot_v2.py`.

**Naming:**
- Not applicable in the current repository state.

**Structure:**
```
/home/xeron/Coding/weatherbot/
├── bot_v1.py
├── bot_v2.py
├── config.json
└── .planning/codebase/
```

## Test Structure

**Suite Organization:**
```python
# Not applicable — no test suites were detected in `/home/xeron/Coding/weatherbot`.
# Validation currently happens through executable CLI paths in:
# - `bot_v1.py:442-454`
# - `bot_v2.py:1017-1028`
```

**Patterns:**
- Setup pattern: manual runtime setup through checked-in configuration in `config.json` plus filesystem initialization in `bot_v2.py:47-53`.
- Teardown pattern: no automated teardown; scripts persist JSON state to `simulation.json` in `bot_v1.py` and `data/state.json` / `data/markets/*.json` in `bot_v2.py`.
- Assertion pattern: no explicit assertions. Success/failure is communicated through console output and persisted state updates in `bot_v1.py` and `bot_v2.py`.

## Mocking

**Framework:** Not detected

**Patterns:**
```python
# No mocking framework is used.
# External dependencies are called directly, for example:
# - `requests.get(...)` in `bot_v1.py:133,147,170,222,272,349`
# - `requests.get(...)` in `bot_v2.py:189,217,237,260,274,298,308,659,880`
```

**What to Mock:**
- If tests are added, mock all network boundaries currently invoked directly from `bot_v1.py` and `bot_v2.py`:
  - NWS / weather.gov calls in `bot_v1.py:132-157`
  - Open-Meteo calls in `bot_v2.py:180-200` and `bot_v2.py:208-228`
  - METAR calls in `bot_v2.py:235-246`
  - Polymarket Gamma calls in `bot_v1.py:168-176`, `bot_v2.py:295-312`, `bot_v2.py:659-675`, and `bot_v2.py:880-885`
  - Visual Crossing calls in `bot_v2.py:254-266`
- Mock filesystem persistence when testing state transitions around `simulation.json`, `data/state.json`, `data/calibration.json`, and `data/markets/*.json` used by `load_sim()`, `save_sim()`, `load_state()`, `save_state()`, `load_market()`, and `save_market()`.

**What NOT to Mock:**
- Pure computation helpers in `bot_v2.py` should stay real in tests because they are deterministic and side-effect free: `norm_cdf()`, `bucket_prob()`, `calc_ev()`, `calc_kelly()`, `bet_size()`, `parse_temp_range()`, `hours_to_resolution()`, and `in_bucket()`.
- Parsing and formatting helpers in `bot_v1.py`, such as `parse_temp_range()` and `hours_until_resolution()`, should also be exercised directly.

## Fixtures and Factories

**Test Data:**
```python
# No test fixtures or factories exist.
# The closest production-side data factories are:
# - `load_sim()` default simulation payload in `bot_v1.py:89-104`
# - `new_market()` market record factory in `bot_v2.py:370-389`
# - `load_state()` default account state in `bot_v2.py:395-405`
```

**Location:**
- Not applicable. No fixture directories, factory modules, or canned API payload files are present in `/home/xeron/Coding/weatherbot`.

## Coverage

**Requirements:** None enforced

**View Coverage:**
```bash
Not applicable
```

## Test Types

**Unit Tests:**
- Not used.
- The repository has several good unit-test candidates, especially pure helpers in `bot_v2.py:97-121` and parsing/date logic in `bot_v1.py:182-204` plus `bot_v2.py:314-341`.

**Integration Tests:**
- Not used as standalone test files.
- Current runtime behavior effectively performs live integrations against weather APIs and Polymarket from `bot_v1.py` and `bot_v2.py`, but those checks happen only during manual script execution.

**E2E Tests:**
- Not used.
- The closest end-to-end flow is running `python bot_v1.py`, `python bot_v1.py --positions`, `python bot_v2.py status`, or `python bot_v2.py report` through the CLI entry points in `bot_v1.py:442-454` and `bot_v2.py:1017-1028`.

## Common Patterns

**Async Testing:**
```python
# Not applicable — the codebase is synchronous.
# Delays and polling use `time.sleep(...)` in `bot_v2.py:197,225,461,692,740,988,992,1006`.
```

**Error Testing:**
```python
# No automated error tests exist.
# Error handling currently relies on broad exception recovery, for example:
try:
    data = requests.get(url, timeout=(5, 10)).json()
except Exception as e:
    print(f"  [ECMWF] {city_slug}: {e}")

# Source: `bot_v2.py:187-200`
```

---

*Testing analysis: 2026-04-17*
