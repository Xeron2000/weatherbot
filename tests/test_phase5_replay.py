from datetime import datetime, timedelta, timezone

import bot_v2

from tests.test_phase4_scan_loop import configure_runtime_paths


def make_event(ts, order_id, event_type, status_before, status_after, reason, **extra):
    event = {
        "event_type": event_type,
        "ts": ts,
        "order_id": order_id,
        "status_before": status_before,
        "status_after": status_after,
        "reason": reason,
        "simulated_fill_shares": 0.0,
        "queue_ahead_shares": 0.0,
        "latency_ms": 0,
    }
    event.update(extra)
    return event


def make_replay_market(city, date_str, order_id, status, updated_at):
    market = bot_v2.new_market(
        city,
        date_str,
        {"id": f"evt-{city}-{date_str}", "slug": f"evt-{city}-{date_str}", "endDate": f"{date_str}T23:59:00Z"},
        18.0,
    )
    market["market_contracts"] = [
        {
            "market_id": f"mkt-{city}-{date_str}",
            "question": "Between 65-69F",
            "range": [65.0, 69.0],
            "condition_id": f"cond-{city}-{date_str}",
            "token_id_yes": f"yes-{city}-{date_str}",
            "token_id_no": f"no-{city}-{date_str}",
            "unit": "F",
        }
    ]
    market["paper_execution_state"] = {
        "order_id": order_id,
        "status": status,
        "submitted_at": updated_at,
        "submit_ready_at": updated_at,
        "cancel_requested_at": None,
        "cancel_ready_at": None,
        "cancel_reason": None,
        "touch_count": 0,
        "queue_ahead_shares": 0.0,
        "filled_shares": 0.0,
        "remaining_shares": 0.0,
        "last_event_ts": updated_at,
        "last_reason": status,
    }
    market["execution_metrics"] = {
        "event_count": 0,
        "touch_not_fill_count": 0,
        "partial_fill_count": 0,
        "filled_count": 0,
        "cancel_requested_count": 0,
        "cancel_count": 0,
        "filled_shares_total": 0.0,
    }
    return market


def test_print_replay_shows_submit_touch_queue_partial_fill_and_cancel_timeline(
    tmp_path, monkeypatch, capsys
):
    configure_runtime_paths(tmp_path, monkeypatch)
    base = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)

    filled_order_id = "ord-filled-1"
    filled_market = make_replay_market("nyc", "2026-04-18", filled_order_id, "filled", (base + timedelta(seconds=9)).isoformat())
    filled_market["execution_events"] = [
        make_event(base.isoformat(), filled_order_id, "submission_pending", "idle", "submitting", "submission_latency_pending", queue_ahead_shares=80.0, latency_ms=5000),
        make_event((base + timedelta(seconds=5)).isoformat(), filled_order_id, "submission_released", "submitting", "queued", "submission_latency_elapsed", queue_ahead_shares=80.0, latency_ms=5000),
        make_event((base + timedelta(seconds=6)).isoformat(), filled_order_id, "touch_not_fill", "queued", "queued", "queue_ahead_remaining", queue_ahead_shares=50.0),
        make_event((base + timedelta(seconds=8)).isoformat(), filled_order_id, "partial_fill", "queued", "partial", "queue_cleared_partial_fill", simulated_fill_shares=120.0, simulated_fill_price=0.09),
        make_event((base + timedelta(seconds=9)).isoformat(), filled_order_id, "filled", "partial", "filled", "queue_cleared_full_fill", simulated_fill_shares=80.0, simulated_fill_price=0.08),
    ]
    filled_market["paper_execution_state"].update(
        {
            "touch_count": 1,
            "filled_shares": 200.0,
            "remaining_shares": 0.0,
            "last_event_ts": (base + timedelta(seconds=9)).isoformat(),
            "last_reason": "queue_cleared_full_fill",
        }
    )
    filled_market["execution_metrics"].update(
        {
            "event_count": 5,
            "touch_not_fill_count": 1,
            "partial_fill_count": 1,
            "filled_count": 1,
            "filled_shares_total": 200.0,
        }
    )
    filled_market["order_history"] = [
        {
            "order_id": filled_order_id,
            "market_id": "mkt-nyc-2026-04-18",
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "limit_price": 0.10,
            "shares": 200.0,
            "filled_shares": 200.0,
            "remaining_shares": 0.0,
            "status": "filled",
            "status_reason": "queue_cleared_full_fill",
            "created_at": base.isoformat(),
            "updated_at": (base + timedelta(seconds=9)).isoformat(),
            "history": [],
        }
    ]

    canceled_order_id = "ord-canceled-1"
    canceled_market = make_replay_market("chicago", "2026-04-19", canceled_order_id, "canceled", (base + timedelta(seconds=14)).isoformat())
    canceled_market["execution_events"] = [
        make_event(base.isoformat(), canceled_order_id, "submission_pending", "idle", "submitting", "submission_latency_pending", queue_ahead_shares=60.0, latency_ms=5000),
        make_event((base + timedelta(seconds=5)).isoformat(), canceled_order_id, "submission_released", "submitting", "queued", "submission_latency_elapsed", queue_ahead_shares=60.0, latency_ms=5000),
        make_event((base + timedelta(seconds=10)).isoformat(), canceled_order_id, "cancel_requested", "queued", "cancel_pending", "cancel_latency_pending", queue_ahead_shares=60.0, latency_ms=4000, cancel_reason="candidate_downgraded"),
        make_event((base + timedelta(seconds=14)).isoformat(), canceled_order_id, "cancel_confirmed", "cancel_pending", "canceled", "cancel_latency_elapsed", queue_ahead_shares=60.0, latency_ms=4000, cancel_reason="candidate_downgraded"),
    ]
    canceled_market["paper_execution_state"].update(
        {
            "cancel_requested_at": (base + timedelta(seconds=10)).isoformat(),
            "cancel_ready_at": (base + timedelta(seconds=14)).isoformat(),
            "cancel_reason": "candidate_downgraded",
            "remaining_shares": 150.0,
            "last_event_ts": (base + timedelta(seconds=14)).isoformat(),
            "last_reason": "cancel_latency_elapsed",
        }
    )
    canceled_market["execution_metrics"].update(
        {
            "event_count": 4,
            "cancel_requested_count": 1,
            "cancel_count": 1,
        }
    )
    canceled_market["order_history"] = [
        {
            "order_id": canceled_order_id,
            "market_id": "mkt-chicago-2026-04-19",
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "limit_price": 0.10,
            "shares": 150.0,
            "filled_shares": 0.0,
            "remaining_shares": 150.0,
            "status": "canceled",
            "status_reason": "candidate_downgraded",
            "created_at": base.isoformat(),
            "updated_at": (base + timedelta(seconds=14)).isoformat(),
            "history": [],
        }
    ]

    bot_v2.save_market(filled_market)
    bot_v2.save_market(canceled_market)

    bot_v2.print_replay(limit=5)
    out = capsys.readouterr().out

    assert "Replay orders" in out
    assert filled_order_id in out
    assert canceled_order_id in out
    assert "submission_pending" in out
    assert "touch_not_fill" in out
    assert "partial_fill" in out
    assert "filled" in out
    assert "cancel_requested" in out
    assert "cancel_confirmed" in out


def test_print_replay_shows_fill_quality_summary_and_parameter_tuning_hints(
    tmp_path, monkeypatch, capsys
):
    configure_runtime_paths(tmp_path, monkeypatch)
    base = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    order_id = "ord-filled-2"
    market = make_replay_market("nyc", "2026-04-18", order_id, "filled", (base + timedelta(seconds=9)).isoformat())
    market["execution_events"] = [
        make_event(base.isoformat(), order_id, "submission_pending", "idle", "submitting", "submission_latency_pending", queue_ahead_shares=80.0, latency_ms=5000),
        make_event((base + timedelta(seconds=5)).isoformat(), order_id, "submission_released", "submitting", "queued", "submission_latency_elapsed", queue_ahead_shares=80.0, latency_ms=5000),
        make_event((base + timedelta(seconds=6)).isoformat(), order_id, "touch_not_fill", "queued", "queued", "queue_ahead_remaining", queue_ahead_shares=50.0),
        make_event((base + timedelta(seconds=8)).isoformat(), order_id, "partial_fill", "queued", "partial", "queue_cleared_partial_fill", simulated_fill_shares=120.0, simulated_fill_price=0.09),
        make_event((base + timedelta(seconds=9)).isoformat(), order_id, "filled", "partial", "filled", "queue_cleared_full_fill", simulated_fill_shares=80.0, simulated_fill_price=0.08),
    ]
    market["paper_execution_state"].update(
        {
            "touch_count": 1,
            "filled_shares": 200.0,
            "remaining_shares": 0.0,
            "last_event_ts": (base + timedelta(seconds=9)).isoformat(),
            "last_reason": "queue_cleared_full_fill",
        }
    )
    market["execution_metrics"] = {
        "event_count": 5,
        "touch_not_fill_count": 1,
        "partial_fill_count": 1,
        "filled_count": 1,
        "cancel_requested_count": 0,
        "cancel_count": 0,
        "filled_shares_total": 200.0,
    }
    market["order_history"] = [
        {
            "order_id": order_id,
            "market_id": "mkt-nyc-2026-04-18",
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "limit_price": 0.10,
            "shares": 200.0,
            "filled_shares": 200.0,
            "remaining_shares": 0.0,
            "status": "filled",
            "status_reason": "queue_cleared_full_fill",
            "created_at": base.isoformat(),
            "updated_at": (base + timedelta(seconds=9)).isoformat(),
            "history": [],
        }
    ]
    bot_v2.save_market(market)

    bot_v2.print_replay(order_filter=order_id)
    out = capsys.readouterr().out

    assert "touch_not_fill=1" in out
    assert "queue_wait_ms=3000" in out
    assert "partial_fill_slices=1" in out
    assert "filled_shares=200.0000/200.0000" in out
    assert "unfilled_shares=0.0000" in out
    assert "adverse_buffer_hits=2" in out
    assert "queue_ahead_shares / touch_not_fill_min_touches" in out
    assert "partial_fill_slice_ratio" in out
    assert "adverse_fill_buffer_ticks" in out


def test_print_replay_supports_recent_market_and_order_filters_without_rescanning(
    tmp_path, monkeypatch, capsys
):
    configure_runtime_paths(tmp_path, monkeypatch)
    base = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)

    older = make_replay_market("nyc", "2026-04-18", "ord-old", "filled", base.isoformat())
    older["execution_events"] = [
        make_event(base.isoformat(), "ord-old", "submission_pending", "idle", "submitting", "submission_latency_pending")
    ]
    older["order_history"] = [
        {
            "order_id": "ord-old",
            "market_id": "mkt-old",
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "limit_price": 0.10,
            "shares": 100.0,
            "filled_shares": 100.0,
            "remaining_shares": 0.0,
            "status": "filled",
            "status_reason": "queue_cleared_full_fill",
            "created_at": base.isoformat(),
            "updated_at": base.isoformat(),
            "history": [],
        }
    ]

    newer = make_replay_market("chicago", "2026-04-19", "ord-new", "canceled", (base + timedelta(minutes=1)).isoformat())
    newer["execution_events"] = [
        make_event((base + timedelta(minutes=1)).isoformat(), "ord-new", "cancel_confirmed", "cancel_pending", "canceled", "cancel_latency_elapsed")
    ]
    newer["order_history"] = [
        {
            "order_id": "ord-new",
            "market_id": "mkt-new",
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": [65.0, 69.0],
            "limit_price": 0.10,
            "shares": 100.0,
            "filled_shares": 0.0,
            "remaining_shares": 100.0,
            "status": "canceled",
            "status_reason": "candidate_downgraded",
            "created_at": (base + timedelta(minutes=1)).isoformat(),
            "updated_at": (base + timedelta(minutes=1)).isoformat(),
            "history": [],
        }
    ]

    bot_v2.save_market(older)
    bot_v2.save_market(newer)

    bot_v2.print_replay(limit=1)
    out = capsys.readouterr().out
    assert "ord-new" in out
    assert "ord-old" not in out

    bot_v2.print_replay(market_filter="mkt-old")
    out = capsys.readouterr().out
    assert "ord-old" in out
    assert "ord-new" not in out

    bot_v2.print_replay(order_filter="missing-order")
    out = capsys.readouterr().out
    assert "No replay orders matched" in out
    assert "order_id=missing-order" in out
