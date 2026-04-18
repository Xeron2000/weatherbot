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


def test_config_json_contains_no_specific_sizing_controls():
    with open("config.json", encoding="utf-8") as handle:
        config_dict = json.load(handle)

    assert config_dict["no_kelly_fraction"] == 1.5
    assert config_dict["no_strategy"]["max_size"] > config_dict["yes_strategy"]["max_size"]


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


def test_candidate_worst_loss_uses_strategy_size_not_quote_price(monkeypatch):
    monkeypatch.setattr(bot_v2._strategy, "NO_KELLY_FRACTION", 1.0, raising=False)
    monkeypatch.setattr(
        bot_v2,
        "YES_STRATEGY",
        {
            "max_price": 0.25,
            "min_probability": 0.14,
            "min_edge": 0.03,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )
    monkeypatch.setattr(
        bot_v2,
        "NO_STRATEGY",
        {
            "min_price": 0.65,
            "min_probability": 0.70,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    yes_assessment = make_assessment(
        strategy_leg="YES_SNIPER",
        token_side="yes",
        size_multiplier=1.0,
        ask=0.02,
    )
    no_assessment = make_assessment(
        strategy_leg="NO_CARRY",
        token_side="no",
        size_multiplier=0.5,
        bid=0.95,
    )

    assert bot_v2.candidate_worst_loss(yes_assessment, 10000.0) == 20.0
    assert bot_v2.candidate_worst_loss(no_assessment, 10000.0) == 10.0


def test_no_candidate_worst_loss_and_route_use_no_specific_scaling(monkeypatch):
    monkeypatch.setattr(bot_v2._strategy, "NO_KELLY_FRACTION", 1.5, raising=False)
    monkeypatch.setattr(
        bot_v2,
        "YES_STRATEGY",
        {
            "max_price": 0.25,
            "min_probability": 0.14,
            "min_edge": 0.03,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )
    monkeypatch.setattr(
        bot_v2,
        "NO_STRATEGY",
        {
            "min_price": 0.65,
            "min_probability": 0.70,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 30.0,
            "min_size": 1.0,
        },
    )
    monkeypatch.setattr(bot_v2, "NO_KELLY_FRACTION", 1.5, raising=False)
    monkeypatch.setattr(bot_v2, "KELLY_FRACTION", 0.01)

    yes_assessment = make_assessment(
        strategy_leg="YES_SNIPER",
        token_side="yes",
        size_multiplier=1.0,
    )
    no_assessment = make_assessment(
        strategy_leg="NO_CARRY",
        token_side="no",
        size_multiplier=0.5,
    )
    market = make_market()
    risk_state = make_risk_state()
    router_cfg = load_router_cfg()

    yes_loss = bot_v2.candidate_worst_loss(yes_assessment, 10000.0)
    no_loss = bot_v2.candidate_worst_loss(no_assessment, 10000.0)
    decision = bot_v2.route_candidate_assessment(
        no_assessment, market, risk_state, router_cfg
    )

    assert yes_loss == 20.0
    assert no_loss == 22.5
    assert decision["status"] == "accepted"
    assert decision["reserved_worst_loss"] == 22.5


def test_route_candidate_assessment_normalizes_allowed_candidate_statuses():
    market = make_market()
    risk_state = make_risk_state()
    router_cfg = load_router_cfg()

    accepted = bot_v2.route_candidate_assessment(
        make_assessment(status="accepted"), market, risk_state, router_cfg
    )
    size_down = bot_v2.route_candidate_assessment(
        make_assessment(status="size_down", size_multiplier=0.5),
        market,
        risk_state,
        router_cfg,
    )
    reprice = bot_v2.route_candidate_assessment(
        make_assessment(status="reprice"), market, risk_state, router_cfg
    )
    rejected = bot_v2.route_candidate_assessment(
        make_assessment(status="rejected", edge=None), market, risk_state, router_cfg
    )

    assert accepted["status"] == "accepted"
    assert size_down["status"] == "accepted"
    assert reprice["status"] == "rejected"
    assert rejected["status"] == "rejected"
