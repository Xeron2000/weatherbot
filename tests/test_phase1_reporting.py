import copy

import bot_v2 as weatherbot


def make_market(city_slug, date_str, event):
    market = weatherbot.new_market(city_slug, date_str, event, 12)
    market["created_at"] = "2026-04-17T00:00:00+00:00"
    return market


def test_print_status_shows_accepted_and_skipped_scan_semantics(
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

    skipped_event = copy.deepcopy(phase1_gamma_event)
    skipped_event["id"] = "evt-chicago-2026-04-17"
    skipped_event["slug"] = "highest-temperature-in-chicago-on-april-17-2026"
    skipped = make_market("chicago", "2026-04-17", skipped_event)
    skipped["last_scan_status"] = "skipped"
    skipped["last_scan_reason"] = "unit_mismatch"
    skipped["scan_guardrails"] = {
        **skipped["scan_guardrails"],
        "skip_reasons": ["unit_mismatch", "missing_rule_mapping"],
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

    assert "Accepted scan markets" in out
    assert "Skipped scan markets" in out
    assert "KLGA" in out
    assert "52.0-53.0F" in out
    assert "mkt-nyc-52-53" in out
    assert "unit_mismatch, missing_rule_mapping" in out


def test_print_report_keeps_scan_summary_separate_from_trade_counts(
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

    skipped = make_market("nyc", "2026-04-18", phase1_gamma_event)
    skipped["last_scan_status"] = "skipped"
    skipped["last_scan_reason"] = "weather_data_stale"
    skipped["scan_guardrails"] = {
        **skipped["scan_guardrails"],
        "skip_reasons": ["weather_data_stale"],
    }

    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [accepted, skipped])

    weatherbot.print_report()
    out = capsys.readouterr().out

    assert "No resolved markets yet." in out
    assert "Accepted scan markets" in out
    assert "Skipped scan markets" in out
    assert "weather_data_stale" in out


def test_status_counts_do_not_treat_skipped_markets_as_open_positions(
    phase1_gamma_event, monkeypatch, capsys
):
    skipped = make_market("nyc", "2026-04-17", phase1_gamma_event)
    skipped["last_scan_status"] = "skipped"
    skipped["last_scan_reason"] = "unit_mismatch"
    skipped["scan_guardrails"] = {
        **skipped["scan_guardrails"],
        "skip_reasons": ["unit_mismatch"],
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
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [skipped])

    weatherbot.print_status()
    out = capsys.readouterr().out

    assert "Open:        0" in out
    assert "Resolved:    0" in out
    assert "unit_mismatch" in out
