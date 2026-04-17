# External Integrations

**Analysis Date:** 2026-04-17

## APIs & External Services

**Weather Forecast APIs:**
- Open-Meteo - daily max temperature forecasts for ECMWF and US short-horizon model data
  - SDK/Client: `requests` in `bot_v2.py:174-228`
  - Auth: None
- US National Weather Service (weather.gov) - hourly forecast and station observations for the v1 bot
  - SDK/Client: `requests` in `bot_v1.py:43-51` and `bot_v1.py:132-157`
  - Auth: None
- Aviation Weather / METAR - current airport observations in the v2 bot
  - SDK/Client: `requests` in `bot_v2.py:230-246`
  - Auth: None
- Visual Crossing - historical actual temperatures for market resolution
  - SDK/Client: `requests` in `bot_v2.py:248-266`
  - Auth: `vc_key` from `config.json:12`, loaded in `bot_v2.py:42`

**Trading/Market APIs:**
- Polymarket Gamma API - event lookup, market pricing, orderbook-derived bid/ask reads, and resolution status
  - SDK/Client: `requests` in `bot_v1.py:165-176`, `bot_v1.py:221-223`, `bot_v1.py:271-273`, `bot_v2.py:268-312`, `bot_v2.py:658-675`, and `bot_v2.py:877-885`
  - Auth: None detected

**Browser/CDN Assets:**
- Google Fonts - dashboard font delivery in `sim_dashboard_repost.html:6`
  - SDK/Client: browser `<link>` tag
  - Auth: None
- cdnjs / Chart.js - dashboard chart library in `sim_dashboard_repost.html:7`
  - SDK/Client: browser `<script>` tag
  - Auth: None

## Data Storage

**Databases:**
- None
  - Connection: Not applicable
  - Client: Not applicable

**File Storage:**
- Local filesystem only
  - `data/state.json` for portfolio state in `bot_v2.py:49`, `bot_v2.py:395-408`
  - `data/calibration.json` for model calibration in `bot_v2.py:52`, `bot_v2.py:129-168`
  - `data/markets/*.json` for per-market records in `bot_v2.py:50-51`, `bot_v2.py:348-389`
  - `simulation.json` for v1 simulation state in `bot_v1.py:87`, `bot_v1.py:89-107`

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- No user authentication provider detected
  - Implementation: The bot runs as local scripts without login flows; external services are mostly anonymous requests, with only Visual Crossing using an API key from `config.json` in `bot_v2.py:42` and `config.json:12`

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- Console logging via `print()` and helper wrappers in `bot_v1.py:69-81`, `bot_v1.py:245-454`, and `bot_v2.py:166-167`, `bot_v2.py:456-1010`
- Local dashboard reads simulation JSON and renders status in `sim_dashboard_repost.html:237-300`

## CI/CD & Deployment

**Hosting:**
- Not detected; intended runtime is a local Python process started manually from `README.md:93-98` and `bot_v2.py:1017-1028`

**CI Pipeline:**
- None detected (`.github/` and pipeline YAML files are not present in the repository root)

## Environment Configuration

**Required env vars:**
- None detected; configuration is file-based rather than environment-based

**Secrets location:**
- `config.json` stores the Visual Crossing key placeholder and other runtime settings in `config.json:1-14`
- `.env` is ignored by `.gitignore:137-145`, but no `.env` file is present in the repository root

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-04-17*
