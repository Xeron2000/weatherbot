from datetime import datetime, timezone

import bot_v2

from tests.test_phase4_scan_loop import (
    configure_runtime_paths,
    make_assessment,
    make_quote_snapshot,
    patch_probability_and_candidates,
    patch_scan_inputs,
    prepare_single_market,
)


def write_market(bot_module, market):
    bot_module.save_market(market)
    return bot_module.load_market(market["city"], market["date"])


def build_partial_order(ts, limit_price=0.11, shares=200.0, filled_shares=120.0):
    order = {
        "order_id": "mkt-65-69:YES_SNIPER:yes:65.0-69.0:0.1100",
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "limit_price": limit_price,
        "shares": shares,
        "filled_shares": 0.0,
        "remaining_shares": shares,
        "time_in_force": "GTC",
        "expires_at": None,
        "status": "planned",
        "status_reason": "accepted_route",
        "created_at": ts,
        "updated_at": ts,
        "history": [
            {
                "status": "planned",
                "reason": "accepted_route",
                "ts": ts,
                "fill_shares": 0.0,
                "fill_price": None,
            }
        ],
    }
    order = bot_v2.apply_order_transition(order, "working", "order_submitted", ts)
    return bot_v2.apply_order_transition(
        order,
        "partial",
        "quote_touched_limit",
        ts,
        fill_shares=filled_shares,
        fill_price=0.10,
    )


def build_terminal_order(ts, status, reason):
    order = build_partial_order(ts, filled_shares=0.0)
    order["filled_shares"] = 0.0
    order["remaining_shares"] = order["shares"]
    return bot_v2.apply_order_transition(order, status, reason, ts)


def test_load_state_restores_order_state_from_market_json(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    ts = datetime.now(timezone.utc).isoformat()
    market = bot_v2.new_market(city, event["target_date"], event["payload"], 18.0)
    market["reserved_exposure"] = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "status": "accepted",
        "range": [65.0, 69.0],
        "reserved_worst_loss": 20.0,
        "reserved_at": ts,
        "release_reason": None,
        "reasons": [],
        "budget_bucket": "YES_SNIPER",
        "exposure_keys": {
            "city": city,
            "date": event["target_date"],
            "event": event["payload"].get("id"),
        },
    }
    market["active_order"] = build_partial_order(ts)
    market["order_history"] = [
        build_terminal_order(ts, "filled", "quote_touched_limit"),
        build_terminal_order(ts, "canceled", "candidate_downgraded"),
        build_terminal_order(ts, "expired", "expired"),
    ]
    write_market(bot_v2, market)

    state = bot_v2.load_state()

    assert state["order_state"]["status_counts"]["planned"] == 0
    assert state["order_state"]["status_counts"]["working"] == 0
    assert state["order_state"]["status_counts"]["partial"] == 1
    assert state["order_state"]["status_counts"]["filled"] == 1
    assert state["order_state"]["status_counts"]["canceled"] == 1
    assert state["order_state"]["status_counts"]["expired"] == 1
    assert len(state["order_state"]["active_orders"]) == 1
    assert state["order_state"]["active_orders"][0]["market_key"] == (
        f"{city}:{event['target_date']}"
    )
    assert state["order_state"]["active_orders"][0]["status"] == "partial"
    assert state["order_state"]["active_orders"][0]["filled_shares"] == 120.0


def test_sync_market_order_resumes_partial_order_without_duplicate_creation(
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
        [make_quote_snapshot(yes_bid=0.09, yes_ask=0.10, yes_ask_size=500.0)],
    )

    ts = event["default_snapshot"]["ts"]
    market = bot_v2.new_market(city, event["target_date"], event["payload"], 18.0)
    market["market_contracts"] = [
        {
            "market_id": "mkt-65-69",
            "question": "Between 65-69F",
            "range": [65.0, 69.0],
            "condition_id": "cond-65-69",
            "token_id_yes": "yes-65-69",
            "token_id_no": "no-65-69",
            "unit": "F",
        }
    ]
    market["candidate_assessments"] = [make_assessment()]
    market["quote_snapshot"] = make_quote_snapshot(
        yes_bid=0.09, yes_ask=0.10, yes_ask_size=500.0
    )
    market["route_decisions"] = [
        {
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "status": "accepted",
        }
    ]
    market["reserved_exposure"] = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "status": "accepted",
        "range": [65.0, 69.0],
        "reserved_worst_loss": 20.0,
        "reserved_at": ts,
        "release_reason": None,
        "reasons": [],
        "budget_bucket": "YES_SNIPER",
        "exposure_keys": {
            "city": city,
            "date": event["target_date"],
            "event": event["payload"].get("id"),
        },
    }
    market["active_order"] = build_partial_order(ts)
    write_market(bot_v2, market)

    state = bot_v2.load_state()
    risk_state = state["risk_state"]
    restored_market = bot_v2.load_market(city, event["target_date"])
    original_order_id = restored_market["active_order"]["order_id"]

    update = bot_v2.sync_market_order(
        restored_market,
        risk_state,
        event["default_snapshot"],
        market_ready=True,
    )

    assert update["opened_position"] is True
    assert restored_market["active_order"] is None
    assert restored_market["position"] is not None
    assert restored_market["position"]["shares"] == 200.0
    assert restored_market["paper_execution_state"]["status"] == "filled"
    assert restored_market["order_history"][-1]["order_id"] == original_order_id


def test_load_state_keeps_partial_order_reservation_consistent_after_restart(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    ts = datetime.now(timezone.utc).isoformat()
    market = bot_v2.new_market(city, event["target_date"], event["payload"], 18.0)
    market["reserved_exposure"] = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "status": "accepted",
        "range": [65.0, 69.0],
        "reserved_worst_loss": 20.0,
        "reserved_at": ts,
        "release_reason": None,
        "reasons": [],
        "budget_bucket": "YES_SNIPER",
        "exposure_keys": {
            "city": city,
            "date": event["target_date"],
            "event": event["payload"].get("id"),
        },
    }
    market["position"] = {
        "market_id": "mkt-65-69",
        "status": "open",
        "shares": 120.0,
        "cost": 12.0,
        "entry_price": 0.10,
        "bucket_low": 65.0,
        "bucket_high": 69.0,
    }
    market["active_order"] = build_partial_order(ts)
    write_market(bot_v2, market)

    state = bot_v2.load_state()

    assert state["risk_state"]["global_reserved_worst_loss"] == 20.0
    restored = state["order_state"]["active_orders"][0]
    assert restored["position_status"] == "open"
    assert restored["filled_shares"] == 120.0
    assert restored["remaining_shares"] == 80.0
    assert restored["reserved_worst_loss"] == 20.0


def test_load_state_excludes_terminal_orders_from_active_restore(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    ts = datetime.now(timezone.utc).isoformat()
    market = bot_v2.new_market(city, event["target_date"], event["payload"], 18.0)
    market["active_order"] = build_terminal_order(
        ts, "canceled", "candidate_downgraded"
    )
    market["order_history"] = [
        build_terminal_order(ts, "filled", "quote_touched_limit"),
        build_terminal_order(ts, "expired", "expired"),
    ]
    write_market(bot_v2, market)

    state = bot_v2.load_state()

    assert state["order_state"]["active_orders"] == []
    assert state["order_state"]["status_counts"]["canceled"] == 1
    assert state["order_state"]["status_counts"]["filled"] == 1
    assert state["order_state"]["status_counts"]["expired"] == 1


def test_monitor_positions_keeps_legacy_position_compatible_without_side_fields(
    tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(bot_v2, "LOCATIONS", {"nyc": bot_v2.LOCATIONS["nyc"]})
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        bot_v2,
        "get_token_quote_snapshot",
        lambda token_id, side: {
            "token_id": token_id,
            "side": side,
            "book_ok": True,
            "bid": 0.2,
        },
    )

    market = {
        "city": "nyc",
        "date": "2026-04-17",
        "event_end_date": "2026-04-19T23:59:00Z",
        "position": {
            "market_id": "mkt-65-69",
            "entry_price": 0.34,
            "shares": 10.0,
            "cost": 3.4,
            "status": "open",
            "stop_price": 0.32,
        },
        "all_outcomes": [
            {
                "market_id": "mkt-65-69",
                "token_id_yes": "yes-65-69",
                "bid": 0.2,
                "price": 0.21,
            }
        ],
        "quote_snapshot": [
            {
                "market_id": "mkt-65-69",
                "yes": {"token_id": "yes-65-69"},
                "no": {},
            }
        ],
    }
    write_market(bot_v2, market)

    closed = bot_v2.monitor_positions()
    updated = bot_v2.load_market("nyc", "2026-04-17")

    assert closed == 1
    assert updated["position"]["status"] == "closed"
    assert updated["position"]["close_reason"] == "stop_loss"
