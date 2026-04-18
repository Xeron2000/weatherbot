from datetime import datetime, timezone


def format_bucket_label(contract):
    rng = contract.get("range") or (None, None)
    unit = contract.get("unit") or ""
    low, high = rng
    if low is None or high is None:
        return "unknown"
    return f"{low}-{high}{unit}"

def format_resolution_text(text, limit=120):
    summary = " ".join((text or "").split())
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3].rstrip() + "..."

def format_quote_context(quote_context):
    if not quote_context:
        return "quote=unknown"
    parts = []
    if quote_context.get("ask") is not None:
        parts.append(f"ask={quote_context['ask']:.2f}")
    if quote_context.get("bid") is not None:
        parts.append(f"bid={quote_context['bid']:.2f}")
    if quote_context.get("book_ok") is not None:
        parts.append(f"book_ok={quote_context['book_ok']}")
    return "quote=" + " ".join(parts) if parts else "quote=unknown"

def print_candidate_assessments(markets):
    entries = []
    for m in sorted(markets, key=lambda x: (x.get("date", ""), x.get("city", ""))):
        for assessment in m.get("candidate_assessments", []) or []:
            if assessment.get("strategy_leg") != "YES_SNIPER":
                continue
            entries.append((m, assessment))

    if not entries:
        return

    print(f"\n  Candidate assessments: {len(entries)}")
    for market, assessment in entries:
        rng = assessment.get("range") or (None, None)
        bucket = (
            f"{rng[0]}-{rng[1]}"
            if rng[0] is not None and rng[1] is not None
            else "unknown"
        )
        reasons = ",".join(assessment.get("reasons", [])) or "none"
        fair_price = assessment.get("fair_price")
        fair_text = (
            f"fair={fair_price:.3f}" if fair_price is not None else "fair=unknown"
        )
        quote_text = format_quote_context(assessment.get("quote_context", {}))
        print(
            f"    {market['city_name']:<16} {market['date']} | {assessment.get('strategy_leg')} | {bucket} | "
            f"status={assessment.get('status')} | reasons={reasons} | {fair_text} | {quote_text}"
        )

def print_scan_summary(markets):
    accepted = [m for m in markets if m.get("last_scan_status") == "ready"]
    skipped = [m for m in markets if m.get("last_scan_status") == "skipped"]

    if not accepted and not skipped:
        return

    print(f"\n  Accepted scan markets: {len(accepted)}")
    if accepted:
        for m in sorted(accepted, key=lambda x: (x["date"], x["city"])):
            metadata = m.get("resolution_metadata", {})
            station = metadata.get("station") or m.get("station") or "?"
            unit = metadata.get("unit") or m.get("unit") or ""
            resolution_text = format_resolution_text(metadata.get("resolution_text"))
            contract = (m.get("market_contracts") or [{}])[0]
            bucket = format_bucket_label(contract)
            market_id = contract.get("market_id") or "unknown"
            condition_id = contract.get("condition_id") or "unknown"
            token_id_yes = contract.get("token_id_yes") or "unknown"
            token_id_no = contract.get("token_id_no") or "unknown"
            print(
                f"    {m['city_name']:<16} {m['date']} | {station} | {bucket:<12} | {market_id} | {unit} | resolution_text={resolution_text} | condition_id={condition_id} | token_id_yes={token_id_yes} | token_id_no={token_id_no}"
            )

    print(f"\n  Skipped scan markets: {len(skipped)}")
    if skipped:
        for m in sorted(skipped, key=lambda x: (x["date"], x["city"])):
            reasons = ", ".join(m.get("scan_guardrails", {}).get("skip_reasons", []))
            if not reasons:
                reasons = m.get("last_scan_reason") or "unknown"
            print(f"    {m['city_name']:<16} {m['date']} | {reasons}")

    print_candidate_assessments(markets)

def print_risk_summary(state):
    risk_state = state.get("risk_state") or {}
    if not risk_state:
        return

    bankroll = float(risk_state.get("bankroll", 0.0) or 0.0)
    global_reserved = float(risk_state.get("global_reserved_worst_loss", 0.0) or 0.0)
    usage_pct = (global_reserved / bankroll * 100.0) if bankroll else 0.0

    print(f"\n  Risk usage")
    for leg in ["YES_SNIPER"]:
        leg_state = (risk_state.get("legs", {}) or {}).get(leg, {}) or {}
        budget = float(leg_state.get("budget", 0.0) or 0.0)
        reserved = float(leg_state.get("reserved", 0.0) or 0.0)
        available = max(0.0, budget - reserved)
        print(
            f"    {leg:<10} budget={budget:.2f} reserved={reserved:.2f} available={available:.2f}"
        )
    print(
        f"    global_reserved_worst_loss={global_reserved:.2f} usage={usage_pct:.1f}%"
    )

def print_exposure_summary(state):
    risk_state = state.get("risk_state") or {}
    if not risk_state:
        return

    sections = [
        ("City exposure", risk_state.get("city_exposure", {}) or {}),
        ("Date exposure", risk_state.get("date_exposure", {}) or {}),
        ("Event exposure", risk_state.get("event_exposure", {}) or {}),
    ]
    for title, ledger in sections:
        print(f"\n  {title}")
        if not ledger:
            print("    none")
            continue
        for key, value in sorted(ledger.items()):
            print(f"    {key}: {float(value):.2f}")

def print_route_decision_summary(markets):
    accepted = 0
    rejected = 0
    released = 0
    reason_counts = {}

    for market in markets:
        for decision in market.get("route_decisions", []) or []:
            if decision.get("strategy_leg") != "YES_SNIPER":
                continue
            status = decision.get("status")
            if status == "accepted":
                accepted += 1
            elif status == "rejected":
                rejected += 1
            for reason in decision.get("reasons", []) or []:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        reservation = market.get("reserved_exposure")
        if (
            reservation
            and reservation.get("strategy_leg") == "YES_SNIPER"
            and reservation.get("release_reason")
        ):
            released += 1
            reason = reservation.get("release_reason")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    print(
        f"\n  Route decisions: accepted={accepted} rejected={rejected} released={released}"
    )
    if not reason_counts:
        print("    reasons=none")
        return
    summary = ", ".join(
        f"{reason}={count}" for reason, count in sorted(reason_counts.items())
    )
    print(f"    reasons={summary}")

def format_order_reason_counts(reason_counts):
    if not reason_counts:
        return "none"
    return ", ".join(
        f"{reason}={count}" for reason, count in sorted(reason_counts.items())
    )

def collect_active_order_facts(markets):
    active_orders = []
    for market in sorted(markets, key=lambda x: (x.get("date", ""), x.get("city", ""))):
        ensure_market_order_defaults(market)
        active_order = market.get("active_order")
        if (
            active_order
            and active_order.get("strategy_leg") == "YES_SNIPER"
            and active_order.get("token_side") == "yes"
            and is_order_unfinished(active_order)
        ):
            active_orders.append((market, active_order))
    return active_orders

def collect_recent_terminal_orders(markets, limit=10):
    terminal_orders = []
    for market in markets or []:
        ensure_market_order_defaults(market)
        for order in market.get("order_history", []) or []:
            if order.get("strategy_leg") != "YES_SNIPER" or order.get("token_side") != "yes":
                continue
            if not is_order_terminal(order):
                continue
            terminal_orders.append((market, order))

    terminal_orders.sort(
        key=lambda item: (
            item[1].get("updated_at") or item[1].get("created_at") or "",
            item[1].get("order_id") or "",
        ),
        reverse=True,
    )
    return terminal_orders[:limit]

def summarize_terminal_order_reasons(markets, limit=10):
    terminal_orders = []
    for _, order in collect_recent_terminal_orders(markets, limit=limit):
        terminal_orders.append(
            {
                "status": order.get("status"),
                "reason": order.get("status_reason") or "unknown",
                "updated_at": order.get("updated_at") or order.get("created_at") or "",
            }
        )

    summary = {"filled": {}, "canceled": {}, "expired": {}}
    for order in terminal_orders:
        status = order.get("status")
        if status not in summary:
            continue
        reason = order.get("reason") or "unknown"
        summary[status][reason] = summary[status].get(reason, 0) + 1
    return summary

def replay_order_sort_key(entry):
    order = entry.get("order") or {}
    return (
        order.get("updated_at") or order.get("created_at") or "",
        order.get("order_id") or "",
    )

def collect_replay_orders(markets, market_filter=None, order_filter=None, limit=5):
    replay_orders = []
    for market in markets or []:
        ensure_market_order_defaults(market)
        orders = []
        active_order = market.get("active_order")
        if active_order and active_order.get("order_id"):
            orders.append(active_order)
        orders.extend(market.get("order_history", []) or [])

        for order in orders:
            if market_filter and order.get("market_id") != market_filter:
                continue
            if order_filter and order.get("order_id") != order_filter:
                continue
            replay_orders.append({"market": market, "order": order})

    replay_orders.sort(key=replay_order_sort_key, reverse=True)
    if limit is not None:
        replay_orders = replay_orders[: max(0, int(limit))]
    return replay_orders

def events_for_order(market, order_id):
    matched = []
    for event in market.get("execution_events", []) or []:
        if event.get("order_id") == order_id:
            matched.append(event)
    matched.sort(key=lambda item: (item.get("ts") or "", item.get("event_type") or ""))
    return matched

def parse_iso_or_none(ts):
    if not ts:
        return None
    try:
        return parse_simulation_ts(ts)
    except Exception:
        return None

def delta_ms(start_ts, end_ts):
    start_dt = parse_iso_or_none(start_ts)
    end_dt = parse_iso_or_none(end_ts)
    if not start_dt or not end_dt:
        return None
    return max(0, int((end_dt - start_dt).total_seconds() * 1000))

def first_event_by_type(events, event_types):
    wanted = set(event_types)
    for event in events or []:
        if event.get("event_type") in wanted:
            return event
    return None

def count_adverse_buffer_hits(events, order):
    limit_price = safe_float((order or {}).get("limit_price"))
    if limit_price is None:
        return 0
    hits = 0
    for event in events or []:
        if event.get("event_type") not in {"partial_fill", "filled"}:
            continue
        fill_price = safe_float(event.get("simulated_fill_price"))
        if fill_price is None:
            continue
        if fill_price < limit_price:
            hits += 1
    return hits

def build_replay_fill_quality(order, events, paper_state=None):
    paper_state = paper_state or {}
    touch_not_fill_count = sum(
        1 for event in events or [] if event.get("event_type") == "touch_not_fill"
    )
    partial_fill_slices = sum(
        1 for event in events or [] if event.get("event_type") == "partial_fill"
    )
    submission_released = first_event_by_type(events, {"submission_released"})
    first_fill = first_event_by_type(events, {"partial_fill", "filled"})
    cancel_requested = first_event_by_type(events, {"cancel_requested"})
    cancel_confirmed = first_event_by_type(events, {"cancel_confirmed"})

    queue_wait_ms = None
    if submission_released:
        queue_end = first_fill or cancel_requested or cancel_confirmed
        queue_wait_ms = delta_ms(submission_released.get("ts"), (queue_end or {}).get("ts"))

    cancel_delay_ms = None
    if cancel_requested and cancel_confirmed:
        cancel_delay_ms = delta_ms(cancel_requested.get("ts"), cancel_confirmed.get("ts"))

    total_shares = round(float((order or {}).get("shares", 0.0) or 0.0), 4)
    filled_shares = round(float((order or {}).get("filled_shares", 0.0) or 0.0), 4)
    if filled_shares <= 0 and paper_state.get("order_id") == (order or {}).get("order_id"):
        filled_shares = round(float(paper_state.get("filled_shares", 0.0) or 0.0), 4)
    remaining_shares = round(max(0.0, total_shares - filled_shares), 4)
    adverse_buffer_hits = count_adverse_buffer_hits(events, order)

    tune_hints = []
    if touch_not_fill_count > 0 or (queue_wait_ms or 0) > 0:
        tune_hints.append("queue_ahead_shares / touch_not_fill_min_touches")
    if partial_fill_slices > 0 or (filled_shares > 0 and remaining_shares > 0):
        tune_hints.append("partial_fill_slice_ratio")
    if (cancel_delay_ms or 0) > 0:
        tune_hints.append("cancel_latency_ms")
    if adverse_buffer_hits > 0:
        tune_hints.append("adverse_fill_buffer_ticks")

    return {
        "touch_not_fill_count": touch_not_fill_count,
        "queue_wait_ms": queue_wait_ms,
        "partial_fill_slices": partial_fill_slices,
        "cancel_delay_ms": cancel_delay_ms,
        "filled_shares": filled_shares,
        "total_shares": total_shares,
        "unfilled_shares": remaining_shares,
        "adverse_buffer_hits": adverse_buffer_hits,
        "tune_hints": tune_hints,
    }

def format_replay_quality(summary):
    queue_wait_ms = summary.get("queue_wait_ms")
    cancel_delay_ms = summary.get("cancel_delay_ms")
    hints = summary.get("tune_hints") or []
    return (
        f"touch_not_fill={summary.get('touch_not_fill_count', 0)} | "
        f"queue_wait_ms={queue_wait_ms if queue_wait_ms is not None else 'n/a'} | "
        f"partial_fill_slices={summary.get('partial_fill_slices', 0)} | "
        f"cancel_delay_ms={cancel_delay_ms if cancel_delay_ms is not None else 'n/a'} | "
        f"filled_shares={summary.get('filled_shares', 0.0):.4f}/{summary.get('total_shares', 0.0):.4f} | "
        f"unfilled_shares={summary.get('unfilled_shares', 0.0):.4f} | "
        f"adverse_buffer_hits={summary.get('adverse_buffer_hits', 0)} | "
        f"tune_hints={', '.join(hints) if hints else 'none'}"
    )

def format_replay_event_line(event):
    fill_shares = round(float(event.get("simulated_fill_shares", 0.0) or 0.0), 4)
    queue_ahead = round(float(event.get("queue_ahead_shares", 0.0) or 0.0), 4)
    latency_ms = int(event.get("latency_ms", 0) or 0)
    fill_price = safe_float(event.get("simulated_fill_price"))
    fill_price_text = f"{fill_price:.4f}" if fill_price is not None else "n/a"
    cancel_reason = event.get("cancel_reason")
    cancel_text = f" | cancel_reason={cancel_reason}" if cancel_reason else ""
    return (
        f"      {event.get('ts') or 'unknown'} | {event.get('event_type') or 'unknown'} | "
        f"{event.get('status_before') or 'unknown'}->{event.get('status_after') or 'unknown'} | "
        f"reason={event.get('reason') or 'unknown'} | fill_shares={fill_shares:.4f} | "
        f"fill_price={fill_price_text} | queue_ahead={queue_ahead:.4f} | latency_ms={latency_ms}{cancel_text}"
    )

def print_replay(limit=5, market_filter=None, order_filter=None):
    markets = load_all_markets()
    replay_orders = collect_replay_orders(
        markets,
        market_filter=market_filter,
        order_filter=order_filter,
        limit=limit,
    )

    print("\n  Replay orders")
    print(
        "    "
        f"limit={limit} market_filter={market_filter or 'all'} order_filter={order_filter or 'all'}"
    )

    if not replay_orders:
        filters = []
        if market_filter:
            filters.append(f"market_id={market_filter}")
        if order_filter:
            filters.append(f"order_id={order_filter}")
        print(
            "    No replay orders matched"
            + (f" ({', '.join(filters)})" if filters else ".")
        )
        return

    for entry in replay_orders:
        market = entry.get("market") or {}
        order = entry.get("order") or {}
        order_id = order.get("order_id")
        paper_state = market.get("paper_execution_state") or {}
        if paper_state.get("order_id") != order_id:
            paper_state = {}
        events = events_for_order(market, order_id)
        quality = build_replay_fill_quality(order, events, paper_state)
        bucket = format_bucket_label(
            {"range": order.get("range"), "unit": market.get("unit") or ""}
        )
        print(
            "    "
            f"{market.get('city_name', market.get('city')):<16} {market.get('date')} | "
            f"order_id={order_id or 'unknown'} | market_id={order.get('market_id') or 'unknown'} | "
            f"status={order.get('status') or paper_state.get('status') or 'unknown'} | "
            f"reason={order.get('status_reason') or paper_state.get('cancel_reason') or paper_state.get('last_reason') or 'unknown'} | "
            f"bucket={bucket} | updated_at={order.get('updated_at') or order.get('created_at') or paper_state.get('last_event_ts') or 'unknown'}"
        )
        print(f"      fill_quality | {format_replay_quality(quality)}")
        print("      timeline")
        if not events:
            print("        none")
            continue
        for event in events:
            print(format_replay_event_line(event))

def print_order_summary(state, markets):
    active_orders = collect_active_order_facts(markets)
    terminal_orders = collect_recent_terminal_orders(markets)
    terminal_reason_summary = summarize_terminal_order_reasons(markets)
    status_counts = {
        "planned": 0,
        "working": 0,
        "partial": 0,
        "filled": 0,
        "canceled": 0,
        "expired": 0,
    }
    for _, order in active_orders:
        status = order.get("status")
        if status in status_counts:
            status_counts[status] += 1
    for _, order in terminal_orders:
        status = order.get("status")
        if status in status_counts:
            status_counts[status] += 1

    print(f"\n  Order lifecycle")
    print(
        "    "
        f"active_orders={len(active_orders)} "
        f"planned={int(status_counts.get('planned', 0) or 0)} "
        f"working={int(status_counts.get('working', 0) or 0)} "
        f"partial={int(status_counts.get('partial', 0) or 0)} "
        f"filled={int(status_counts.get('filled', 0) or 0)} "
        f"canceled={int(status_counts.get('canceled', 0) or 0)} "
        f"expired={int(status_counts.get('expired', 0) or 0)}"
    )

    if not active_orders:
        print("    active_order_details=none")
    else:
        for market, order in active_orders:
            bucket = format_bucket_label(
                {"range": order.get("range"), "unit": market.get("unit") or ""}
            )
            limit_price = safe_float(order.get("limit_price"))
            filled_shares = round(float(order.get("filled_shares", 0.0) or 0.0), 4)
            remaining_shares = round(
                float(order.get("remaining_shares", 0.0) or 0.0), 4
            )
            limit_text = f"{limit_price:.4f}" if limit_price is not None else "unknown"
            print(
                f"    {market.get('city_name', market.get('city')):<16} {market.get('date')} | "
                f"{order.get('strategy_leg')} {order.get('token_side')} | {bucket:<12} | "
                f"status={order.get('status') or 'unknown'} | "
                f"limit={limit_text} | time_in_force={order.get('time_in_force') or 'unknown'} | "
                f"expires_at={order.get('expires_at') or 'none'} | "
                f"filled={filled_shares:.4f} remaining={remaining_shares:.4f} | "
                f"status_reason={order.get('status_reason') or 'unknown'}"
            )

    print("    Recent terminal orders")
    if not terminal_orders:
        print("      none")
    else:
        for market, order in terminal_orders:
            limit_price = safe_float(order.get("limit_price"))
            filled_shares = round(float(order.get("filled_shares", 0.0) or 0.0), 4)
            remaining_shares = round(
                float(order.get("remaining_shares", 0.0) or 0.0), 4
            )
            limit_text = f"{limit_price:.4f}" if limit_price is not None else "unknown"
            updated_at = order.get("updated_at") or order.get("created_at") or "unknown"
            print(
                f"      {market.get('city_name', market.get('city')):<16} {market.get('date')} | "
                f"order_id={order.get('order_id') or 'unknown'} | "
                f"status={order.get('status') or 'unknown'} | "
                f"reason={order.get('status_reason') or 'unknown'} | "
                f"updated_at={updated_at} | "
                f"limit={limit_text} | "
                f"filled={filled_shares:.4f} remaining={remaining_shares:.4f}"
            )

    print("    Recent terminal reasons")
    print(
        "      "
        f"fill_reasons={format_order_reason_counts(terminal_reason_summary['filled'])}"
    )
    print(
        "      "
        f"cancel_reasons={format_order_reason_counts(terminal_reason_summary['canceled'])}"
    )
    print(
        "      "
        f"expire_reasons={format_order_reason_counts(terminal_reason_summary['expired'])}"
    )

def print_status():
    state = load_state()
    markets = load_all_markets()
    open_pos = [
        m
        for m in markets
        if m.get("position") and m["position"].get("status") == "open"
    ]
    resolved = [
        m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None
    ]

    bal = state["balance"]
    start = state["starting_balance"]
    ret_pct = (bal - start) / start * 100
    wins = state["wins"]
    losses = state["losses"]
    total = wins + losses

    print(f"\n{'=' * 55}")
    print(f"  WEATHERBET — STATUS")
    print(f"{'=' * 55}")
    print(
        f"  Balance:     ${bal:,.2f}  (start ${start:,.2f}, {'+' if ret_pct >= 0 else ''}{ret_pct:.1f}%)"
    )
    print(
        f"  Trades:      {total} | W: {wins} | L: {losses} | WR: {wins / total:.0%}"
        if total
        else "  No trades yet"
    )
    print(f"  Open:        {len(open_pos)}")
    print(f"  Resolved:    {len(resolved)}")

    print_risk_summary(state)
    print_scan_summary(markets)
    print_route_decision_summary(markets)
    print_order_summary(state, markets)

    if open_pos:
        print(f"\n  Open positions:")
        total_unrealized = 0.0
        for m in open_pos:
            pos = m["position"]
            unit_sym = "F" if m["unit"] == "F" else "C"
            label = f"{pos['bucket_low']}-{pos['bucket_high']}{unit_sym}"

            # Current price from latest market snapshot
            current_price = pos["entry_price"]
            snaps = m.get("market_snapshots", [])
            if snaps:
                # Find our bucket price in all_outcomes
                for o in m.get("all_outcomes", []):
                    if o["market_id"] == pos["market_id"]:
                        current_price = o["price"]
                        break

            unrealized = round((current_price - pos["entry_price"]) * pos["shares"], 2)
            total_unrealized += unrealized
            pnl_str = f"{'+' if unrealized >= 0 else ''}{unrealized:.2f}"

            print(
                f"    {m['city_name']:<16} {m['date']} | {label:<14} | "
                f"entry ${pos['entry_price']:.3f} -> ${current_price:.3f} | "
                f"PnL: {pnl_str} | {pos['forecast_src'].upper()}"
            )

        sign = "+" if total_unrealized >= 0 else ""
        print(f"\n  Unrealized PnL: {sign}{total_unrealized:.2f}")

    print(f"{'=' * 55}\n")

def print_report():
    state = load_state()
    markets = load_all_markets()
    resolved = [
        m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None
    ]

    print(f"\n{'=' * 55}")
    print(f"  WEATHERBET — FULL REPORT")
    print(f"{'=' * 55}")

    print_risk_summary(state)
    print_exposure_summary(state)
    print_scan_summary(markets)
    print_route_decision_summary(markets)
    print_order_summary(state, markets)

    if not resolved:
        print("  No resolved markets yet.")
        return

    total_pnl = sum(m["pnl"] for m in resolved)
    wins = [m for m in resolved if m["resolved_outcome"] == "win"]
    losses = [m for m in resolved if m["resolved_outcome"] == "loss"]

    print(f"\n  Total resolved: {len(resolved)}")
    print(f"  Wins:           {len(wins)} | Losses: {len(losses)}")
    print(f"  Win rate:       {len(wins) / len(resolved):.0%}")
    print(f"  Total PnL:      {'+' if total_pnl >= 0 else ''}{total_pnl:.2f}")

    print(f"\n  By city:")
    for city in sorted(set(m["city"] for m in resolved)):
        group = [m for m in resolved if m["city"] == city]
        w = len([m for m in group if m["resolved_outcome"] == "win"])
        pnl = sum(m["pnl"] for m in group)
        name = LOCATIONS[city]["name"]
        print(
            f"    {name:<16} {w}/{len(group)} ({w / len(group):.0%})  PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
        )

    print(f"\n  Market details:")
    for m in sorted(resolved, key=lambda x: x["date"]):
        pos = m.get("position", {})
        unit_sym = "F" if m["unit"] == "F" else "C"
        snaps = m.get("forecast_snapshots", [])
        first_fc = snaps[0]["best"] if snaps else None
        last_fc = snaps[-1]["best"] if snaps else None
        label = (
            f"{pos.get('bucket_low')}-{pos.get('bucket_high')}{unit_sym}"
            if pos
            else "no position"
        )
        result = m["resolved_outcome"].upper()
        pnl_str = (
            f"{'+' if m['pnl'] >= 0 else ''}{m['pnl']:.2f}"
            if m["pnl"] is not None
            else "-"
        )
        fc_str = (
            f"forecast {first_fc}->{last_fc}{unit_sym}" if first_fc else "no forecast"
        )
        actual = f"actual {m['actual_temp']}{unit_sym}" if m["actual_temp"] else ""
        print(
            f"    {m['city_name']:<16} {m['date']} | {label:<14} | {fc_str} | {actual} | {result} {pnl_str}"
        )

    print(f"{'=' * 55}\n")
