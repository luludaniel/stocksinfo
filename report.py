from __future__ import annotations

DISCLAIMER = "⚠️ 본 내용은 투자 참고용이며 투자 결정의 책임은 본인에게 있습니다."
RULE = "━" * 30


def group_signals(signals: list[dict]) -> dict:
    grouped = {"red": [], "yellow": []}
    for sig in signals:
        grouped.setdefault(sig["severity"], []).append(sig)
    return grouped


def build_calendar_line(calendar_events: list[str]) -> str:
    if not calendar_events:
        return ""
    return "📅 이번 주  " + " · ".join(calendar_events)


def build_header(signals: list[dict], watchlist_symbols: list[str], today: str) -> str:
    """Deterministic traffic-light block: numbers come straight from the rule
    engine, not the LLM, so this section can never contain an invented figure.
    """
    grouped = group_signals(signals)
    flagged = {s["symbol"] for s in signals}
    normal = [s for s in watchlist_symbols if s not in flagged]

    lines = [RULE, f"📊 {today}   신호 {len(signals)}건", RULE, ""]

    if grouped["red"]:
        lines.append(f"🔴 확인 필요 ({len(grouped['red'])})")
        for s in grouped["red"]:
            lines.append(f"  {s['symbol']:<8}{s['message']}")
        lines.append("")

    if grouped["yellow"]:
        lines.append(f"🟡 관찰 ({len(grouped['yellow'])})")
        for s in grouped["yellow"]:
            lines.append(f"  {s['symbol']:<8}{s['message']}")
        lines.append("")

    if normal:
        lines.append(f"⚪ 정상 범위 ({len(normal)})")
        lines.append("  " + " · ".join(normal))
        lines.append("")

    return "\n".join(lines).rstrip()


def build_no_signal_report(watchlist_symbols: list[str], today: str, calendar_events: list[str]) -> str:
    """Zero signals -> one line, no LLM call. Cost 0, and a quiet day reads as
    genuinely quiet instead of a forced five-section report with nothing to say.
    """
    parts = [
        RULE,
        f"📊 {today}   신호 0건",
        RULE,
        "",
        "오늘은 관심종목에 특이사항이 없습니다.",
    ]
    if watchlist_symbols:
        parts.append("⚪ " + " · ".join(watchlist_symbols))

    cal_line = build_calendar_line(calendar_events)
    if cal_line:
        parts += ["", cal_line]

    parts += ["", DISCLAIMER]
    return "\n".join(parts)


def build_report(signals: list[dict], watchlist_symbols: list[str], today: str,
                  calendar_events: list[str], detail_text: str = "") -> str:
    parts = [build_header(signals, watchlist_symbols, today)]

    cal_line = build_calendar_line(calendar_events)
    if cal_line:
        parts += ["", cal_line]

    if detail_text:
        parts += ["", "─── 상세 " + "─" * 20, detail_text]

    parts += ["", DISCLAIMER]
    return "\n".join(parts)
