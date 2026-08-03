from __future__ import annotations

from datetime import date, datetime

DEFAULT_FOCUS_CONFIG = {
    "severity_weight": {"red": 3.0, "yellow": 1.0},
    "news_weight": 0.5,
    "event_bonus": {"earnings_d3": 2.0, "ex_dividend_d2": 1.0},
}

MAX_NEWS_COUNTED = 3
EARNINGS_BONUS_LOOKAHEAD_DAYS = 3
EX_DIVIDEND_BONUS_LOOKAHEAD_DAYS = 2


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _event_bonus(fund: dict, today: date, event_bonus_cfg: dict) -> float:
    bonus = 0.0

    edate = _parse_date(fund.get("next_earnings_date"))
    if edate is not None and 0 <= (edate - today).days <= EARNINGS_BONUS_LOOKAHEAD_DAYS:
        bonus += event_bonus_cfg.get("earnings_d3", 0.0)

    exdiv = _parse_date(fund.get("ex_dividend_date"))
    if exdiv is not None and 0 <= (exdiv - today).days <= EX_DIVIDEND_BONUS_LOOKAHEAD_DAYS:
        bonus += event_bonus_cfg.get("ex_dividend_d2", 0.0)

    return bonus


def build_focus(signals: list, watchlist: dict, fundamentals_data: dict,
                 related_news_by_symbol: dict, today: date,
                 focus_config: dict | None = None) -> list[dict]:
    """SPEC-DASHBOARD.md §6.1 "오늘 볼 순서": which symbols deserve attention
    first. Entirely arithmetic on numbers signals.py / news matching already
    produced — the LLM never touches ranking, only interprets what's handed
    to it after. A symbol with nothing going on (no signal, no news, no
    upcoming event) scores 0 and is left out rather than padded into the list.
    """
    cfg = focus_config or DEFAULT_FOCUS_CONFIG
    severity_weight = cfg.get("severity_weight") or DEFAULT_FOCUS_CONFIG["severity_weight"]
    news_weight = cfg.get("news_weight", DEFAULT_FOCUS_CONFIG["news_weight"])
    event_bonus_cfg = cfg.get("event_bonus") or DEFAULT_FOCUS_CONFIG["event_bonus"]

    signals_by_symbol: dict = {}
    for sig in signals or []:
        signals_by_symbol.setdefault(sig["symbol"], []).append(sig)

    all_symbols = set(signals_by_symbol) | set((watchlist or {}).keys())
    focus = []
    for symbol in all_symbols:
        symbol_signals = signals_by_symbol.get(symbol, [])
        severity_score = sum(severity_weight.get(s["severity"], 0.0) for s in symbol_signals)

        related_news = (related_news_by_symbol or {}).get(symbol, [])
        news_score = min(len(related_news), MAX_NEWS_COUNTED) * news_weight

        fund = (fundamentals_data or {}).get(symbol) or {}
        event_score = 0.0 if "error" in fund else _event_bonus(fund, today, event_bonus_cfg)

        total = severity_score + news_score + event_score
        if total <= 0:
            continue

        focus.append({
            "symbol": symbol,
            "score": round(total, 2),
            "score_breakdown": {
                "severity": round(severity_score, 2),
                "news": round(news_score, 2),
                "event": round(event_score, 2),
            },
            "signals": symbol_signals,
            "news": related_news[:MAX_NEWS_COUNTED],
        })

    focus.sort(key=lambda f: f["score"], reverse=True)
    for rank, entry in enumerate(focus, start=1):
        entry["rank"] = rank

    return focus
