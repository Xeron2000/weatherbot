import json

from .paths import CONFIG_FILE


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

def load_paper_execution_config(config_dict):
    raw = config_dict.get("paper_execution")
    if not isinstance(raw, dict):
        raise ValueError("paper_execution_missing_block")

    spec = {
        "submission_latency_ms": {"type": int, "min": 1},
        "queue_ahead_shares": {"type": float, "min": 0.0},
        "queue_ahead_ratio": {"type": float, "min": 0.0, "max": 1.0},
        "touch_not_fill_min_touches": {"type": int, "min": 1},
        "partial_fill_slice_ratio": {"type": float, "min": 0.000001, "max": 1.0},
        "cancel_latency_ms": {"type": int, "min": 1},
        "adverse_fill_buffer_ticks": {"type": int, "min": 0},
    }

    loaded = {}
    for key, rules in spec.items():
        if key not in raw:
            raise ValueError(f"paper_execution_missing_{key}")
        value = raw.get(key)
        try:
            value = rules["type"](value)
        except Exception:
            raise ValueError(f"paper_execution_invalid_{key}")
        if value < rules["min"]:
            raise ValueError(f"paper_execution_invalid_{key}")
        if "max" in rules and value > rules["max"]:
            raise ValueError(f"paper_execution_invalid_{key}")
        loaded[key] = value
    return loaded

def load_config(config_path=CONFIG_FILE):
    with open(config_path, encoding="utf-8") as handle:
        return json.load(handle)
