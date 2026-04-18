import json
import re
import requests

from datetime import datetime, timezone


WEATHER_FRESHNESS_HOURS = 6.0


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

