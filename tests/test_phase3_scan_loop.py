from datetime import datetime, timezone

import bot_v2


def configure_runtime_paths(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    markets_dir = data_dir / "markets"
    data_dir.mkdir()
    markets_dir.mkdir()
    monkeypatch.setattr(bot_v2, "DATA_DIR", data_dir)
    monkeypatch.setattr(bot_v2, "MARKETS_DIR", markets_dir)
    monkeypatch.setattr(bot_v2, "STATE_FILE", data_dir / "state.json")
    monkeypatch.setattr(bot_v2, "CALIBRATION_FILE", data_dir / "calibration.json")


def patch_scan_inputs(monkeypatch, city_events, city_snapshots):
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_take_forecast_snapshot(city_slug, dates):
        snapshots = {
            date: {"ts": None, "best": None, "best_source": None} for date in dates
        }
        snapshots.update(city_snapshots.get(city_slug, {}))
        return snapshots

    def fake_get_polymarket_event(city_slug, month, day, year):
        return city_events.get((city_slug, f"{year:04d}-{month}-{day:02d}"))

    monkeypatch.setattr(bot_v2, "take_forecast_snapshot", fake_take_forecast_snapshot)
    monkeypatch.setattr(bot_v2, "get_polymarket_event", fake_get_polymarket_event)


def make_assessment(
    strategy_leg,
    token_side,
    bucket_range,
    edge,
    status="accepted",
    size_multiplier=1.0,
):
    return {
        "strategy_leg": strategy_leg,
        "token_side": token_side,
        "range": bucket_range,
        "status": status,
        "edge": edge,
        "size_multiplier": size_multiplier,
        "reasons": [],
        "quote_context": {
            "ask": 0.11 if token_side == "yes" else 0.21,
            "bid": 0.09 if token_side == "yes" else 0.81,
            "bid_size": 40.0,
            "ask_size": 35.0,
            "book_ok": True,
        },
    }


def prepare_single_market(monkeypatch, phase2_gamma_event, phase2_weather_snapshot):
    city = "nyc"
    today = datetime.now(timezone.utc)
    target_date = today.strftime("%Y-%m-%d")
    month = bot_v2.MONTHS[today.month - 1]
    event = dict(phase2_gamma_event)
    event["endDate"] = f"{target_date}T23:59:00Z"
    event["rules"] = (
        "This market resolves based on the highest temperature recorded at "
        "LaGuardia Airport (KLGA) in °F. Temperatures are rounded to the nearest "
        "whole degree using the official airport reading."
    )
    market_with_target = dict(event["markets"][2])
    market_with_target["question"] = "Between 65-69F"
    market_with_target["clobTokenIds"] = '["yes-65-69","no-65-69"]'
    event["markets"] = [market_with_target]

    monkeypatch.setattr(bot_v2, "LOCATIONS", {city: bot_v2.LOCATIONS[city]})
    patch_scan_inputs(
        monkeypatch,
        {(city, f"{today.year:04d}-{month}-{today.day:02d}"): event},
        {
            city: {
                target_date: {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "ecmwf": phase2_weather_snapshot["sources"]["ecmwf"],
                    "hrrr": phase2_weather_snapshot["sources"]["hrrr"],
                    "metar": phase2_weather_snapshot["sources"]["metar_anchor"],
                    "best": phase2_weather_snapshot["sources"]["ecmwf"],
                    "best_source": "ecmwf",
                }
            }
        },
    )
    monkeypatch.setattr(
        bot_v2,
        "build_quote_snapshot",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        bot_v2,
        "aggregate_probability",
        lambda *_args, **_kwargs: [{"market_id": "mkt-65-69", "range": (65.0, 69.0)}],
    )
    return city, target_date


def test_scan_and_update_persists_route_decisions_and_risk_state(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, target_date = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    monkeypatch.setattr(
        bot_v2,
        "build_candidate_assessments",
        lambda *_args, **_kwargs: [
            make_assessment("YES_SNIPER", "yes", (65.0, 69.0), 0.09),
            make_assessment("NO_CARRY", "no", (65.0, 69.0), 0.08),
        ],
    )

    bot_v2.scan_and_update()

    state = bot_v2.load_state()
    market = bot_v2.load_market(city, target_date)

    assert state["risk_state"]["bankroll"] == state["starting_balance"]
    assert state["risk_state"]["global_reserved_worst_loss"] == 20.0
    assert state["risk_state"]["legs"]["YES_SNIPER"]["budget"] == 3000.0
    assert state["risk_state"]["legs"]["YES_SNIPER"]["reserved"] == 20.0
    assert state["risk_state"]["legs"]["NO_CARRY"]["budget"] == 7000.0
    assert state["risk_state"]["legs"]["NO_CARRY"]["reserved"] == 0.0

    assert market["route_decisions"]
    assert market["reserved_exposure"]["reserved_worst_loss"] == 20.0
    assert market["reserved_exposure"]["strategy_leg"] == "YES_SNIPER"
    assert market["route_decisions"][0]["budget_bucket"] == "YES_SNIPER"
    assert market["route_decisions"][0]["status"] == "accepted"
    assert any(
        item["status"] == "rejected" and "same_bucket_conflict" in item["reasons"]
        for item in market["route_decisions"]
    )


def test_scan_and_update_routes_within_leg_by_edge_before_global_cap(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, target_date = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    monkeypatch.setattr(
        bot_v2,
        "RISK_ROUTER",
        {
            **bot_v2.RISK_ROUTER,
            "yes_budget_pct": 0.30,
            "no_budget_pct": 0.70,
            "yes_leg_cap_pct": 0.30,
            "no_leg_cap_pct": 0.70,
            "global_usage_cap_pct": 0.003,
        },
    )
    monkeypatch.setattr(
        bot_v2,
        "build_candidate_assessments",
        lambda *_args, **_kwargs: [
            make_assessment("YES_SNIPER", "yes", (70.0, 74.0), 0.04),
            make_assessment("YES_SNIPER", "yes", (65.0, 69.0), 0.09),
        ],
    )

    bot_v2.scan_and_update()

    market = bot_v2.load_market(city, target_date)
    accepted = [
        item for item in market["route_decisions"] if item["status"] == "accepted"
    ]
    rejected = [
        item for item in market["route_decisions"] if item["status"] == "rejected"
    ]

    assert len(accepted) == 1
    assert accepted[0]["range"] == (65.0, 69.0)
    assert accepted[0]["reserved_worst_loss"] == 20.0
    assert any("global_cap_exceeded" in item["reasons"] for item in rejected)
