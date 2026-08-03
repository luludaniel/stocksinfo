from __future__ import annotations

DISCLAIMER = "⚠️ 본 내용은 투자 참고용이며 투자 결정의 책임은 본인에게 있습니다."
RULE = "━" * 30
SEVERITY_LABELS = {"red": "🔴 확인 필요", "yellow": "🟡 관찰"}
SEVERITY_ORDER = ["red", "yellow"]


def group_signals(signals: list[dict]) -> dict:
    """Group by whatever severity value is actually present — no pre-seeded
    keys — so a future severity beyond red/yellow can't be silently dropped
    by callers that only iterate ("red", "yellow").
    """
    grouped: dict = {}
    for sig in signals:
        grouped.setdefault(sig["severity"], []).append(sig)
    return grouped


def _label(symbol: str, names: dict) -> str:
    name = (names or {}).get(symbol)
    return f"{symbol} {name}" if name else symbol


def _is_failed(pos: dict) -> bool:
    return not pos or "error" in pos


def _position_summary_line(pos: dict) -> str:
    parts = []
    if pos.get("week52_pct") is not None:
        parts.append(f"52주 {pos['week52_pct']:.0f}%")
    if pos.get("pct_vs_ma200") is not None:
        parts.append(f"200일선 {pos['pct_vs_ma200']:+.0f}%")
    if pos.get("relative_strength_6m_pct") is not None:
        parts.append(f"6M {pos['relative_strength_6m_pct']:+.0f}%p")
    return " · ".join(parts) if parts else "데이터 부족"


def build_calendar_line(calendar_events: list[str]) -> str:
    if not calendar_events:
        return ""
    return "📅 이번 주  " + " · ".join(calendar_events)


def build_header(signals: list[dict], watchlist: dict, names: dict, today: str) -> str:
    """Deterministic traffic-light block: numbers come straight from the rule
    engine, not the LLM, so this section can never contain an invented figure.

    watchlist is the full {symbol: position_dict} map (not just symbol names)
    so failed collections can be called out explicitly instead of silently
    reading identical to "nothing happened today" — and so a healthy day can
    show each normal symbol's actual position, not just its ticker.
    """
    watchlist = watchlist or {}
    grouped = group_signals(signals)
    flagged = {s["symbol"] for s in signals}
    failed = [sym for sym, pos in watchlist.items() if _is_failed(pos)]
    normal = [sym for sym in watchlist if sym not in flagged and sym not in failed]

    lines = [RULE, f"📊 {today}   신호 {len(signals)}건", RULE, ""]

    if failed:
        lines.append(f"⚠️ 수집 실패 ({len(failed)})")
        lines.append("  " + " · ".join(_label(sym, names) for sym in failed))
        lines.append("")

    for severity in SEVERITY_ORDER:
        bucket = grouped.pop(severity, [])
        if not bucket:
            continue
        lines.append(f"{SEVERITY_LABELS[severity]} ({len(bucket)})")
        for s in bucket:
            lines.append(f"  {_label(s['symbol'], names)} — {s['message']}")
        lines.append("")

    # Any severity beyond red/yellow still renders instead of vanishing.
    for severity, bucket in grouped.items():
        lines.append(f"⚠️ {severity} ({len(bucket)})")
        for s in bucket:
            lines.append(f"  {_label(s['symbol'], names)} — {s['message']}")
        lines.append("")

    if normal:
        lines.append(f"⚪ 정상 범위 ({len(normal)})")
        for sym in normal:
            lines.append(f"  {_label(sym, names)} — {_position_summary_line(watchlist[sym])}")
        lines.append("")

    return "\n".join(lines).rstrip()


def build_report(signals: list[dict], watchlist: dict, names: dict, today: str,
                  calendar_events: list[str], detail_text: str = "", history_note: str = "") -> str:
    watchlist = watchlist or {}
    has_failures = any(_is_failed(pos) for pos in watchlist.values())
    parts = [build_header(signals, watchlist, names, today)]

    if not signals and not has_failures:
        parts += ["", "오늘은 관심종목에 특이사항이 없습니다."]

    cal_line = build_calendar_line(calendar_events)
    if cal_line:
        parts += ["", cal_line]

    if detail_text:
        parts += ["", "─── 상세 " + "─" * 20, detail_text]

    if history_note:
        parts += ["", history_note]

    parts += ["", DISCLAIMER]
    return "\n".join(parts)
