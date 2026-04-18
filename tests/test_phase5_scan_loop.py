from datetime import datetime, timedelta, timezone

import bot_v2

from tests.test_phase4_scan_loop import (
    configure_runtime_paths,
    make_assessment,
    make_quote_snapshot,
    patch_probability_and_candidates,
    patch_scan_inputs,
    prepare_single_market,
)


def configure_phase5_runtime(monkeypatch):
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


def freeze_bot_now(monkeypatch, ts):
    frozen = datetime.fromisoformat(ts)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen
            return frozen.astimezone(tz)

    monkeypatch.setattr(bot_v2, "datetime", FrozenDateTime)


def build_ready_market_context(phase2_gamma_event, phase2_weather_snapshot, monkeypatch):
    city, _month, event = prepare_single_market(
        monkeypatch, phase2_gamma_event, phase2_weather_snapshot
    )
    return city, event


def test_scan_and_update_records_touch_without_opening_position_on_first_limit_touch(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    configure_phase5_runtime(monkeypatch)
    city, event = build_ready_market_context(
        phase2_gamma_event, phase2_weather_snapshot, monkeypatch
    )
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [
            event["default_snapshot"],
            {
                **event["default_snapshot"],
                "ts": (
                    datetime.fromisoformat(event["default_snapshot"]["ts"])
                    + timedelta(seconds=6)
                ).isoformat(),
            },
            {
                **event["default_snapshot"],
                "ts": (
                    datetime.fromisoformat(event["default_snapshot"]["ts"])
                    + timedelta(seconds=7)
                ).isoformat(),
            },
        ],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()], [make_assessment()], [make_assessment()]],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.10, yes_ask_size=30.0),
        ],
    )

    bot_v2.scan_and_update()
    bot_v2.scan_and_update()
    bot_v2.scan_and_update()

    market = bot_v2.load_market(city, event["target_date"])

    assert market["position"] is None
    assert market["active_order"] is not None
    assert market["active_order"]["status"] == "working"
    assert market["active_order"]["filled_shares"] == 0.0
    assert market["paper_execution_state"]["status"] == "queued"
    assert market["paper_execution_state"]["queue_ahead_shares"] == 50.0
    assert market["execution_events"][-1]["event_type"] == "touch_not_fill"
    assert market["execution_events"][-1]["reason"] == "queue_ahead_remaining"


def test_scan_and_monitor_progress_partial_then_filled_using_simulated_fill_prices(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    configure_phase5_runtime(monkeypatch)
    city, event = build_ready_market_context(
        phase2_gamma_event, phase2_weather_snapshot, monkeypatch
    )
    base_ts = datetime.fromisoformat(event["default_snapshot"]["ts"])
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [
            event["default_snapshot"],
            {**event["default_snapshot"], "ts": (base_ts + timedelta(seconds=6)).isoformat()},
            {**event["default_snapshot"], "ts": (base_ts + timedelta(seconds=7)).isoformat()},
            {**event["default_snapshot"], "ts": (base_ts + timedelta(seconds=8)).isoformat()},
            {**event["default_snapshot"], "ts": (base_ts + timedelta(seconds=9)).isoformat()},
        ],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [
            [make_assessment()],
            [make_assessment()],
            [make_assessment()],
            [make_assessment()],
            [make_assessment()],
        ],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.10, yes_ask_size=30.0),
            make_quote_snapshot(yes_bid=0.08, yes_ask=0.09, yes_ask_size=180.0),
            make_quote_snapshot(yes_bid=0.07, yes_ask=0.08, yes_ask_size=120.0),
        ],
    )

    bot_v2.scan_and_update()
    bot_v2.scan_and_update()
    bot_v2.scan_and_update()
    resumed_partial = bot_v2.monitor_active_orders()
    resumed_filled = bot_v2.monitor_active_orders()

    market = bot_v2.load_market(city, event["target_date"])
    state = bot_v2.load_state()

    assert resumed_partial == 0
    assert resumed_filled == 1
    assert market["active_order"] is None
    assert market["paper_execution_state"]["status"] == "filled"
    assert market["position"] is not None
    assert market["position"]["shares"] == 200.0
    assert market["position"]["entry_price"] == 0.085
    assert market["position"]["cost"] == 17.0
    assert [event["event_type"] for event in market["execution_events"][-2:]] == [
        "partial_fill",
        "filled",
    ]
    assert state["balance"] == 9983.0


def test_scan_and_monitor_use_cancel_pending_before_terminal_cancel_and_release(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    configure_phase5_runtime(monkeypatch)
    city, event = build_ready_market_context(
        phase2_gamma_event, phase2_weather_snapshot, monkeypatch
    )
    base_ts = datetime.fromisoformat(event["default_snapshot"]["ts"])
    patch_scan_inputs(
        monkeypatch,
        city,
        event,
        [
            event["default_snapshot"],
            {**event["default_snapshot"], "ts": (base_ts + timedelta(seconds=6)).isoformat()},
        ],
    )
    patch_probability_and_candidates(
        monkeypatch,
        [[make_assessment()], [make_assessment(status="rejected", edge=0.01)]],
        [
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
            make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
        ],
    )

    bot_v2.scan_and_update()
    bot_v2.scan_and_update()

    pending_market = bot_v2.load_market(city, event["target_date"])
    pending_state = bot_v2.load_state()

    assert pending_market["active_order"] is not None
    assert pending_market["active_order"]["status"] == "working"
    assert pending_market["paper_execution_state"]["status"] == "cancel_pending"
    assert pending_market["reserved_exposure"]["release_reason"] is None
    assert pending_state["risk_state"]["global_reserved_worst_loss"] == 20.0
    assert pending_market["execution_events"][-1]["event_type"] == "cancel_requested"

    later_snapshot = {
        "ts": (base_ts + timedelta(seconds=11)).isoformat(),
        "best": event["default_snapshot"]["best"],
        "best_source": event["default_snapshot"]["best_source"],
    }

    market_for_monitor = bot_v2.load_market(city, event["target_date"])
    market_for_monitor["quote_snapshot"] = [
        make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0)[0]
    ]
    bot_v2.save_market(market_for_monitor)
    monkeypatch.setattr(
        bot_v2,
        "refresh_active_order_quotes",
        lambda mkt: mkt.get("quote_snapshot", []),
    )
    freeze_bot_now(monkeypatch, later_snapshot["ts"])

    bot_v2.monitor_active_orders()

    canceled_market = bot_v2.load_market(city, event["target_date"])
    canceled_state = bot_v2.load_state()

    assert canceled_market["active_order"] is None
    assert canceled_market["order_history"][-1]["status"] == "canceled"
    assert canceled_market["paper_execution_state"]["status"] == "canceled"
    assert canceled_market["reserved_exposure"]["release_reason"] == "candidate_downgraded"
    assert canceled_state["risk_state"]["global_reserved_worst_loss"] == 0.0


def test_sync_market_order_cancels_active_order_when_candidate_assessment_disappears(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    configure_phase5_runtime(monkeypatch)
    city, event = build_ready_market_context(
        phase2_gamma_event, phase2_weather_snapshot, monkeypatch
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
    market["candidate_assessments"] = []
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
            "market": f"{city}|{event['target_date']}|65.0-69.0",
            "city": city,
            "date": event["target_date"],
            "event": f"{city}|{event['target_date']}|{event['payload'].get('id')}",
            "bucket": "65.0-69.0",
        },
    }
    market["quote_snapshot"] = make_quote_snapshot(
        yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0
    )

    order_intent = bot_v2.build_passive_order_intent(
        market,
        market["reserved_exposure"],
        make_assessment(),
        market["quote_snapshot"],
        ts,
    )
    market["active_order"] = bot_v2.apply_order_transition(
        order_intent["order"], "working", "order_submitted", ts
    )
    market["paper_execution_state"] = {
        "order_id": market["active_order"]["order_id"],
        "status": "queued",
        "submitted_at": ts,
        "submit_ready_at": (datetime.fromisoformat(ts) - timedelta(seconds=1)).isoformat(),
        "cancel_requested_at": None,
        "cancel_ready_at": None,
        "touch_count": 0,
        "queue_ahead_shares": 80.0,
        "filled_shares": 0.0,
        "remaining_shares": 200.0,
        "last_event_ts": ts,
        "last_reason": "submission_latency_elapsed",
    }
    market["execution_events"] = []
    market["execution_metrics"] = {}

    state = bot_v2.load_state()
    update = bot_v2.sync_market_order(
        market,
        state["risk_state"],
        {
            "ts": (datetime.fromisoformat(ts) + timedelta(seconds=1)).isoformat(),
            "best": event["default_snapshot"]["best"],
            "best_source": event["default_snapshot"]["best_source"],
        },
        market_ready=True,
    )

    assert update == {"filled_cost": 0.0, "opened_position": False}
    assert market["active_order"] is not None
    assert market["active_order"]["status"] == "working"
    assert market["paper_execution_state"]["status"] == "cancel_pending"
    assert market["paper_execution_state"]["cancel_reason"] == "candidate_missing"
    assert market["reserved_exposure"]["release_reason"] is None
    assert market["execution_events"][-1]["event_type"] == "cancel_requested"
    assert market["execution_events"][-1]["cancel_reason"] == "candidate_missing"


def test_monitor_active_orders_resumes_existing_paper_execution_state_without_reset(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    configure_phase5_runtime(monkeypatch)
    city, event = build_ready_market_context(
        phase2_gamma_event, phase2_weather_snapshot, monkeypatch
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
            "market": f"{city}|{event['target_date']}|65.0-69.0",
            "city": city,
            "date": event["target_date"],
            "event": f"{city}|{event['target_date']}|{event['payload'].get('id')}",
            "bucket": "65.0-69.0",
        },
    }
    order_intent = bot_v2.build_passive_order_intent(
        market,
        market["reserved_exposure"],
        make_assessment(),
        make_quote_snapshot(yes_bid=0.09, yes_ask=0.11, yes_ask_size=500.0),
        ts,
    )
    market["active_order"] = bot_v2.apply_order_transition(
        order_intent["order"], "working", "order_submitted", ts
    )
    market["paper_execution_state"] = {
        "order_id": market["active_order"]["order_id"],
        "status": "queued",
        "submitted_at": ts,
        "submit_ready_at": (datetime.fromisoformat(ts) - timedelta(seconds=1)).isoformat(),
        "cancel_requested_at": None,
        "cancel_ready_at": None,
        "touch_count": 1,
        "queue_ahead_shares": 50.0,
        "filled_shares": 0.0,
        "remaining_shares": 200.0,
        "last_event_ts": (datetime.fromisoformat(ts) + timedelta(seconds=7)).isoformat(),
        "last_reason": "queue_ahead_remaining",
    }
    market["execution_events"] = [
        {
            "event_type": "submission_pending",
            "ts": ts,
            "order_id": market["active_order"]["order_id"],
            "status_before": "idle",
            "status_after": "submitting",
            "reason": "submission_latency_pending",
            "simulated_fill_shares": 0.0,
            "queue_ahead_shares": 80.0,
            "latency_ms": 5000,
        },
        {
            "event_type": "submission_released",
            "ts": (datetime.fromisoformat(ts) + timedelta(seconds=6)).isoformat(),
            "order_id": market["active_order"]["order_id"],
            "status_before": "submitting",
            "status_after": "queued",
            "reason": "submission_latency_elapsed",
            "simulated_fill_shares": 0.0,
            "queue_ahead_shares": 80.0,
            "latency_ms": 5000,
        },
        {
            "event_type": "touch_not_fill",
            "ts": (datetime.fromisoformat(ts) + timedelta(seconds=7)).isoformat(),
            "order_id": market["active_order"]["order_id"],
            "status_before": "queued",
            "status_after": "queued",
            "reason": "queue_ahead_remaining",
            "simulated_fill_shares": 0.0,
            "queue_ahead_shares": 50.0,
            "latency_ms": 0,
        },
    ]
    market["execution_metrics"] = {
        "event_count": 3,
        "touch_not_fill_count": 1,
        "partial_fill_count": 0,
        "filled_count": 0,
        "cancel_requested_count": 0,
        "cancel_count": 0,
        "filled_shares_total": 0.0,
    }
    market["forecast_snapshots"] = [
        {
            "ts": ts,
            "best": event["default_snapshot"]["best"],
            "best_source": event["default_snapshot"]["best_source"],
        }
    ]
    market["quote_snapshot"] = make_quote_snapshot(
        yes_bid=0.09, yes_ask=0.10, yes_ask_size=30.0
    )
    bot_v2.save_market(market)

    monkeypatch.setattr(
        bot_v2,
        "refresh_active_order_quotes",
        lambda mkt: mkt.get("quote_snapshot", []),
    )
    freeze_bot_now(monkeypatch, (datetime.fromisoformat(ts) + timedelta(seconds=8)).isoformat())

    bot_v2.monitor_active_orders()

    restored_market = bot_v2.load_market(city, event["target_date"])

    assert restored_market["paper_execution_state"]["status"] == "queued"
    assert restored_market["paper_execution_state"]["touch_count"] == 2
    assert restored_market["paper_execution_state"]["queue_ahead_shares"] == 20.0
    assert len(restored_market["execution_events"]) == 4
    assert restored_market["execution_events"][0]["event_type"] == "submission_pending"
    assert restored_market["execution_events"][-1]["event_type"] == "touch_not_fill"
    assert restored_market["execution_events"][-1]["status_before"] == "queued"
