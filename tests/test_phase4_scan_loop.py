from datetime import datetime, timedelta, timezone

import bot_v2


def make_yes_market():
    market = {
        "city": "nyc",
        "date": "2026-04-18",
        "city_name": "New York City",
        "event_id": "evt-nyc-2026-04-18",
        "event_slug": "evt-nyc-2026-04-18",
        "market_contracts": [
            {
                "market_id": "mkt-65-69",
                "question": "Between 65-69F",
                "range": [65.0, 69.0],
            }
        ],
        "candidate_assessments": [
            {
                "strategy_leg": "YES_SNIPER",
                "token_side": "yes",
                "range": [65.0, 69.0],
                "status": "accepted",
                "edge": 0.09,
                "size_multiplier": 1.0,
                "aggregate_probability": 0.22,
                "fair_yes": 0.22,
                "fair_no": 0.78,
                "fair_price": 0.22,
                "reasons": [],
                "quote_context": {"bid": 0.09, "ask": 0.11, "tick_size": 0.01},
            }
        ],
        "route_decisions": [
            {
                "strategy_leg": "YES_SNIPER",
                "token_side": "yes",
                "range": [65.0, 69.0],
                "status": "accepted",
                "reserved_worst_loss": 20.0,
                "budget_bucket": "YES_SNIPER",
                "reasons": [],
            }
        ],
        "reserved_exposure": {
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "reserved_worst_loss": 20.0,
            "release_reason": None,
            "budget_bucket": "YES_SNIPER",
        },
        "quote_snapshot": [
            {
                "market_id": "mkt-65-69",
                "question": "Between 65-69F",
                "range": [65.0, 69.0],
                "yes": {
                    "bid": 0.09,
                    "ask": 0.11,
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
        "position": None,
        "active_order": None,
        "order_history": [],
        "paper_execution_state": bot_v2.build_empty_paper_execution_state(),
        "execution_events": [],
        "execution_metrics": {},
    }
    return bot_v2.ensure_market_order_defaults(market)


def make_risk_state():
    return bot_v2.build_empty_risk_state(10000.0, bot_v2.RISK_ROUTER)


def configure_paper_runtime(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "PAPER_EXECUTION",
        {
            "submission_latency_ms": 5000,
            "queue_ahead_shares": 80.0,
            "queue_ahead_ratio": 0.0,
            "touch_not_fill_min_touches": 1,
            "partial_fill_slice_ratio": 0.5,
            "cancel_latency_ms": 4000,
            "adverse_fill_buffer_ticks": 0,
        },
    )


def test_sync_market_order_creates_yes_active_order(monkeypatch):
    configure_paper_runtime(monkeypatch)
    market = make_yes_market()
    risk_state = make_risk_state()

    result = bot_v2.sync_market_order(
        market,
        risk_state,
        {"ts": "2026-04-18T12:00:00+00:00", "best": 67.0, "best_source": "ecmwf"},
        market_ready=True,
    )

    assert result == {"filled_cost": 0.0, "opened_position": False}
    assert market["active_order"] is not None
    assert market["active_order"]["strategy_leg"] == "YES_SNIPER"
    assert market["active_order"]["token_side"] == "yes"
    assert market["active_order"]["status"] == "working"
    assert market["paper_execution_state"]["status"] == "submitting"


def test_sync_market_order_cancels_non_yes_active_order(monkeypatch):
    configure_paper_runtime(monkeypatch)
    market = make_yes_market()
    market["candidate_assessments"] = [
        {
            **market["candidate_assessments"][0],
            "strategy_leg": "NO_CARRY",
            "token_side": "no",
        }
    ]
    market["route_decisions"] = [
        {
            **market["route_decisions"][0],
            "strategy_leg": "NO_CARRY",
            "token_side": "no",
        }
    ]
    market["reserved_exposure"] = {
        **market["reserved_exposure"],
        "strategy_leg": "NO_CARRY",
        "token_side": "no",
    }
    market["active_order"] = {
        "order_id": "mkt-65-69:NO_CARRY:no:65.0-69.0:0.8100",
        "strategy_leg": "NO_CARRY",
        "token_side": "no",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "limit_price": 0.81,
        "shares": 20.0,
        "filled_shares": 0.0,
        "remaining_shares": 20.0,
        "time_in_force": "GTC",
        "expires_at": None,
        "status": "working",
        "status_reason": "order_submitted",
        "created_at": "2026-04-18T12:00:00+00:00",
        "updated_at": "2026-04-18T12:00:00+00:00",
        "history": [],
    }
    market["paper_execution_state"] = {
        **bot_v2.build_empty_paper_execution_state(),
        "order_id": market["active_order"]["order_id"],
        "status": "cancel_pending",
        "cancel_reason": "yes_only_runtime",
        "cancel_ready_at": "2026-04-18T12:00:00+00:00",
    }
    risk_state = make_risk_state()
    bot_v2.apply_reservation_to_risk_state(risk_state, market["reserved_exposure"])

    result = bot_v2.sync_market_order(
        market,
        risk_state,
        {"ts": "2026-04-18T12:00:01+00:00", "best": 67.0, "best_source": "ecmwf"},
        market_ready=True,
    )

    assert result == {"filled_cost": 0.0, "opened_position": False}
    assert market["active_order"] is None
    assert market["order_history"][-1]["status"] == "canceled"
    assert market["order_history"][-1]["status_reason"] == "yes_only_runtime"
    assert market["reserved_exposure"]["release_reason"] == "yes_only_runtime"


def test_sync_market_order_expires_yes_order(monkeypatch):
    configure_paper_runtime(monkeypatch)
    market = make_yes_market()
    market["active_order"] = {
        "order_id": "mkt-65-69:YES_SNIPER:yes:65.0-69.0:0.1000",
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "limit_price": 0.10,
        "shares": 200.0,
        "filled_shares": 0.0,
        "remaining_shares": 200.0,
        "time_in_force": "GTD",
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "status": "working",
        "status_reason": "order_submitted",
        "created_at": "2026-04-18T12:00:00+00:00",
        "updated_at": "2026-04-18T12:00:00+00:00",
        "history": [],
    }
    risk_state = make_risk_state()
    bot_v2.apply_reservation_to_risk_state(risk_state, market["reserved_exposure"])

    result = bot_v2.sync_market_order(
        market,
        risk_state,
        {"ts": datetime.now(timezone.utc).isoformat(), "best": 67.0, "best_source": "ecmwf"},
        market_ready=True,
    )

    assert result == {"filled_cost": 0.0, "opened_position": False}
    assert market["active_order"] is None
    assert market["order_history"][-1]["status"] == "expired"
    assert market["reserved_exposure"]["release_reason"] == "expired"


def test_restore_order_state_from_markets_ignores_non_yes_active_orders():
    yes_market = make_yes_market()
    yes_market["active_order"] = {
        "order_id": "yes-active",
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "status": "working",
        "filled_shares": 0.0,
        "remaining_shares": 200.0,
        "updated_at": "2026-04-18T12:00:00+00:00",
    }
    no_market = make_yes_market()
    no_market["active_order"] = {
        "order_id": "no-active",
        "strategy_leg": "NO_CARRY",
        "token_side": "no",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "status": "working",
        "filled_shares": 0.0,
        "remaining_shares": 20.0,
        "updated_at": "2026-04-18T12:00:00+00:00",
    }

    restored = bot_v2.restore_order_state_from_markets([yes_market, no_market])

    assert [item["order_id"] for item in restored["active_orders"]] == ["yes-active"]
