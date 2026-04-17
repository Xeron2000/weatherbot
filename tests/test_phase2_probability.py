import json
from pathlib import Path

import bot_v2


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with (FIXTURES / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_market_contracts(event):
    contracts = []
    for market in event["markets"]:
        rng = bot_v2.parse_temp_range(market["question"])
        yes_token, no_token = json.loads(market["clobTokenIds"])
        contracts.append(
            {
                "question": market["question"],
                "market_id": market["id"],
                "range": rng,
                "condition_id": market["conditionId"],
                "token_id_yes": yes_token,
                "token_id_no": no_token,
                "bid": float(market["bestBid"]),
                "ask": float(market["bestAsk"]),
                "price": float(market["bestAsk"]),
                "spread": float(market["bestAsk"]) - float(market["bestBid"]),
                "volume": float(market["volume"]),
            }
        )
    return contracts


def test_middle_bucket_returns_continuous_probability_mass():
    prob = bot_v2.bucket_prob(67.0, 65, 69, sigma=2.5)

    assert 0.0 < prob < 1.0
    assert prob != 1.0


def test_probability_table_exposes_per_source_probabilities():
    event = load_fixture("phase2_gamma_event.json")
    weather = load_fixture("phase2_weather_snapshot.json")
    contracts = build_market_contracts(event)

    records = bot_v2.aggregate_probability(
        contracts, weather["sources"], weather["sigmas"]
    )

    assert len(records) == len(contracts)
    for record, contract in zip(records, contracts):
        assert record["range"] == contract["range"]
        assert set(record["per_source_probability"].keys()) == {
            "ecmwf",
            "hrrr",
            "metar_anchor",
        }
        for value in record["per_source_probability"].values():
            assert value is None or 0.0 <= value <= 1.0


def test_aggregate_probability_outputs_fair_yes_and_no_for_all_buckets():
    event = load_fixture("phase2_gamma_event.json")
    weather = load_fixture("phase2_weather_snapshot.json")
    contracts = build_market_contracts(event)

    records = bot_v2.aggregate_probability(
        contracts, weather["sources"], weather["sigmas"]
    )

    assert len(records) == len(contracts)
    total_probability = sum(record["aggregate_probability"] for record in records)
    assert 0.98 <= total_probability <= 1.02
    for record in records:
        assert 0.0 <= record["aggregate_probability"] <= 1.0
        assert record["fair_yes"] == record["aggregate_probability"]
        assert record["fair_no"] == 1.0 - record["aggregate_probability"]
