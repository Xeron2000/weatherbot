import copy

import bot_v2 as weatherbot


def configure_markets_dir(tmp_path, monkeypatch):
    markets_dir = tmp_path / "markets"
    markets_dir.mkdir()
    monkeypatch.setattr(weatherbot, "MARKETS_DIR", markets_dir)
    return markets_dir


def test_new_market_initializes_semantic_scan_fields(phase1_gamma_event):
    market = weatherbot.new_market("nyc", "2026-04-17", phase1_gamma_event, 12.4)

    assert market["event_slug"] == phase1_gamma_event["slug"]
    assert market["event_id"] == phase1_gamma_event["id"]
    assert market["resolution_metadata"] == {
        "station": "KLGA",
        "unit": "F",
        "resolution_text": "",
        "resolution_source": "",
        "rounding_rule": "",
    }
    assert market["market_contracts"] == []
    assert market["scan_guardrails"] == {
        "admissible": False,
        "skip_reasons": [],
        "weather_fresh": False,
        "mapping_ok": False,
        "unit_ok": False,
    }
    assert market["last_scan_status"] == "pending"
    assert market["last_scan_at"] is None
    assert market["last_scan_reason"] is None


def test_guardrail_failure_persists_skip_reasons(
    phase1_gamma_event, phase1_weather_snapshot, tmp_path, monkeypatch
):
    configure_markets_dir(tmp_path, monkeypatch)
    broken_event = copy.deepcopy(phase1_gamma_event)
    broken_event["rules"] = broken_event["rules"].replace("°F", "°C")

    loc = weatherbot.LOCATIONS["nyc"]
    market = weatherbot.new_market("nyc", "2026-04-17", broken_event, 8)
    market["resolution_metadata"] = weatherbot.extract_resolution_metadata(
        broken_event, loc
    )
    contracts = weatherbot.build_market_contracts(broken_event, loc["unit"])
    verdict = weatherbot.evaluate_market_guardrails(
        loc,
        market["resolution_metadata"],
        contracts,
        phase1_weather_snapshot["fresh"],
        8,
    )

    market["market_contracts"] = contracts["contracts"]
    market["scan_guardrails"] = {
        **market["scan_guardrails"],
        **verdict,
        "weather_fresh": "weather_data_stale" not in verdict["skip_reasons"],
        "mapping_ok": "missing_rule_mapping" not in verdict["skip_reasons"],
        "unit_ok": "unit_mismatch" not in verdict["skip_reasons"],
    }
    market["last_scan_status"] = "skipped"
    market["last_scan_reason"] = verdict["skip_reasons"][0]
    market["last_scan_at"] = phase1_weather_snapshot["fresh"]["ts"]

    weatherbot.save_market(market)
    persisted = weatherbot.load_market("nyc", "2026-04-17")

    assert persisted["last_scan_status"] == "skipped"
    assert persisted["last_scan_reason"] == "unit_mismatch"
    assert persisted["scan_guardrails"]["admissible"] is False
    assert persisted["scan_guardrails"]["skip_reasons"] == ["unit_mismatch"]


def test_admissible_market_persists_semantic_contract_identifiers(
    phase1_gamma_event, phase1_weather_snapshot, tmp_path, monkeypatch
):
    configure_markets_dir(tmp_path, monkeypatch)
    loc = weatherbot.LOCATIONS["nyc"]
    market = weatherbot.new_market("nyc", "2026-04-17", phase1_gamma_event, 8)
    metadata = weatherbot.extract_resolution_metadata(phase1_gamma_event, loc)
    contracts = weatherbot.build_market_contracts(phase1_gamma_event, loc["unit"])
    verdict = weatherbot.evaluate_market_guardrails(
        loc,
        metadata,
        contracts,
        phase1_weather_snapshot["fresh"],
        8,
    )

    market["resolution_metadata"] = metadata
    market["market_contracts"] = contracts["contracts"]
    market["scan_guardrails"] = {
        **market["scan_guardrails"],
        **verdict,
        "weather_fresh": True,
        "mapping_ok": True,
        "unit_ok": True,
    }
    market["last_scan_status"] = "ready"
    market["last_scan_at"] = phase1_weather_snapshot["fresh"]["ts"]

    weatherbot.save_market(market)
    persisted = weatherbot.load_market("nyc", "2026-04-17")

    assert persisted["last_scan_status"] == "ready"
    assert persisted["scan_guardrails"]["skip_reasons"] == []
    assert persisted["scan_guardrails"]["admissible"] is True
    assert persisted["resolution_metadata"]["station"] == "KLGA"
    assert persisted["resolution_metadata"]["resolution_source"] == "rules+location"
    assert persisted["market_contracts"][0]["condition_id"] == "cond-nyc-52-53"
    assert persisted["market_contracts"][0]["token_id_yes"] == "yes-nyc-52-53"
