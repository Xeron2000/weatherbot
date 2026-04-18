import json
import math
import time
import requests

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from . import paper_execution
from .config import load_config
from .domain import TIMEZONES
from .polymarket import normalize_skip_reasons, quote_for_side


_cfg = load_config()

MIN_HOURS = _cfg.get("min_hours", 2.0)
MAX_HOURS = _cfg.get("max_hours", 72.0)
KELLY_FRACTION = _cfg.get("kelly_fraction", 0.25)
NO_KELLY_FRACTION = _cfg.get("no_kelly_fraction", 1.0)
MAX_BET = _cfg.get("max_bet", 20.0)
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
        "max_ask": 0.95,
        "min_probability": 0.70,
        "min_edge": 0.04,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
        "max_size": 20.0,
        "min_size": 1.0,
    },
)


YES_PEAK_WINDOW_END_HOUR = 15
YES_PEAK_WINDOW_NEAR_BUFFER = 1.0
YES_PEAK_WINDOW_PENALTY = 0.35
MONITOR_INTERVAL = 600


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

def get_local_now(city_slug, now_ts=None):
    tz_name = TIMEZONES.get(city_slug, "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    if now_ts:
        try:
            parsed = datetime.fromisoformat(str(now_ts).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(tz)
        except Exception:
            pass

    return datetime.now(timezone.utc).astimezone(tz)

def assess_yes_peak_window_penalty(bucket_probability, market_context=None):
    context = market_context or {}
    city_slug = context.get("city_slug")
    market_date = context.get("market_date")
    metar_temp = context.get("metar")
    rng = bucket_probability.get("range") if bucket_probability else None

    result = {
        "applied": False,
        "penalty_factor": 1.0,
        "reason": None,
        "local_time": None,
    }

    if not city_slug or not market_date or metar_temp is None or not rng:
        return result
    if rng[0] == -999 or rng[1] == 999:
        return result

    local_now = get_local_now(city_slug, context.get("now_ts"))
    result["local_time"] = local_now.isoformat()
    market_day = str(market_date).split("T", 1)[0]
    if market_day != local_now.strftime("%Y-%m-%d"):
        return result
    if local_now.hour < YES_PEAK_WINDOW_END_HOUR:
        return result

    try:
        observed = float(metar_temp)
        t_low, t_high = rng
    except Exception:
        return result

    if observed > float(t_high):
        result["applied"] = True
        result["penalty_factor"] = 0.0
        result["reason"] = "yes_peak_window_metar_above_bucket"
        return result

    if observed >= float(t_high) - YES_PEAK_WINDOW_NEAR_BUFFER:
        result["applied"] = True
        result["penalty_factor"] = YES_PEAK_WINDOW_PENALTY
        result["reason"] = "yes_peak_window_metar_near_bucket_ceiling"

    return result

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

def evaluate_yes_candidate(
    bucket_probability, quote_snapshot, hours, market_context=None
):
    reasons = []
    quote = quote_for_side(quote_snapshot, "yes")
    raw_probability = float(bucket_probability.get("aggregate_probability", 0.0) or 0.0)
    peak_window_penalty = assess_yes_peak_window_penalty(
        bucket_probability, market_context
    )
    adjusted_probability = round(
        raw_probability * peak_window_penalty.get("penalty_factor", 1.0), 6
    )
    fair_price = adjusted_probability
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
    if peak_window_penalty.get("applied") and peak_window_penalty.get("reason"):
        reasons.append(peak_window_penalty["reason"])
    if adjusted_probability < YES_STRATEGY.get("min_probability", 0.0):
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
        "adjusted_probability": adjusted_probability,
        "fair_price": fair_price,
        "fair_yes": fair_price,
        "fair_no": bucket_probability.get("fair_no"),
        "quote_context": quote,
        "status": status,
        "reasons": normalize_skip_reasons(reasons),
        "size_multiplier": size_multiplier,
        "edge": edge,
        "probability_penalty_factor": peak_window_penalty.get("penalty_factor", 1.0),
        "probability_penalty_reason": peak_window_penalty.get("reason"),
        "probability_local_time": peak_window_penalty.get("local_time"),
    }

def evaluate_no_candidate(bucket_probability, quote_snapshot, hours):
    reasons = []
    quote = quote_for_side(quote_snapshot, "no")
    fair_price = bucket_probability.get("fair_no")
    ask = quote.get("ask")
    target_price, target_reason = paper_execution.compute_passive_limit_price(
        quote, paper_execution.ORDER_POLICY
    )
    max_ask = NO_STRATEGY.get("max_ask")
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
    if target_reason:
        reasons.append("missing_quote_price")
    if target_price is not None and target_price < NO_STRATEGY.get("min_price", 0.0):
        reasons.append("price_below_min")
    if ask is not None and max_ask is not None and ask > max_ask:
        reasons.append("ask_above_max")
    if bucket_probability.get("fair_no", 0.0) < NO_STRATEGY.get("min_probability", 0.0):
        reasons.append("probability_below_min")

    edge = (
        round((fair_price or 0.0) - target_price, 6)
        if target_price is not None
        else None
    )
    if edge is None:
        status = "rejected"
        size_multiplier = 0.0
    else:
        size_multiplier, status = determine_size_multiplier(
            edge, NO_STRATEGY.get("min_edge", 0.0)
        )
    if "price_below_min" in reasons or "ask_above_max" in reasons:
        status = "reprice"
        size_multiplier = 0.0
    if any(reason not in {"price_below_min", "ask_above_max"} for reason in reasons):
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

def build_candidate_assessments(
    bucket_probabilities, quote_snapshot, hours, market_context=None
):
    assessments = []
    quote_by_market = {entry.get("market_id"): entry for entry in quote_snapshot or []}
    for bucket in bucket_probabilities or []:
        quote = quote_by_market.get(bucket.get("market_id"), {})
        yes_candidate = evaluate_yes_candidate(bucket, quote, hours, market_context)
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

def sizing_fraction_for_leg(strategy_leg):
    if strategy_leg == "NO_CARRY":
        return float(NO_KELLY_FRACTION or 1.0)
    return 1.0

def candidate_worst_loss(assessment, bankroll):
    strategy_leg = assessment.get("strategy_leg")
    strategy = strategy_for_leg(strategy_leg)
    max_size = float(strategy.get("max_size", 0.0) or 0.0)
    min_size = float(strategy.get("min_size", 0.0) or 0.0)
    size_multiplier = float(assessment.get("size_multiplier", 0.0) or 0.0)
    sizing_fraction = sizing_fraction_for_leg(strategy_leg)
    effective_max_size = max_size * sizing_fraction

    if effective_max_size <= 0 or size_multiplier <= 0:
        return 0.0

    worst_loss = effective_max_size * size_multiplier
    if worst_loss < min_size:
        worst_loss = min_size
    return round(min(effective_max_size, worst_loss), 2)

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

def position_entry_side(position):
    return (position or {}).get("token_side") or (position or {}).get("entry_side")

def find_market_quote_entry(market, market_id):
    return next(
        (
            quote
            for quote in market.get("quote_snapshot", []) or []
            if quote.get("market_id") == market_id
        ),
        None,
    )

def resolve_position_token_id(market, market_id, side):
    quote_entry = find_market_quote_entry(market, market_id)
    token_id = quote_for_side(quote_entry, side).get("token_id")
    if token_id:
        return token_id

    token_key = "token_id_yes" if side == "yes" else "token_id_no"
    for outcome in market.get("all_outcomes", []) or []:
        if outcome.get("market_id") == market_id:
            return outcome.get(token_key)
    return None

def resolve_position_exit_price(market, position, outcomes=None, refresh_live=False):
    side = position_entry_side(position)
    market_id = (position or {}).get("market_id")
    outcome_rows = outcomes if outcomes is not None else market.get("all_outcomes", []) or []

    if side in {"yes", "no"}:
        token_id = resolve_position_token_id(market, market_id, side)
        if refresh_live and token_id:
            quote = get_token_quote_snapshot(token_id, side)
            if quote.get("book_ok") and quote.get("bid") is not None:
                return quote["bid"]

        quote_entry = find_market_quote_entry(market, market_id)
        side_quote = quote_for_side(quote_entry, side)
        if side_quote.get("bid") is not None:
            return side_quote.get("bid")

    else:
        token_id = resolve_position_token_id(market, market_id, "yes")
        if refresh_live and token_id:
            quote = get_token_quote_snapshot(token_id, "yes")
            if quote.get("book_ok") and quote.get("bid") is not None:
                return quote["bid"]

    for outcome in outcome_rows:
        if outcome.get("market_id") == market_id:
            return outcome.get("bid", outcome.get("price"))
    return None

def evaluate_position_stop_rule(position, current_price):
    side = position_entry_side(position)
    entry = float((position or {}).get("entry_price", 0.0) or 0.0)

    if side == "yes":
        return {
            "side": side,
            "legacy": False,
            "trailing_enabled": False,
            "stop_triggered": False,
            "stop_price": None,
        }

    if side == "no":
        high_price_stop = entry >= 0.80
        return {
            "side": side,
            "legacy": False,
            "trailing_enabled": False,
            "stop_triggered": bool(high_price_stop and current_price is not None and current_price <= 0.70),
            "stop_price": 0.70 if high_price_stop else None,
        }

    stop = (position or {}).get("stop_price", entry * 0.80)
    return {
        "side": None,
        "legacy": True,
        "trailing_enabled": True,
        "stop_triggered": bool(current_price is not None and current_price <= stop),
        "stop_price": stop,
    }

def ensure_position_runtime_defaults(position):
    if not isinstance(position, dict):
        return position
    position.setdefault("pnl", None)
    position.setdefault("exit_price", None)
    position.setdefault("close_reason", None)
    position.setdefault("closed_at", None)
    return position

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
                sync_market_order(mkt, risk_state, snap, market_ready=False)
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
                {
                    "city_slug": city_slug,
                    "market_date": date,
                    "metar": snap.get("metar"),
                    "now_ts": snap.get("ts"),
                },
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
            order_update = sync_market_order(mkt, risk_state, snap, market_ready=True)
            if order_update.get("opened_position"):
                balance -= order_update.get("filled_cost", 0.0)
                state["total_trades"] += 1
                new_pos += 1

            # --- STOP-LOSS AND TRAILING STOP ---
            if mkt.get("position") and mkt["position"].get("status") == "open":
                pos = ensure_position_runtime_defaults(mkt["position"])
                current_price = resolve_position_exit_price(mkt, pos, outcomes=outcomes)
                if current_price is not None:
                    entry = pos["entry_price"]
                    stop_state = evaluate_position_stop_rule(pos, current_price)

                    # Trailing: legacy positions only, if up 20%+ — move stop to breakeven
                    if (
                        stop_state["trailing_enabled"]
                        and current_price >= entry * 1.20
                        and stop_state["stop_price"] < entry
                    ):
                        pos["stop_price"] = entry
                        pos["trailing_activated"] = True
                        stop_state = evaluate_position_stop_rule(pos, current_price)

                    # Check stop
                    if stop_state["stop_triggered"]:
                        pnl = round((current_price - entry) * pos["shares"], 2)
                        balance += pos["cost"] + pnl
                        pos["closed_at"] = snap.get("ts")
                        pos["close_reason"] = (
                            "trailing_stop"
                            if stop_state["legacy"] and current_price >= entry
                            else "stop_loss"
                        )
                        pos["exit_price"] = current_price
                        pos["pnl"] = pnl
                        pos["status"] = "closed"
                        closed += 1
                        reason = (
                            "TRAILING BE"
                            if stop_state["legacy"] and current_price >= entry
                            else "STOP"
                        )
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
        pos = ensure_position_runtime_defaults(mkt["position"])
        current_price = resolve_position_exit_price(mkt, pos, refresh_live=True)

        if current_price is None:
            continue

        entry = pos["entry_price"]
        stop_state = evaluate_position_stop_rule(pos, current_price)
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

        # Trailing: legacy positions only, if up 20%+ — move stop to breakeven
        if (
            stop_state["trailing_enabled"]
            and current_price >= entry * 1.20
            and stop_state["stop_price"] < entry
        ):
            pos["stop_price"] = entry
            pos["trailing_activated"] = True
            stop_state = evaluate_position_stop_rule(pos, current_price)
            print(
                f"  [TRAILING] {city_name} {mkt['date']} — stop moved to breakeven ${entry:.3f}"
            )

        # Check take-profit
        take_triggered = take_profit is not None and current_price >= take_profit
        # Check stop
        stop_triggered = stop_state["stop_triggered"]

        if take_triggered or stop_triggered:
            pnl = round((current_price - entry) * pos["shares"], 2)
            balance += pos["cost"] + pnl
            pos["closed_at"] = datetime.now(timezone.utc).isoformat()
            if take_triggered:
                pos["close_reason"] = "take_profit"
                reason = "TAKE"
            else:
                pos["close_reason"] = (
                    "trailing_stop"
                    if stop_state["legacy"] and current_price >= entry
                    else "stop_loss"
                )
                reason = (
                    "TRAILING BE"
                    if stop_state["legacy"] and current_price >= entry
                    else "STOP"
                )
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

def refresh_active_order_quotes(market):
    contracts = market.get("market_contracts", []) or []
    if not contracts:
        return market.get("quote_snapshot", []) or []
    market["quote_snapshot"] = build_quote_snapshot(contracts)
    return market["quote_snapshot"]

def monitor_active_orders():
    markets = load_all_markets()
    active_markets = [m for m in markets if is_order_unfinished(m.get("active_order"))]
    if not active_markets:
        return 0

    state = load_state()
    balance = state["balance"]
    resumed = 0

    for mkt in active_markets:
        refresh_active_order_quotes(mkt)
        forecast_snap = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "best": (mkt.get("forecast_snapshots") or [{}])[-1].get("best")
            if mkt.get("forecast_snapshots")
            else None,
            "best_source": (mkt.get("forecast_snapshots") or [{}])[-1].get(
                "best_source"
            )
            if mkt.get("forecast_snapshots")
            else None,
        }
        update = sync_market_order(
            mkt, state["risk_state"], forecast_snap, market_ready=True
        )
        if update.get("opened_position"):
            balance -= update.get("filled_cost", 0.0)
            state["total_trades"] += 1
            resumed += 1
        save_market(mkt)

    state["balance"] = round(balance, 2)
    state["risk_state"] = state.get("risk_state") or build_empty_risk_state(
        state.get("starting_balance", BALANCE), RISK_ROUTER
    )
    state["order_state"] = restore_order_state_from_markets(load_all_markets())
    save_state(state)
    return resumed

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
                resumed = monitor_active_orders()
                if stopped or resumed:
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
