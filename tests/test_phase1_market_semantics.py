import copy

import bot_v2 as weatherbot


def call_helper(name, *args):
    helper = getattr(weatherbot, name, None)
    assert helper is not None, f"{name} helper missing"
    return helper(*args)


def test_parse_temp_range_handles_bucket_shapes():
    assert weatherbot.parse_temp_range(
        "Will the highest temperature be between 52-53°F on April 17?"
    ) == (52.0, 53.0)
    assert weatherbot.parse_temp_range(
        "Will the highest temperature be 56°F or below on April 17?"
    ) == (-999.0, 56.0)
    assert weatherbot.parse_temp_range(
        "Will the highest temperature be 60°F or higher on April 17?"
    ) == (60.0, 999.0)


def test_resolution_metadata_uses_event_and_location_contract(phase1_gamma_event):
    loc = weatherbot.LOCATIONS["nyc"]

    metadata = call_helper("extract_resolution_metadata", phase1_gamma_event, loc)

    assert metadata["station"] == "KLGA"
    assert metadata["unit"] == "F"
    assert "LaGuardia Airport" in metadata["resolution_text"]
    assert metadata["resolution_source"] in {"rules", "title", "rules+location"}


def test_build_market_contracts_rejects_missing_contract_identifiers(
    phase1_gamma_event,
):
    broken_event = copy.deepcopy(phase1_gamma_event)
    broken_event["markets"][0].pop("conditionId", None)
    broken_event["markets"][0].pop("clobTokenIds", None)

    contracts = call_helper("build_market_contracts", broken_event, "F")

    assert contracts["contracts"] == []
    assert "missing_contract_identifiers" in contracts["skip_reasons"]


def test_guardrails_reject_unit_mismatch(phase1_gamma_event, phase1_weather_snapshot):
    loc = weatherbot.LOCATIONS["nyc"]
    wrong_unit_event = copy.deepcopy(phase1_gamma_event)
    wrong_unit_event["markets"][0]["question"] = (
        "Will the highest temperature in New York City be between 12-13°C on April 17, 2026?"
    )

    metadata = call_helper("extract_resolution_metadata", wrong_unit_event, loc)
    contracts = call_helper("build_market_contracts", wrong_unit_event, loc["unit"])
    verdict = call_helper(
        "evaluate_market_guardrails",
        loc,
        metadata,
        contracts,
        phase1_weather_snapshot["fresh"],
        12,
    )

    assert verdict["admissible"] is False
    assert "unit_mismatch" in verdict["skip_reasons"]


def test_guardrails_reject_weather_data_stale(
    phase1_gamma_event, phase1_weather_snapshot
):
    loc = weatherbot.LOCATIONS["nyc"]

    metadata = call_helper("extract_resolution_metadata", phase1_gamma_event, loc)
    contracts = call_helper("build_market_contracts", phase1_gamma_event, loc["unit"])
    verdict = call_helper(
        "evaluate_market_guardrails",
        loc,
        metadata,
        contracts,
        phase1_weather_snapshot["stale"],
        12,
    )

    assert verdict["admissible"] is False
    assert "weather_data_stale" in verdict["skip_reasons"]
