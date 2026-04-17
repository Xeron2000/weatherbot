import json

import bot_v2


def make_market(city="nyc", date="2026-04-17", event_id="evt-nyc-2026-04-17"):
    return {
        "city": city,
        "date": date,
        "event_id": event_id,
        "event_slug": event_id,
    }


def make_assessment(
    strategy_leg="YES_SNIPER",
    token_side="yes",
    status="accepted",
    edge=0.08,
    bucket_range=(65.0, 69.0),
    size_multiplier=1.0,
    ask=0.11,
    bid=0.09,
    bid_size=100.0,
    ask_size=80.0,
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
            "ask": ask,
            "bid": bid,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "book_ok": True,
        },
    }


def make_risk_state(bankroll=10000.0):
    return {
        "bankroll": bankroll,
        "global_reserved_worst_loss": 0.0,
        "legs": {
            "YES_SNIPER": {"budget": 3000.0, "reserved": 0.0, "hard_cap": 3000.0},
            "NO_CARRY": {"budget": 7000.0, "reserved": 0.0, "hard_cap": 7000.0},
        },
        "market_exposure": {},
        "city_exposure": {},
        "date_exposure": {},
        "event_exposure": {},
        "active_reservations": [],
    }


def load_router_cfg():
    with open("config.json", encoding="utf-8") as handle:
        config_dict = json.load(handle)
    return bot_v2.load_risk_router_config(config_dict)


def test_config_json_contains_conservative_risk_router_defaults():
    with open("config.json", encoding="utf-8") as handle:
        config_dict = json.load(handle)

    router = config_dict["risk_router"]

    assert router["yes_budget_pct"] == 0.30
    assert router["no_budget_pct"] == 0.70
    assert router["global_usage_cap_pct"] == 0.85
    assert router["per_market_cap_pct"] == 0.08
    assert router["per_city_cap_pct"] == 0.18
    assert router["per_date_cap_pct"] == 0.18
    assert router["per_event_cap_pct"] == 0.18


def test_load_risk_router_config_keeps_independent_leg_budgets():
    router = load_router_cfg()

    assert router["yes_budget_pct"] == 0.30
    assert router["no_budget_pct"] == 0.70
    assert router["yes_leg_cap_pct"] == 0.30
    assert router["no_leg_cap_pct"] == 0.70


def test_route_candidate_assessment_rejects_each_budget_and_cap_reason():
    market = make_market()
    assessment = make_assessment()
    router_cfg = load_router_cfg()

    scenarios = [
        (
            "leg_budget_exceeded",
            {
                "legs": {
                    "YES_SNIPER": {"budget": 10.0, "reserved": 10.0, "hard_cap": 3000.0}
                }
            },
        ),
        (
            "leg_cap_exceeded",
            {
                "legs": {
                    "YES_SNIPER": {
                        "budget": 3000.0,
                        "reserved": 2990.0,
                        "hard_cap": 3000.0,
                    }
                }
            },
        ),
        ("global_cap_exceeded", {"global_reserved_worst_loss": 8490.0}),
        (
            "market_cap_exceeded",
            {"market_exposure": {"nyc|2026-04-17|65.0-69.0": 799.0}},
        ),
        ("city_cap_exceeded", {"city_exposure": {"nyc": 1799.0}}),
        ("date_cap_exceeded", {"date_exposure": {"2026-04-17": 1799.0}}),
        (
            "event_cap_exceeded",
            {"event_exposure": {"nyc|2026-04-17|evt-nyc-2026-04-17": 1799.0}},
        ),
    ]

    for reason_code, overrides in scenarios:
        risk_state = make_risk_state()
        for key, value in overrides.items():
            if isinstance(value, dict):
                risk_state[key].update(value)
            else:
                risk_state[key] = value

        decision = bot_v2.route_candidate_assessment(
            assessment, market, risk_state, router_cfg
        )

        assert decision["status"] == "rejected"
        assert reason_code in decision["reasons"]


def test_route_candidate_assessment_blocks_same_bucket_and_event_cluster_conflicts():
    market = make_market()
    router_cfg = load_router_cfg()

    same_bucket_state = make_risk_state()
    same_bucket_state["active_reservations"].append(
        {
            "event": "nyc|2026-04-17|evt-nyc-2026-04-17",
            "bucket": "65.0-69.0",
            "token_side": "yes",
            "strategy_leg": "YES_SNIPER",
        }
    )
    same_bucket_decision = bot_v2.route_candidate_assessment(
        make_assessment(strategy_leg="NO_CARRY", token_side="no"),
        market,
        same_bucket_state,
        router_cfg,
    )

    assert same_bucket_decision["status"] == "rejected"
    assert "same_bucket_conflict" in same_bucket_decision["reasons"]

    event_conflict_state = make_risk_state()
    event_conflict_state["active_reservations"].append(
        {
            "event": "nyc|2026-04-17|evt-nyc-2026-04-17",
            "bucket": "70.0-74.0",
            "token_side": "yes",
            "strategy_leg": "YES_SNIPER",
        }
    )
    event_conflict_decision = bot_v2.route_candidate_assessment(
        make_assessment(strategy_leg="YES_SNIPER", token_side="yes"),
        market,
        event_conflict_state,
        router_cfg,
    )

    assert event_conflict_decision["status"] == "rejected"
    assert "event_cluster_conflict" in event_conflict_decision["reasons"]


def test_sort_leg_candidates_orders_by_edge_then_liquidity():
    low_edge = make_assessment(strategy_leg="NO_CARRY", token_side="no", edge=0.05)
    high_edge_low_liq = make_assessment(
        strategy_leg="NO_CARRY",
        token_side="no",
        edge=0.08,
        bid_size=10.0,
        ask_size=10.0,
    )
    high_edge_high_liq = make_assessment(
        strategy_leg="NO_CARRY",
        token_side="no",
        edge=0.08,
        bid_size=50.0,
        ask_size=40.0,
    )

    ordered = bot_v2.sort_leg_candidates(
        [low_edge, high_edge_low_liq, high_edge_high_liq]
    )

    assert [item["edge"] for item in ordered] == [0.08, 0.08, 0.05]
    assert ordered[0]["quote_context"]["bid_size"] == 50.0
