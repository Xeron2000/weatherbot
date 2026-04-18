import json

from datetime import datetime, timezone

from .config import load_config, load_risk_router_config
from .domain import LOCATIONS
from .paper_execution import build_empty_paper_execution_state, ensure_market_order_defaults, restore_order_state_from_markets
from .paths import CALIBRATION_FILE, MARKETS_DIR, STATE_FILE
from .strategy import restore_risk_state_from_markets


_cfg = load_config()

BALANCE = _cfg.get("balance", 10000.0)
CALIBRATION_MIN = _cfg.get("calibration_min", 30)
RISK_ROUTER = load_risk_router_config(_cfg)
_cal = {}


SIGMA_F = 2.0
SIGMA_C = 1.2


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
        "paper_execution_state": build_empty_paper_execution_state(),
        "execution_events": [],
        "execution_metrics": {
            "event_count": 0,
            "touch_not_fill_count": 0,
            "partial_fill_count": 0,
            "filled_count": 0,
            "cancel_requested_count": 0,
            "cancel_count": 0,
            "filled_shares_total": 0.0,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

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
    markets = load_all_markets()
    state["risk_state"] = restore_risk_state_from_markets(state, markets, RISK_ROUTER)
    state["order_state"] = restore_order_state_from_markets(markets)
    return state

def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
