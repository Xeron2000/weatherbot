import pytest

import weatherbot

from weatherbot import paper_execution, strategy


def configure_strategy_runtime(monkeypatch, no_kelly_fraction=1.0, no_max_size=20.0):
    yes_strategy = {
        "max_price": 0.25,
        "min_probability": 0.14,
        "min_edge": 0.03,
        "min_hours": 2.0,
        "max_hours": 72.0,
        "max_size": 20.0,
        "min_size": 1.0,
    }
    no_strategy = {
        "min_price": 0.65,
        "min_probability": 0.7,
        "min_edge": 0.04,
        "min_hours": 2.0,
        "max_hours": 72.0,
        "max_size": no_max_size,
        "min_size": 1.0,
    }
    monkeypatch.setattr(strategy, "YES_STRATEGY", yes_strategy)
    monkeypatch.setattr(strategy, "NO_STRATEGY", no_strategy)
    monkeypatch.setattr(strategy, "NO_KELLY_FRACTION", no_kelly_fraction, raising=False)
    monkeypatch.setattr(strategy, "KELLY_FRACTION", 0.01)
    monkeypatch.setattr(strategy, "TIMEZONES", {"nyc": "UTC"})
    monkeypatch.setattr(weatherbot, "YES_STRATEGY", yes_strategy)
    monkeypatch.setattr(weatherbot, "NO_STRATEGY", no_strategy)
    monkeypatch.setattr(weatherbot, "NO_KELLY_FRACTION", no_kelly_fraction, raising=False)
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
            "no": {"bid": 0.9, "ask": 0.93, "spread": 0.03},
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

    yes_assessment = next(item for item in assessments if item["token_side"] == "yes")
    no_assessment = next(item for item in assessments if item["token_side"] == "no")

    assert yes_assessment["strategy_leg"] == "YES_SNIPER"
    assert yes_assessment["status"] == "accepted"
    assert yes_assessment["reasons"] == []
    assert no_assessment["strategy_leg"] == "NO_CARRY"
    assert no_assessment["status"] == "accepted"
    assert no_assessment["reasons"] == []


def test_no_passive_order_shares_scale_with_reserved_worst_loss_only(monkeypatch):
    configure_strategy_runtime(monkeypatch, no_kelly_fraction=1.5, no_max_size=30.0)
    configure_paper_execution_runtime(monkeypatch)
    market = make_market()
    assessment = make_assessment(token_side="no")
    no_reservation = {
        "strategy_leg": "NO_CARRY",
        "reserved_worst_loss": strategy.candidate_worst_loss(
            {
                "strategy_leg": "NO_CARRY",
                "token_side": "no",
                "size_multiplier": 0.5,
            },
            10000.0,
        ),
    }
    baseline_reservation = {
        "strategy_leg": "NO_CARRY",
        "reserved_worst_loss": 15.0,
    }
    ts = "2026-04-18T12:00:00+00:00"

    baseline = paper_execution.build_passive_order_intent(
        market, baseline_reservation, assessment, make_quote_snapshot(), ts
    )
    scaled = paper_execution.build_passive_order_intent(
        market, no_reservation, assessment, make_quote_snapshot(), ts
    )

    assert baseline["reason"] is None
    assert scaled["reason"] is None
    assert no_reservation["reserved_worst_loss"] == 22.5
    assert baseline["order"]["shares"] == 18.0723
    assert scaled["order"]["shares"] == 27.1084
    assert scaled["order"]["time_in_force"] == "GTC"
    assert scaled["order"]["expires_at"] is None


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
