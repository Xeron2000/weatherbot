from datetime import datetime, timedelta, timezone

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


def make_assessment(
    strategy_leg="YES_SNIPER",
    token_side="yes",
    bucket_range=(65.0, 69.0),
    edge=0.09,
    status="accepted",
):
    return {
        "strategy_leg": strategy_leg,
        "token_side": token_side,
        "range": bucket_range,
        "status": status,
        "edge": edge,
        "size_multiplier": 1.0,
        "reasons": [],
        "quote_context": {
            "bid": 0.09 if token_side == "yes" else 0.81,
            "ask": 0.11 if token_side == "yes" else 0.83,
            "bid_size": 40.0,
            "ask_size": 35.0,
            "tick_size": 0.01,
            "book_ok": True,
        },
    }


def make_quote_snapshot(
    market_id="mkt-65-69",
    yes_bid=0.09,
    yes_ask=0.11,
    yes_ask_size=500.0,
    no_bid=0.81,
    no_ask=0.83,
    no_ask_size=500.0,
):
    return [
        {
            "market_id": market_id,
            "question": "Between 65-69F",
            "range": (65.0, 69.0),
            "yes": {
                "bid": yes_bid,
                "ask": yes_ask,
                "bid_size": 500.0,
                "ask_size": yes_ask_size,
                "tick_size": 0.01,
                "min_order_size": 1.0,
                "spread": round(yes_ask - yes_bid, 4),
            },
            "no": {
                "bid": no_bid,
                "ask": no_ask,
                "bid_size": 500.0,
                "ask_size": no_ask_size,
                "tick_size": 0.01,
                "min_order_size": 1.0,
                "spread": round(no_ask - no_bid, 4),
            },
            "execution_ok": True,
            "execution_stop_reasons": [],
        }
    ]


def patch_scan_inputs(monkeypatch, city, event, snapshot_sequence):
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)
    calls = {"snapshot": 0}
    target_dt = datetime.strptime(event["target_date"], "%Y-%m-%d")

    def fake_take_forecast_snapshot(city_slug, dates):
        idx = min(calls["snapshot"], len(snapshot_sequence) - 1)
        calls["snapshot"] += 1
        snap = snapshot_sequence[idx]
        return {
            date: {"ts": None, "best": None, "best_source": None} for date in dates
        } | {event["target_date"]: snap}

    def fake_get_polymarket_event(city_slug, month, day, year):
        if city_slug != city:
            return None
        if (
            year != target_dt.year
            or month != bot_v2.MONTHS[target_dt.month - 1]
            or day != target_dt.day
        ):
            return None
        return event["payload"]

    monkeypatch.setattr(bot_v2, "take_forecast_snapshot", fake_take_forecast_snapshot)
    monkeypatch.setattr(bot_v2, "get_polymarket_event", fake_get_polymarket_event)
    monkeypatch.setattr(bot_v2, "LOCATIONS", {city: bot_v2.LOCATIONS[city]})


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
    market_with_target["outcomePrices"] = "[0.10,0.90]"
    event["markets"] = [market_with_target]
    return (
        city,
        month,
        {
            "target_date": target_date,
            "payload": event,
            "default_snapshot": {
                "ts": datetime.now(timezone.utc).isoformat(),
                "ecmwf": phase2_weather_snapshot["sources"]["ecmwf"],
                "hrrr": phase2_weather_snapshot["sources"]["hrrr"],
                "metar": phase2_weather_snapshot["sources"]["metar_anchor"],
                "best": phase2_weather_snapshot["sources"]["ecmwf"],
                "best_source": "ecmwf",
            },
        },
    )


def patch_probability_and_candidates(monkeypatch, assessment_sequence, quote_sequence):
    monkeypatch.setattr(
        bot_v2,
        "aggregate_probability",
        lambda *_args, **_kwargs: [
            {
                "market_id": "mkt-65-69",
                "question": "Between 65-69F",
                "range": (65.0, 69.0),
                "aggregate_probability": 0.22,
                "fair_yes": 0.22,
                "fair_no": 0.78,
                "volume": 2000,
                "price": 0.10,
            }
        ],
    )
    counters = {"assessment": 0, "quote": 0}

    def fake_assessments(*_args, **_kwargs):
        idx = min(counters["assessment"], len(assessment_sequence) - 1)
        counters["assessment"] += 1
        return assessment_sequence[idx]

    def fake_quotes(*_args, **_kwargs):
        idx = min(counters["quote"], len(quote_sequence) - 1)
        counters["quote"] += 1
        return quote_sequence[idx]

    monkeypatch.setattr(bot_v2, "build_candidate_assessments", fake_assessments)
    monkeypatch.setattr(bot_v2, "build_quote_snapshot", fake_quotes)


def test_scan_and_update_creates_active_order_before_position_opens(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    patch_scan_inputs(monkeypatch, city, event, [event["default_snapshot"]])
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()]],
        [make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0)],
    )

    bot_v2.scan_and_update()

    market = bot_v2.load_market(city, event["target_date"])

    assert market["position"] is None
    assert market["active_order"] is not None
    assert market["active_order"]["status"] == "working"
    assert [item["status"] for item in market["active_order"]["history"]] == [
        "planned",
        "working",
    ]
    assert market["order_history"] == []


def test_scan_and_update_tracks_partial_and_filled_orders_into_position(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [
            event["default_snapshot"],
            event["default_snapshot"],
            event["default_snapshot"],
        ],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()], [make_assessment()], [make_assessment()]],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.10, yes_ask_size=120.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.10, yes_ask_size=500.0),
        ],
    )

    bot_v2.scan_and_update()
    bot_v2.scan_and_update()

    partial_market = bot_v2.load_market(city, event["target_date"])
    assert partial_market["active_order"]["status"] == "partial"
    assert partial_market["active_order"]["filled_shares"] == 120.0
    assert partial_market["active_order"]["remaining_shares"] == 80.0
    assert partial_market["reserved_exposure"]["reserved_worst_loss"] == 20.0

    bot_v2.scan_and_update()

    filled_market = bot_v2.load_market(city, event["target_date"])
    assert filled_market["active_order"] is None
    assert filled_market["position"] is not None
    assert filled_market["position"]["status"] == "open"
    assert filled_market["position"]["market_id"] == "mkt-65-69"
    assert filled_market["position"]["shares"] == 200.0
    assert filled_market["order_history"][-1]["status"] == "filled"


def test_scan_and_update_cancels_on_candidate_downgrade_and_releases_reservation(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [event["default_snapshot"], event["default_snapshot"]],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()], [make_assessment(status="rejected", edge=0.01)]],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11),
        ],
    )

    bot_v2.scan_and_update()
    bot_v2.scan_and_update()

    state = bot_v2.load_state()
    market = bot_v2.load_market(city, event["target_date"])

    assert market["active_order"] is None
    assert market["order_history"][-1]["status"] == "canceled"
    assert market["order_history"][-1]["status_reason"] == "candidate_downgraded"
    assert market["reserved_exposure"]["release_reason"] == "candidate_downgraded"
    assert market["reserved_exposure"]["reserved_worst_loss"] == 0.0
    assert state["risk_state"]["global_reserved_worst_loss"] == 0.0


def test_scan_and_update_refreshes_single_active_order_when_quote_reprices(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [event["default_snapshot"], event["default_snapshot"]],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()], [make_assessment()]],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11),
            make_quote_snapshot(yes_bid=0.12, yes_ask=0.14),
        ],
    )

    bot_v2.scan_and_update()
    first_market = bot_v2.load_market(city, event["target_date"])
    first_order_id = first_market["active_order"]["order_id"]

    bot_v2.scan_and_update()

    market = bot_v2.load_market(city, event["target_date"])

    assert market["active_order"] is not None
    assert market["active_order"]["order_id"] != first_order_id
    assert market["active_order"]["status"] == "working"
    assert market["order_history"][-1]["status"] == "canceled"
    assert market["order_history"][-1]["status_reason"] == "quote_repriced"
    assert market["reserved_exposure"]["reserved_worst_loss"] == 20.0


def test_scan_and_update_cancels_when_market_is_no_longer_ready(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    stale_snapshot = {
        "ts": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "ecmwf": None,
        "hrrr": None,
        "metar": None,
        "best": None,
        "best_source": None,
    }
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [event["default_snapshot"], stale_snapshot],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()], [make_assessment()]],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11),
        ],
    )

    bot_v2.scan_and_update()
    bot_v2.scan_and_update()

    state = bot_v2.load_state()
    market = bot_v2.load_market(city, event["target_date"])

    assert market["active_order"] is None
    assert market["order_history"][-1]["status"] == "canceled"
    assert market["order_history"][-1]["status_reason"] == "market_no_longer_ready"
    assert market["reserved_exposure"]["release_reason"] == "market_no_longer_ready"
    assert state["risk_state"]["global_reserved_worst_loss"] == 0.0


def test_scan_and_update_expires_gtd_orders(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    no_event = dict(event)
    no_event["payload"] = dict(event["payload"])
    no_market = dict(no_event["payload"]["markets"][0])
    no_market["question"] = "Between 70-74F"
    no_market["id"] = "mkt-70-74"
    no_market["clobTokenIds"] = '["yes-70-74","no-70-74"]'
    no_event["payload"]["markets"] = [no_market]

    patch_scan_inputs(
        monkeypatch,
        city,
        no_event,
        [event["default_snapshot"], event["default_snapshot"]],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [
            [
                make_assessment(
                    strategy_leg="NO_CARRY",
                    token_side="no",
                    bucket_range=(70.0, 74.0),
                )
            ],
            [
                make_assessment(
                    strategy_leg="NO_CARRY",
                    token_side="no",
                    bucket_range=(70.0, 74.0),
                )
            ],
        ],
        [
            [
                {
                    "market_id": "mkt-70-74",
                    "question": "Between 70-74F",
                    "range": (70.0, 74.0),
                    "yes": {
                        "bid": 0.05,
                        "ask": 0.07,
                        "bid_size": 500.0,
                        "ask_size": 500.0,
                        "tick_size": 0.01,
                        "min_order_size": 1.0,
                        "spread": 0.02,
                    },
                    "no": {
                        "bid": 0.81,
                        "ask": 0.83,
                        "bid_size": 500.0,
                        "ask_size": 500.0,
                        "tick_size": 0.01,
                        "min_order_size": 1.0,
                        "spread": 0.02,
                    },
                    "execution_ok": True,
                    "execution_stop_reasons": [],
                }
            ],
            [
                {
                    "market_id": "mkt-70-74",
                    "question": "Between 70-74F",
                    "range": (70.0, 74.0),
                    "yes": {
                        "bid": 0.05,
                        "ask": 0.07,
                        "bid_size": 500.0,
                        "ask_size": 500.0,
                        "tick_size": 0.01,
                        "min_order_size": 1.0,
                        "spread": 0.02,
                    },
                    "no": {
                        "bid": 0.81,
                        "ask": 0.83,
                        "bid_size": 500.0,
                        "ask_size": 500.0,
                        "tick_size": 0.01,
                        "min_order_size": 1.0,
                        "spread": 0.02,
                    },
                    "execution_ok": True,
                    "execution_stop_reasons": [],
                }
            ],
        ],
    )
    monkeypatch.setattr(
        bot_v2,
        "aggregate_probability",
        lambda *_args, **_kwargs: [
            {
                "market_id": "mkt-70-74",
                "question": "Between 70-74F",
                "range": (70.0, 74.0),
                "aggregate_probability": 0.20,
                "fair_yes": 0.20,
                "fair_no": 0.80,
                "volume": 2000,
                "price": 0.81,
            }
        ],
    )

    bot_v2.scan_and_update()
    market = bot_v2.load_market(city, no_event["target_date"])
    market["active_order"]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()
    bot_v2.save_market(market)

    bot_v2.scan_and_update()

    state = bot_v2.load_state()
    market = bot_v2.load_market(city, no_event["target_date"])

    assert market["active_order"] is None
    assert market["order_history"][-1]["status"] == "expired"
    assert market["order_history"][-1]["status_reason"] == "expired"
    assert market["reserved_exposure"]["release_reason"] == "expired"
    assert state["risk_state"]["global_reserved_worst_loss"] == 0.0
