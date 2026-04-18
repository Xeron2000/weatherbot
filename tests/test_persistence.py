import json

from weatherbot import persistence


def configure_persistence_runtime(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    markets_dir = data_dir / "markets"
    data_dir.mkdir()
    markets_dir.mkdir()

    monkeypatch.setattr(persistence, "STATE_FILE", data_dir / "state.json")
    monkeypatch.setattr(persistence, "CALIBRATION_FILE", data_dir / "calibration.json")
    monkeypatch.setattr(persistence, "MARKETS_DIR", markets_dir)
    monkeypatch.setattr(persistence, "BALANCE", 321.0)
    monkeypatch.setattr(persistence, "RISK_ROUTER", {"name": "router"})
    monkeypatch.setattr(
        persistence,
        "LOCATIONS",
        {
            "nyc": {
                "name": "New York",
                "unit": "F",
                "station": "KNYC",
            }
        },
    )

    def ensure_market_order_defaults(market):
        updated = dict(market)
        updated.setdefault("active_order", None)
        updated.setdefault("order_history", [])
        updated.setdefault(
            "paper_execution_state",
            {"status": "idle", "order_id": None},
        )
        updated.setdefault("execution_events", [])
        updated.setdefault(
            "execution_metrics",
            {
                "event_count": 0,
                "touch_not_fill_count": 0,
                "partial_fill_count": 0,
                "filled_count": 0,
                "cancel_requested_count": 0,
                "cancel_count": 0,
                "filled_shares_total": 0.0,
            },
        )
        updated["backfilled"] = True
        return updated

    restore_calls = {"risk": [], "order": []}

    def restore_risk_state_from_markets(state, markets, router_cfg):
        restore_calls["risk"].append((dict(state), list(markets), router_cfg))
        return {"restored": len(markets), "router": router_cfg}

    def restore_order_state_from_markets(markets):
        restore_calls["order"].append(list(markets))
        return {"active_orders": len(markets)}

    monkeypatch.setattr(
        persistence,
        "ensure_market_order_defaults",
        ensure_market_order_defaults,
    )
    monkeypatch.setattr(
        persistence,
        "build_empty_paper_execution_state",
        lambda: {"status": "idle", "order_id": None},
    )
    monkeypatch.setattr(
        persistence,
        "restore_risk_state_from_markets",
        restore_risk_state_from_markets,
    )
    monkeypatch.setattr(
        persistence,
        "restore_order_state_from_markets",
        restore_order_state_from_markets,
    )
    monkeypatch.setattr(persistence, "_cal", {})

    return markets_dir, restore_calls


def test_load_market_and_load_all_markets_backfill_old_json(tmp_path, monkeypatch):
    markets_dir, _restore_calls = configure_persistence_runtime(tmp_path, monkeypatch)
    legacy_market = {
        "city": "nyc",
        "date": "2026-04-18",
        "status": "open",
    }
    (markets_dir / "nyc_2026-04-18.json").write_text(
        json.dumps(legacy_market),
        encoding="utf-8",
    )
    (markets_dir / "broken.json").write_text("{", encoding="utf-8")

    loaded = persistence.load_market("nyc", "2026-04-18")
    all_markets = persistence.load_all_markets()

    assert loaded["backfilled"] is True
    assert loaded["active_order"] is None
    assert loaded["paper_execution_state"]["status"] == "idle"
    assert len(all_markets) == 1
    assert all_markets[0]["backfilled"] is True


def test_load_state_restores_runtime_state_and_backfills_missing_defaults(
    tmp_path, monkeypatch
):
    markets_dir, restore_calls = configure_persistence_runtime(tmp_path, monkeypatch)
    (markets_dir / "nyc_2026-04-18.json").write_text(
        json.dumps({"city": "nyc", "date": "2026-04-18", "status": "open"}),
        encoding="utf-8",
    )

    state = persistence.load_state()

    assert state["balance"] == 321.0
    assert state["starting_balance"] == 321.0
    assert state["total_trades"] == 0
    assert state["wins"] == 0
    assert state["losses"] == 0
    assert state["peak_balance"] == 321.0
    assert state["risk_state"] == {"restored": 1, "router": {"name": "router"}}
    assert state["order_state"] == {"active_orders": 1}
    assert restore_calls["risk"][0][2] == {"name": "router"}
    assert restore_calls["order"][0][0]["backfilled"] is True


def test_new_market_and_save_market_persist_modular_execution_fields(
    tmp_path, monkeypatch
):
    _markets_dir, _restore_calls = configure_persistence_runtime(tmp_path, monkeypatch)
    market = persistence.new_market(
        "nyc",
        "2026-04-18",
        {"slug": "event-slug", "id": "event-id", "endDate": "2026-04-19T00:00:00Z"},
        18.0,
    )

    persistence.save_market(market)
    loaded = persistence.load_market("nyc", "2026-04-18")

    assert market["active_order"] is None
    assert market["order_history"] == []
    assert market["paper_execution_state"]["status"] == "idle"
    assert market["execution_events"] == []
    assert market["execution_metrics"]["filled_count"] == 0
    assert loaded["event_slug"] == "event-slug"
    assert loaded["event_id"] == "event-id"
    assert loaded["backfilled"] is True
