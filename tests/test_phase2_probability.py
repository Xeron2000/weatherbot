import json
from pathlib import Path
from datetime import datetime, timezone

import bot_v2


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with (FIXTURES / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def configure_runtime_paths(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    markets_dir = data_dir / "markets"
    data_dir.mkdir()
    markets_dir.mkdir()
    monkeypatch.setattr(bot_v2, "DATA_DIR", data_dir)
    monkeypatch.setattr(bot_v2, "MARKETS_DIR", markets_dir)
    monkeypatch.setattr(bot_v2, "STATE_FILE", data_dir / "state.json")
    monkeypatch.setattr(bot_v2, "CALIBRATION_FILE", data_dir / "calibration.json")


def patch_scan_inputs(monkeypatch, city_events, city_snapshots):
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        bot_v2,
        "requests",
        type(
            "RequestsStub",
            (),
            {"get": staticmethod(lambda *_args, **_kwargs: DummyResponse({}))},
        )(),
    )

    def fake_take_forecast_snapshot(city_slug, dates):
        snapshots = {
            date: {"ts": None, "best": None, "best_source": None} for date in dates
        }
        snapshots.update(city_snapshots.get(city_slug, {}))
        return snapshots

    def fake_get_polymarket_event(city_slug, month, day, year):
        return city_events.get((city_slug, f"{year:04d}-{month}-{day:02d}"))

    monkeypatch.setattr(bot_v2, "take_forecast_snapshot", fake_take_forecast_snapshot)
    monkeypatch.setattr(bot_v2, "get_polymarket_event", fake_get_polymarket_event)


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


def test_scan_and_update_persists_bucket_probabilities_for_admissible_market(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city = "nyc"
    today = datetime.now(timezone.utc)
    target_date = today.strftime("%Y-%m-%d")
    month = bot_v2.MONTHS[today.month - 1]
    now_ts = today.isoformat()
    event = dict(phase2_gamma_event)
    event["endDate"] = f"{target_date}T23:59:00Z"
    event["rules"] = (
        "This market resolves based on the highest temperature recorded at "
        "LaGuardia Airport (KLGA) in °F. Temperatures are rounded to the nearest "
        "whole degree using the official airport reading."
    )

    monkeypatch.setattr(bot_v2, "LOCATIONS", {city: bot_v2.LOCATIONS[city]})
    patch_scan_inputs(
        monkeypatch,
        {(city, f"{today.year:04d}-{month}-{today.day:02d}"): event},
        {
            city: {
                target_date: {
                    "ts": now_ts,
                    "ecmwf": phase2_weather_snapshot["sources"]["ecmwf"],
                    "hrrr": phase2_weather_snapshot["sources"]["hrrr"],
                    "metar": phase2_weather_snapshot["sources"]["metar_anchor"],
                    "best": phase2_weather_snapshot["sources"]["ecmwf"],
                    "best_source": "ecmwf",
                }
            }
        },
    )

    bot_v2.scan_and_update()
    market = bot_v2.load_market(city, target_date)

    assert market["last_scan_status"] == "ready"
    assert len(market["bucket_probabilities"]) == len(market["market_contracts"])
    assert (
        market["bucket_probabilities"][0]["range"]
        == market["market_contracts"][0]["range"]
    )


def test_scan_and_update_clears_stale_bucket_probabilities_for_skipped_market(
    phase2_gamma_event, phase2_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    city = "nyc"
    today = datetime.now(timezone.utc)
    target_date = today.strftime("%Y-%m-%d")
    month = bot_v2.MONTHS[today.month - 1]
    now_ts = today.isoformat()

    monkeypatch.setattr(bot_v2, "LOCATIONS", {city: bot_v2.LOCATIONS[city]})
    good_event = dict(phase2_gamma_event)
    good_event["endDate"] = f"{target_date}T23:59:00Z"
    good_event["rules"] = (
        "This market resolves based on the highest temperature recorded at "
        "LaGuardia Airport (KLGA) in °F. Temperatures are rounded to the nearest "
        "whole degree using the official airport reading."
    )
    bad_event = dict(good_event)
    bad_event["rules"] = good_event["rules"].replace("°F", "°C")

    snapshots = {
        city: {
            target_date: {
                "ts": now_ts,
                "ecmwf": phase2_weather_snapshot["sources"]["ecmwf"],
                "hrrr": phase2_weather_snapshot["sources"]["hrrr"],
                "metar": phase2_weather_snapshot["sources"]["metar_anchor"],
                "best": phase2_weather_snapshot["sources"]["ecmwf"],
                "best_source": "ecmwf",
            }
        }
    }

    patch_scan_inputs(
        monkeypatch,
        {(city, f"{today.year:04d}-{month}-{today.day:02d}"): good_event},
        snapshots,
    )
    bot_v2.scan_and_update()

    patch_scan_inputs(
        monkeypatch,
        {(city, f"{today.year:04d}-{month}-{today.day:02d}"): bad_event},
        snapshots,
    )
    bot_v2.scan_and_update()

    market = bot_v2.load_market(city, target_date)

    assert market["last_scan_status"] == "skipped"
    assert market["bucket_probabilities"] == []
