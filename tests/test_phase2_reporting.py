import copy

import bot_v2 as weatherbot


def make_market(city_slug, date_str, event):
    market = weatherbot.new_market(city_slug, date_str, event, 12)
    market["created_at"] = "2026-04-17T00:00:00+00:00"
    return market


def make_candidate_assessments():
    return [
        {
            "strategy_leg": "YES_SNIPER",
            "token_side": "yes",
            "range": (65.0, 69.0),
            "aggregate_probability": 0.18,
            "fair_price": 0.18,
            "status": "reprice",
            "reasons": ["price_above_max"],
            "size_multiplier": 0.0,
            "quote_context": {"ask": 0.34, "bid": 0.31, "book_ok": True},
        },
        {
            "strategy_leg": "NO_CARRY",
            "token_side": "no",
            "range": (65.0, 69.0),
            "aggregate_probability": 0.18,
            "fair_price": 0.82,
            "status": "accepted",
            "reasons": [],
            "size_multiplier": 1.0,
            "quote_context": {"bid": 0.9, "ask": 0.93, "book_ok": True},
        },
    ]


def test_print_status_shows_candidate_assessment_summary(
    phase1_gamma_event, phase1_weather_snapshot, monkeypatch, capsys
):
    accepted = make_market("nyc", "2026-04-17", phase1_gamma_event)
    accepted["last_scan_status"] = "ready"
    accepted["last_scan_at"] = phase1_weather_snapshot["fresh"]["ts"]
    accepted["resolution_metadata"] = weatherbot.extract_resolution_metadata(
        phase1_gamma_event, weatherbot.LOCATIONS["nyc"]
    )
    accepted["market_contracts"] = weatherbot.build_market_contracts(
        phase1_gamma_event, "F"
    )["contracts"]
    accepted["candidate_assessments"] = make_candidate_assessments()

    monkeypatch.setattr(
        weatherbot,
        "load_state",
        lambda: {
            "balance": 10000.0,
            "starting_balance": 10000.0,
            "wins": 0,
            "losses": 0,
        },
    )
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [accepted])

    weatherbot.print_status()
    out = capsys.readouterr().out

    assert "Candidate assessments" in out
    assert "YES_SNIPER" in out
    assert "NO_CARRY" in out
    assert "65.0-69.0" in out
    assert "status=reprice" in out
    assert "status=accepted" in out
    assert "reasons=price_above_max" in out
    assert "fair=0.180" in out
    assert "quote=ask=0.34 bid=0.31" in out


def test_print_report_shows_candidate_assessments_without_resolved_trades(
    phase1_gamma_event, phase1_weather_snapshot, monkeypatch, capsys
):
    accepted = make_market("nyc", "2026-04-17", phase1_gamma_event)
    accepted["last_scan_status"] = "ready"
    accepted["last_scan_at"] = phase1_weather_snapshot["fresh"]["ts"]
    accepted["resolution_metadata"] = weatherbot.extract_resolution_metadata(
        phase1_gamma_event, weatherbot.LOCATIONS["nyc"]
    )
    accepted["market_contracts"] = weatherbot.build_market_contracts(
        phase1_gamma_event, "F"
    )["contracts"]
    accepted["candidate_assessments"] = make_candidate_assessments()

    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [accepted])

    weatherbot.print_report()
    out = capsys.readouterr().out

    assert "Candidate assessments" in out
    assert "YES_SNIPER" in out
    assert "NO_CARRY" in out
    assert "No resolved markets yet." in out


def test_reporting_keeps_trade_stats_separate_from_candidate_counts(
    phase1_gamma_event, phase1_weather_snapshot, monkeypatch, capsys
):
    accepted = make_market("nyc", "2026-04-17", phase1_gamma_event)
    accepted["last_scan_status"] = "ready"
    accepted["last_scan_at"] = phase1_weather_snapshot["fresh"]["ts"]
    accepted["candidate_assessments"] = make_candidate_assessments()

    skipped_event = copy.deepcopy(phase1_gamma_event)
    skipped_event["id"] = "evt-chicago-2026-04-17"
    skipped = make_market("chicago", "2026-04-17", skipped_event)
    skipped["last_scan_status"] = "skipped"
    skipped["last_scan_reason"] = "weather_data_stale"
    skipped["scan_guardrails"] = {
        **skipped["scan_guardrails"],
        "skip_reasons": ["weather_data_stale"],
    }

    monkeypatch.setattr(
        weatherbot,
        "load_state",
        lambda: {
            "balance": 10000.0,
            "starting_balance": 10000.0,
            "wins": 0,
            "losses": 0,
        },
    )
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [accepted, skipped])

    weatherbot.print_status()
    out = capsys.readouterr().out

    assert "Open:        0" in out
    assert "Resolved:    0" in out
    assert "Accepted scan markets: 1" in out
    assert "Skipped scan markets: 1" in out
    assert "Candidate assessments: 2" in out
