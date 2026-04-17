import bot_v2 as weatherbot


def make_market(event):
    market = weatherbot.new_market("nyc", "2026-04-17", event, 12)
    market["created_at"] = "2026-04-17T00:00:00+00:00"
    market["last_scan_status"] = "ready"
    market["route_decisions"] = [
        {
            "strategy_leg": "YES_SNIPER",
            "status": "accepted",
            "reserved_worst_loss": 20.0,
            "budget_bucket": "YES_SNIPER",
            "reasons": [],
            "range": [65.0, 69.0],
        },
        {
            "strategy_leg": "NO_CARRY",
            "status": "rejected",
            "reserved_worst_loss": 0.0,
            "budget_bucket": "NO_CARRY",
            "reasons": ["same_bucket_conflict"],
            "range": [65.0, 69.0],
        },
    ]
    market["reserved_exposure"] = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "reserved_worst_loss": 20.0,
        "release_reason": "candidate_downgraded",
        "budget_bucket": "YES_SNIPER",
        "range": [65.0, 69.0],
    }
    return market


def make_risk_state():
    return {
        "bankroll": 10000.0,
        "global_reserved_worst_loss": 20.0,
        "legs": {
            "YES_SNIPER": {"budget": 3000.0, "reserved": 20.0, "hard_cap": 3000.0},
            "NO_CARRY": {"budget": 7000.0, "reserved": 0.0, "hard_cap": 7000.0},
        },
        "city_exposure": {"nyc": 20.0},
        "date_exposure": {"2026-04-17": 20.0},
        "event_exposure": {"nyc|2026-04-17|evt-nyc-2026-04-17": 20.0},
        "active_reservations": [],
    }


def test_print_status_shows_risk_budget_summary(
    phase1_gamma_event, monkeypatch, capsys
):
    market = make_market(phase1_gamma_event)
    monkeypatch.setattr(
        weatherbot,
        "load_state",
        lambda: {
            "balance": 10000.0,
            "starting_balance": 10000.0,
            "wins": 0,
            "losses": 0,
            "risk_state": make_risk_state(),
        },
    )
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [market])

    weatherbot.print_status()
    out = capsys.readouterr().out

    assert "Risk usage" in out
    assert "YES_SNIPER" in out
    assert "NO_CARRY" in out
    assert "budget=3000.00" in out
    assert "reserved=20.00" in out
    assert "available=2980.00" in out
    assert "global_reserved_worst_loss=20.00" in out


def test_print_report_shows_exposure_and_release_reason_summaries(
    phase1_gamma_event, monkeypatch, capsys
):
    market = make_market(phase1_gamma_event)
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [market])
    monkeypatch.setattr(
        weatherbot,
        "load_state",
        lambda: {
            "balance": 10000.0,
            "starting_balance": 10000.0,
            "wins": 0,
            "losses": 0,
            "risk_state": make_risk_state(),
        },
    )

    weatherbot.print_report()
    out = capsys.readouterr().out

    assert "Risk usage" in out
    assert "City exposure" in out
    assert "Date exposure" in out
    assert "Event exposure" in out
    assert "same_bucket_conflict" in out
    assert "candidate_downgraded" in out
    assert "No resolved markets yet." in out
