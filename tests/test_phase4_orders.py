import json
from datetime import datetime, timedelta

import bot_v2


def load_order_cfg():
    with open("config.json", encoding="utf-8") as handle:
        config_dict = json.load(handle)
    return config_dict["order_policy"], bot_v2.load_order_policy_config(config_dict)


def make_market(city="nyc", date="2026-04-17", event_id="evt-nyc-2026-04-17"):
    return {
        "city": city,
        "date": date,
        "event_id": event_id,
        "event_slug": event_id,
        "market_contracts": [
            {
                "market_id": "mkt-65-69",
                "range": (65.0, 69.0),
            }
        ],
        "candidate_assessments": [make_assessment()],
        "route_decisions": [],
        "reserved_exposure": None,
    }


def make_reservation(
    strategy_leg="YES_SNIPER",
    token_side="yes",
    bucket_range=(65.0, 69.0),
    reserved_worst_loss=20.0,
):
    return {
        "strategy_leg": strategy_leg,
        "token_side": token_side,
        "range": list(bucket_range),
        "reserved_worst_loss": reserved_worst_loss,
    }


def make_assessment(
    strategy_leg="YES_SNIPER",
    token_side="yes",
    status="accepted",
    edge=0.08,
    bucket_range=(65.0, 69.0),
    bid=0.09,
    ask=0.11,
    tick_size=0.01,
    fair_yes=0.18,
    fair_no=0.82,
):
    return {
        "strategy_leg": strategy_leg,
        "token_side": token_side,
        "range": bucket_range,
        "status": status,
        "edge": edge,
        "fair_yes": fair_yes,
        "fair_no": fair_no,
        "reasons": [],
        "quote_context": {
            "bid": bid,
            "ask": ask,
            "tick_size": tick_size,
        },
    }


def make_quote_snapshot(
    yes_bid=0.09, yes_ask=0.11, no_bid=0.81, no_ask=0.83, tick_size=0.01
):
    return [
        {
            "market_id": "mkt-65-69",
            "yes": {
                "bid": yes_bid,
                "ask": yes_ask,
                "tick_size": tick_size,
                "min_order_size": 1.0,
            },
            "no": {
                "bid": no_bid,
                "ask": no_ask,
                "tick_size": tick_size,
                "min_order_size": 1.0,
            },
            "execution_ok": True,
            "execution_stop_reasons": [],
        }
    ]


def test_config_json_contains_phase4_order_policy_defaults():
    raw, policy = load_order_cfg()

    assert raw["yes_time_in_force"] == "GTC"
    assert raw["gtd_buffer_hours"] == 6.0
    assert raw["price_improve_ticks"] == 1
    assert raw["replace_edge_buffer"] == 0.02
    assert raw["max_order_hours_open"] == 72.0

    assert policy["yes_time_in_force"] == "GTC"


def test_build_passive_order_intent_only_builds_for_accepted_route_with_initial_planned_history():
    market = make_market()
    reservation = make_reservation()
    assessment = market["candidate_assessments"][0]
    quote_snapshot = make_quote_snapshot()
    now_ts = "2026-04-17T12:00:00+00:00"

    built = bot_v2.build_passive_order_intent(
        market,
        reservation,
        assessment,
        quote_snapshot,
        now_ts,
    )

    assert built["reason"] is None
    order = built["order"]

    assert order["status"] == "planned"
    assert order["strategy_leg"] == "YES_SNIPER"
    assert order["token_side"] == "yes"
    assert order["market_id"] == "mkt-65-69"
    assert order["range"] == [65.0, 69.0]
    assert order["limit_price"] == 0.1
    assert order["shares"] == 200.0
    assert order["filled_shares"] == 0.0
    assert order["remaining_shares"] == 200.0
    assert order["time_in_force"] == "GTC"
    assert order["expires_at"] is None
    assert order["created_at"] == now_ts
    assert order["updated_at"] == now_ts
    assert order["status_reason"] == "accepted_route"
    assert order["history"][0]["status"] == "planned"
    assert order["history"][0]["reason"] == "accepted_route"


def test_build_passive_order_intent_rejects_unaccepted_or_non_yes_routes():
    market = make_market()
    quote_snapshot = make_quote_snapshot()
    now_ts = "2026-04-17T12:00:00+00:00"

    blocked = bot_v2.build_passive_order_intent(
        market,
        make_reservation(),
        make_assessment(status="rejected"),
        quote_snapshot,
        now_ts,
    )

    assert blocked["order"] is None
    assert blocked["reason"] == "route_not_accepted"

    no_route = bot_v2.build_passive_order_intent(
        market,
        make_reservation(strategy_leg="NO_CARRY", token_side="no"),
        make_assessment(strategy_leg="NO_CARRY", token_side="no"),
        quote_snapshot,
        now_ts,
    )

    assert no_route["order"] is None
    assert no_route["reason"] == "yes_only_runtime"


def test_build_passive_order_intent_keeps_yes_gtd_policy_when_configured(monkeypatch):
    market = make_market()
    monkeypatch.setattr(
        bot_v2,
        "ORDER_POLICY",
        {
            **bot_v2.ORDER_POLICY,
            "yes_time_in_force": "GTD",
            "gtd_buffer_hours": 6.0,
        },
    )

    built = bot_v2.build_passive_order_intent(
        market,
        make_reservation(),
        make_assessment(),
        make_quote_snapshot(),
        "2026-04-17T12:00:00+00:00",
    )

    assert built["reason"] is None
    assert built["order"]["time_in_force"] == "GTD"
    assert built["order"]["expires_at"] == (
        datetime.fromisoformat("2026-04-17T12:00:00+00:00")
        + timedelta(hours=6.0)
    ).isoformat()


def test_build_passive_order_intent_returns_deterministic_quote_reasons_without_crossing_spread():
    market = make_market()
    reservation = make_reservation()
    assessment = make_assessment()
    now_ts = "2026-04-17T12:00:00+00:00"

    missing_tick = bot_v2.build_passive_order_intent(
        market,
        reservation,
        assessment,
        make_quote_snapshot(tick_size=None),
        now_ts,
    )
    missing_quote = bot_v2.build_passive_order_intent(
        market,
        reservation,
        assessment,
        [
            {
                "market_id": "mkt-65-69",
                "yes": {"bid": None, "ask": 0.11, "tick_size": 0.01},
            }
        ],
        now_ts,
    )

    assert missing_tick["order"] is None
    assert missing_tick["reason"] == "tick_size_missing"
    assert missing_quote["order"] is None
    assert missing_quote["reason"] == "quote_price_missing"


def test_apply_order_transition_normalizes_statuses_and_appends_history():
    order = {
        "order_id": "ord-1",
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "limit_price": 0.1,
        "shares": 200.0,
        "filled_shares": 0.0,
        "remaining_shares": 200.0,
        "time_in_force": "GTC",
        "expires_at": None,
        "status": "planned",
        "status_reason": "accepted_route",
        "created_at": "2026-04-17T12:00:00+00:00",
        "updated_at": "2026-04-17T12:00:00+00:00",
        "history": [
            {
                "status": "planned",
                "reason": "accepted_route",
                "ts": "2026-04-17T12:00:00+00:00",
                "fill_shares": 0.0,
                "fill_price": None,
            }
        ],
    }

    statuses = ["planned", "working", "partial", "filled", "canceled", "expired"]
    current = order
    for idx, status in enumerate(statuses[1:], start=1):
        current = bot_v2.apply_order_transition(
            current,
            status,
            f"reason_{status}",
            f"2026-04-17T12:0{idx}:00+00:00",
            fill_shares=25.0 if status in {"partial", "filled"} else 0.0,
            fill_price=0.1 if status in {"partial", "filled"} else None,
        )
        assert current["status"] == status
        assert current["status_reason"] == f"reason_{status}"

    assert current["filled_shares"] == 50.0
    assert current["remaining_shares"] == 150.0
    assert [item["status"] for item in current["history"]] == statuses
    assert current["history"][3]["fill_shares"] == 25.0
    assert bot_v2.is_order_terminal(current) is True


def test_market_defaults_and_loader_backfill_phase4_order_fields(tmp_path, monkeypatch):
    fresh = bot_v2.new_market(
        "nyc",
        "2026-04-17",
        {"slug": "evt-nyc-2026-04-17", "id": "evt-nyc-2026-04-17"},
        24.0,
    )

    assert fresh["active_order"] is None
    assert fresh["order_history"] == []

    monkeypatch.setattr(bot_v2, "MARKETS_DIR", tmp_path)
    legacy_path = bot_v2.market_path("nyc", "2026-04-18")
    legacy_path.write_text(
        json.dumps(
            {
                "city": "nyc",
                "date": "2026-04-18",
                "event_slug": "evt-legacy",
                "event_id": "evt-legacy",
                "status": "open",
            }
        ),
        encoding="utf-8",
    )

    restored = bot_v2.load_market("nyc", "2026-04-18")

    assert restored["active_order"] is None
    assert restored["order_history"] == []
