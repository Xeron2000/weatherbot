#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weatherbet.py — Weather Trading Bot for Polymarket
=====================================================
Tracks weather forecasts from 3 sources (ECMWF, HRRR, METAR),
compares with Polymarket markets, paper trades using Kelly criterion.

Usage:
    python weatherbet.py          # main loop
    python weatherbet.py report   # full report
    python weatherbet.py status   # balance and open positions
"""

import re
import sys
import json
import math
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# =============================================================================
# CONFIG
# =============================================================================

with open("config.json", encoding="utf-8") as f:
    _cfg = json.load(f)

BALANCE = _cfg.get("balance", 10000.0)
MIN_VOLUME = _cfg.get("min_volume", 500)
MIN_HOURS = _cfg.get("min_hours", 2.0)
MAX_HOURS = _cfg.get("max_hours", 72.0)
KELLY_FRACTION = _cfg.get("kelly_fraction", 0.25)
MAX_SLIPPAGE = _cfg.get("max_slippage", 0.03)  # max allowed ask-bid spread
SCAN_INTERVAL = _cfg.get("scan_interval", 3600)  # every hour
CALIBRATION_MIN = _cfg.get("calibration_min", 30)
VC_KEY = _cfg.get("vc_key", "")

YES_STRATEGY = _cfg.get(
    "yes_strategy",
    {
        "max_price": 0.25,
        "min_probability": 0.14,
        "min_edge": 0.03,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
        "max_size": 20.0,
        "min_size": 1.0,
    },
)
NO_STRATEGY = _cfg.get(
    "no_strategy",
    {
        "min_price": 0.65,
        "min_probability": 0.70,
        "min_edge": 0.04,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
        "max_size": 20.0,
        "min_size": 1.0,
    },
)


def load_risk_router_config(config_dict):
    router = {
        "yes_budget_pct": 0.30,
        "no_budget_pct": 0.70,
        "yes_leg_cap_pct": 0.30,
        "no_leg_cap_pct": 0.70,
        "global_usage_cap_pct": 0.85,
        "per_market_cap_pct": 0.08,
        "per_city_cap_pct": 0.18,
        "per_date_cap_pct": 0.18,
        "per_event_cap_pct": 0.18,
    }
    raw = config_dict.get("risk_router", {}) or {}
    for key, default in router.items():
        value = raw.get(key, default)
        try:
            value = float(value)
        except Exception:
            value = default
        if value <= 0:
            value = default
        router[key] = round(value, 6)
    return router


RISK_ROUTER = load_risk_router_config(_cfg)


def load_order_policy_config(config_dict):
    policy = {
        "yes_time_in_force": "GTC",
        "no_time_in_force": "GTD",
        "gtd_buffer_hours": 6.0,
        "price_improve_ticks": 1,
        "replace_edge_buffer": 0.02,
        "max_order_hours_open": 72.0,
    }
    raw = config_dict.get("order_policy", {}) or {}
    tif_keys = ["yes_time_in_force", "no_time_in_force"]
    for key in tif_keys:
        value = str(raw.get(key, policy[key]) or policy[key]).upper()
        if value not in {"GTC", "GTD"}:
            value = policy[key]
        policy[key] = value
    float_keys = ["gtd_buffer_hours", "replace_edge_buffer", "max_order_hours_open"]
    for key in float_keys:
        value = raw.get(key, policy[key])
        try:
            value = float(value)
        except Exception:
            value = policy[key]
        if value <= 0:
            value = policy[key]
        policy[key] = round(value, 6)
    value = raw.get("price_improve_ticks", policy["price_improve_ticks"])
    try:
        value = int(value)
    except Exception:
        value = policy["price_improve_ticks"]
    if value < 0:
        value = policy["price_improve_ticks"]
    policy["price_improve_ticks"] = value
    return policy


ORDER_POLICY = load_order_policy_config(_cfg)

MAX_BET = YES_STRATEGY.get("max_size", _cfg.get("max_bet", 20.0))  # compatibility
MIN_EV = _cfg.get("min_ev", 0.10)
MAX_PRICE = YES_STRATEGY.get("max_price", _cfg.get("max_price", 0.45))

SIGMA_F = 2.0
SIGMA_C = 1.2

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "state.json"
MARKETS_DIR = DATA_DIR / "markets"
MARKETS_DIR.mkdir(exist_ok=True)
CALIBRATION_FILE = DATA_DIR / "calibration.json"

LOCATIONS = {
    "nyc": {
        "lat": 40.7772,
        "lon": -73.8726,
        "name": "New York City",
        "station": "KLGA",
        "unit": "F",
        "region": "us",
    },
    "chicago": {
        "lat": 41.9742,
        "lon": -87.9073,
        "name": "Chicago",
        "station": "KORD",
        "unit": "F",
        "region": "us",
    },
    "miami": {
        "lat": 25.7959,
        "lon": -80.2870,
        "name": "Miami",
        "station": "KMIA",
        "unit": "F",
        "region": "us",
    },
    "dallas": {
        "lat": 32.8471,
        "lon": -96.8518,
        "name": "Dallas",
        "station": "KDAL",
        "unit": "F",
        "region": "us",
    },
    "seattle": {
        "lat": 47.4502,
        "lon": -122.3088,
        "name": "Seattle",
        "station": "KSEA",
        "unit": "F",
        "region": "us",
    },
    "atlanta": {
        "lat": 33.6407,
        "lon": -84.4277,
        "name": "Atlanta",
        "station": "KATL",
        "unit": "F",
        "region": "us",
    },
    "london": {
        "lat": 51.5048,
        "lon": 0.0495,
        "name": "London",
        "station": "EGLC",
        "unit": "C",
        "region": "eu",
    },
    "paris": {
        "lat": 48.9962,
        "lon": 2.5979,
        "name": "Paris",
        "station": "LFPG",
        "unit": "C",
        "region": "eu",
    },
    "munich": {
        "lat": 48.3537,
        "lon": 11.7750,
        "name": "Munich",
        "station": "EDDM",
        "unit": "C",
        "region": "eu",
    },
    "ankara": {
        "lat": 40.1281,
        "lon": 32.9951,
        "name": "Ankara",
        "station": "LTAC",
        "unit": "C",
        "region": "eu",
    },
    "seoul": {
        "lat": 37.4691,
        "lon": 126.4505,
        "name": "Seoul",
        "station": "RKSI",
        "unit": "C",
        "region": "asia",
    },
    "tokyo": {
        "lat": 35.7647,
        "lon": 140.3864,
        "name": "Tokyo",
        "station": "RJTT",
        "unit": "C",
        "region": "asia",
    },
    "shanghai": {
        "lat": 31.1443,
        "lon": 121.8083,
        "name": "Shanghai",
        "station": "ZSPD",
        "unit": "C",
        "region": "asia",
    },
    "singapore": {
        "lat": 1.3502,
        "lon": 103.9940,
        "name": "Singapore",
        "station": "WSSS",
        "unit": "C",
        "region": "asia",
    },
    "lucknow": {
        "lat": 26.7606,
        "lon": 80.8893,
        "name": "Lucknow",
        "station": "VILK",
        "unit": "C",
        "region": "asia",
    },
    "tel-aviv": {
        "lat": 32.0114,
        "lon": 34.8867,
        "name": "Tel Aviv",
        "station": "LLBG",
        "unit": "C",
        "region": "asia",
    },
    "toronto": {
        "lat": 43.6772,
        "lon": -79.6306,
        "name": "Toronto",
        "station": "CYYZ",
        "unit": "C",
        "region": "ca",
    },
    "sao-paulo": {
        "lat": -23.4356,
        "lon": -46.4731,
        "name": "Sao Paulo",
        "station": "SBGR",
        "unit": "C",
        "region": "sa",
    },
    "buenos-aires": {
        "lat": -34.8222,
        "lon": -58.5358,
        "name": "Buenos Aires",
        "station": "SAEZ",
        "unit": "C",
        "region": "sa",
    },
    "wellington": {
        "lat": -41.3272,
        "lon": 174.8052,
        "name": "Wellington",
        "station": "NZWN",
        "unit": "C",
        "region": "oc",
    },
}

TIMEZONES = {
    "nyc": "America/New_York",
    "chicago": "America/Chicago",
    "miami": "America/New_York",
    "dallas": "America/Chicago",
    "seattle": "America/Los_Angeles",
    "atlanta": "America/New_York",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "munich": "Europe/Berlin",
    "ankara": "Europe/Istanbul",
    "seoul": "Asia/Seoul",
    "tokyo": "Asia/Tokyo",
    "shanghai": "Asia/Shanghai",
    "singapore": "Asia/Singapore",
    "lucknow": "Asia/Kolkata",
    "tel-aviv": "Asia/Jerusalem",
    "toronto": "America/Toronto",
    "sao-paulo": "America/Sao_Paulo",
    "buenos-aires": "America/Argentina/Buenos_Aires",
    "wellington": "Pacific/Auckland",
}

MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]

# =============================================================================
# MATH
# =============================================================================


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bucket_prob(forecast, t_low, t_high, sigma=None):
    """Returns probability mass for a bucket using a normal approximation."""
    s = sigma or 2.0
    if t_low == -999:
        return norm_cdf((t_high - float(forecast)) / s)
    if t_high == 999:
        return 1.0 - norm_cdf((t_low - float(forecast)) / s)
    upper = norm_cdf((t_high - float(forecast)) / s)
    lower = norm_cdf((t_low - float(forecast)) / s)
    return max(0.0, min(1.0, upper - lower))


def normalize_probability_weights(weights):
    total = sum(weights)
    if total <= 0:
        return []
    return [w / total for w in weights]


def get_source_sigma(city_slug, source, source_sigmas=None):
    if source_sigmas and source in source_sigmas and source_sigmas[source] is not None:
        return source_sigmas[source]
    cal_source = "metar" if source == "metar_anchor" else source
    return get_sigma(city_slug, cal_source)


def aggregate_probability(
    contracts, source_forecasts, source_sigmas=None, city_slug=None
):
    records = []

    for contract in contracts:
        t_low, t_high = contract["range"]
        per_source = {}
        source_values = []

        for source in ["ecmwf", "hrrr", "metar_anchor"]:
            forecast = source_forecasts.get(source)
            if forecast is None:
                per_source[source] = None
                continue
            sigma = get_source_sigma(city_slug, source, source_sigmas)
            prob = bucket_prob(forecast, t_low, t_high, sigma=sigma)
            per_source[source] = round(prob, 6)
            source_values.append(prob)

        agg = sum(source_values) / len(source_values) if source_values else 0.0
        records.append(
            {
                "question": contract.get("question"),
                "market_id": contract.get("market_id"),
                "range": contract["range"],
                "condition_id": contract.get("condition_id"),
                "token_id_yes": contract.get("token_id_yes"),
                "token_id_no": contract.get("token_id_no"),
                "per_source_probability": per_source,
                "aggregate_probability": agg,
            }
        )

    normalized = normalize_probability_weights(
        [record["aggregate_probability"] for record in records]
    )
    for record, agg in zip(records, normalized):
        record["aggregate_probability"] = round(agg, 6)
        record["fair_yes"] = record["aggregate_probability"]
        record["fair_no"] = 1.0 - record["aggregate_probability"]

    return records


def calc_ev(p, price):
    if price <= 0 or price >= 1:
        return 0.0
    return round(p * (1.0 / price - 1.0) - (1.0 - p), 4)


def calc_kelly(p, price):
    if price <= 0 or price >= 1:
        return 0.0
    b = 1.0 / price - 1.0
    f = (p * b - (1.0 - p)) / b
    return round(min(max(0.0, f) * KELLY_FRACTION, 1.0), 4)


def bet_size(kelly, balance):
    raw = kelly * balance
    return round(min(raw, MAX_BET), 2)


# =============================================================================
# CALIBRATION
# =============================================================================

_cal: dict = {}


def load_cal():
    if CALIBRATION_FILE.exists():
        return json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    return {}


def get_sigma(city_slug, source="ecmwf"):
    key = f"{city_slug}_{source}"
    if key in _cal:
        return _cal[key]["sigma"]
    return SIGMA_F if LOCATIONS[city_slug]["unit"] == "F" else SIGMA_C


def run_calibration(markets):
    """Recalculates sigma from resolved markets."""
    resolved = [
        m for m in markets if m.get("resolved") and m.get("actual_temp") is not None
    ]
    cal = load_cal()
    updated = []

    for source in ["ecmwf", "hrrr", "metar"]:
        for city in set(m["city"] for m in resolved):
            group = [m for m in resolved if m["city"] == city]
            errors = []
            for m in group:
                snap = next(
                    (
                        s
                        for s in reversed(m.get("forecast_snapshots", []))
                        if s["source"] == source
                    ),
                    None,
                )
                if snap and snap.get("temp") is not None:
                    errors.append(abs(snap["temp"] - m["actual_temp"]))
            if len(errors) < CALIBRATION_MIN:
                continue
            mae = sum(errors) / len(errors)
            key = f"{city}_{source}"
            old = cal.get(key, {}).get(
                "sigma", SIGMA_F if LOCATIONS[city]["unit"] == "F" else SIGMA_C
            )
            new = round(mae, 3)
            cal[key] = {
                "sigma": new,
                "n": len(errors),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if abs(new - old) > 0.05:
                updated.append(
                    f"{LOCATIONS[city]['name']} {source}: {old:.2f}->{new:.2f}"
                )

    CALIBRATION_FILE.write_text(json.dumps(cal, indent=2), encoding="utf-8")
    if updated:
        print(f"  [CAL] {', '.join(updated)}")
    return cal


# =============================================================================
# FORECASTS
# =============================================================================


def get_ecmwf(city_slug, dates):
    """ECMWF via Open-Meteo with bias correction. For all cities."""
    loc = LOCATIONS[city_slug]
    unit = loc["unit"]
    temp_unit = "fahrenheit" if unit == "F" else "celsius"
    result = {}
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc['lat']}&longitude={loc['lon']}"
        f"&daily=temperature_2m_max&temperature_unit={temp_unit}"
        f"&forecast_days=7&timezone={TIMEZONES.get(city_slug, 'UTC')}"
        f"&models=ecmwf_ifs025&bias_correction=true"
    )
    for attempt in range(3):
        try:
            data = requests.get(url, timeout=(5, 10)).json()
            if "error" not in data:
                for date, temp in zip(
                    data["daily"]["time"], data["daily"]["temperature_2m_max"]
                ):
                    if date in dates and temp is not None:
                        result[date] = round(temp, 1) if unit == "C" else round(temp)
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                print(f"  [ECMWF] {city_slug}: {e}")
    return result


def get_hrrr(city_slug, dates):
    """HRRR via Open-Meteo. US cities only, up to 48h horizon."""
    loc = LOCATIONS[city_slug]
    if loc["region"] != "us":
        return {}
    result = {}
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc['lat']}&longitude={loc['lon']}"
        f"&daily=temperature_2m_max&temperature_unit=fahrenheit"
        f"&forecast_days=3&timezone={TIMEZONES.get(city_slug, 'UTC')}"
        f"&models=gfs_seamless"  # HRRR+GFS seamless — best option for US
    )
    for attempt in range(3):
        try:
            data = requests.get(url, timeout=(5, 10)).json()
            if "error" not in data:
                for date, temp in zip(
                    data["daily"]["time"], data["daily"]["temperature_2m_max"]
                ):
                    if date in dates and temp is not None:
                        result[date] = round(temp)
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
            else:
                print(f"  [HRRR] {city_slug}: {e}")
    return result


def get_metar(city_slug):
    """Current observed temperature from METAR station. D+0 only."""
    loc = LOCATIONS[city_slug]
    station = loc["station"]
    unit = loc["unit"]
    try:
        url = f"https://aviationweather.gov/api/data/metar?ids={station}&format=json"
        data = requests.get(url, timeout=(5, 8)).json()
        if data and isinstance(data, list):
            temp_c = data[0].get("temp")
            if temp_c is not None:
                if unit == "F":
                    return round(float(temp_c) * 9 / 5 + 32)
                return round(float(temp_c), 1)
    except Exception as e:
        print(f"  [METAR] {city_slug}: {e}")
    return None


def get_actual_temp(city_slug, date_str):
    """Actual temperature via Visual Crossing for closed markets."""
    loc = LOCATIONS[city_slug]
    station = loc["station"]
    unit = loc["unit"]
    vc_unit = "us" if unit == "F" else "metric"
    url = (
        f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        f"/{station}/{date_str}/{date_str}"
        f"?unitGroup={vc_unit}&key={VC_KEY}&include=days&elements=tempmax"
    )
    try:
        data = requests.get(url, timeout=(5, 8)).json()
        days = data.get("days", [])
        if days and days[0].get("tempmax") is not None:
            return round(float(days[0]["tempmax"]), 1)
    except Exception as e:
        print(f"  [VC] {city_slug} {date_str}: {e}")
    return None


def check_market_resolved(market_id):
    """
    Checks if the market closed on Polymarket and who won.
    Returns: None (still open), True (YES won), False (NO won)
    """
    try:
        r = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=(5, 8)
        )
        data = r.json()
        closed = data.get("closed", False)
        if not closed:
            return None
        # Check YES price — if ~1.0 then WIN, if ~0.0 then LOSS
        prices = json.loads(data.get("outcomePrices", "[0.5,0.5]"))
        yes_price = float(prices[0])
        if yes_price >= 0.95:
            return True  # WIN
        elif yes_price <= 0.05:
            return False  # LOSS
        return None  # not yet determined
    except Exception as e:
        print(f"  [RESOLVE] {market_id}: {e}")
    return None


# =============================================================================
# POLYMARKET
# =============================================================================


def get_polymarket_event(city_slug, month, day, year):
    slug = f"highest-temperature-in-{city_slug}-on-{month}-{day}-{year}"
    try:
        r = requests.get(
            f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=(5, 8)
        )
        data = r.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
    except Exception:
        pass
    return None


def get_market_price(market_id):
    try:
        r = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=(3, 5)
        )
        prices = json.loads(r.json().get("outcomePrices", "[0.5,0.5]"))
        return float(prices[0])
    except Exception:
        return None


def parse_temp_range(question):
    if not question:
        return None
    num = r"(-?\d+(?:\.\d+)?)"
    if re.search(r"or below", question, re.IGNORECASE):
        m = re.search(num + r"[°]?[FC] or below", question, re.IGNORECASE)
        if m:
            return (-999.0, float(m.group(1)))
    if re.search(r"or higher", question, re.IGNORECASE):
        m = re.search(num + r"[°]?[FC] or higher", question, re.IGNORECASE)
        if m:
            return (float(m.group(1)), 999.0)
    m = re.search(r"between " + num + r"-" + num + r"[°]?[FC]", question, re.IGNORECASE)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = re.search(r"be " + num + r"[°]?[FC] on", question, re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return (v, v)
    return None


def hours_to_resolution(end_date_str):
    try:
        end = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        return max(0.0, (end - datetime.now(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return 999.0


def in_bucket(forecast, t_low, t_high):
    if t_low == t_high:
        return round(float(forecast)) == round(t_low)
    return t_low <= float(forecast) <= t_high


WEATHER_FRESHNESS_HOURS = 6.0


def parse_market_unit(text):
    if not text:
        return None
    if re.search(r"(?:°\s*F\b|\bF\b|fahrenheit)", text, re.IGNORECASE):
        return "F"
    if re.search(r"(?:°\s*C\b|\bC\b|celsius)", text, re.IGNORECASE):
        return "C"
    return None


def parse_station_code(text):
    if not text:
        return None
    m = re.search(r"\(([A-Z]{4})\)", text)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{4})\b", text)
    if m:
        return m.group(1)
    return None


def normalize_skip_reasons(reasons):
    seen = set()
    ordered = []
    for reason in reasons:
        if not reason or reason in seen:
            continue
        seen.add(reason)
        ordered.append(reason)
    return ordered


def extract_resolution_metadata(event, loc):
    rules = event.get("rules") or event.get("description") or ""
    title = event.get("title") or ""
    resolution_text = rules or title

    station = (
        parse_station_code(rules) or parse_station_code(title) or loc.get("station")
    )
    unit = parse_market_unit(rules) or parse_market_unit(title) or loc.get("unit")

    if rules and station == loc.get("station") and unit == loc.get("unit"):
        resolution_source = "rules+location"
    elif rules:
        resolution_source = "rules"
    elif title:
        resolution_source = "title"
    else:
        resolution_source = "location"

    rounding_rule = (
        "nearest_degree"
        if re.search(
            r"nearest (whole )?degree|rounded to the nearest",
            resolution_text,
            re.IGNORECASE,
        )
        else "unspecified"
    )

    return {
        "station": station,
        "unit": unit,
        "resolution_text": resolution_text,
        "resolution_source": resolution_source,
        "rounding_rule": rounding_rule,
    }


def extract_token_ids(market):
    raw = market.get("clobTokenIds")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, list) and len(raw) >= 2:
        return raw[0], raw[1]
    return None, None


def build_market_contracts(event, expected_unit):
    contracts = []
    skip_reasons = []

    for market in event.get("markets", []):
        question = market.get("question", "")
        rng = parse_temp_range(question)
        if not rng:
            skip_reasons.append("unparseable_temperature_range")
            continue

        unit = parse_market_unit(question)
        if unit and expected_unit and unit != expected_unit:
            skip_reasons.append("unit_mismatch")
            continue

        condition_id = market.get("conditionId") or event.get("conditionId")
        token_id_yes, token_id_no = extract_token_ids(market)
        if not condition_id or not token_id_yes or not token_id_no:
            skip_reasons.append("missing_contract_identifiers")
            return {
                "contracts": [],
                "skip_reasons": normalize_skip_reasons(skip_reasons),
            }

        contracts.append(
            {
                "market_id": market.get("id", ""),
                "question": question,
                "range": rng,
                "condition_id": condition_id,
                "token_id_yes": token_id_yes,
                "token_id_no": token_id_no,
                "unit": unit or expected_unit,
            }
        )

    return {
        "contracts": contracts,
        "skip_reasons": normalize_skip_reasons(skip_reasons),
    }


def evaluate_market_guardrails(
    loc, resolution_metadata, market_contracts, weather_snapshot, hours
):
    reasons = list(market_contracts.get("skip_reasons", []))
    contracts = market_contracts.get("contracts", [])
    expected_unit = loc.get("unit")
    expected_station = loc.get("station")

    if not resolution_metadata.get("resolution_text"):
        reasons.append("missing_rule_mapping")
    if resolution_metadata.get("station") != expected_station:
        reasons.append("missing_rule_mapping")
    if resolution_metadata.get("unit") != expected_unit:
        reasons.append("unit_mismatch")

    for contract in contracts:
        if contract.get("unit") != expected_unit:
            reasons.append("unit_mismatch")

    snap_ts = weather_snapshot.get("ts") if weather_snapshot else None
    best = weather_snapshot.get("best") if weather_snapshot else None
    if snap_ts is None or best is None:
        reasons.append("weather_data_missing")
    else:
        try:
            snap_time = datetime.fromisoformat(str(snap_ts).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - snap_time).total_seconds() / 3600
            if age_hours > WEATHER_FRESHNESS_HOURS:
                reasons.append("weather_data_stale")
        except Exception:
            reasons.append("weather_data_stale")

    if hours <= 0:
        reasons.append("event_outside_time_window")

    reasons = normalize_skip_reasons(reasons)
    return {
        "admissible": len(reasons) == 0 and len(contracts) > 0,
        "skip_reasons": reasons,
    }


def safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def get_clob_book(token_id):
    try:
        data = requests.get(
            f"https://clob.polymarket.com/book?token_id={token_id}", timeout=(3, 5)
        ).json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_clob_tick_size(token_id):
    try:
        data = requests.get(
            f"https://clob.polymarket.com/tick-size?token_id={token_id}",
            timeout=(3, 5),
        ).json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_token_quote_snapshot(token_id, side):
    reason_codes = []
    book = get_clob_book(token_id)
    tick_data = get_clob_tick_size(token_id)

    if not book:
        reason_codes.append("missing_quote_book")
        return {
            "token_id": token_id,
            "side": side,
            "bid": None,
            "ask": None,
            "spread": None,
            "tick_size": None,
            "min_order_size": None,
            "book_ok": False,
            "reason_codes": reason_codes,
        }

    if book.get("closed") is True:
        reason_codes.append("market_closed")

    bids = book.get("bids")
    asks = book.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list):
        reason_codes.append("missing_quote_book")
    elif not bids or not asks:
        reason_codes.append("orderbook_empty")

    bid = safe_float(bids[0].get("price")) if isinstance(bids, list) and bids else None
    ask = safe_float(asks[0].get("price")) if isinstance(asks, list) and asks else None
    spread = round(ask - bid, 4) if bid is not None and ask is not None else None

    tick_size = None
    if isinstance(tick_data, dict):
        tick_size = safe_float(
            tick_data.get("minimum_tick_size")
            or tick_data.get("tick_size")
            or tick_data.get("tickSize")
        )
    if tick_size is None:
        tick_size = safe_float(book.get("tick_size"))
    if tick_size is None:
        reason_codes.append("tick_size_missing")

    min_order_size = safe_float(book.get("min_order_size"))

    return {
        "token_id": token_id,
        "side": side,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "tick_size": tick_size,
        "min_order_size": min_order_size,
        "book_ok": len(reason_codes) == 0,
        "reason_codes": normalize_skip_reasons(reason_codes),
    }


def build_quote_snapshot(contracts):
    snapshots = []
    for contract in contracts:
        yes_quote = get_token_quote_snapshot(contract.get("token_id_yes"), "yes")
        no_quote = get_token_quote_snapshot(contract.get("token_id_no"), "no")
        reasons = normalize_skip_reasons(
            yes_quote.get("reason_codes", []) + no_quote.get("reason_codes", [])
        )
        snapshots.append(
            {
                "market_id": contract.get("market_id"),
                "question": contract.get("question"),
                "range": contract.get("range"),
                "yes": yes_quote,
                "no": no_quote,
                "execution_ok": len(reasons) == 0,
                "execution_stop_reasons": reasons,
            }
        )
    return snapshots


def quote_for_side(quote_snapshot, side):
    if not quote_snapshot:
        return {}
    return quote_snapshot.get(side, {})


def strategy_hours_ok(strategy_cfg, hours):
    return (
        strategy_cfg.get("min_hours", MIN_HOURS)
        <= hours
        <= strategy_cfg.get("max_hours", MAX_HOURS)
    )


def determine_size_multiplier(edge, min_edge):
    if edge >= min_edge * 2:
        return 1.0, "accepted"
    if edge >= min_edge:
        return 0.5, "size_down"
    return 0.0, "rejected"


def evaluate_yes_candidate(bucket_probability, quote_snapshot, hours):
    reasons = []
    quote = quote_for_side(quote_snapshot, "yes")
    fair_price = bucket_probability.get("fair_yes")
    ask = quote.get("ask")
    reasons.extend(
        missing_strategy_fields(
            YES_STRATEGY,
            [
                "max_price",
                "min_probability",
                "min_edge",
                "min_hours",
                "max_hours",
                "max_size",
                "min_size",
            ],
        )
    )

    if not strategy_hours_ok(YES_STRATEGY, hours):
        reasons.append("outside_strategy_window")
    if quote_snapshot and quote_snapshot.get("execution_stop_reasons"):
        reasons.extend(quote_snapshot.get("execution_stop_reasons", []))
    if ask is None:
        reasons.append("missing_quote_price")
    if ask is not None and ask > YES_STRATEGY.get("max_price", 1.0):
        reasons.append("price_above_max")
    if bucket_probability.get("aggregate_probability", 0.0) < YES_STRATEGY.get(
        "min_probability", 0.0
    ):
        reasons.append("probability_below_min")

    edge = round((fair_price or 0.0) - (ask or 0.0), 6) if ask is not None else None
    if edge is None:
        status = "rejected"
        size_multiplier = 0.0
    else:
        size_multiplier, status = determine_size_multiplier(
            edge, YES_STRATEGY.get("min_edge", 0.0)
        )
    if "price_above_max" in reasons:
        status = "reprice"
        size_multiplier = 0.0
    if any(reason != "price_above_max" for reason in reasons):
        status = "rejected"
        size_multiplier = 0.0

    return {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "range": bucket_probability.get("range"),
        "aggregate_probability": bucket_probability.get("aggregate_probability"),
        "fair_price": fair_price,
        "fair_yes": bucket_probability.get("fair_yes"),
        "fair_no": bucket_probability.get("fair_no"),
        "quote_context": quote,
        "status": status,
        "reasons": normalize_skip_reasons(reasons),
        "size_multiplier": size_multiplier,
        "edge": edge,
    }


def evaluate_no_candidate(bucket_probability, quote_snapshot, hours):
    reasons = []
    quote = quote_for_side(quote_snapshot, "no")
    fair_price = bucket_probability.get("fair_no")
    bid = quote.get("bid")
    reasons.extend(
        missing_strategy_fields(
            NO_STRATEGY,
            [
                "min_price",
                "min_probability",
                "min_edge",
                "min_hours",
                "max_hours",
                "max_size",
                "min_size",
            ],
        )
    )

    if not strategy_hours_ok(NO_STRATEGY, hours):
        reasons.append("outside_strategy_window")
    if quote_snapshot and quote_snapshot.get("execution_stop_reasons"):
        reasons.extend(quote_snapshot.get("execution_stop_reasons", []))
    if bid is None:
        reasons.append("missing_quote_price")
    if bid is not None and bid < NO_STRATEGY.get("min_price", 0.0):
        reasons.append("price_below_min")
    if bucket_probability.get("fair_no", 0.0) < NO_STRATEGY.get("min_probability", 0.0):
        reasons.append("probability_below_min")

    edge = round((bid or 0.0) - (fair_price or 0.0), 6) if bid is not None else None
    if edge is None:
        status = "rejected"
        size_multiplier = 0.0
    else:
        size_multiplier, status = determine_size_multiplier(
            edge, NO_STRATEGY.get("min_edge", 0.0)
        )
    if "price_below_min" in reasons:
        status = "reprice"
        size_multiplier = 0.0
    if any(reason != "price_below_min" for reason in reasons):
        status = "rejected"
        size_multiplier = 0.0

    return {
        "strategy_leg": "NO_CARRY",
        "token_side": "no",
        "range": bucket_probability.get("range"),
        "aggregate_probability": bucket_probability.get("aggregate_probability"),
        "fair_price": fair_price,
        "fair_yes": bucket_probability.get("fair_yes"),
        "fair_no": bucket_probability.get("fair_no"),
        "quote_context": quote,
        "status": status,
        "reasons": normalize_skip_reasons(reasons),
        "size_multiplier": size_multiplier,
        "edge": edge,
    }


def build_candidate_assessments(bucket_probabilities, quote_snapshot, hours):
    assessments = []
    quote_by_market = {entry.get("market_id"): entry for entry in quote_snapshot or []}
    for bucket in bucket_probabilities or []:
        quote = quote_by_market.get(bucket.get("market_id"), {})
        yes_candidate = evaluate_yes_candidate(bucket, quote, hours)
        no_candidate = evaluate_no_candidate(bucket, quote, hours)
        assessments.extend([yes_candidate, no_candidate])
    return assessments


def missing_strategy_fields(strategy_cfg, required_fields):
    missing = []
    for field in required_fields:
        if strategy_cfg.get(field) is None:
            missing.append(f"config_missing_{field}")
    return missing


def normalize_route_reason_codes(reasons):
    normalized = []
    for reason in reasons or []:
        if reason and reason not in normalized:
            normalized.append(reason)
    return normalized


def strategy_for_leg(strategy_leg):
    if strategy_leg == "YES_SNIPER":
        return YES_STRATEGY
    if strategy_leg == "NO_CARRY":
        return NO_STRATEGY
    return {}


def candidate_worst_loss(assessment, bankroll):
    strategy = strategy_for_leg(assessment.get("strategy_leg"))
    max_size = float(strategy.get("max_size", 0.0) or 0.0)
    min_size = float(strategy.get("min_size", 0.0) or 0.0)
    size_multiplier = float(assessment.get("size_multiplier", 0.0) or 0.0)

    if max_size <= 0 or size_multiplier <= 0:
        return 0.0

    worst_loss = max_size * size_multiplier
    if worst_loss < min_size:
        worst_loss = min_size
    return round(min(max_size, worst_loss), 2)


def assessment_liquidity(assessment):
    quote = assessment.get("quote_context", {}) or {}
    sizes = []
    for field in ["bid_size", "ask_size", "size", "liquidity"]:
        value = quote.get(field)
        if value is not None:
            sizes.append(float(value))
    if sizes:
        return round(sum(sizes), 6)
    return 0.0


def sort_leg_candidates(assessments):
    return sorted(
        assessments or [],
        key=lambda item: (
            -(item.get("edge") if item.get("edge") is not None else -999.0),
            -assessment_liquidity(item),
        ),
    )


def build_exposure_keys(city_slug_or_market, date_str=None, assessment=None):
    market = city_slug_or_market if isinstance(city_slug_or_market, dict) else {}
    city_slug = market.get("city", city_slug_or_market)
    date_value = market.get("date", date_str)
    assessment = assessment or market.get("assessment", {})
    rng = assessment.get("range") or (None, None)
    bucket = (
        f"{rng[0]}-{rng[1]}" if rng[0] is not None and rng[1] is not None else "unknown"
    )
    event_id = market.get("event_id") or market.get("event_slug") or "event"
    event_key = f"{city_slug}|{date_value}|{event_id}"
    return {
        "market": f"{city_slug}|{date_value}|{bucket}",
        "city": city_slug,
        "date": date_value,
        "event": event_key,
        "bucket": bucket,
    }


def route_candidate_assessment(assessment, market, risk_state, router_cfg):
    allowed = {"accepted", "size_down", "reprice", "rejected"}
    input_status = assessment.get("status")
    reasons = list(assessment.get("reasons", []) or [])
    if input_status not in allowed:
        reasons.append("invalid_candidate_status")
        input_status = "rejected"

    keys = build_exposure_keys(market, assessment=assessment)
    bankroll = float(risk_state.get("bankroll", 0.0) or 0.0)
    strategy_leg = assessment.get("strategy_leg")
    leg_state = (risk_state.get("legs", {}) or {}).get(strategy_leg, {}) or {}
    reserved_worst_loss = candidate_worst_loss(assessment, bankroll)
    decision = {
        "strategy_leg": strategy_leg,
        "token_side": assessment.get("token_side"),
        "range": assessment.get("range"),
        "input_status": assessment.get("status"),
        "status": "rejected",
        "reserved_worst_loss": 0.0,
        "budget_bucket": strategy_leg,
        "reasons": normalize_route_reason_codes(reasons),
        "exposure_keys": keys,
    }

    if input_status not in {"accepted", "size_down"}:
        return decision

    for reservation in risk_state.get("active_reservations", []) or []:
        if reservation.get("event") != keys["event"]:
            continue
        if reservation.get("bucket") == keys["bucket"]:
            if reservation.get("token_side") != assessment.get("token_side"):
                decision["reasons"] = normalize_route_reason_codes(
                    decision["reasons"] + ["same_bucket_conflict"]
                )
                return decision
            continue
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["event_cluster_conflict"]
        )
        return decision

    leg_reserved = float(leg_state.get("reserved", 0.0) or 0.0)
    leg_budget = float(
        leg_state.get(
            "budget",
            bankroll
            * (
                router_cfg.get("yes_budget_pct", 0.0)
                if strategy_leg == "YES_SNIPER"
                else router_cfg.get("no_budget_pct", 0.0)
            ),
        )
        or 0.0
    )
    leg_cap = float(
        leg_state.get(
            "hard_cap",
            bankroll
            * (
                router_cfg.get("yes_leg_cap_pct", 0.0)
                if strategy_leg == "YES_SNIPER"
                else router_cfg.get("no_leg_cap_pct", 0.0)
            ),
        )
        or 0.0
    )
    if leg_reserved + reserved_worst_loss > leg_cap:
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["leg_cap_exceeded"]
        )
        return decision
    if leg_reserved + reserved_worst_loss > leg_budget:
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["leg_budget_exceeded"]
        )
        return decision

    if float(
        risk_state.get("global_reserved_worst_loss", 0.0) or 0.0
    ) + reserved_worst_loss > bankroll * router_cfg.get("global_usage_cap_pct", 0.0):
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["global_cap_exceeded"]
        )
        return decision

    if float(
        (risk_state.get("market_exposure", {}) or {}).get(keys["market"], 0.0) or 0.0
    ) + reserved_worst_loss > bankroll * router_cfg.get("per_market_cap_pct", 0.0):
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["market_cap_exceeded"]
        )
        return decision

    if float(
        (risk_state.get("city_exposure", {}) or {}).get(keys["city"], 0.0) or 0.0
    ) + reserved_worst_loss > bankroll * router_cfg.get("per_city_cap_pct", 0.0):
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["city_cap_exceeded"]
        )
        return decision

    if float(
        (risk_state.get("date_exposure", {}) or {}).get(keys["date"], 0.0) or 0.0
    ) + reserved_worst_loss > bankroll * router_cfg.get("per_date_cap_pct", 0.0):
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["date_cap_exceeded"]
        )
        return decision

    if float(
        (risk_state.get("event_exposure", {}) or {}).get(keys["event"], 0.0) or 0.0
    ) + reserved_worst_loss > bankroll * router_cfg.get("per_event_cap_pct", 0.0):
        decision["reasons"] = normalize_route_reason_codes(
            decision["reasons"] + ["event_cap_exceeded"]
        )
        return decision

    decision["status"] = "accepted"
    decision["reserved_worst_loss"] = reserved_worst_loss
    decision["reasons"] = normalize_route_reason_codes(decision["reasons"])
    return decision


def build_leg_risk_state(bankroll, router_cfg):
    return {
        "YES_SNIPER": {
            "budget": round(bankroll * router_cfg.get("yes_budget_pct", 0.0), 2),
            "reserved": 0.0,
            "hard_cap": round(bankroll * router_cfg.get("yes_leg_cap_pct", 0.0), 2),
        },
        "NO_CARRY": {
            "budget": round(bankroll * router_cfg.get("no_budget_pct", 0.0), 2),
            "reserved": 0.0,
            "hard_cap": round(bankroll * router_cfg.get("no_leg_cap_pct", 0.0), 2),
        },
    }


def build_empty_risk_state(bankroll, router_cfg):
    return {
        "bankroll": round(bankroll, 2),
        "global_reserved_worst_loss": 0.0,
        "legs": build_leg_risk_state(bankroll, router_cfg),
        "market_exposure": {},
        "city_exposure": {},
        "date_exposure": {},
        "event_exposure": {},
        "active_reservations": [],
    }


def apply_reservation_to_risk_state(risk_state, reservation):
    if not reservation:
        return
    reserved = float(reservation.get("reserved_worst_loss", 0.0) or 0.0)
    if reserved <= 0:
        return
    strategy_leg = reservation.get("strategy_leg")
    keys = reservation.get("exposure_keys", {}) or {}
    if strategy_leg in risk_state.get("legs", {}):
        risk_state["legs"][strategy_leg]["reserved"] = round(
            float(risk_state["legs"][strategy_leg].get("reserved", 0.0) or 0.0)
            + reserved,
            2,
        )
    risk_state["global_reserved_worst_loss"] = round(
        float(risk_state.get("global_reserved_worst_loss", 0.0) or 0.0) + reserved,
        2,
    )
    for bucket_name in ["market", "city", "date", "event"]:
        bucket_key = keys.get(bucket_name)
        if bucket_key is None:
            continue
        ledger_name = f"{bucket_name}_exposure"
        risk_state.setdefault(ledger_name, {})
        risk_state[ledger_name][bucket_key] = round(
            float(risk_state[ledger_name].get(bucket_key, 0.0) or 0.0) + reserved,
            2,
        )
    active_reservation = {
        "market": keys.get("market"),
        "city": keys.get("city"),
        "date": keys.get("date"),
        "event": keys.get("event"),
        "bucket": keys.get("bucket"),
        "token_side": reservation.get("token_side"),
        "strategy_leg": strategy_leg,
        "reserved_worst_loss": reserved,
    }
    risk_state.setdefault("active_reservations", []).append(active_reservation)


def remove_reservation_from_risk_state(risk_state, reservation):
    if not reservation:
        return
    reserved = float(reservation.get("reserved_worst_loss", 0.0) or 0.0)
    if reserved <= 0:
        return
    strategy_leg = reservation.get("strategy_leg")
    keys = reservation.get("exposure_keys", {}) or {}
    if strategy_leg in risk_state.get("legs", {}):
        risk_state["legs"][strategy_leg]["reserved"] = round(
            max(
                0.0,
                float(risk_state["legs"][strategy_leg].get("reserved", 0.0) or 0.0)
                - reserved,
            ),
            2,
        )
    risk_state["global_reserved_worst_loss"] = round(
        max(
            0.0,
            float(risk_state.get("global_reserved_worst_loss", 0.0) or 0.0) - reserved,
        ),
        2,
    )
    for bucket_name in ["market", "city", "date", "event"]:
        bucket_key = keys.get(bucket_name)
        if bucket_key is None:
            continue
        ledger_name = f"{bucket_name}_exposure"
        current = float(
            (risk_state.get(ledger_name, {}) or {}).get(bucket_key, 0.0) or 0.0
        )
        updated = round(max(0.0, current - reserved), 2)
        if updated == 0.0:
            (risk_state.get(ledger_name, {}) or {}).pop(bucket_key, None)
        else:
            risk_state[ledger_name][bucket_key] = updated
    remaining = []
    for active in risk_state.get("active_reservations", []) or []:
        if (
            active.get("market") == keys.get("market")
            and active.get("strategy_leg") == strategy_leg
            and active.get("token_side") == reservation.get("token_side")
            and active.get("bucket") == keys.get("bucket")
        ):
            continue
        remaining.append(active)
    risk_state["active_reservations"] = remaining


def assessment_matches_reservation(assessment, reservation):
    return (
        assessment.get("strategy_leg") == reservation.get("strategy_leg")
        and assessment.get("token_side") == reservation.get("token_side")
        and list(assessment.get("range") or []) == list(reservation.get("range") or [])
    )


def release_reserved_exposure(market, risk_state, release_reason, released_at=None):
    reservation = market.get("reserved_exposure")
    if not reservation or reservation.get("release_reason"):
        return None
    remove_reservation_from_risk_state(risk_state, reservation)
    released = dict(reservation)
    released["release_reason"] = release_reason
    released["released_at"] = released_at or datetime.now(timezone.utc).isoformat()
    released["reserved_worst_loss"] = 0.0
    market["reserved_exposure"] = released
    return released


def restore_risk_state_from_markets(state, markets, router_cfg):
    bankroll = float(state.get("starting_balance", BALANCE) or BALANCE)
    risk_state = build_empty_risk_state(bankroll, router_cfg)
    for market in markets or []:
        reservation = market.get("reserved_exposure")
        if not reservation:
            continue
        if reservation.get("release_reason"):
            continue
        restored = dict(reservation)
        restored.setdefault(
            "exposure_keys",
            build_exposure_keys(
                market,
                assessment={
                    "range": reservation.get("range"),
                    "strategy_leg": reservation.get("strategy_leg"),
                },
            ),
        )
        apply_reservation_to_risk_state(risk_state, restored)
    return risk_state


def build_reserved_exposure(market, decision, reserved_at):
    return {
        "strategy_leg": decision.get("strategy_leg"),
        "token_side": decision.get("token_side"),
        "status": decision.get("status"),
        "range": list(decision.get("range") or []),
        "reserved_worst_loss": round(
            decision.get("reserved_worst_loss", 0.0) or 0.0, 2
        ),
        "reserved_at": reserved_at,
        "release_reason": None,
        "reasons": list(decision.get("reasons", []) or []),
        "budget_bucket": decision.get("budget_bucket"),
        "exposure_keys": dict(decision.get("exposure_keys", {}) or {}),
    }


# =============================================================================
# PHASE 4 ORDER HELPERS
# =============================================================================


def find_assessment_for_reservation(market):
    reservation = market.get("reserved_exposure")
    if not reservation:
        return None
    for assessment in market.get("candidate_assessments", []) or []:
        if assessment_matches_reservation(assessment, reservation):
            return assessment
    return None


def find_quote_for_market(quote_snapshot, market_id):
    for quote in quote_snapshot or []:
        if quote.get("market_id") == market_id:
            return quote
    return None


def resolve_market_id_for_range(market, assessment):
    target_range = list(assessment.get("range") or [])
    for contract in market.get("market_contracts", []) or []:
        if list(contract.get("range") or []) == target_range:
            return contract.get("market_id")
    return None


def compute_passive_limit_price(side_quote, policy):
    bid = side_quote.get("bid")
    ask = side_quote.get("ask")
    tick_size = side_quote.get("tick_size")
    if tick_size is None:
        return None, "tick_size_missing"
    try:
        tick_size = float(tick_size)
    except Exception:
        return None, "tick_size_missing"
    if tick_size <= 0:
        return None, "tick_size_missing"
    if bid is None or ask is None:
        return None, "quote_price_missing"
    try:
        bid = float(bid)
        ask = float(ask)
    except Exception:
        return None, "quote_price_missing"
    improve_ticks = int(policy.get("price_improve_ticks", 0) or 0)
    candidate = bid + (tick_size * improve_ticks)
    candidate = max(candidate, bid)
    if ask > bid:
        candidate = min(candidate, ask - tick_size)
    candidate = round(candidate, 6)
    if candidate <= 0:
        return None, "quote_price_missing"
    return round(candidate, 4), None


def build_passive_order_intent(market, reservation, assessment, quote_snapshot, now_ts):
    if not reservation:
        return {"order": None, "reason": "reservation_missing"}
    if not assessment or assessment.get("status") != "accepted":
        return {"order": None, "reason": "route_not_accepted"}
    market_id = resolve_market_id_for_range(market, assessment)
    if not market_id:
        return {"order": None, "reason": "market_contract_missing"}
    quote = find_quote_for_market(quote_snapshot, market_id)
    if not quote:
        return {"order": None, "reason": "quote_snapshot_missing"}
    token_side = assessment.get("token_side")
    side_quote = (quote.get(token_side) if token_side in {"yes", "no"} else None) or {}
    if not side_quote:
        return {"order": None, "reason": "quote_snapshot_missing"}
    limit_price, reason = compute_passive_limit_price(side_quote, ORDER_POLICY)
    if reason:
        return {"order": None, "reason": reason}
    reserved_worst_loss = float(reservation.get("reserved_worst_loss", 0.0) or 0.0)
    if reserved_worst_loss <= 0:
        return {"order": None, "reason": "reserved_worst_loss_missing"}
    shares = round(reserved_worst_loss / limit_price, 4)
    tif_key = "yes_time_in_force" if token_side == "yes" else "no_time_in_force"
    time_in_force = ORDER_POLICY.get(tif_key, "GTC")
    expires_at = None
    if time_in_force == "GTD":
        try:
            expires_at = (
                datetime.fromisoformat(now_ts)
                + timedelta(hours=ORDER_POLICY.get("gtd_buffer_hours", 6.0))
            ).isoformat()
        except Exception:
            expires_at = None
    order = {
        "order_id": f"{market_id}:{token_side}:{int(datetime.fromisoformat(now_ts).timestamp())}",
        "strategy_leg": reservation.get("strategy_leg"),
        "token_side": token_side,
        "market_id": market_id,
        "range": list(assessment.get("range") or []),
        "limit_price": limit_price,
        "shares": shares,
        "filled_shares": 0.0,
        "remaining_shares": shares,
        "time_in_force": time_in_force,
        "expires_at": expires_at,
        "status": "planned",
        "status_reason": "accepted_route",
        "created_at": now_ts,
        "updated_at": now_ts,
        "history": [
            {
                "status": "planned",
                "reason": "accepted_route",
                "ts": now_ts,
                "fill_shares": 0.0,
                "fill_price": None,
            }
        ],
    }
    return {"order": order, "reason": None}


def apply_order_transition(
    order,
    next_status,
    reason,
    ts,
    fill_shares=0.0,
    fill_price=None,
    patch=None,
):
    allowed = {"planned", "working", "partial", "filled", "canceled", "expired"}
    if next_status not in allowed:
        raise ValueError(f"unsupported_order_status:{next_status}")
    updated = dict(order or {})
    history = list(updated.get("history", []) or [])
    delta = round(float(fill_shares or 0.0), 4)
    updated["filled_shares"] = round(
        float(updated.get("filled_shares", 0.0) or 0.0) + delta,
        4,
    )
    total_shares = round(float(updated.get("shares", 0.0) or 0.0), 4)
    updated["remaining_shares"] = round(
        max(0.0, total_shares - updated["filled_shares"]),
        4,
    )
    updated["status"] = next_status
    updated["status_reason"] = reason
    updated["updated_at"] = ts
    if patch:
        updated.update(patch)
    history.append(
        {
            "status": next_status,
            "reason": reason,
            "ts": ts,
            "fill_shares": delta,
            "fill_price": fill_price,
        }
    )
    updated["history"] = history
    return updated


def is_order_terminal(order):
    return (order or {}).get("status") in {"filled", "canceled", "expired"}


def ensure_market_order_defaults(market):
    market.setdefault("active_order", None)
    market.setdefault("order_history", [])
    return market


def route_market_candidates(
    market,
    risk_state,
    router_cfg,
    reserved_at=None,
    kept_reservation=None,
    initial_decisions=None,
):
    assessments = market.get("candidate_assessments", []) or []
    decisions = list(initial_decisions or [])
    reserved_exposure = (
        kept_reservation
        if kept_reservation is not None
        else market.get("reserved_exposure")
    )

    for leg in ["YES_SNIPER", "NO_CARRY"]:
        leg_assessments = []
        for assessment in assessments:
            if assessment.get("strategy_leg") != leg:
                continue
            if kept_reservation and assessment_matches_reservation(
                assessment, kept_reservation
            ):
                continue
            leg_assessments.append(assessment)
        for assessment in sort_leg_candidates(leg_assessments):
            decision = route_candidate_assessment(
                assessment, market, risk_state, router_cfg
            )
            decisions.append(decision)
            if decision.get("status") == "accepted" and reserved_exposure is None:
                reserved_exposure = build_reserved_exposure(
                    market,
                    decision,
                    reserved_at or datetime.now(timezone.utc).isoformat(),
                )
                apply_reservation_to_risk_state(risk_state, reserved_exposure)

    market["route_decisions"] = decisions
    market["reserved_exposure"] = reserved_exposure
    return decisions, reserved_exposure


def reconcile_market_reservation(market, risk_state, router_cfg, reserved_at=None):
    existing = market.get("reserved_exposure")
    kept_reservation = None
    decisions = []

    if existing and not existing.get("release_reason"):
        matching_assessment = next(
            (
                assessment
                for assessment in market.get("candidate_assessments", []) or []
                if assessment_matches_reservation(assessment, existing)
            ),
            None,
        )

        if matching_assessment is None:
            release_reserved_exposure(
                market, risk_state, "candidate_missing", reserved_at
            )
        elif matching_assessment.get("status") not in {"accepted", "size_down"}:
            release_reserved_exposure(
                market, risk_state, "candidate_downgraded", reserved_at
            )
        else:
            remove_reservation_from_risk_state(risk_state, existing)
            kept_decision = {
                "strategy_leg": existing.get("strategy_leg"),
                "token_side": existing.get("token_side"),
                "range": list(existing.get("range") or []),
                "input_status": matching_assessment.get("status"),
                "status": "accepted",
                "reserved_worst_loss": candidate_worst_loss(
                    matching_assessment, risk_state.get("bankroll", 0.0)
                ),
                "budget_bucket": existing.get("budget_bucket"),
                "reasons": normalize_route_reason_codes(
                    matching_assessment.get("reasons", [])
                ),
                "exposure_keys": build_exposure_keys(
                    market, assessment=matching_assessment
                ),
            }
            kept_reservation = build_reserved_exposure(
                market, kept_decision, reserved_at
            )
            apply_reservation_to_risk_state(risk_state, kept_reservation)
            decisions.append(kept_decision)

    return route_market_candidates(
        market,
        risk_state,
        router_cfg,
        reserved_at=reserved_at,
        kept_reservation=kept_reservation,
        initial_decisions=decisions,
    )


# =============================================================================
# MARKET DATA STORAGE
# Each market is stored in a separate file: data/markets/{city}_{date}.json
# =============================================================================


def market_path(city_slug, date_str):
    return MARKETS_DIR / f"{city_slug}_{date_str}.json"


def load_market(city_slug, date_str):
    p = market_path(city_slug, date_str)
    if p.exists():
        return ensure_market_order_defaults(json.loads(p.read_text(encoding="utf-8")))
    return None


def save_market(market):
    p = market_path(market["city"], market["date"])
    p.write_text(json.dumps(market, indent=2, ensure_ascii=False), encoding="utf-8")


def load_all_markets():
    markets = []
    for f in MARKETS_DIR.glob("*.json"):
        try:
            markets.append(
                ensure_market_order_defaults(json.loads(f.read_text(encoding="utf-8")))
            )
        except Exception:
            pass
    return markets


def new_market(city_slug, date_str, event, hours):
    loc = LOCATIONS[city_slug]
    return {
        "city": city_slug,
        "city_name": loc["name"],
        "date": date_str,
        "unit": loc["unit"],
        "station": loc["station"],
        "event_slug": event.get("slug", ""),
        "event_id": event.get("id", ""),
        "event_end_date": event.get("endDate", ""),
        "hours_at_discovery": round(hours, 1),
        "status": "open",  # open | closed | resolved
        "position": None,  # filled when position opens
        "actual_temp": None,  # filled after resolution
        "resolved_outcome": None,  # win / loss / no_position
        "pnl": None,
        "resolution_metadata": {
            "station": loc["station"],
            "unit": loc["unit"],
            "resolution_text": "",
            "resolution_source": "",
            "rounding_rule": "",
        },
        "market_contracts": [],
        "scan_guardrails": {
            "admissible": False,
            "skip_reasons": [],
            "weather_fresh": False,
            "mapping_ok": False,
            "unit_ok": False,
        },
        "last_scan_status": "pending",
        "last_scan_at": None,
        "last_scan_reason": None,
        "forecast_snapshots": [],  # list of forecast snapshots
        "market_snapshots": [],  # list of market price snapshots
        "all_outcomes": [],  # all market buckets
        "bucket_probabilities": [],
        "quote_snapshot": [],
        "candidate_assessments": [],
        "route_decisions": [],
        "reserved_exposure": None,
        "active_order": None,
        "order_history": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# STATE (balance and open positions)
# =============================================================================


def load_state():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    else:
        state = {
            "balance": BALANCE,
            "starting_balance": BALANCE,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "peak_balance": BALANCE,
        }
    state.setdefault("balance", BALANCE)
    state.setdefault("starting_balance", BALANCE)
    state.setdefault("total_trades", 0)
    state.setdefault("wins", 0)
    state.setdefault("losses", 0)
    state.setdefault("peak_balance", BALANCE)
    state["risk_state"] = restore_risk_state_from_markets(
        state, load_all_markets(), RISK_ROUTER
    )
    return state


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# =============================================================================
# CORE LOGIC
# =============================================================================


def take_forecast_snapshot(city_slug, dates):
    """Fetches forecasts from all sources and returns a snapshot."""
    now_str = datetime.now(timezone.utc).isoformat()
    ecmwf = get_ecmwf(city_slug, dates)
    hrrr = get_hrrr(city_slug, dates)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    snapshots = {}
    for date in dates:
        snap = {
            "ts": now_str,
            "ecmwf": ecmwf.get(date),
            "hrrr": hrrr.get(date)
            if date
            <= (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
            else None,
            "metar": get_metar(city_slug) if date == today else None,
        }
        # Best forecast: HRRR for US D+0/D+1, otherwise ECMWF
        loc = LOCATIONS[city_slug]
        if loc["region"] == "us" and snap["hrrr"] is not None:
            snap["best"] = snap["hrrr"]
            snap["best_source"] = "hrrr"
        elif snap["ecmwf"] is not None:
            snap["best"] = snap["ecmwf"]
            snap["best_source"] = "ecmwf"
        else:
            snap["best"] = None
            snap["best_source"] = None
        snapshots[date] = snap
    return snapshots


def scan_and_update():
    """Main function of one cycle: updates forecasts, opens/closes positions."""
    global _cal
    now = datetime.now(timezone.utc)
    state = load_state()
    balance = state["balance"]
    risk_state = state.get("risk_state") or build_empty_risk_state(
        state.get("starting_balance", BALANCE), RISK_ROUTER
    )
    new_pos = 0
    closed = 0
    resolved = 0

    for city_slug, loc in LOCATIONS.items():
        unit = loc["unit"]
        unit_sym = "F" if unit == "F" else "C"
        print(f"  -> {loc['name']}...", end=" ", flush=True)

        try:
            dates = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)]
            snapshots = take_forecast_snapshot(city_slug, dates)
            time.sleep(0.3)
        except Exception as e:
            print(f"skipped ({e})")
            continue

        for i, date in enumerate(dates):
            dt = datetime.strptime(date, "%Y-%m-%d")
            event = get_polymarket_event(
                city_slug, MONTHS[dt.month - 1], dt.day, dt.year
            )
            if not event:
                continue

            end_date = event.get("endDate", "")
            hours = hours_to_resolution(end_date) if end_date else 0
            horizon = f"D+{i}"

            # Load or create market record
            mkt = load_market(city_slug, date)
            if mkt is None:
                if hours < MIN_HOURS or hours > MAX_HOURS:
                    continue
                mkt = new_market(city_slug, date, event, hours)
            else:
                mkt.setdefault("event_slug", event.get("slug", ""))
                mkt.setdefault("event_id", event.get("id", ""))
                mkt.setdefault(
                    "resolution_metadata",
                    {
                        "station": loc["station"],
                        "unit": loc["unit"],
                        "resolution_text": "",
                        "resolution_source": "",
                        "rounding_rule": "",
                    },
                )
                mkt.setdefault("market_contracts", [])
                mkt.setdefault(
                    "scan_guardrails",
                    {
                        "admissible": False,
                        "skip_reasons": [],
                        "weather_fresh": False,
                        "mapping_ok": False,
                        "unit_ok": False,
                    },
                )
                mkt.setdefault("last_scan_status", "pending")
                mkt.setdefault("last_scan_at", None)
                mkt.setdefault("last_scan_reason", None)
                mkt.setdefault("bucket_probabilities", [])
                mkt.setdefault("quote_snapshot", [])
                mkt.setdefault("candidate_assessments", [])
                mkt.setdefault("route_decisions", [])
                mkt.setdefault("reserved_exposure", None)
                ensure_market_order_defaults(mkt)

            mkt["event_slug"] = event.get("slug", mkt.get("event_slug", ""))
            mkt["event_id"] = event.get("id", mkt.get("event_id", ""))

            # Skip if market already resolved
            if mkt["status"] == "resolved":
                continue

            snap = snapshots.get(date, {})
            resolution_metadata = extract_resolution_metadata(event, loc)
            contract_payload = build_market_contracts(event, loc["unit"])
            verdict = evaluate_market_guardrails(
                loc, resolution_metadata, contract_payload, snap, hours
            )

            mkt["resolution_metadata"] = resolution_metadata
            mkt["market_contracts"] = contract_payload["contracts"]
            mkt["scan_guardrails"] = {
                "admissible": verdict["admissible"],
                "skip_reasons": verdict["skip_reasons"],
                "weather_fresh": not any(
                    reason in verdict["skip_reasons"]
                    for reason in ["weather_data_missing", "weather_data_stale"]
                ),
                "mapping_ok": "missing_rule_mapping" not in verdict["skip_reasons"],
                "unit_ok": "unit_mismatch" not in verdict["skip_reasons"],
            }
            mkt["last_scan_at"] = snap.get("ts")
            mkt["last_scan_reason"] = (
                verdict["skip_reasons"][0] if verdict["skip_reasons"] else None
            )

            if not verdict["admissible"]:
                if mkt.get("reserved_exposure") and not mkt["reserved_exposure"].get(
                    "release_reason"
                ):
                    release_reserved_exposure(
                        mkt,
                        risk_state,
                        "market_no_longer_ready",
                        released_at=snap.get("ts"),
                    )
                mkt["last_scan_status"] = "skipped"
                mkt["all_outcomes"] = []
                mkt["bucket_probabilities"] = []
                mkt["quote_snapshot"] = []
                mkt["candidate_assessments"] = []
                mkt["route_decisions"] = []
                save_market(mkt)
                print(
                    f"  [SKIP] {loc['name']} {date} — {mkt['last_scan_reason'] or 'guardrail_rejected'}"
                )
                time.sleep(0.1)
                continue

            mkt["last_scan_status"] = "ready"

            # Update outcomes list — prices taken directly from event
            outcomes = []
            event_markets = {
                str(market.get("id", "")): market for market in event.get("markets", [])
            }
            for contract in mkt["market_contracts"]:
                market = event_markets.get(contract.get("market_id"))
                if not market:
                    continue
                try:
                    prices = json.loads(market.get("outcomePrices", "[0.5,0.5]"))
                    bid = float(prices[0])
                    ask = float(prices[1]) if len(prices) > 1 else bid
                except Exception:
                    continue
                outcomes.append(
                    {
                        "question": contract["question"],
                        "market_id": contract["market_id"],
                        "range": contract["range"],
                        "condition_id": contract["condition_id"],
                        "token_id_yes": contract["token_id_yes"],
                        "token_id_no": contract["token_id_no"],
                        "unit": contract.get("unit"),
                        "bid": round(bid, 4),
                        "ask": round(ask, 4),
                        "price": round(bid, 4),  # for compatibility
                        "spread": round(ask - bid, 4),
                        "volume": round(float(market.get("volume", 0)), 0),
                    }
                )

            outcomes.sort(key=lambda x: x["range"][0])
            mkt["all_outcomes"] = outcomes
            mkt["bucket_probabilities"] = aggregate_probability(
                mkt["market_contracts"],
                {
                    "ecmwf": snap.get("ecmwf"),
                    "hrrr": snap.get("hrrr"),
                    "metar_anchor": snap.get("metar"),
                },
                city_slug=city_slug,
            )
            mkt["quote_snapshot"] = build_quote_snapshot(mkt["market_contracts"])
            mkt["candidate_assessments"] = build_candidate_assessments(
                mkt["bucket_probabilities"],
                mkt["quote_snapshot"],
                hours,
            )
            reconcile_market_reservation(
                mkt, risk_state, RISK_ROUTER, reserved_at=snap.get("ts")
            )

            # Forecast snapshot
            forecast_snap = {
                "ts": snap.get("ts"),
                "horizon": horizon,
                "hours_left": round(hours, 1),
                "ecmwf": snap.get("ecmwf"),
                "hrrr": snap.get("hrrr"),
                "metar": snap.get("metar"),
                "best": snap.get("best"),
                "best_source": snap.get("best_source"),
            }
            mkt["forecast_snapshots"].append(forecast_snap)

            # Market price snapshot
            top = max(outcomes, key=lambda x: x["price"]) if outcomes else None
            market_snap = {
                "ts": snap.get("ts"),
                "top_bucket": f"{top['range'][0]}-{top['range'][1]}{unit_sym}"
                if top
                else None,
                "top_price": top["price"] if top else None,
            }
            mkt["market_snapshots"].append(market_snap)

            forecast_temp = snap.get("best")
            best_source = snap.get("best_source")

            # --- STOP-LOSS AND TRAILING STOP ---
            if mkt.get("position") and mkt["position"].get("status") == "open":
                pos = mkt["position"]
                current_price = None
                for o in outcomes:
                    if o["market_id"] == pos["market_id"]:
                        current_price = o["price"]
                        break

                if current_price is not None:
                    current_price = o.get("bid", current_price)  # sell at bid
                    entry = pos["entry_price"]
                    stop = pos.get("stop_price", entry * 0.80)  # 20% stop by default

                    # Trailing: if up 20%+ — move stop to breakeven
                    if current_price >= entry * 1.20 and stop < entry:
                        pos["stop_price"] = entry
                        pos["trailing_activated"] = True

                    # Check stop
                    if current_price <= stop:
                        pnl = round((current_price - entry) * pos["shares"], 2)
                        balance += pos["cost"] + pnl
                        pos["closed_at"] = snap.get("ts")
                        pos["close_reason"] = (
                            "stop_loss" if current_price < entry else "trailing_stop"
                        )
                        pos["exit_price"] = current_price
                        pos["pnl"] = pnl
                        pos["status"] = "closed"
                        closed += 1
                        reason = "STOP" if current_price < entry else "TRAILING BE"
                        print(
                            f"  [{reason}] {loc['name']} {date} | entry ${entry:.3f} exit ${current_price:.3f} | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
                        )

            # --- CLOSE POSITION if forecast shifted 2+ degrees ---
            if mkt.get("position") and forecast_temp is not None:
                pos = mkt["position"]
                old_bucket_low = pos["bucket_low"]
                old_bucket_high = pos["bucket_high"]
                # 2-degree buffer — avoid closing on small forecast fluctuations
                unit = loc["unit"]
                buffer = 2.0 if unit == "F" else 1.0
                mid_bucket = (
                    (old_bucket_low + old_bucket_high) / 2
                    if old_bucket_low != -999 and old_bucket_high != 999
                    else forecast_temp
                )
                forecast_far = abs(forecast_temp - mid_bucket) > (
                    abs(mid_bucket - old_bucket_low) + buffer
                )
                if (
                    not in_bucket(forecast_temp, old_bucket_low, old_bucket_high)
                    and forecast_far
                ):
                    current_price = None
                    for o in outcomes:
                        if o["market_id"] == pos["market_id"]:
                            current_price = o["price"]
                            break
                    if current_price is not None:
                        pnl = round(
                            (current_price - pos["entry_price"]) * pos["shares"], 2
                        )
                        balance += pos["cost"] + pnl
                        mkt["position"]["closed_at"] = snap.get("ts")
                        mkt["position"]["close_reason"] = "forecast_changed"
                        mkt["position"]["exit_price"] = current_price
                        mkt["position"]["pnl"] = pnl
                        mkt["position"]["status"] = "closed"
                        closed += 1
                        print(
                            f"  [CLOSE] {loc['name']} {date} — forecast changed | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
                        )

            # --- OPEN POSITION ---
            if (
                not mkt.get("position")
                and forecast_temp is not None
                and hours >= MIN_HOURS
            ):
                sigma = get_sigma(city_slug, best_source or "ecmwf")
                best_signal = None

                # Find exactly ONE bucket that matches the forecast
                # If forecast doesn't fit any bucket cleanly — skip this market
                matched_bucket = None
                for o in outcomes:
                    t_low, t_high = o["range"]
                    if in_bucket(forecast_temp, t_low, t_high):
                        matched_bucket = o
                        break

                if matched_bucket:
                    approved_yes_route = next(
                        (
                            route
                            for route in mkt.get("route_decisions", [])
                            if route.get("status") == "accepted"
                            and route.get("strategy_leg") == "YES_SNIPER"
                            and tuple(route.get("range") or ())
                            == tuple(matched_bucket.get("range") or ())
                        ),
                        None,
                    )
                    if not approved_yes_route:
                        matched_bucket = None

                if matched_bucket:
                    o = matched_bucket
                    t_low, t_high = o["range"]
                    volume = o["volume"]
                    quote_entry = next(
                        (
                            q
                            for q in mkt.get("quote_snapshot", [])
                            if q.get("market_id") == o.get("market_id")
                        ),
                        None,
                    )
                    yes_quote = quote_entry.get("yes", {}) if quote_entry else {}
                    bid = yes_quote.get("bid")
                    ask = yes_quote.get("ask")
                    spread = yes_quote.get("spread")

                    # All filters — if any fails, skip this market entirely
                    if (
                        quote_entry
                        and quote_entry.get("execution_ok")
                        and bid is not None
                        and ask is not None
                        and spread is not None
                        and volume >= MIN_VOLUME
                    ):
                        p = bucket_prob(forecast_temp, t_low, t_high, sigma)
                        ev = calc_ev(p, ask)
                        if ev >= MIN_EV:
                            kelly = calc_kelly(p, ask)
                            size = bet_size(kelly, balance)
                            if size >= 0.50:
                                best_signal = {
                                    "market_id": o["market_id"],
                                    "question": o["question"],
                                    "bucket_low": t_low,
                                    "bucket_high": t_high,
                                    "entry_price": ask,
                                    "bid_at_entry": bid,
                                    "spread": spread,
                                    "shares": round(size / ask, 2),
                                    "cost": size,
                                    "p": round(p, 4),
                                    "ev": round(ev, 4),
                                    "kelly": round(kelly, 4),
                                    "forecast_temp": forecast_temp,
                                    "forecast_src": best_source,
                                    "sigma": sigma,
                                    "opened_at": snap.get("ts"),
                                    "status": "open",
                                    "pnl": None,
                                    "exit_price": None,
                                    "close_reason": None,
                                    "closed_at": None,
                                }

                if best_signal:
                    if (
                        best_signal["spread"] <= MAX_SLIPPAGE
                        and best_signal["entry_price"] < MAX_PRICE
                    ):
                        balance -= best_signal["cost"]
                        mkt["position"] = best_signal
                        state["total_trades"] += 1
                        new_pos += 1
                        bucket_label = f"{best_signal['bucket_low']}-{best_signal['bucket_high']}{unit_sym}"
                        print(
                            f"  [BUY]  {loc['name']} {horizon} {date} | {bucket_label} | "
                            f"${best_signal['entry_price']:.3f} | EV {best_signal['ev']:+.2f} | "
                            f"${best_signal['cost']:.2f} ({best_signal['forecast_src'].upper()})"
                        )

            # Market closed by time
            if hours < 0.5 and mkt["status"] == "open":
                mkt["status"] = "closed"

            save_market(mkt)
            time.sleep(0.1)

        print("ok")

    # --- AUTO-RESOLUTION ---
    for mkt in load_all_markets():
        if mkt["status"] == "resolved":
            continue

        pos = mkt.get("position")
        if not pos or pos.get("status") != "open":
            continue

        market_id = pos.get("market_id")
        if not market_id:
            continue

        # Check if market closed on Polymarket
        won = check_market_resolved(market_id)
        if won is None:
            continue  # market still open

        # Market closed — record result
        price = pos["entry_price"]
        size = pos["cost"]
        shares = pos["shares"]
        pnl = round(shares * (1 - price), 2) if won else round(-size, 2)

        balance += size + pnl
        pos["exit_price"] = 1.0 if won else 0.0
        pos["pnl"] = pnl
        pos["close_reason"] = "resolved"
        pos["closed_at"] = now.isoformat()
        pos["status"] = "closed"
        mkt["pnl"] = pnl
        mkt["status"] = "resolved"
        mkt["resolved_outcome"] = "win" if won else "loss"

        if won:
            state["wins"] += 1
        else:
            state["losses"] += 1

        result = "WIN" if won else "LOSS"
        print(
            f"  [{result}] {mkt['city_name']} {mkt['date']} | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
        )
        resolved += 1

        save_market(mkt)
        time.sleep(0.3)

    state["balance"] = round(balance, 2)
    state["peak_balance"] = max(state.get("peak_balance", balance), balance)
    state["risk_state"] = risk_state
    save_state(state)

    # Run calibration if enough data collected
    all_mkts = load_all_markets()
    resolved_count = len([m for m in all_mkts if m["status"] == "resolved"])
    if resolved_count >= CALIBRATION_MIN:
        global _cal
        _cal = run_calibration(all_mkts)

    return new_pos, closed, resolved


# =============================================================================
# REPORT
# =============================================================================


def format_bucket_label(contract):
    rng = contract.get("range") or (None, None)
    unit = contract.get("unit") or ""
    low, high = rng
    if low is None or high is None:
        return "unknown"
    return f"{low}-{high}{unit}"


def format_resolution_text(text, limit=120):
    summary = " ".join((text or "").split())
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3].rstrip() + "..."


def format_quote_context(quote_context):
    if not quote_context:
        return "quote=unknown"
    parts = []
    if quote_context.get("ask") is not None:
        parts.append(f"ask={quote_context['ask']:.2f}")
    if quote_context.get("bid") is not None:
        parts.append(f"bid={quote_context['bid']:.2f}")
    if quote_context.get("book_ok") is not None:
        parts.append(f"book_ok={quote_context['book_ok']}")
    return "quote=" + " ".join(parts) if parts else "quote=unknown"


def print_candidate_assessments(markets):
    entries = []
    for m in sorted(markets, key=lambda x: (x.get("date", ""), x.get("city", ""))):
        for assessment in m.get("candidate_assessments", []) or []:
            entries.append((m, assessment))

    if not entries:
        return

    print(f"\n  Candidate assessments: {len(entries)}")
    for market, assessment in entries:
        rng = assessment.get("range") or (None, None)
        bucket = (
            f"{rng[0]}-{rng[1]}"
            if rng[0] is not None and rng[1] is not None
            else "unknown"
        )
        reasons = ",".join(assessment.get("reasons", [])) or "none"
        fair_price = assessment.get("fair_price")
        fair_text = (
            f"fair={fair_price:.3f}" if fair_price is not None else "fair=unknown"
        )
        quote_text = format_quote_context(assessment.get("quote_context", {}))
        print(
            f"    {market['city_name']:<16} {market['date']} | {assessment.get('strategy_leg')} | {bucket} | "
            f"status={assessment.get('status')} | reasons={reasons} | {fair_text} | {quote_text}"
        )


def print_scan_summary(markets):
    accepted = [m for m in markets if m.get("last_scan_status") == "ready"]
    skipped = [m for m in markets if m.get("last_scan_status") == "skipped"]

    if not accepted and not skipped:
        return

    print(f"\n  Accepted scan markets: {len(accepted)}")
    if accepted:
        for m in sorted(accepted, key=lambda x: (x["date"], x["city"])):
            metadata = m.get("resolution_metadata", {})
            station = metadata.get("station") or m.get("station") or "?"
            unit = metadata.get("unit") or m.get("unit") or ""
            resolution_text = format_resolution_text(metadata.get("resolution_text"))
            contract = (m.get("market_contracts") or [{}])[0]
            bucket = format_bucket_label(contract)
            market_id = contract.get("market_id") or "unknown"
            condition_id = contract.get("condition_id") or "unknown"
            token_id_yes = contract.get("token_id_yes") or "unknown"
            token_id_no = contract.get("token_id_no") or "unknown"
            print(
                f"    {m['city_name']:<16} {m['date']} | {station} | {bucket:<12} | {market_id} | {unit} | resolution_text={resolution_text} | condition_id={condition_id} | token_id_yes={token_id_yes} | token_id_no={token_id_no}"
            )

    print(f"\n  Skipped scan markets: {len(skipped)}")
    if skipped:
        for m in sorted(skipped, key=lambda x: (x["date"], x["city"])):
            reasons = ", ".join(m.get("scan_guardrails", {}).get("skip_reasons", []))
            if not reasons:
                reasons = m.get("last_scan_reason") or "unknown"
            print(f"    {m['city_name']:<16} {m['date']} | {reasons}")

    print_candidate_assessments(markets)


def print_risk_summary(state):
    risk_state = state.get("risk_state") or {}
    if not risk_state:
        return

    bankroll = float(risk_state.get("bankroll", 0.0) or 0.0)
    global_reserved = float(risk_state.get("global_reserved_worst_loss", 0.0) or 0.0)
    usage_pct = (global_reserved / bankroll * 100.0) if bankroll else 0.0

    print(f"\n  Risk usage")
    for leg in ["YES_SNIPER", "NO_CARRY"]:
        leg_state = (risk_state.get("legs", {}) or {}).get(leg, {}) or {}
        budget = float(leg_state.get("budget", 0.0) or 0.0)
        reserved = float(leg_state.get("reserved", 0.0) or 0.0)
        available = max(0.0, budget - reserved)
        print(
            f"    {leg:<10} budget={budget:.2f} reserved={reserved:.2f} available={available:.2f}"
        )
    print(
        f"    global_reserved_worst_loss={global_reserved:.2f} usage={usage_pct:.1f}%"
    )


def print_exposure_summary(state):
    risk_state = state.get("risk_state") or {}
    if not risk_state:
        return

    sections = [
        ("City exposure", risk_state.get("city_exposure", {}) or {}),
        ("Date exposure", risk_state.get("date_exposure", {}) or {}),
        ("Event exposure", risk_state.get("event_exposure", {}) or {}),
    ]
    for title, ledger in sections:
        print(f"\n  {title}")
        if not ledger:
            print("    none")
            continue
        for key, value in sorted(ledger.items()):
            print(f"    {key}: {float(value):.2f}")


def print_route_decision_summary(markets):
    accepted = 0
    rejected = 0
    released = 0
    reason_counts = {}

    for market in markets:
        for decision in market.get("route_decisions", []) or []:
            status = decision.get("status")
            if status == "accepted":
                accepted += 1
            elif status == "rejected":
                rejected += 1
            for reason in decision.get("reasons", []) or []:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        reservation = market.get("reserved_exposure")
        if reservation and reservation.get("release_reason"):
            released += 1
            reason = reservation.get("release_reason")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    print(
        f"\n  Route decisions: accepted={accepted} rejected={rejected} released={released}"
    )
    if not reason_counts:
        print("    reasons=none")
        return
    summary = ", ".join(
        f"{reason}={count}" for reason, count in sorted(reason_counts.items())
    )
    print(f"    reasons={summary}")


def print_status():
    state = load_state()
    markets = load_all_markets()
    open_pos = [
        m
        for m in markets
        if m.get("position") and m["position"].get("status") == "open"
    ]
    resolved = [
        m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None
    ]

    bal = state["balance"]
    start = state["starting_balance"]
    ret_pct = (bal - start) / start * 100
    wins = state["wins"]
    losses = state["losses"]
    total = wins + losses

    print(f"\n{'=' * 55}")
    print(f"  WEATHERBET — STATUS")
    print(f"{'=' * 55}")
    print(
        f"  Balance:     ${bal:,.2f}  (start ${start:,.2f}, {'+' if ret_pct >= 0 else ''}{ret_pct:.1f}%)"
    )
    print(
        f"  Trades:      {total} | W: {wins} | L: {losses} | WR: {wins / total:.0%}"
        if total
        else "  No trades yet"
    )
    print(f"  Open:        {len(open_pos)}")
    print(f"  Resolved:    {len(resolved)}")

    print_risk_summary(state)
    print_scan_summary(markets)
    print_route_decision_summary(markets)

    if open_pos:
        print(f"\n  Open positions:")
        total_unrealized = 0.0
        for m in open_pos:
            pos = m["position"]
            unit_sym = "F" if m["unit"] == "F" else "C"
            label = f"{pos['bucket_low']}-{pos['bucket_high']}{unit_sym}"

            # Current price from latest market snapshot
            current_price = pos["entry_price"]
            snaps = m.get("market_snapshots", [])
            if snaps:
                # Find our bucket price in all_outcomes
                for o in m.get("all_outcomes", []):
                    if o["market_id"] == pos["market_id"]:
                        current_price = o["price"]
                        break

            unrealized = round((current_price - pos["entry_price"]) * pos["shares"], 2)
            total_unrealized += unrealized
            pnl_str = f"{'+' if unrealized >= 0 else ''}{unrealized:.2f}"

            print(
                f"    {m['city_name']:<16} {m['date']} | {label:<14} | "
                f"entry ${pos['entry_price']:.3f} -> ${current_price:.3f} | "
                f"PnL: {pnl_str} | {pos['forecast_src'].upper()}"
            )

        sign = "+" if total_unrealized >= 0 else ""
        print(f"\n  Unrealized PnL: {sign}{total_unrealized:.2f}")

    print(f"{'=' * 55}\n")


def print_report():
    state = load_state()
    markets = load_all_markets()
    resolved = [
        m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None
    ]

    print(f"\n{'=' * 55}")
    print(f"  WEATHERBET — FULL REPORT")
    print(f"{'=' * 55}")

    print_risk_summary(state)
    print_exposure_summary(state)
    print_scan_summary(markets)
    print_route_decision_summary(markets)

    if not resolved:
        print("  No resolved markets yet.")
        return

    total_pnl = sum(m["pnl"] for m in resolved)
    wins = [m for m in resolved if m["resolved_outcome"] == "win"]
    losses = [m for m in resolved if m["resolved_outcome"] == "loss"]

    print(f"\n  Total resolved: {len(resolved)}")
    print(f"  Wins:           {len(wins)} | Losses: {len(losses)}")
    print(f"  Win rate:       {len(wins) / len(resolved):.0%}")
    print(f"  Total PnL:      {'+' if total_pnl >= 0 else ''}{total_pnl:.2f}")

    print(f"\n  By city:")
    for city in sorted(set(m["city"] for m in resolved)):
        group = [m for m in resolved if m["city"] == city]
        w = len([m for m in group if m["resolved_outcome"] == "win"])
        pnl = sum(m["pnl"] for m in group)
        name = LOCATIONS[city]["name"]
        print(
            f"    {name:<16} {w}/{len(group)} ({w / len(group):.0%})  PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
        )

    print(f"\n  Market details:")
    for m in sorted(resolved, key=lambda x: x["date"]):
        pos = m.get("position", {})
        unit_sym = "F" if m["unit"] == "F" else "C"
        snaps = m.get("forecast_snapshots", [])
        first_fc = snaps[0]["best"] if snaps else None
        last_fc = snaps[-1]["best"] if snaps else None
        label = (
            f"{pos.get('bucket_low')}-{pos.get('bucket_high')}{unit_sym}"
            if pos
            else "no position"
        )
        result = m["resolved_outcome"].upper()
        pnl_str = (
            f"{'+' if m['pnl'] >= 0 else ''}{m['pnl']:.2f}"
            if m["pnl"] is not None
            else "-"
        )
        fc_str = (
            f"forecast {first_fc}->{last_fc}{unit_sym}" if first_fc else "no forecast"
        )
        actual = f"actual {m['actual_temp']}{unit_sym}" if m["actual_temp"] else ""
        print(
            f"    {m['city_name']:<16} {m['date']} | {label:<14} | {fc_str} | {actual} | {result} {pnl_str}"
        )

    print(f"{'=' * 55}\n")


# =============================================================================
# MAIN LOOP
# =============================================================================

MONITOR_INTERVAL = 600  # monitor positions every 10 minutes


def monitor_positions():
    """Quick stop check on open positions without full scan."""
    markets = load_all_markets()
    open_pos = [
        m
        for m in markets
        if m.get("position") and m["position"].get("status") == "open"
    ]
    if not open_pos:
        return 0

    state = load_state()
    balance = state["balance"]
    closed = 0

    for mkt in open_pos:
        pos = mkt["position"]
        mid = pos["market_id"]

        current_price = None

        quote_entry = next(
            (q for q in mkt.get("quote_snapshot", []) if q.get("market_id") == mid),
            None,
        )
        yes_token_id = None
        if quote_entry:
            yes_token_id = quote_entry.get("yes", {}).get("token_id")
        if yes_token_id is None:
            for o in mkt.get("all_outcomes", []):
                if o["market_id"] == mid:
                    yes_token_id = o.get("token_id_yes")
                    break

        if yes_token_id:
            quote = get_token_quote_snapshot(yes_token_id, "yes")
            if quote.get("book_ok") and quote.get("bid") is not None:
                current_price = quote["bid"]

        # Fallback to cached price if API failed
        if current_price is None:
            for o in mkt.get("all_outcomes", []):
                if o["market_id"] == mid:
                    current_price = o.get("bid", o["price"])
                    break

        if current_price is None:
            continue

        entry = pos["entry_price"]
        stop = pos.get("stop_price", entry * 0.80)
        city_name = LOCATIONS.get(mkt["city"], {}).get("name", mkt["city"])

        # Hours left to resolution
        end_date = mkt.get("event_end_date", "")
        hours_left = hours_to_resolution(end_date) if end_date else 999.0

        # Take-profit threshold based on hours to resolution
        if hours_left < 24:
            take_profit = None  # hold to resolution
        elif hours_left < 48:
            take_profit = 0.85  # 24-48h: take profit at $0.85
        else:
            take_profit = 0.75  # 48h+: take profit at $0.75

        # Trailing: if up 20%+ — move stop to breakeven
        if current_price >= entry * 1.20 and stop < entry:
            pos["stop_price"] = entry
            pos["trailing_activated"] = True
            print(
                f"  [TRAILING] {city_name} {mkt['date']} — stop moved to breakeven ${entry:.3f}"
            )

        # Check take-profit
        take_triggered = take_profit is not None and current_price >= take_profit
        # Check stop
        stop_triggered = current_price <= stop

        if take_triggered or stop_triggered:
            pnl = round((current_price - entry) * pos["shares"], 2)
            balance += pos["cost"] + pnl
            pos["closed_at"] = datetime.now(timezone.utc).isoformat()
            if take_triggered:
                pos["close_reason"] = "take_profit"
                reason = "TAKE"
            elif current_price < entry:
                pos["close_reason"] = "stop_loss"
                reason = "STOP"
            else:
                pos["close_reason"] = "trailing_stop"
                reason = "TRAILING BE"
            pos["exit_price"] = current_price
            pos["pnl"] = pnl
            pos["status"] = "closed"
            closed += 1
            print(
                f"  [{reason}] {city_name} {mkt['date']} | entry ${entry:.3f} exit ${current_price:.3f} | {hours_left:.0f}h left | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
            )
            save_market(mkt)

    if closed:
        state["balance"] = round(balance, 2)
        save_state(state)

    return closed


def run_loop():
    global _cal
    _cal = load_cal()

    print(f"\n{'=' * 55}")
    print(f"  WEATHERBET — STARTING")
    print(f"{'=' * 55}")
    print(f"  Cities:     {len(LOCATIONS)}")
    print(f"  Balance:    ${BALANCE:,.0f} | Max bet: ${MAX_BET}")
    print(
        f"  Scan:       {SCAN_INTERVAL // 60} min | Monitor: {MONITOR_INTERVAL // 60} min"
    )
    print(f"  Sources:    ECMWF + HRRR(US) + METAR(D+0)")
    print(f"  Data:       {DATA_DIR.resolve()}")
    print(f"  Ctrl+C to stop\n")

    last_full_scan = 0

    while True:
        now_ts = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Full scan once per hour
        if now_ts - last_full_scan >= SCAN_INTERVAL:
            print(f"[{now_str}] full scan...")
            try:
                new_pos, closed, resolved = scan_and_update()
                state = load_state()
                print(
                    f"  balance: ${state['balance']:,.2f} | "
                    f"new: {new_pos} | closed: {closed} | resolved: {resolved}"
                )
                last_full_scan = time.time()
            except KeyboardInterrupt:
                print(f"\n  Stopping — saving state...")
                save_state(load_state())
                print(f"  Done. Bye!")
                break
            except requests.exceptions.ConnectionError:
                print(f"  Connection lost — waiting 60 sec")
                time.sleep(60)
                continue
            except Exception as e:
                print(f"  Error: {e} — waiting 60 sec")
                time.sleep(60)
                continue
        else:
            # Quick stop monitoring
            print(f"[{now_str}] monitoring positions...")
            try:
                stopped = monitor_positions()
                if stopped:
                    state = load_state()
                    print(f"  balance: ${state['balance']:,.2f}")
            except Exception as e:
                print(f"  Monitor error: {e}")

        try:
            time.sleep(MONITOR_INTERVAL)
        except KeyboardInterrupt:
            print(f"\n  Stopping — saving state...")
            save_state(load_state())
            print(f"  Done. Bye!")
            break


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run_loop()
    elif cmd == "status":
        _cal = load_cal()
        print_status()
    elif cmd == "report":
        _cal = load_cal()
        print_report()
    else:
        print("Usage: python weatherbet.py [run|status|report]")
