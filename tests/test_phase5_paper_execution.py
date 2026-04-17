import json

import pytest

import bot_v2


def load_config_dict():
    with open("config.json", encoding="utf-8") as handle:
        return json.load(handle)


def make_paper_config(**overrides):
    cfg = {
        "submission_latency_ms": 5000,
        "queue_ahead_shares": 80.0,
        "queue_ahead_ratio": 0.0,
        "touch_not_fill_min_touches": 1,
        "partial_fill_slice_ratio": 0.5,
        "cancel_latency_ms": 4000,
        "adverse_fill_buffer_ticks": 0,
    }
    cfg.update(overrides)
    return cfg


def make_market():
    return {
        "city": "nyc",
        "date": "2026-04-18",
        "paper_execution_state": None,
        "execution_events": [],
        "execution_metrics": {},
    }


def make_order():
    return {
        "order_id": "ord-paper-1",
        "market_id": "mkt-65-69",
        "token_side": "yes",
        "limit_price": 0.10,
        "shares": 100.0,
        "filled_shares": 0.0,
        "remaining_shares": 100.0,
        "status": "working",
    }


def make_quote_snapshot(ask=0.11, ask_size=0.0, bid=0.09, tick_size=0.01):
    return [
        {
            "market_id": "mkt-65-69",
            "yes": {
                "bid": bid,
                "ask": ask,
                "ask_size": ask_size,
                "tick_size": tick_size,
            },
            "execution_ok": True,
            "execution_stop_reasons": [],
        }
    ]


def assert_event_schema(event, event_type, status_before, status_after, reason):
    assert event["event_type"] == event_type
    assert event["status_before"] == status_before
    assert event["status_after"] == status_after
    assert event["reason"] == reason
    assert set(event).issuperset(
        {
            "event_type",
            "ts",
            "order_id",
            "status_before",
            "status_after",
            "reason",
            "simulated_fill_shares",
            "queue_ahead_shares",
            "latency_ms",
        }
    )


def test_load_paper_execution_config_requires_explicit_phase5_fields():
    config_dict = load_config_dict()

    assert "paper_execution" in config_dict

    loaded = bot_v2.load_paper_execution_config(config_dict)

    assert loaded["submission_latency_ms"] > 0
    assert loaded["queue_ahead_shares"] >= 0
    assert loaded["queue_ahead_ratio"] >= 0
    assert loaded["touch_not_fill_min_touches"] >= 1
    assert loaded["partial_fill_slice_ratio"] > 0
    assert loaded["cancel_latency_ms"] > 0
    assert loaded["adverse_fill_buffer_ticks"] >= 0

    with pytest.raises(ValueError, match="paper_execution_missing_submission_latency_ms"):
        bot_v2.load_paper_execution_config({"paper_execution": {}})


def test_submission_latency_keeps_order_in_submitting_state_before_any_fill():
    step = bot_v2.simulate_paper_execution_step(
        make_market(),
        make_order(),
        make_quote_snapshot(ask=0.09, ask_size=500.0),
        "2026-04-18T12:00:00+00:00",
        paper_config=make_paper_config(),
    )

    state = step["market"]["paper_execution_state"]
    event = step["market"]["execution_events"][-1]

    assert state["status"] == "submitting"
    assert state["filled_shares"] == 0.0
    assert step["filled_shares"] == 0.0
    assert_event_schema(
        event,
        "submission_pending",
        "idle",
        "submitting",
        "submission_latency_pending",
    )


def test_quote_touch_records_touch_not_fill_until_queue_ahead_is_consumed():
    cfg = make_paper_config()
    market = make_market()
    order = make_order()

    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:00+00:00",
        paper_config=cfg,
    )["market"]
    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:06+00:00",
        paper_config=cfg,
    )["market"]

    step = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(ask=0.10, ask_size=30.0),
        "2026-04-18T12:00:07+00:00",
        paper_config=cfg,
    )

    state = step["market"]["paper_execution_state"]
    event = step["market"]["execution_events"][-1]

    assert state["status"] == "queued"
    assert state["queue_ahead_shares"] == 50.0
    assert state["filled_shares"] == 0.0
    assert step["filled_shares"] == 0.0
    assert_event_schema(
        event,
        "touch_not_fill",
        "queued",
        "queued",
        "queue_ahead_remaining",
    )


def test_queue_consumption_allows_partial_fill_then_full_fill_with_append_only_events():
    cfg = make_paper_config()
    order = make_order()
    market = make_market()

    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:00+00:00",
        paper_config=cfg,
    )["market"]
    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:06+00:00",
        paper_config=cfg,
    )["market"]
    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(ask=0.10, ask_size=30.0),
        "2026-04-18T12:00:07+00:00",
        paper_config=cfg,
    )["market"]

    partial = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(ask=0.09, ask_size=180.0),
        "2026-04-18T12:00:08+00:00",
        paper_config=cfg,
    )

    partial_state = partial["market"]["paper_execution_state"]
    partial_event = partial["market"]["execution_events"][-1]
    assert partial_state["status"] == "partial"
    assert partial_state["filled_shares"] == 50.0
    assert partial_state["remaining_shares"] == 50.0
    assert partial["filled_shares"] == 50.0
    assert_event_schema(
        partial_event,
        "partial_fill",
        "queued",
        "partial",
        "queue_cleared_partial_fill",
    )

    filled = bot_v2.simulate_paper_execution_step(
        partial["market"],
        order,
        make_quote_snapshot(ask=0.09, ask_size=100.0),
        "2026-04-18T12:00:09+00:00",
        paper_config=cfg,
    )

    filled_state = filled["market"]["paper_execution_state"]
    filled_event = filled["market"]["execution_events"][-1]
    assert filled_state["status"] == "filled"
    assert filled_state["filled_shares"] == 100.0
    assert filled_state["remaining_shares"] == 0.0
    assert filled["filled_shares"] == 50.0
    assert len(filled["market"]["execution_events"]) == 5
    assert_event_schema(
        filled_event,
        "filled",
        "partial",
        "filled",
        "queue_cleared_full_fill",
    )


def test_cancel_request_waits_for_cancel_latency_before_terminal_cancel_event():
    cfg = make_paper_config()
    order = make_order()
    market = make_market()

    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:00+00:00",
        paper_config=cfg,
    )["market"]
    market = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:06+00:00",
        paper_config=cfg,
    )["market"]

    pending = bot_v2.simulate_paper_execution_step(
        market,
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:07+00:00",
        paper_config=cfg,
        cancel_requested=True,
    )

    pending_state = pending["market"]["paper_execution_state"]
    pending_event = pending["market"]["execution_events"][-1]
    assert pending_state["status"] == "cancel_pending"
    assert_event_schema(
        pending_event,
        "cancel_requested",
        "queued",
        "cancel_pending",
        "cancel_latency_pending",
    )

    still_pending = bot_v2.simulate_paper_execution_step(
        pending["market"],
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:09+00:00",
        paper_config=cfg,
        cancel_requested=True,
    )
    assert still_pending["market"]["paper_execution_state"]["status"] == "cancel_pending"
    assert len(still_pending["market"]["execution_events"]) == len(
        pending["market"]["execution_events"]
    )

    canceled = bot_v2.simulate_paper_execution_step(
        still_pending["market"],
        order,
        make_quote_snapshot(),
        "2026-04-18T12:00:11+00:00",
        paper_config=cfg,
        cancel_requested=True,
    )

    canceled_state = canceled["market"]["paper_execution_state"]
    canceled_event = canceled["market"]["execution_events"][-1]
    assert canceled_state["status"] == "canceled"
    assert_event_schema(
        canceled_event,
        "cancel_confirmed",
        "cancel_pending",
        "canceled",
        "cancel_latency_elapsed",
    )
