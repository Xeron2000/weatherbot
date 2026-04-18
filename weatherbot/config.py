import json
import os

from .paths import CONFIG_FILE


_STRIPPED_TOP_LEVEL_KEYS = {
    "no_strategy",
    "no_kelly_fraction",
}
_STRIPPED_RISK_ROUTER_KEYS = {
    "no_budget_pct",
    "no_leg_cap_pct",
}
_STRIPPED_ORDER_POLICY_KEYS = {
    "no_time_in_force",
}


def _deep_merge_dicts(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override

    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _drop_removed_runtime_fields(config_dict):
    cleaned = dict(config_dict)

    for key in _STRIPPED_TOP_LEVEL_KEYS:
        cleaned.pop(key, None)

    risk_router = cleaned.get("risk_router")
    if isinstance(risk_router, dict):
        cleaned["risk_router"] = {
            key: value
            for key, value in risk_router.items()
            if key not in _STRIPPED_RISK_ROUTER_KEYS
        }

    order_policy = cleaned.get("order_policy")
    if isinstance(order_policy, dict):
        cleaned["order_policy"] = {
            key: value
            for key, value in order_policy.items()
            if key not in _STRIPPED_ORDER_POLICY_KEYS
        }

    return cleaned


def load_risk_router_config(config_dict):
    router = {
        "yes_budget_pct": 0.30,
        "yes_leg_cap_pct": 0.30,
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
        "gtd_buffer_hours": 6.0,
        "price_improve_ticks": 1,
        "replace_edge_buffer": 0.02,
        "max_order_hours_open": 72.0,
    }
    raw = config_dict.get("order_policy", {}) or {}
    tif_keys = ["yes_time_in_force"]
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

def load_config(config_path=None):
    if config_path is None:
        config_path = CONFIG_FILE

    with open(config_path, encoding="utf-8") as handle:
        loaded = json.load(handle)

    profile_name = loaded.get("strategy_profile")
    if profile_name is not None:
        profiles = loaded.get("strategy_profiles")
        if not isinstance(profiles, dict) or profile_name not in profiles:
            raise ValueError(f"unknown_strategy_profile:{profile_name}")
        loaded = _deep_merge_dicts(loaded, profiles[profile_name])

    loaded = _drop_removed_runtime_fields(loaded)

    env_vc_key = os.environ.get("VISUAL_CROSSING_KEY")
    if env_vc_key is not None:
        loaded["vc_key"] = env_vc_key
    return loaded
