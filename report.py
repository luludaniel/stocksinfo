from __future__ import annotations

DISCLAIMER = "⚠️ 본 내용은 투자 참고용이며 투자 결정의 책임은 본인에게 있습니다."
DISCOVERY_WARNING = "ⓘ 기사 빈도는 중장기 가치와 상관이 낮습니다. 매수 추천이 아니라 후보 제시입니다."
RULE = "━" * 30
SEVERITY_LABELS = {"red": "🔴 확인 필요", "yellow": "🟡 관찰"}
SEVERITY_ORDER = ["red", "yellow"]
# "focus" and "positions" always effectively render (they're the report's
# core content); calendar/discovery are the ones actually worth omitting.
# All four are still real toggles — this default is just the pre-Phase-9
# behavior so existing callers that don't pass `blocks` see no change.
DEFAULT_BLOCKS = frozenset({"focus", "positions", "calendar", "discovery"})


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


def _append_focus_ranked(lines: list, focus: list, names: dict) -> set:
    lines.append(f"🎯 오늘 볼 순서 ({len(focus)})")
    for f in focus:
        top = (f.get("signals") or [{}])[0].get("message", "")
        detail = f" — {top}" if top else ""
        lines.append(f"  {f['rank']}. {_label(f['symbol'], names)} (점수 {f['score']}){detail}")
    lines.append("")
    return {f["symbol"] for f in focus}


def _append_severity_groups(lines: list, grouped: dict, names: dict) -> set:
    covered = set()
    for severity in SEVERITY_ORDER:
        bucket = grouped.pop(severity, [])
        if not bucket:
            continue
        lines.append(f"{SEVERITY_LABELS[severity]} ({len(bucket)})")
        for s in bucket:
            lines.append(f"  {_label(s['symbol'], names)} — {s['message']}")
            covered.add(s["symbol"])
        lines.append("")

    # Any severity beyond red/yellow still renders instead of vanishing.
    for severity, bucket in grouped.items():
        lines.append(f"⚠️ {severity} ({len(bucket)})")
        for s in bucket:
            lines.append(f"  {_label(s['symbol'], names)} — {s['message']}")
            covered.add(s["symbol"])
        lines.append("")
    return covered


def build_header(signals: list[dict], watchlist: dict, names: dict, today: str,
                  blocks: frozenset = DEFAULT_BLOCKS, focus: list | None = None) -> str:
    """Deterministic traffic-light block: numbers come straight from the rule
    engine, not the LLM, so this section can never contain an invented figure.

    watchlist is the full {symbol: position_dict} map (not just symbol names)
    so failed collections can be called out explicitly instead of silently
    reading identical to "nothing happened today" — and so a healthy day can
    show each normal symbol's actual position, not just its ticker.

    Failure visibility isn't a configurable block — REVIEW.md #2 was about a
    total collection failure being indistinguishable from a quiet day, so
    that stays on regardless of `blocks`.
    """
    watchlist = watchlist or {}
    failed = [sym for sym, pos in watchlist.items() if _is_failed(pos)]

    lines = [RULE, f"📊 {today}   신호 {len(signals)}건", RULE, ""]

    if failed:
        lines.append(f"⚠️ 수집 실패 ({len(failed)})")
        lines.append("  " + " · ".join(_label(sym, names) for sym in failed))
        lines.append("")

    if "focus" in blocks and focus:
        covered = _append_focus_ranked(lines, focus, names)
    else:
        covered = _append_severity_groups(lines, group_signals(signals), names)

    if "positions" in blocks:
        normal = [sym for sym in watchlist if sym not in covered and sym not in failed]
        if normal:
            lines.append(f"⚪ 정상 범위 ({len(normal)})")
            for sym in normal:
                lines.append(f"  {_label(sym, names)} — {_position_summary_line(watchlist[sym])}")
            lines.append("")

    return "\n".join(lines).rstrip()


def build_report(signals: list[dict], watchlist: dict, names: dict, today: str,
                  calendar_events: list[str], detail_text: str = "", history_note: str = "",
                  blocks: frozenset | None = None, focus: list | None = None,
                  discovery: list | None = None) -> str:
    blocks = DEFAULT_BLOCKS if blocks is None else frozenset(blocks)
    watchlist = watchlist or {}
    has_failures = any(_is_failed(pos) for pos in watchlist.values())
    parts = [build_header(signals, watchlist, names, today, blocks=blocks, focus=focus)]

    if not signals and not has_failures:
        parts += ["", "오늘은 관심종목에 특이사항이 없습니다."]

    if "calendar" in blocks:
        cal_line = build_calendar_line(calendar_events)
        if cal_line:
            parts += ["", cal_line]

    if "discovery" in blocks and discovery:
        lines = [f"🔎 오늘 기사에서 뜬 종목 ({len(discovery)})"]
        for d in discovery:
            lines.append(f"  {_label(d['symbol'], names)} — {d.get('why', '')}")
        lines.append(DISCOVERY_WARNING)
        parts += [""] + lines

    if detail_text:
        parts += ["", "─── 상세 " + "─" * 20, detail_text]

    if history_note:
        parts += ["", history_note]

    parts += ["", DISCLAIMER]
    return "\n".join(parts)
