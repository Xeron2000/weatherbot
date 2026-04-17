import bot_v2 as weatherbot


def make_risk_state():
    return {
        "bankroll": 10000.0,
        "global_reserved_worst_loss": 20.0,
        "legs": {
            "YES_SNIPER": {"budget": 3000.0, "reserved": 20.0, "hard_cap": 3000.0},
            "NO_CARRY": {"budget": 7000.0, "reserved": 0.0, "hard_cap": 7000.0},
        },
        "city_exposure": {"nyc": 20.0},
        "date_exposure": {"2026-04-17": 20.0},
        "event_exposure": {"nyc|2026-04-17|evt-nyc-2026-04-17": 20.0},
        "active_reservations": [],
    }


def make_active_order(ts):
    return {
        "order_id": "mkt-65-69:YES_SNIPER:yes:65.0-69.0:0.1100",
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "limit_price": 0.11,
        "shares": 200.0,
        "filled_shares": 120.0,
        "remaining_shares": 80.0,
        "time_in_force": "GTD",
        "expires_at": "2026-04-17T18:00:00+00:00",
        "status": "partial",
        "status_reason": "quote_repriced",
        "created_at": ts,
        "updated_at": ts,
        "history": [
            {
                "status": "planned",
                "reason": "accepted_route",
                "ts": ts,
                "fill_shares": 0.0,
                "fill_price": None,
            },
            {
                "status": "working",
                "reason": "order_submitted",
                "ts": ts,
                "fill_shares": 0.0,
                "fill_price": None,
            },
            {
                "status": "partial",
                "reason": "quote_repriced",
                "ts": ts,
                "fill_shares": 120.0,
                "fill_price": 0.10,
            },
        ],
    }


def make_terminal_order(ts, status, reason, limit_price=0.11):
    return {
        "order_id": f"terminal:{status}:{reason}:{limit_price:.4f}",
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "market_id": "mkt-65-69",
        "range": [65.0, 69.0],
        "limit_price": limit_price,
        "shares": 200.0,
        "filled_shares": 200.0 if status == "filled" else 0.0,
        "remaining_shares": 0.0 if status == "filled" else 200.0,
        "time_in_force": "GTC",
        "expires_at": None,
        "status": status,
        "status_reason": reason,
        "created_at": ts,
        "updated_at": ts,
        "history": [
            {
                "status": status,
                "reason": reason,
                "ts": ts,
                "fill_shares": 200.0 if status == "filled" else 0.0,
                "fill_price": 0.10 if status == "filled" else None,
            }
        ],
    }


def make_market(event, ts):
    market = weatherbot.new_market("nyc", "2026-04-17", event, 12)
    market["created_at"] = ts
    market["last_scan_status"] = "ready"
    market["route_decisions"] = [
        {
            "strategy_leg": "YES_SNIPER",
            "status": "accepted",
            "reserved_worst_loss": 20.0,
            "budget_bucket": "YES_SNIPER",
            "reasons": [],
            "range": [65.0, 69.0],
            "token_side": "yes",
        }
    ]
    market["reserved_exposure"] = {
        "strategy_leg": "YES_SNIPER",
        "token_side": "yes",
        "reserved_worst_loss": 20.0,
        "release_reason": None,
        "budget_bucket": "YES_SNIPER",
        "range": [65.0, 69.0],
    }
    market["active_order"] = make_active_order(ts)
    market["order_history"] = [
        make_terminal_order(ts, "filled", "passive_fill_complete", limit_price=0.10),
        make_terminal_order(ts, "canceled", "candidate_downgraded", limit_price=0.11),
        make_terminal_order(ts, "canceled", "quote_repriced", limit_price=0.10),
        make_terminal_order(ts, "expired", "expired", limit_price=0.12),
    ]
    return market


def make_state(ts):
    return {
        "balance": 10000.0,
        "starting_balance": 10000.0,
        "wins": 0,
        "losses": 0,
        "risk_state": make_risk_state(),
        "order_state": {
            "active_orders": [
                {
                    "market_key": "nyc:2026-04-17",
                    "city": "nyc",
                    "date": "2026-04-17",
                    "city_name": "New York City",
                    "status": "partial",
                    "order_id": "mkt-65-69:YES_SNIPER:yes:65.0-69.0:0.1100",
                    "strategy_leg": "YES_SNIPER",
                    "token_side": "yes",
                    "market_id": "mkt-65-69",
                    "range": [65.0, 69.0],
                    "filled_shares": 120.0,
                    "remaining_shares": 80.0,
                    "reserved_worst_loss": 20.0,
                    "position_status": "open",
                    "position_shares": 120.0,
                    "updated_at": ts,
                }
            ],
            "status_counts": {
                "planned": 1,
                "working": 2,
                "partial": 1,
                "filled": 3,
                "canceled": 2,
                "expired": 1,
            },
            "last_restored_at": ts,
        },
    }


def test_print_status_shows_order_lifecycle_summary(
    phase1_gamma_event, monkeypatch, capsys
):
    ts = "2026-04-17T12:00:00+00:00"
    market = make_market(phase1_gamma_event, ts)
    monkeypatch.setattr(weatherbot, "load_state", lambda: make_state(ts))
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [market])

    weatherbot.print_status()
    out = capsys.readouterr().out

    assert "Order lifecycle" in out
    assert "planned" in out
    assert "working" in out
    assert "partial" in out
    assert "filled" in out
    assert "canceled" in out
    assert "expired" in out
    assert "active_orders=1" in out
    assert "YES_SNIPER" in out
    assert "status=partial" in out
    assert "time_in_force" in out
    assert "limit=0.1100" in out
    assert "remaining=80.0000" in out
    assert "status_reason=quote_repriced" in out


def test_print_report_shows_recent_terminal_orders(
    phase1_gamma_event, monkeypatch, capsys
):
    ts = "2026-04-17T12:00:00+00:00"
    market = make_market(phase1_gamma_event, ts)
    monkeypatch.setattr(weatherbot, "load_state", lambda: make_state(ts))
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [market])

    weatherbot.print_report()
    out = capsys.readouterr().out

    assert "Order lifecycle" in out
    assert "Recent terminal orders" in out
    assert "Recent terminal reasons" in out
    assert "terminal:filled:passive_fill_complete:0.1000" in out
    assert "terminal:canceled:candidate_downgraded:0.1100" in out
    assert "terminal:expired:expired:0.1200" in out
    assert "status=filled" in out
    assert "status=canceled" in out
    assert "status=expired" in out
    assert "reason=passive_fill_complete" in out
    assert "reason=candidate_downgraded" in out
    assert "reason=expired" in out
    assert "updated_at=2026-04-17T12:00:00+00:00" in out
    assert "limit=0.1000" in out
    assert "limit=0.1100" in out
    assert "limit=0.1200" in out


def test_order_summary_stays_separate_from_trade_and_candidate_sections(
    phase1_gamma_event, monkeypatch, capsys
):
    ts = "2026-04-17T12:00:00+00:00"
    market = make_market(phase1_gamma_event, ts)
    monkeypatch.setattr(weatherbot, "load_state", lambda: make_state(ts))
    monkeypatch.setattr(weatherbot, "load_all_markets", lambda: [market])

    weatherbot.print_status()
    out = capsys.readouterr().out

    order_idx = out.index("Order lifecycle")
    route_idx = out.index("Route decisions")
    assert route_idx < order_idx
    assert "No trades yet" in out
    assert "accepted=1" not in out[order_idx:]
