from datetime import datetime, timezone

import bot_v2


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


def install_quote_requests(monkeypatch, payloads):
    def fake_get(url, timeout=(3, 5)):
        if "book?token_id=" in url:
            token_id = url.split("token_id=")[-1]
            return DummyResponse(payloads["book"].get(token_id))
        if "tick-size?token_id=" in url:
            token_id = url.split("token_id=")[-1]
            return DummyResponse(payloads["tick_size"].get(token_id))
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(
        bot_v2,
        "requests",
        type("RequestsStub", (), {"get": staticmethod(fake_get)})(),
    )


def patch_scan_inputs(monkeypatch, city_events, city_snapshots):
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)

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


def test_token_quote_snapshot_reads_yes_and_no_books(
    phase2_clob_book_yes, phase2_clob_book_no, monkeypatch
):
    install_quote_requests(
        monkeypatch,
        {
            "book": {
                "yes-65-69": phase2_clob_book_yes,
                "no-65-69": phase2_clob_book_no,
            },
            "tick_size": {
                "yes-65-69": {"minimum_tick_size": "0.01"},
                "no-65-69": {"minimum_tick_size": "0.01"},
            },
        },
    )

    yes_quote = bot_v2.get_token_quote_snapshot("yes-65-69", "yes")
    no_quote = bot_v2.get_token_quote_snapshot("no-65-69", "no")

    assert yes_quote["side"] == "yes"
    assert yes_quote["bid"] == 0.31
    assert yes_quote["ask"] == 0.34
    assert yes_quote["spread"] == 0.03
    assert yes_quote["tick_size"] == 0.01
    assert yes_quote["min_order_size"] == 5.0
    assert yes_quote["book_ok"] is True

    assert no_quote["side"] == "no"
    assert no_quote["bid"] == 0.66
    assert no_quote["ask"] == 0.7
    assert no_quote["ask"] != round(1 - yes_quote["bid"], 2)


def test_quote_snapshot_returns_reason_codes_for_missing_or_closed_books(
    phase2_clob_book_yes, monkeypatch
):
    closed_book = dict(phase2_clob_book_yes)
    closed_book["closed"] = True

    install_quote_requests(
        monkeypatch,
        {
            "book": {
                "missing": None,
                "empty": {
                    "asset_id": "empty",
                    "bids": [],
                    "asks": [],
                    "min_order_size": "5",
                    "closed": False,
                },
                "closed": closed_book,
                "tickless": phase2_clob_book_yes,
            },
            "tick_size": {
                "missing": {"minimum_tick_size": "0.01"},
                "empty": {"minimum_tick_size": "0.01"},
                "closed": {"minimum_tick_size": "0.01"},
                "tickless": {},
            },
        },
    )

    assert (
        "missing_quote_book"
        in bot_v2.get_token_quote_snapshot("missing", "yes")["reason_codes"]
    )
    assert (
        "orderbook_empty"
        in bot_v2.get_token_quote_snapshot("empty", "yes")["reason_codes"]
    )
    assert (
        "market_closed"
        in bot_v2.get_token_quote_snapshot("closed", "yes")["reason_codes"]
    )
    assert (
        "tick_size_missing"
        in bot_v2.get_token_quote_snapshot("tickless", "yes")["reason_codes"]
    )


def test_scan_and_update_persists_quote_snapshots_with_execution_stop_reasons(
    phase2_gamma_event,
    phase2_weather_snapshot,
    phase2_clob_book_yes,
    phase2_clob_book_no,
    tmp_path,
    monkeypatch,
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

    market_with_target = dict(event["markets"][2])
    market_with_target["question"] = "Between 65-69F"
    market_with_target["clobTokenIds"] = '["yes-65-69","no-65-69"]'
    event["markets"] = [market_with_target]

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
    install_quote_requests(
        monkeypatch,
        {
            "book": {
                "yes-65-69": phase2_clob_book_yes,
                "no-65-69": {
                    "asset_id": "no-65-69",
                    "bids": [],
                    "asks": [],
                    "min_order_size": "5",
                    "closed": False,
                },
            },
            "tick_size": {
                "yes-65-69": {"minimum_tick_size": "0.01"},
                "no-65-69": {"minimum_tick_size": "0.01"},
            },
        },
    )

    bot_v2.scan_and_update()
    market = bot_v2.load_market(city, target_date)

    assert market["last_scan_status"] == "ready"
    assert len(market["quote_snapshot"]) == 1
    assert market["quote_snapshot"][0]["yes"]["ask"] == 0.34
    assert market["quote_snapshot"][0]["no"]["book_ok"] is False
    assert "orderbook_empty" in market["quote_snapshot"][0]["execution_stop_reasons"]


def test_monitor_positions_uses_yes_token_quote_for_exit_price(
    phase2_clob_book_yes, tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(bot_v2, "LOCATIONS", {"nyc": bot_v2.LOCATIONS["nyc"]})
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)
    install_quote_requests(
        monkeypatch,
        {
            "book": {"yes-65-69": phase2_clob_book_yes},
            "tick_size": {"yes-65-69": {"minimum_tick_size": "0.01"}},
        },
    )

    market = {
        "city": "nyc",
        "date": "2026-04-17",
        "event_end_date": "2026-04-18T23:59:00Z",
        "position": {
            "market_id": "mkt-65-69",
            "entry_price": 0.34,
            "shares": 10.0,
            "cost": 3.4,
            "status": "open",
            "stop_price": 0.32,
        },
        "all_outcomes": [
            {
                "market_id": "mkt-65-69",
                "token_id_yes": "yes-65-69",
                "bid": 0.2,
                "price": 0.21,
            }
        ],
        "quote_snapshot": [
            {
                "market_id": "mkt-65-69",
                "yes": {"token_id": "yes-65-69"},
                "no": {},
            }
        ],
    }
    bot_v2.save_market(market)

    closed = bot_v2.monitor_positions()
    updated = bot_v2.load_market("nyc", "2026-04-17")

    assert closed == 1
    assert updated["position"]["exit_price"] == 0.31


def test_monitor_positions_keeps_yes_position_open_even_below_legacy_stop(
    tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(bot_v2, "LOCATIONS", {"nyc": bot_v2.LOCATIONS["nyc"]})
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        bot_v2,
        "get_token_quote_snapshot",
        lambda token_id, side: {
            "token_id": token_id,
            "side": side,
            "book_ok": True,
            "bid": 0.2,
        },
    )

    market = {
        "city": "nyc",
        "date": "2026-04-17",
        "event_end_date": "2026-04-19T23:59:00Z",
        "position": {
            "market_id": "mkt-65-69",
            "entry_price": 0.34,
            "shares": 10.0,
            "cost": 3.4,
            "status": "open",
            "stop_price": 0.32,
            "token_side": "yes",
            "entry_side": "yes",
        },
        "all_outcomes": [
            {
                "market_id": "mkt-65-69",
                "token_id_yes": "yes-65-69",
                "token_id_no": "no-65-69",
                "bid": 0.2,
                "price": 0.21,
            }
        ],
        "quote_snapshot": [
            {
                "market_id": "mkt-65-69",
                "yes": {"token_id": "yes-65-69"},
                "no": {"token_id": "no-65-69"},
            }
        ],
    }
    bot_v2.save_market(market)

    closed = bot_v2.monitor_positions()
    updated = bot_v2.load_market("nyc", "2026-04-17")

    assert closed == 0
    assert updated["position"]["status"] == "open"
    assert updated["position"].get("exit_price") is None


def test_monitor_positions_stops_only_large_no_positions_using_no_quote(
    tmp_path, monkeypatch
):
    configure_runtime_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(bot_v2, "LOCATIONS", {"nyc": bot_v2.LOCATIONS["nyc"]})
    monkeypatch.setattr(bot_v2.time, "sleep", lambda *_args, **_kwargs: None)

    quotes = {
        ("yes-65-69", "yes"): {
            "token_id": "yes-65-69",
            "side": "yes",
            "book_ok": True,
            "bid": 0.18,
        },
        ("no-65-69", "no"): {
            "token_id": "no-65-69",
            "side": "no",
            "book_ok": True,
            "bid": 0.7,
        },
    }
    monkeypatch.setattr(
        bot_v2,
        "get_token_quote_snapshot",
        lambda token_id, side: quotes[(token_id, side)],
    )

    market = {
        "city": "nyc",
        "date": "2026-04-17",
        "event_end_date": "2026-04-19T23:59:00Z",
        "position": {
            "market_id": "mkt-65-69",
            "entry_price": 0.82,
            "shares": 10.0,
            "cost": 8.2,
            "status": "open",
            "token_side": "no",
            "entry_side": "no",
        },
        "all_outcomes": [
            {
                "market_id": "mkt-65-69",
                "token_id_yes": "yes-65-69",
                "token_id_no": "no-65-69",
                "bid": 0.18,
                "price": 0.19,
            }
        ],
        "quote_snapshot": [
            {
                "market_id": "mkt-65-69",
                "yes": {"token_id": "yes-65-69"},
                "no": {"token_id": "no-65-69"},
            }
        ],
    }
    bot_v2.save_market(market)

    closed = bot_v2.monitor_positions()
    updated = bot_v2.load_market("nyc", "2026-04-17")

    assert closed == 1
    assert updated["position"]["status"] == "closed"
    assert updated["position"]["close_reason"] == "stop_loss"
    assert updated["position"]["exit_price"] == 0.7
