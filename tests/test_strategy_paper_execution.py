import pytest

import weatherbot

from weatherbot import paper_execution, strategy


def configure_strategy_runtime(monkeypatch):
    yes_strategy = {
        "max_price": 0.25,
        "min_probability": 0.14,
        "min_edge": 0.03,
        "min_hours": 2.0,
        "max_hours": 72.0,
        "max_size": 20.0,
        "min_size": 1.0,
    }
    monkeypatch.setattr(strategy, "YES_STRATEGY", yes_strategy)
    monkeypatch.setattr(strategy, "KELLY_FRACTION", 0.01)
    monkeypatch.setattr(strategy, "TIMEZONES", {"nyc": "UTC"})
    monkeypatch.setattr(weatherbot, "YES_STRATEGY", yes_strategy)
    monkeypatch.setattr(weatherbot, "KELLY_FRACTION", 0.01, raising=False)
    monkeypatch.setattr(weatherbot, "TIMEZONES", {"nyc": "UTC"})


def configure_paper_execution_runtime(monkeypatch):
    order_policy = {
        "price_improve_ticks": 1,
        "yes_time_in_force": "GTD",
        "no_time_in_force": "GTC",
        "gtd_buffer_hours": 6.0,
    }
    monkeypatch.setattr(paper_execution, "ORDER_POLICY", order_policy)
    monkeypatch.setattr(weatherbot, "ORDER_POLICY", order_policy)


def make_market():
    return {
        "city": "nyc",
        "date": "2026-04-18",
        "event_id": "evt-123",
        "market_contracts": [
            {
                "market_id": "mkt-65-69",
                "question": "65-69F",
                "range": [65.0, 69.0],
            }
        ],
    }


def make_assessment(status="accepted", token_side="yes"):
    return {
        "status": status,
        "strategy_leg": "YES_SNIPER" if token_side == "yes" else "NO_CARRY",
        "token_side": token_side,
        "range": [65.0, 69.0],
        "aggregate_probability": 0.18,
        "fair_yes": 0.18,
        "fair_no": 0.82,
    }


def make_quote_snapshot():
    return [
        {
            "market_id": "mkt-65-69",
            "yes": {
                "bid": 0.09,
                "ask": 0.11,
                "tick_size": 0.01,
            },
            "no": {
                "bid": 0.82,
                "ask": 0.85,
                "tick_size": 0.01,
            },
        }
    ]


def test_build_passive_order_intent_has_stable_reasons_and_deterministic_order(monkeypatch):
    configure_paper_execution_runtime(monkeypatch)
    market = make_market()
    reservation = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "reserved_worst_loss": 20.0,
    }
    assessment = make_assessment()
    ts = "2026-04-18T12:00:00+00:00"

    assert paper_execution.build_passive_order_intent(
        market, None, assessment, make_quote_snapshot(), ts
    ) == {"order": None, "reason": "reservation_missing"}
    assert paper_execution.build_passive_order_intent(
        market, reservation, make_assessment(status="rejected"), make_quote_snapshot(), ts
    ) == {"order": None, "reason": "route_not_accepted"}
    assert paper_execution.build_passive_order_intent(
        market, reservation, assessment, [], ts
    ) == {"order": None, "reason": "quote_snapshot_missing"}

    built = paper_execution.build_passive_order_intent(
        market, reservation, assessment, make_quote_snapshot(), ts
    )

    assert built["reason"] is None
    assert built["order"]["order_id"] == "mkt-65-69:YES_SNIPER:yes:65.0-69.0:0.1000"
    assert built["order"]["limit_price"] == 0.1
    assert built["order"]["shares"] == 200.0
    assert built["order"]["time_in_force"] == "GTD"
    assert built["order"]["expires_at"] == "2026-04-18T18:00:00+00:00"


def test_build_position_from_order_persists_side_metadata(monkeypatch):
    configure_paper_execution_runtime(monkeypatch)
    market = make_market()
    order = {
        "market_id": "mkt-65-69",
        "token_side": "no",
        "range": [65.0, 69.0],
        "filled_shares": 100.0,
        "limit_price": 0.82,
        "updated_at": "2026-04-18T12:00:00+00:00",
        "history": [
            {
                "status": "filled",
                "reason": "quote_touched_limit",
                "ts": "2026-04-18T12:00:00+00:00",
                "fill_shares": 100.0,
                "fill_price": 0.82,
            }
        ],
    }
    assessment = {
        "aggregate_probability": 0.18,
        "fair_no": 0.82,
        "edge": 0.0,
        "quote_context": {"bid": 0.81, "spread": 0.02},
    }
    forecast_snap = {"best": 67.0, "best_source": "ecmwf"}

    position = paper_execution.build_position_from_order(
        market, order, assessment, forecast_snap
    )

    assert position["token_side"] == "no"
    assert position["entry_side"] == "no"


def test_apply_order_transition_appends_history_and_rejects_invalid_status():
    order = {
        "shares": 200.0,
        "filled_shares": 0.0,
        "remaining_shares": 200.0,
        "history": [],
    }

    updated = paper_execution.apply_order_transition(
        order,
        "partial",
        "queue_cleared_partial_fill",
        "2026-04-18T12:00:00+00:00",
        fill_shares=80.0,
        fill_price=0.1,
    )

    assert updated["status"] == "partial"
    assert updated["filled_shares"] == 80.0
    assert updated["remaining_shares"] == 120.0
    assert updated["history"][-1] == {
        "status": "partial",
        "reason": "queue_cleared_partial_fill",
        "ts": "2026-04-18T12:00:00+00:00",
        "fill_shares": 80.0,
        "fill_price": 0.1,
    }

    with pytest.raises(ValueError, match="unsupported_order_status:bad"):
        paper_execution.apply_order_transition(order, "bad", "nope", "2026-04-18T12:00:00+00:00")


def test_strategy_assessments_keep_leg_semantics_and_statuses(monkeypatch):
    configure_strategy_runtime(monkeypatch)
    bucket_probabilities = [
        {
            "market_id": "mkt-65-69",
            "range": [65.0, 69.0],
            "aggregate_probability": 0.18,
            "fair_yes": 0.18,
            "fair_no": 0.82,
        }
    ]
    quote_snapshot = [
        {
            "market_id": "mkt-65-69",
            "yes": {"ask": 0.11, "bid": 0.09, "spread": 0.02},
            "no": {"bid": 0.72, "ask": 0.74, "spread": 0.02, "tick_size": 0.01},
            "execution_stop_reasons": [],
        }
    ]

    assert strategy.determine_size_multiplier(0.06, 0.03) == (1.0, "accepted")
    assert strategy.determine_size_multiplier(0.03, 0.03) == (0.5, "size_down")
    assert strategy.determine_size_multiplier(0.02, 0.03) == (0.0, "rejected")

    assessments = strategy.build_candidate_assessments(
        bucket_probabilities,
        quote_snapshot,
        24,
        {"city_slug": "nyc", "market_date": "2026-04-17", "metar": 66.0, "now_ts": "2026-04-18T12:00:00+00:00"},
    )

    assert len(assessments) == 1
    yes_assessment = assessments[0]

    assert yes_assessment["strategy_leg"] == "YES_SNIPER"
    assert yes_assessment["status"] == "accepted"
    assert yes_assessment["reasons"] == []


def test_route_helpers_keep_yes_reservation_shared_state_shape(monkeypatch):
    configure_strategy_runtime(monkeypatch)
    decision = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "range": [65.0, 69.0],
        "status": "accepted",
        "reserved_worst_loss": 20.0,
        "budget_bucket": "YES_SNIPER",
        "reasons": [],
        "exposure_keys": strategy.build_exposure_keys(make_market(), assessment={"range": [65.0, 69.0]}),
    }

    reservation = strategy.build_reserved_exposure(
        make_market(),
        decision,
        "2026-04-18T12:00:00+00:00",
    )
    risk_state = strategy.build_empty_risk_state(
        10000.0,
        {
            "yes_budget_pct": 0.3,
            "no_budget_pct": 0.7,
            "yes_leg_cap_pct": 0.3,
            "no_leg_cap_pct": 0.7,
            "global_usage_cap_pct": 1.0,
            "per_market_cap_pct": 1.0,
            "per_city_cap_pct": 1.0,
            "per_date_cap_pct": 1.0,
            "per_event_cap_pct": 1.0,
        },
    )

    strategy.apply_reservation_to_risk_state(risk_state, reservation)

    assert reservation["strategy_leg"] == "YES_SNIPER"
    assert reservation["token_side"] == "yes"
    assert reservation["reserved_worst_loss"] == 20.0
    assert risk_state["legs"]["YES_SNIPER"]["reserved"] == 20.0
    assert risk_state["active_reservations"][0]["token_side"] == "yes"


def test_build_exposure_keys_stays_stable_for_market_dict_and_primitives():
    assessment = {"range": [65.0, 69.0]}
    market_keys = strategy.build_exposure_keys(make_market(), assessment=assessment)
    primitive_keys = strategy.build_exposure_keys("nyc", "2026-04-18", assessment)

    assert market_keys == {
        "market": "nyc|2026-04-18|65.0-69.0",
        "city": "nyc",
        "date": "2026-04-18",
        "event": "nyc|2026-04-18|evt-123",
        "bucket": "65.0-69.0",
    }
    assert primitive_keys == {
        "market": "nyc|2026-04-18|65.0-69.0",
        "city": "nyc",
        "date": "2026-04-18",
        "event": "nyc|2026-04-18|event",
        "bucket": "65.0-69.0",
    }
