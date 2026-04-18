import copy
from datetime import datetime, timezone

import bot_v2 as weatherbot


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
    monkeypatch.setattr(weatherbot, "DATA_DIR", data_dir)
    monkeypatch.setattr(weatherbot, "MARKETS_DIR", markets_dir)
    monkeypatch.setattr(weatherbot, "STATE_FILE", data_dir / "state.json")
    monkeypatch.setattr(weatherbot, "CALIBRATION_FILE", data_dir / "calibration.json")


def patch_scan_inputs(monkeypatch, city_events, city_snapshots):
    monkeypatch.setattr(weatherbot.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        weatherbot,
        "requests",
        type(
            "RequestsStub",
            (),
            {
                "get": staticmethod(
                    lambda *_args, **_kwargs: DummyResponse(
                        {"bestAsk": 0.12, "bestBid": 0.10}
                    )
                )
            },
        )(),
    )

    def fake_take_forecast_snapshot(city_slug, dates):
        snapshots = {
            date: {"ts": None, "best": None, "best_source": None} for date in dates
        }
        snapshots.update(city_snapshots.get(city_slug, {}))
        return snapshots

    def fake_get_polymarket_event(city_slug, month, day, year):
        month_num = month if isinstance(month, int) else (weatherbot.MONTHS.index(month) + 1)
        return city_events.get((city_slug, f"{year:04d}-{month_num:02d}-{day:02d}"))

    monkeypatch.setattr(
        weatherbot, "take_forecast_snapshot", fake_take_forecast_snapshot
    )
    monkeypatch.setattr(weatherbot, "get_polymarket_event", fake_get_polymarket_event)


def freeze_bot_now(monkeypatch, ts):
    frozen = datetime.fromisoformat(ts)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen
            return frozen.astimezone(tz)

    monkeypatch.setattr(weatherbot, "datetime", FrozenDateTime)


def test_scan_and_update_marks_skipped_market_with_explicit_reason(
    phase1_gamma_event, phase1_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    target_date = phase1_gamma_event["endDate"][:10]
    city = "nyc"
    freeze_bot_now(monkeypatch, "2026-04-16T12:00:00+00:00")
    event = copy.deepcopy(phase1_gamma_event)
    event["rules"] = event["rules"].replace("°F", "°C")
    loc = copy.deepcopy(weatherbot.LOCATIONS[city])

    monkeypatch.setattr(weatherbot, "LOCATIONS", {city: loc})
    patch_scan_inputs(
        monkeypatch,
        {(city, target_date): event},
        {city: {target_date: phase1_weather_snapshot["fresh"]}},
    )

    weatherbot.scan_and_update()

    market = weatherbot.load_market(city, target_date)

    assert market["last_scan_status"] == "skipped"
    assert market["last_scan_reason"] == "unit_mismatch"
    assert market["scan_guardrails"]["skip_reasons"] == ["unit_mismatch"]


def test_scan_and_update_persists_semantic_contracts_for_admissible_market(
    phase1_gamma_event, phase1_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    target_date = phase1_gamma_event["endDate"][:10]
    city = "nyc"
    freeze_bot_now(monkeypatch, "2026-04-16T12:00:00+00:00")
    loc = copy.deepcopy(weatherbot.LOCATIONS[city])

    monkeypatch.setattr(weatherbot, "LOCATIONS", {city: loc})
    patch_scan_inputs(
        monkeypatch,
        {(city, target_date): phase1_gamma_event},
        {city: {target_date: phase1_weather_snapshot["fresh"]}},
    )

    weatherbot.scan_and_update()

    market = weatherbot.load_market(city, target_date)

    assert market["last_scan_status"] == "ready"
    assert market["scan_guardrails"]["admissible"] is True
    assert market["market_contracts"][0]["condition_id"] == "cond-nyc-52-53"
    assert market["resolution_metadata"]["station"] == "KLGA"


def test_scan_loop_continues_after_rejecting_one_market(
    phase1_gamma_event, phase1_weather_snapshot, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    target_date = phase1_gamma_event["endDate"][:10]
    bad_event = copy.deepcopy(phase1_gamma_event)
    bad_event["rules"] = bad_event["rules"].replace("°F", "°C")
    good_event = copy.deepcopy(phase1_gamma_event)
    good_event["id"] = "evt-chicago-2026-04-17"
    good_event["slug"] = "highest-temperature-in-chicago-on-april-17-2026"
    good_event["title"] = "Highest temperature in Chicago on April 17, 2026?"
    good_event["description"] = (
        "Temperature resolves from the official O'Hare Airport observations."
    )
    good_event["rules"] = (
        "This market resolves based on the highest temperature recorded at "
        "O'Hare Airport (KORD) in °F. Temperatures are rounded to the nearest "
        "whole degree using the official airport reading."
    )
    for market in good_event["markets"]:
        market["id"] = market["id"].replace("nyc", "chicago")
        market["conditionId"] = market["conditionId"].replace("nyc", "chicago")
        market["clobTokenIds"] = market["clobTokenIds"].replace("nyc", "chicago")
        market["question"] = market["question"].replace("New York City", "Chicago")

    monkeypatch.setattr(
        weatherbot,
        "LOCATIONS",
        {
            "nyc": copy.deepcopy(weatherbot.LOCATIONS["nyc"]),
            "chicago": copy.deepcopy(weatherbot.LOCATIONS["chicago"]),
        },
    )
    freeze_bot_now(monkeypatch, "2026-04-16T12:00:00+00:00")
    patch_scan_inputs(
        monkeypatch,
        {
            ("nyc", target_date): bad_event,
            ("chicago", target_date): good_event,
        },
        {
            "nyc": {target_date: phase1_weather_snapshot["fresh"]},
            "chicago": {target_date: phase1_weather_snapshot["fresh"]},
        },
    )

    weatherbot.scan_and_update()

    skipped_market = weatherbot.load_market("nyc", target_date)
    ready_market = weatherbot.load_market("chicago", target_date)

    assert skipped_market["last_scan_status"] == "skipped"
    assert ready_market["last_scan_status"] == "ready"
    assert ready_market["market_contracts"][0]["condition_id"] == "cond-chicago-52-53"
