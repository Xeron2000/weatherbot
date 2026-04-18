from datetime import datetime, timezone, timedelta

from .config import load_config, load_order_policy_config


_cfg = load_config()

ORDER_POLICY = load_order_policy_config(_cfg)


def find_assessment_for_reservation(market):
    reservation = market.get("reserved_exposure")
    if not reservation:
        return None
    for assessment in market.get("candidate_assessments", []) or []:
        if assessment_matches_reservation(assessment, reservation):
            return assessment
    return None

def find_quote_for_market(quote_snapshot, market_id):
    for quote in quote_snapshot or []:
        if quote.get("market_id") == market_id:
            return quote
    return None

def resolve_market_id_for_range(market, assessment):
    target_range = list(assessment.get("range") or [])
    for contract in market.get("market_contracts", []) or []:
        if list(contract.get("range") or []) == target_range:
            return contract.get("market_id")
    return None

def compute_passive_limit_price(side_quote, policy):
    bid = side_quote.get("bid")
    ask = side_quote.get("ask")
    tick_size = side_quote.get("tick_size")
    if tick_size is None:
        return None, "tick_size_missing"
    try:
        tick_size = float(tick_size)
    except Exception:
        return None, "tick_size_missing"
    if tick_size <= 0:
        return None, "tick_size_missing"
    if bid is None or ask is None:
        return None, "quote_price_missing"
    try:
        bid = float(bid)
        ask = float(ask)
    except Exception:
        return None, "quote_price_missing"
    improve_ticks = int(policy.get("price_improve_ticks", 0) or 0)
    candidate = bid + (tick_size * improve_ticks)
    candidate = max(candidate, bid)
    if ask > bid:
        candidate = min(candidate, ask - tick_size)
    candidate = round(candidate, 6)
    if candidate <= 0:
        return None, "quote_price_missing"
    return round(candidate, 4), None

def compute_no_anchored_limit_price(side_quote, fair_no, policy):
    bid = side_quote.get("bid")
    ask = side_quote.get("ask")
    tick_size = side_quote.get("tick_size")
    if tick_size is None:
        return None, "tick_size_missing"
    try:
        tick_size = float(tick_size)
    except Exception:
        return None, "tick_size_missing"
    if tick_size <= 0:
        return None, "tick_size_missing"
    if bid is None or ask is None:
        return None, "quote_price_missing"
    try:
        bid = float(bid)
        ask = float(ask)
    except Exception:
        return None, "quote_price_missing"
    if fair_no is None:
        return None, "fair_value_missing"
    try:
        fair_no = float(fair_no)
    except Exception:
        return None, "fair_value_missing"

    anchored_target = fair_no - 0.10
    candidate = anchored_target
    if ask > bid:
        candidate = min(candidate, ask - tick_size)
    candidate = int(candidate / tick_size) * tick_size
    candidate = round(candidate, 6)
    if candidate <= 0:
        return None, "quote_price_missing"
    return round(candidate, 4), None

def build_passive_order_intent(market, reservation, assessment, quote_snapshot, now_ts):
    if not reservation:
        return {"order": None, "reason": "reservation_missing"}
    if not assessment or assessment.get("status") != "accepted":
        return {"order": None, "reason": "route_not_accepted"}
    if (
        reservation.get("strategy_leg") != "YES_SNIPER"
        or reservation.get("token_side") != "yes"
        or assessment.get("strategy_leg") != "YES_SNIPER"
        or assessment.get("token_side") != "yes"
    ):
        return {"order": None, "reason": "yes_only_runtime"}
    market_id = resolve_market_id_for_range(market, assessment)
    if not market_id:
        return {"order": None, "reason": "market_contract_missing"}
    quote = find_quote_for_market(quote_snapshot, market_id)
    if not quote:
        return {"order": None, "reason": "quote_snapshot_missing"}
    token_side = assessment.get("token_side")
    side_quote = (quote.get(token_side) if token_side in {"yes", "no"} else None) or {}
    if not side_quote:
        return {"order": None, "reason": "quote_snapshot_missing"}
    if token_side == "no":
        limit_price, reason = compute_no_anchored_limit_price(
            side_quote, assessment.get("fair_no"), ORDER_POLICY
        )
    else:
        limit_price, reason = compute_passive_limit_price(side_quote, ORDER_POLICY)
    if reason:
        return {"order": None, "reason": reason}
    reserved_worst_loss = float(reservation.get("reserved_worst_loss", 0.0) or 0.0)
    if reserved_worst_loss <= 0:
        return {"order": None, "reason": "reserved_worst_loss_missing"}
    shares = round(reserved_worst_loss / limit_price, 4)
    tif_key = "yes_time_in_force" if token_side == "yes" else "no_time_in_force"
    time_in_force = ORDER_POLICY.get(tif_key, "GTC")
    expires_at = None
    if time_in_force == "GTD":
        try:
            expires_at = (
                datetime.fromisoformat(now_ts)
                + timedelta(hours=ORDER_POLICY.get("gtd_buffer_hours", 6.0))
            ).isoformat()
        except Exception:
            expires_at = None
    order = {
        "order_id": (
            f"{market_id}:{reservation.get('strategy_leg')}:{token_side}:"
            f"{assessment.get('range')[0]}-{assessment.get('range')[1]}:{limit_price:.4f}"
        ),
        "strategy_leg": reservation.get("strategy_leg"),
        "token_side": token_side,
        "market_id": market_id,
        "range": list(assessment.get("range") or []),
        "limit_price": limit_price,
        "shares": shares,
        "filled_shares": 0.0,
        "remaining_shares": shares,
        "time_in_force": time_in_force,
        "expires_at": expires_at,
        "status": "planned",
        "status_reason": "accepted_route",
        "created_at": now_ts,
        "updated_at": now_ts,
        "history": [
            {
                "status": "planned",
                "reason": "accepted_route",
                "ts": now_ts,
                "fill_shares": 0.0,
                "fill_price": None,
            }
        ],
    }
    return {"order": order, "reason": None}

def apply_order_transition(
    order,
    next_status,
    reason,
    ts,
    fill_shares=0.0,
    fill_price=None,
    patch=None,
):
    allowed = {"planned", "working", "partial", "filled", "canceled", "expired"}
    if next_status not in allowed:
        raise ValueError(f"unsupported_order_status:{next_status}")
    updated = dict(order or {})
    history = list(updated.get("history", []) or [])
    delta = round(float(fill_shares or 0.0), 4)
    updated["filled_shares"] = round(
        float(updated.get("filled_shares", 0.0) or 0.0) + delta,
        4,
    )
    total_shares = round(float(updated.get("shares", 0.0) or 0.0), 4)
    updated["remaining_shares"] = round(
        max(0.0, total_shares - updated["filled_shares"]),
        4,
    )
    updated["status"] = next_status
    updated["status_reason"] = reason
    updated["updated_at"] = ts
    if patch:
        updated.update(patch)
    history.append(
        {
            "status": next_status,
            "reason": reason,
            "ts": ts,
            "fill_shares": delta,
            "fill_price": fill_price,
        }
    )
    updated["history"] = history
    return updated

def is_order_terminal(order):
    return (order or {}).get("status") in {"filled", "canceled", "expired"}

def is_order_unfinished(order):
    return (order or {}).get("status") in {"planned", "working", "partial"}

def build_empty_paper_execution_state():
    return {
        "order_id": None,
        "status": "idle",
        "submitted_at": None,
        "submit_ready_at": None,
        "cancel_requested_at": None,
        "cancel_ready_at": None,
        "cancel_reason": None,
        "touch_count": 0,
        "queue_ahead_shares": 0.0,
        "filled_shares": 0.0,
        "remaining_shares": 0.0,
        "last_event_ts": None,
        "last_reason": None,
    }

def ensure_market_paper_execution_defaults(market):
    state = market.get("paper_execution_state")
    if not isinstance(state, dict):
        state = build_empty_paper_execution_state()
    else:
        base = build_empty_paper_execution_state()
        base.update(state)
        state = base
    market["paper_execution_state"] = state
    market.setdefault("execution_events", [])
    metrics = market.get("execution_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    metrics.setdefault("event_count", 0)
    metrics.setdefault("touch_not_fill_count", 0)
    metrics.setdefault("partial_fill_count", 0)
    metrics.setdefault("filled_count", 0)
    metrics.setdefault("cancel_requested_count", 0)
    metrics.setdefault("cancel_count", 0)
    metrics.setdefault("filled_shares_total", 0.0)
    market["execution_metrics"] = metrics
    return market

def ensure_market_order_defaults(market):
    market.setdefault("active_order", None)
    market.setdefault("order_history", [])
    ensure_market_paper_execution_defaults(market)
    return market

def parse_simulation_ts(ts):
    parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed

def add_ms_to_ts(ts, ms):
    return (parse_simulation_ts(ts) + timedelta(milliseconds=int(ms))).isoformat()

def build_paper_execution_state(order, paper_config, now_ts):
    shares = round(float((order or {}).get("shares", 0.0) or 0.0), 4)
    queue_ahead = max(
        float(paper_config.get("queue_ahead_shares", 0.0) or 0.0),
        shares * float(paper_config.get("queue_ahead_ratio", 0.0) or 0.0),
    )
    return {
        "order_id": (order or {}).get("order_id"),
        "status": "submitting",
        "submitted_at": now_ts,
        "submit_ready_at": add_ms_to_ts(
            now_ts, paper_config.get("submission_latency_ms", 0)
        ),
        "cancel_requested_at": None,
        "cancel_ready_at": None,
        "touch_count": 0,
        "queue_ahead_shares": round(queue_ahead, 4),
        "filled_shares": 0.0,
        "remaining_shares": shares,
        "last_event_ts": now_ts,
        "last_reason": "submission_latency_pending",
    }

def record_execution_event(
    events,
    order,
    event_type,
    ts,
    status_before,
    status_after,
    reason,
    simulated_fill_shares=0.0,
    queue_ahead_shares=0.0,
    latency_ms=0,
    patch=None,
):
    event = {
        "event_type": event_type,
        "ts": ts,
        "order_id": (order or {}).get("order_id"),
        "status_before": status_before,
        "status_after": status_after,
        "reason": reason,
        "simulated_fill_shares": round(float(simulated_fill_shares or 0.0), 4),
        "queue_ahead_shares": round(float(queue_ahead_shares or 0.0), 4),
        "latency_ms": int(latency_ms or 0),
    }
    if patch:
        event.update(patch)
    updated = list(events or [])
    updated.append(event)
    return updated, event

def finalize_paper_step(market, state, events, metrics, filled_shares, event=None):
    market["paper_execution_state"] = state
    market["execution_events"] = events
    metrics["event_count"] = len(events)
    market["execution_metrics"] = metrics
    return {
        "market": market,
        "state": state,
        "event": event,
        "filled_shares": round(float(filled_shares or 0.0), 4),
    }

def simulate_paper_execution_step(
    market,
    order,
    quote_snapshot,
    now_ts,
    paper_config=None,
    cancel_requested=False,
    cancel_reason=None,
):
    cfg = paper_config or PAPER_EXECUTION
    updated_market = dict(market or {})
    ensure_market_paper_execution_defaults(updated_market)
    state = dict(updated_market.get("paper_execution_state") or {})
    events = list(updated_market.get("execution_events", []) or [])
    metrics = dict(updated_market.get("execution_metrics", {}) or {})
    order_id = (order or {}).get("order_id")

    if not order_id:
        return finalize_paper_step(updated_market, state, events, metrics, 0.0)

    if state.get("order_id") != order_id or state.get("status") in {None, "idle"}:
        status_before = state.get("status") or "idle"
        state = build_paper_execution_state(order, cfg, now_ts)
        events, event = record_execution_event(
            events,
            order,
            "submission_pending",
            now_ts,
            status_before,
            "submitting",
            "submission_latency_pending",
            queue_ahead_shares=state.get("queue_ahead_shares", 0.0),
            latency_ms=cfg.get("submission_latency_ms", 0),
        )
        return finalize_paper_step(updated_market, state, events, metrics, 0.0, event)

    current_status = state.get("status")
    now_dt = parse_simulation_ts(now_ts)

    if cancel_requested:
        if current_status == "cancel_pending":
            cancel_ready_at = state.get("cancel_ready_at")
            if cancel_ready_at and now_dt >= parse_simulation_ts(cancel_ready_at):
                state["status"] = "canceled"
                state["last_event_ts"] = now_ts
                state["last_reason"] = "cancel_latency_elapsed"
                events, event = record_execution_event(
                    events,
                    order,
                    "cancel_confirmed",
                    now_ts,
                    "cancel_pending",
                    "canceled",
                    "cancel_latency_elapsed",
                    queue_ahead_shares=state.get("queue_ahead_shares", 0.0),
                    latency_ms=cfg.get("cancel_latency_ms", 0),
                    patch={
                        "cancel_reason": state.get("cancel_reason"),
                    },
                )
                metrics["cancel_count"] = int(metrics.get("cancel_count", 0) or 0) + 1
                return finalize_paper_step(
                    updated_market, state, events, metrics, 0.0, event
                )
            return finalize_paper_step(updated_market, state, events, metrics, 0.0)

        if current_status not in {"filled", "canceled"}:
            state["status"] = "cancel_pending"
            state["cancel_requested_at"] = now_ts
            state["cancel_ready_at"] = add_ms_to_ts(
                now_ts, cfg.get("cancel_latency_ms", 0)
            )
            state["cancel_reason"] = cancel_reason or state.get("cancel_reason")
            state["last_event_ts"] = now_ts
            state["last_reason"] = "cancel_latency_pending"
            events, event = record_execution_event(
                events,
                order,
                "cancel_requested",
                now_ts,
                current_status,
                "cancel_pending",
                "cancel_latency_pending",
                queue_ahead_shares=state.get("queue_ahead_shares", 0.0),
                latency_ms=cfg.get("cancel_latency_ms", 0),
                patch={
                    "cancel_reason": state.get("cancel_reason"),
                },
            )
            metrics["cancel_requested_count"] = (
                int(metrics.get("cancel_requested_count", 0) or 0) + 1
            )
            return finalize_paper_step(updated_market, state, events, metrics, 0.0, event)

        return finalize_paper_step(updated_market, state, events, metrics, 0.0)

    if current_status == "submitting":
        submit_ready_at = state.get("submit_ready_at")
        if submit_ready_at and now_dt < parse_simulation_ts(submit_ready_at):
            return finalize_paper_step(updated_market, state, events, metrics, 0.0)
        state["status"] = "queued"
        state["last_event_ts"] = now_ts
        state["last_reason"] = "submission_latency_elapsed"
        events, event = record_execution_event(
            events,
            order,
            "submission_released",
            now_ts,
            "submitting",
            "queued",
            "submission_latency_elapsed",
            queue_ahead_shares=state.get("queue_ahead_shares", 0.0),
            latency_ms=cfg.get("submission_latency_ms", 0),
        )
        return finalize_paper_step(updated_market, state, events, metrics, 0.0, event)

    if current_status not in {"queued", "partial"}:
        return finalize_paper_step(updated_market, state, events, metrics, 0.0)

    quote = find_quote_for_market(quote_snapshot, (order or {}).get("market_id"))
    token_side = (order or {}).get("token_side")
    side_quote = (
        quote.get(token_side) if quote and token_side in {"yes", "no"} else None
    ) or {}

    ask = safe_float(side_quote.get("ask"))
    ask_size = safe_float(side_quote.get("ask_size"))
    tick_size = safe_float(side_quote.get("tick_size")) or 0.0
    limit_price = float((order or {}).get("limit_price", 0.0) or 0.0)
    fill_threshold = limit_price - (
        tick_size * int(cfg.get("adverse_fill_buffer_ticks", 0) or 0)
    )

    if ask is None or ask_size is None or ask > fill_threshold:
        return finalize_paper_step(updated_market, state, events, metrics, 0.0)

    state["touch_count"] = int(state.get("touch_count", 0) or 0) + 1
    queue_before = round(float(state.get("queue_ahead_shares", 0.0) or 0.0), 4)
    queue_after = round(max(0.0, queue_before - ask_size), 4)
    if queue_before > 0 and queue_after > 0:
        state["queue_ahead_shares"] = queue_after
        state["last_event_ts"] = now_ts
        state["last_reason"] = "queue_ahead_remaining"
        events, event = record_execution_event(
            events,
            order,
            "touch_not_fill",
            now_ts,
            current_status,
            current_status,
            "queue_ahead_remaining",
            queue_ahead_shares=queue_after,
        )
        metrics["touch_not_fill_count"] = (
            int(metrics.get("touch_not_fill_count", 0) or 0) + 1
        )
        return finalize_paper_step(updated_market, state, events, metrics, 0.0, event)

    if state["touch_count"] < int(cfg.get("touch_not_fill_min_touches", 1) or 1):
        state["queue_ahead_shares"] = queue_after
        state["last_event_ts"] = now_ts
        state["last_reason"] = "touch_threshold_not_met"
        events, event = record_execution_event(
            events,
            order,
            "touch_not_fill",
            now_ts,
            current_status,
            current_status,
            "touch_threshold_not_met",
            queue_ahead_shares=queue_after,
        )
        metrics["touch_not_fill_count"] = (
            int(metrics.get("touch_not_fill_count", 0) or 0) + 1
        )
        return finalize_paper_step(updated_market, state, events, metrics, 0.0, event)

    executable_shares = round(max(0.0, ask_size - queue_before), 4)
    remaining_before = round(float(state.get("remaining_shares", 0.0) or 0.0), 4)
    target_slice = round(
        remaining_before * float(cfg.get("partial_fill_slice_ratio", 0.0) or 0.0),
        4,
    )
    if current_status == "partial":
        target_slice = remaining_before
    if remaining_before > 0 and target_slice <= 0:
        target_slice = remaining_before
    fill_shares = round(min(remaining_before, executable_shares, target_slice), 4)
    if fill_shares <= 0:
        return finalize_paper_step(updated_market, state, events, metrics, 0.0)

    state["queue_ahead_shares"] = 0.0
    state["filled_shares"] = round(
        float(state.get("filled_shares", 0.0) or 0.0) + fill_shares,
        4,
    )
    state["remaining_shares"] = round(max(0.0, remaining_before - fill_shares), 4)
    if state["remaining_shares"] == 0.0:
        next_status = "filled"
        event_type = "filled"
        reason = "queue_cleared_full_fill"
        metrics["filled_count"] = int(metrics.get("filled_count", 0) or 0) + 1
    else:
        next_status = "partial"
        event_type = "partial_fill"
        reason = "queue_cleared_partial_fill"
        metrics["partial_fill_count"] = int(metrics.get("partial_fill_count", 0) or 0) + 1
    state["status"] = next_status
    state["last_event_ts"] = now_ts
    state["last_reason"] = reason
    metrics["filled_shares_total"] = round(
        float(metrics.get("filled_shares_total", 0.0) or 0.0) + fill_shares,
        4,
    )
    events, event = record_execution_event(
        events,
        order,
        event_type,
        now_ts,
        current_status,
        next_status,
        reason,
        simulated_fill_shares=fill_shares,
        queue_ahead_shares=state.get("queue_ahead_shares", 0.0),
        patch={"simulated_fill_price": ask},
    )
    return finalize_paper_step(updated_market, state, events, metrics, fill_shares, event)

def build_order_restore_entry(market, order):
    reservation = market.get("reserved_exposure") or {}
    position = market.get("position") or {}
    return {
        "market_key": f"{market.get('city')}:{market.get('date')}",
        "city": market.get("city"),
        "date": market.get("date"),
        "city_name": market.get("city_name"),
        "status": order.get("status"),
        "order_id": order.get("order_id"),
        "strategy_leg": order.get("strategy_leg"),
        "token_side": order.get("token_side"),
        "market_id": order.get("market_id"),
        "range": list(order.get("range") or []),
        "filled_shares": round(float(order.get("filled_shares", 0.0) or 0.0), 4),
        "remaining_shares": round(float(order.get("remaining_shares", 0.0) or 0.0), 4),
        "reserved_worst_loss": round(
            float(reservation.get("reserved_worst_loss", 0.0) or 0.0), 2
        ),
        "position_status": position.get("status"),
        "position_shares": round(float(position.get("shares", 0.0) or 0.0), 4),
        "updated_at": order.get("updated_at"),
    }

def restore_order_state_from_markets(markets):
    status_counts = {
        "planned": 0,
        "working": 0,
        "partial": 0,
        "filled": 0,
        "canceled": 0,
        "expired": 0,
    }
    active_orders = []

    for market in markets or []:
        ensure_market_order_defaults(market)
        active_order = market.get("active_order")
        if active_order:
            status = active_order.get("status")
            if (
                active_order.get("strategy_leg") == "YES_SNIPER"
                and active_order.get("token_side") == "yes"
                and status in status_counts
            ):
                status_counts[status] += 1
            if (
                active_order.get("strategy_leg") == "YES_SNIPER"
                and active_order.get("token_side") == "yes"
                and is_order_unfinished(active_order)
            ):
                active_orders.append(build_order_restore_entry(market, active_order))

        for order in market.get("order_history", []) or []:
            status = (order or {}).get("status")
            if status in status_counts:
                status_counts[status] += 1

    active_orders.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("city") or "",
            item.get("order_id") or "",
        )
    )

    return {
        "active_orders": active_orders,
        "status_counts": status_counts,
        "last_restored_at": datetime.now(timezone.utc).isoformat(),
    }

def find_route_for_reservation(market):
    reservation = market.get("reserved_exposure") or {}
    for route in market.get("route_decisions", []) or []:
        if (
            route.get("strategy_leg") == reservation.get("strategy_leg")
            and route.get("token_side") == reservation.get("token_side")
            and list(route.get("range") or []) == list(reservation.get("range") or [])
        ):
            return route
    return None

def archive_order(market, order):
    if not order:
        return
    ensure_market_order_defaults(market)
    market.setdefault("order_history", []).append(dict(order))
    market["active_order"] = None

def average_order_fill_price(order):
    total_shares = 0.0
    total_cost = 0.0
    for item in (order or {}).get("history", []) or []:
        fill_shares = float(item.get("fill_shares", 0.0) or 0.0)
        fill_price = item.get("fill_price")
        if fill_shares <= 0 or fill_price is None:
            continue
        total_shares += fill_shares
        total_cost += fill_shares * float(fill_price)
    if total_shares <= 0:
        return round(float((order or {}).get("limit_price", 0.0) or 0.0), 4)
    return round(total_cost / total_shares, 4)

def build_position_from_order(market, order, assessment, forecast_snap):
    filled_shares = round(float((order or {}).get("filled_shares", 0.0) or 0.0), 4)
    if filled_shares <= 0:
        return None

    entry_price = average_order_fill_price(order)
    token_side = (order or {}).get("token_side")
    rng = list((order or {}).get("range") or [None, None])
    quote_ctx = (assessment or {}).get("quote_context", {}) or {}
    fair_price = (assessment or {}).get("fair_price")
    if fair_price is None:
        fair_price = (
            (assessment or {}).get("fair_yes")
            if (order or {}).get("token_side") == "yes"
            else (assessment or {}).get("fair_no")
        )
    edge = (assessment or {}).get("edge")
    if edge is None and fair_price is not None:
        edge = round(float(fair_price) - entry_price, 6)

    position = {
        "market_id": order.get("market_id"),
        "question": next(
            (
                contract.get("question")
                for contract in market.get("market_contracts", []) or []
                if contract.get("market_id") == order.get("market_id")
            ),
            None,
        ),
        "bucket_low": rng[0],
        "bucket_high": rng[1],
        "entry_price": entry_price,
        "token_side": token_side,
        "entry_side": token_side,
        "bid_at_entry": quote_ctx.get("bid"),
        "spread": quote_ctx.get("spread"),
        "shares": filled_shares,
        "cost": round(filled_shares * entry_price, 2),
        "p": round(
            float((assessment or {}).get("aggregate_probability", 0.0) or 0.0), 4
        ),
        "ev": round(float(edge or 0.0), 4),
        "kelly": None,
        "forecast_temp": (forecast_snap or {}).get("best"),
        "forecast_src": (forecast_snap or {}).get("best_source"),
        "sigma": None,
        "opened_at": order.get("updated_at"),
        "status": "open",
        "pnl": None,
        "exit_price": None,
        "close_reason": None,
        "closed_at": None,
    }
    return position

def maybe_release_order_reservation(market, risk_state, reason, ts):
    if reason not in {
        "candidate_downgraded",
        "candidate_missing",
        "market_no_longer_ready",
        "expired",
        "route_not_accepted",
        "yes_only_runtime",
    }:
        return
    reservation = market.get("reserved_exposure")
    if reservation and not reservation.get("release_reason"):
        release_reserved_exposure(market, risk_state, reason, released_at=ts)

def transition_order_terminal(market, risk_state, order, next_status, reason, ts):
    terminal = apply_order_transition(order, next_status, reason, ts)
    archive_order(market, terminal)
    maybe_release_order_reservation(market, risk_state, reason, ts)
    return terminal

def sync_active_order_with_paper_engine(
    market,
    risk_state,
    active_order,
    assessment,
    forecast_snap,
    ts,
    cancel_requested=False,
    cancel_reason=None,
):
    paper_state = market.get("paper_execution_state") or {}
    if (
        active_order
        and active_order.get("status") == "partial"
        and paper_state.get("status") in {None, "idle"}
    ):
        market["paper_execution_state"] = {
            **build_empty_paper_execution_state(),
            "order_id": active_order.get("order_id"),
            "status": "partial",
            "submitted_at": active_order.get("created_at") or ts,
            "submit_ready_at": active_order.get("updated_at") or ts,
            "queue_ahead_shares": 0.0,
            "filled_shares": float(active_order.get("filled_shares", 0.0) or 0.0),
            "remaining_shares": float(active_order.get("remaining_shares", 0.0) or 0.0),
            "last_event_ts": active_order.get("updated_at") or ts,
            "last_reason": "order_restored_partial",
        }
    step = simulate_paper_execution_step(
        market,
        active_order,
        market.get("quote_snapshot", []),
        ts,
        paper_config=PAPER_EXECUTION,
        cancel_requested=cancel_requested,
        cancel_reason=cancel_reason,
    )
    market["paper_execution_state"] = step["market"].get("paper_execution_state")
    market["execution_events"] = step["market"].get("execution_events", [])
    market["execution_metrics"] = step["market"].get("execution_metrics", {})

    event = step.get("event") or {}
    fill_shares = round(float(step.get("filled_shares", 0.0) or 0.0), 4)
    state = market.get("paper_execution_state", {}) or {}
    state_status = state.get("status")

    if fill_shares > 0 and state_status in {"partial", "filled"}:
        transitioned = apply_order_transition(
            active_order,
            "filled" if state_status == "filled" else "partial",
            event.get("reason") or state.get("last_reason") or "paper_fill",
            event.get("ts") or ts,
            fill_shares=fill_shares,
            fill_price=event.get("simulated_fill_price"),
        )
        if state_status == "partial":
            market["active_order"] = transitioned
            return {"filled_cost": 0.0, "opened_position": False}

        archive_order(market, transitioned)
        release_reserved_exposure(market, risk_state, "filled", released_at=ts)
        market["position"] = build_position_from_order(
            market, transitioned, assessment, forecast_snap
        )
        return {
            "filled_cost": round(
                float((market.get("position") or {}).get("cost", 0.0) or 0.0), 2
            ),
            "opened_position": market.get("position") is not None,
        }

    if state_status == "canceled":
        terminal_reason = state.get("cancel_reason") or cancel_reason or "canceled"
        terminal = apply_order_transition(active_order, "canceled", terminal_reason, ts)
        archive_order(market, terminal)
        maybe_release_order_reservation(market, risk_state, terminal_reason, ts)
        return {"filled_cost": 0.0, "opened_position": False}

    if active_order.get("status") == "planned":
        active_order = apply_order_transition(active_order, "working", "order_resumed", ts)
    else:
        active_order = dict(active_order)
        active_order["updated_at"] = ts
    market["active_order"] = active_order
    return {"filled_cost": 0.0, "opened_position": False}

def sync_market_order(market, risk_state, forecast_snap, market_ready=True):
    ensure_market_order_defaults(market)
    ts = (
        (forecast_snap or {}).get("ts")
        or market.get("last_scan_at")
        or datetime.now(timezone.utc).isoformat()
    )
    active_order = market.get("active_order")

    if active_order and is_order_terminal(active_order):
        archive_order(market, active_order)
        active_order = None

    cancel_reason = None

    if not market_ready:
        cancel_reason = "market_no_longer_ready"

    if (
        market.get("position")
        and market["position"].get("status") == "open"
        and not active_order
    ):
        return {"filled_cost": 0.0, "opened_position": False}

    reservation = market.get("reserved_exposure")
    assessment = find_assessment_for_reservation(market)
    route = find_route_for_reservation(market)

    yes_only_ready = True
    for fact in [reservation, assessment, active_order]:
        if not fact:
            continue
        if fact.get("strategy_leg") != "YES_SNIPER" or fact.get("token_side") != "yes":
            yes_only_ready = False
            break

    if active_order and reservation and reservation.get("release_reason"):
        cancel_reason = reservation.get("release_reason")

    if not yes_only_ready:
        cancel_reason = cancel_reason or "yes_only_runtime"

    if active_order and not reservation:
        cancel_reason = "candidate_missing"

    if active_order:
        if assessment is None:
            cancel_reason = cancel_reason or "candidate_missing"
        elif assessment.get("status") != "accepted":
            cancel_reason = cancel_reason or "candidate_downgraded"

    if active_order and route and route.get("status") != "accepted":
        cancel_reason = cancel_reason or "route_not_accepted"

    if (not reservation or not assessment) and not active_order:
        if cancel_reason:
            maybe_release_order_reservation(market, risk_state, cancel_reason, ts)
        return {"filled_cost": 0.0, "opened_position": False}

    active_order = market.get("active_order")
    if active_order:
        if active_order.get("expires_at"):
            try:
                if datetime.fromisoformat(
                    active_order["expires_at"]
                ) <= datetime.fromisoformat(ts):
                    transition_order_terminal(
                        market, risk_state, active_order, "expired", "expired", ts
                    )
                    return {"filled_cost": 0.0, "opened_position": False}
            except Exception:
                pass
        else:
            max_open_hours = float(
                ORDER_POLICY.get("max_order_hours_open", 72.0) or 72.0
            )
            try:
                created_at = datetime.fromisoformat(
                    active_order.get("created_at") or ts
                )
                if (
                    datetime.fromisoformat(ts) - created_at
                ).total_seconds() / 3600 > max_open_hours:
                    transition_order_terminal(
                        market, risk_state, active_order, "expired", "expired", ts
                    )
                    return {"filled_cost": 0.0, "opened_position": False}
            except Exception:
                pass
        active_order = market.get("active_order")
        if active_order and reservation and assessment:
            paper_state = market.get("paper_execution_state") or {}
            if paper_state.get("status") == "cancel_pending":
                cancel_reason = paper_state.get("cancel_reason") or cancel_reason
            built = build_passive_order_intent(
                market,
                reservation,
                assessment,
                market.get("quote_snapshot", []),
                ts,
            )
            if built.get("order"):
                new_limit = float(built["order"].get("limit_price", 0.0) or 0.0)
                old_limit = float(active_order.get("limit_price", 0.0) or 0.0)
                if (
                    active_order.get("status") == "working"
                    and paper_state.get("status") in {None, "idle", "submitting"}
                    and abs(
                    new_limit - old_limit
                    )
                    > float(ORDER_POLICY.get("replace_edge_buffer", 0.02) or 0.02)
                ):
                    cancel_reason = cancel_reason or "quote_repriced"
        elif active_order:
            paper_state = market.get("paper_execution_state") or {}
            if paper_state.get("status") == "cancel_pending":
                cancel_reason = paper_state.get("cancel_reason") or cancel_reason
        return sync_active_order_with_paper_engine(
            market,
            risk_state,
            active_order,
            assessment,
            forecast_snap,
            ts,
            cancel_requested=bool(cancel_reason),
            cancel_reason=cancel_reason,
        )

    if cancel_reason:
        maybe_release_order_reservation(market, risk_state, cancel_reason, ts)
        return {"filled_cost": 0.0, "opened_position": False}

    built = build_passive_order_intent(
        market,
        reservation,
        assessment,
        market.get("quote_snapshot", []),
        ts,
    )

    if built.get("order"):
        market["active_order"] = apply_order_transition(
            built["order"],
            "working",
            "order_submitted",
            ts,
        )

    active_order = market.get("active_order")
    if not active_order:
        return {"filled_cost": 0.0, "opened_position": False}
    return sync_active_order_with_paper_engine(
        market,
        risk_state,
        active_order,
        assessment,
        forecast_snap,
        ts,
        cancel_requested=bool(cancel_reason),
        cancel_reason=cancel_reason,
    )

def route_market_candidates(
    market,
    risk_state,
    router_cfg,
    reserved_at=None,
    kept_reservation=None,
    initial_decisions=None,
):
    assessments = market.get("candidate_assessments", []) or []
    decisions = list(initial_decisions or [])
    reserved_exposure = (
        kept_reservation
        if kept_reservation is not None
        else market.get("reserved_exposure")
    )

    for leg in ["YES_SNIPER"]:
        leg_assessments = []
        for assessment in assessments:
            if assessment.get("strategy_leg") != leg:
                continue
            if kept_reservation and assessment_matches_reservation(
                assessment, kept_reservation
            ):
                continue
            leg_assessments.append(assessment)
        for assessment in sort_leg_candidates(leg_assessments):
            decision = route_candidate_assessment(
                assessment, market, risk_state, router_cfg
            )
            decisions.append(decision)
            if decision.get("status") == "accepted" and reserved_exposure is None:
                reserved_exposure = build_reserved_exposure(
                    market,
                    decision,
                    reserved_at or datetime.now(timezone.utc).isoformat(),
                )
                apply_reservation_to_risk_state(risk_state, reserved_exposure)

    market["route_decisions"] = decisions
    market["reserved_exposure"] = reserved_exposure
    return decisions, reserved_exposure

def reconcile_market_reservation(market, risk_state, router_cfg, reserved_at=None):
    existing = market.get("reserved_exposure")
    kept_reservation = None
    decisions = []

    if existing and not existing.get("release_reason"):
        active_order = market.get("active_order")
        unfinished_order = is_order_unfinished(active_order)
        matching_assessment = next(
            (
                assessment
                for assessment in market.get("candidate_assessments", []) or []
                if assessment_matches_reservation(assessment, existing)
            ),
            None,
        )

        if matching_assessment is None:
            if not unfinished_order:
                release_reserved_exposure(
                    market, risk_state, "candidate_missing", reserved_at
                )
        elif matching_assessment.get("status") not in {"accepted", "size_down"}:
            if not unfinished_order:
                release_reserved_exposure(
                    market, risk_state, "candidate_downgraded", reserved_at
                )
        else:
            remove_reservation_from_risk_state(risk_state, existing)
            kept_decision = {
                "strategy_leg": existing.get("strategy_leg"),
                "token_side": existing.get("token_side"),
                "range": list(existing.get("range") or []),
                "input_status": matching_assessment.get("status"),
                "status": "accepted",
                "reserved_worst_loss": candidate_worst_loss(
                    matching_assessment, risk_state.get("bankroll", 0.0)
                ),
                "budget_bucket": existing.get("budget_bucket"),
                "reasons": normalize_route_reason_codes(
                    matching_assessment.get("reasons", [])
                ),
                "exposure_keys": build_exposure_keys(
                    market, assessment=matching_assessment
                ),
            }
            kept_reservation = build_reserved_exposure(
                market, kept_decision, reserved_at
            )
            apply_reservation_to_risk_state(risk_state, kept_reservation)
            decisions.append(kept_decision)

    return route_market_candidates(
        market,
        risk_state,
        router_cfg,
        reserved_at=reserved_at,
        kept_reservation=kept_reservation,
        initial_decisions=decisions,
    )
