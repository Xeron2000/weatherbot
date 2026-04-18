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


def make_bucket_probability(prob=0.18):
    return {
        "market_id": "mkt-65-69",
        "range": (65.0, 69.0),
        "aggregate_probability": prob,
        "fair_yes": prob,
        "fair_no": 1.0 - prob,
    }


def make_quote_snapshot(
    yes_ask=0.11, no_bid=0.9, no_ask=None, execution_stop_reasons=None
):
    execution_stop_reasons = execution_stop_reasons or []
    return {
        "market_id": "mkt-65-69",
        "range": (65.0, 69.0),
        "yes": {
            "token_id": "yes-65-69",
            "side": "yes",
            "bid": round(yes_ask - 0.02, 4),
            "ask": yes_ask,
            "spread": 0.02,
            "tick_size": 0.01,
            "min_order_size": 5.0,
            "book_ok": len(execution_stop_reasons) == 0,
            "reason_codes": list(execution_stop_reasons),
        },
        "no": {
            "token_id": "no-65-69",
            "side": "no",
            "bid": no_bid,
            "ask": round(no_bid + 0.03, 4) if no_ask is None else no_ask,
            "spread": 0.03,
            "tick_size": 0.01,
            "min_order_size": 5.0,
            "book_ok": len(execution_stop_reasons) == 0,
            "reason_codes": list(execution_stop_reasons),
        },
        "execution_ok": len(execution_stop_reasons) == 0,
        "execution_stop_reasons": list(execution_stop_reasons),
    }


def test_yes_evaluator_uses_yes_strategy_thresholds_only(monkeypatch):
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
            "min_price": 0.9,
            "min_probability": 0.95,
            "min_edge": 0.2,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    result = bot_v2.evaluate_yes_candidate(
        make_bucket_probability(0.18), make_quote_snapshot(yes_ask=0.11), 24
    )

    assert result["strategy_leg"] == "YES_SNIPER"
    assert result["status"] == "accepted"


def test_no_evaluator_uses_no_strategy_thresholds_only(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "YES_STRATEGY",
        {
            "max_price": 0.2,
            "min_probability": 0.3,
            "min_edge": 0.2,
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
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    result = bot_v2.evaluate_no_candidate(
        make_bucket_probability(0.18),
        make_quote_snapshot(no_bid=0.9, no_ask=0.74),
        24,
    )

    assert result["strategy_leg"] == "NO_CARRY"
    assert result["status"] == "accepted"


def test_no_evaluator_uses_no_ask_for_price_floor_and_edge(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "NO_STRATEGY",
        {
            "min_price": 0.65,
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    result = bot_v2.evaluate_no_candidate(
        make_bucket_probability(0.04),
        make_quote_snapshot(no_bid=0.01, no_ask=0.88),
        24,
    )

    assert "price_below_min" not in result["reasons"]
    assert result["status"] == "accepted"
    assert result["edge"] == 0.08


def test_no_evaluator_reprices_when_no_ask_is_below_min_price(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "NO_STRATEGY",
        {
            "min_price": 0.65,
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    result = bot_v2.evaluate_no_candidate(
        make_bucket_probability(0.04),
        make_quote_snapshot(no_bid=0.9, no_ask=0.64),
        24,
    )

    assert result["status"] == "reprice"
    assert "price_below_min" in result["reasons"]


def test_no_evaluator_reprices_when_no_ask_exceeds_max_ask(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "NO_STRATEGY",
        {
            "min_price": 0.65,
            "max_ask": 0.95,
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    result = bot_v2.evaluate_no_candidate(
        make_bucket_probability(0.04),
        make_quote_snapshot(no_bid=0.96, no_ask=0.99),
        24,
    )

    assert result["status"] == "reprice"
    assert "ask_above_max" in result["reasons"]
    assert result["size_multiplier"] == 0.0


def test_no_evaluator_keeps_backward_compatibility_without_max_ask(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "NO_STRATEGY",
        {
            "min_price": 0.65,
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    result = bot_v2.evaluate_no_candidate(
        make_bucket_probability(0.04),
        make_quote_snapshot(no_bid=0.96, no_ask=0.99),
        24,
    )

    assert result["status"] == "rejected"
    assert "ask_above_max" not in result["reasons"]
    assert result["edge"] == -0.03


def test_same_bucket_can_reject_yes_but_accept_no(monkeypatch):
    monkeypatch.setattr(
        bot_v2,
        "YES_STRATEGY",
        {
            "max_price": 0.15,
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
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    bucket = make_bucket_probability(0.18)
    quote = make_quote_snapshot(yes_ask=0.2, no_bid=0.9, no_ask=0.74)

    yes_result = bot_v2.evaluate_yes_candidate(bucket, quote, 24)
    no_result = bot_v2.evaluate_no_candidate(bucket, quote, 24)

    assert yes_result["status"] == "reprice"
    assert "price_above_max" in yes_result["reasons"]
    assert no_result["status"] == "accepted"


def test_yes_peak_window_penalty_uses_city_local_time_not_utc(monkeypatch):
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

    bucket = make_bucket_probability(0.18)
    quote = make_quote_snapshot(yes_ask=0.11)

    morning_result = bot_v2.evaluate_yes_candidate(
        bucket,
        quote,
        24,
        {
            "city_slug": "nyc",
            "market_date": "2026-04-18",
            "metar": 68.4,
            "now_ts": "2026-04-18T13:30:00+00:00",
        },
    )
    late_result = bot_v2.evaluate_yes_candidate(
        bucket,
        quote,
        24,
        {
            "city_slug": "nyc",
            "market_date": "2026-04-18",
            "metar": 68.4,
            "now_ts": "2026-04-18T21:30:00+00:00",
        },
    )

    assert morning_result["probability_penalty_factor"] == 1.0
    assert morning_result["status"] == "accepted"
    assert late_result["probability_penalty_factor"] == 0.35
    assert late_result["adjusted_probability"] == 0.063
    assert late_result["status"] == "rejected"
    assert "yes_peak_window_metar_near_bucket_ceiling" in late_result["reasons"]


def test_yes_peak_window_penalty_skips_non_same_day_market(monkeypatch):
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

    result = bot_v2.evaluate_yes_candidate(
        make_bucket_probability(0.18),
        make_quote_snapshot(yes_ask=0.11),
        24,
        {
            "city_slug": "nyc",
            "market_date": "2026-04-19",
            "metar": 68.9,
            "now_ts": "2026-04-18T21:30:00+00:00",
        },
    )

    assert result["probability_penalty_factor"] == 1.0
    assert result["probability_penalty_reason"] is None
    assert result["status"] == "accepted"


def test_yes_peak_window_penalty_does_not_touch_no_candidate(monkeypatch):
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
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )

    bucket = make_bucket_probability(0.18)
    quote = make_quote_snapshot(yes_ask=0.11, no_bid=0.9, no_ask=0.74)
    market_context = {
        "city_slug": "nyc",
        "market_date": "2026-04-18",
        "metar": 68.8,
        "now_ts": "2026-04-18T21:30:00+00:00",
    }

    yes_result = bot_v2.evaluate_yes_candidate(bucket, quote, 24, market_context)
    no_result = bot_v2.evaluate_no_candidate(bucket, quote, 24)

    assert yes_result["probability_penalty_factor"] == 0.35
    assert yes_result["status"] == "rejected"
    assert no_result["status"] == "accepted"
    assert "yes_peak_window_metar_near_bucket_ceiling" not in no_result["reasons"]


def test_scan_and_update_persists_dual_candidate_assessments(
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
    monkeypatch.setattr(
        bot_v2,
        "YES_STRATEGY",
        {
            "max_price": 0.2,
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
            "min_probability": 0.7,
            "min_edge": 0.04,
            "min_hours": 2.0,
            "max_hours": 72.0,
            "max_size": 20.0,
            "min_size": 1.0,
        },
    )
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
                "no-65-69": phase2_clob_book_no,
            },
            "tick_size": {
                "yes-65-69": {"minimum_tick_size": "0.01"},
                "no-65-69": {"minimum_tick_size": "0.01"},
            },
        },
    )

    bot_v2.scan_and_update()
    market = bot_v2.load_market(city, target_date)

    assert {item["strategy_leg"] for item in market["candidate_assessments"]} == {
        "YES_SNIPER",
        "NO_CARRY",
    }
    yes_item = next(
        item
        for item in market["candidate_assessments"]
        if item["strategy_leg"] == "YES_SNIPER"
    )
    no_item = next(
        item
        for item in market["candidate_assessments"]
        if item["strategy_leg"] == "NO_CARRY"
    )
    assert yes_item["quote_context"]["ask"] == 0.34
    assert no_item["quote_context"]["bid"] == 0.66
    assert yes_item["status"] in {"accepted", "rejected", "size_down", "reprice"}
    assert no_item["status"] in {"accepted", "rejected", "size_down", "reprice"}


def test_execution_rejects_are_persisted_in_candidate_assessments(monkeypatch):
    monkeypatch.setattr(bot_v2, "YES_STRATEGY", bot_v2.YES_STRATEGY)
    bucket = make_bucket_probability(0.18)
    quote = make_quote_snapshot(execution_stop_reasons=["orderbook_empty"])

    result = bot_v2.evaluate_yes_candidate(bucket, quote, 24)

    assert result["status"] == "rejected"
    assert "orderbook_empty" in result["reasons"]
    assert result["quote_context"]["book_ok"] is False
