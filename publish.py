from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = 1
BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
LATEST_FILE = DATA_DIR / "latest.json"

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
CALENDAR_LOOKAHEAD_DAYS = 7

_POSITION_FIELDS = [
    "last_close", "change_pct", "week52_pct", "pct_vs_ma200", "drawdown_from_high_pct",
    "return_3m_pct", "return_6m_pct", "return_12m_pct", "relative_strength_6m_pct",
]


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _weekday_kr(d: date) -> str:
    return WEEKDAY_KR[d.weekday()]


def build_failed_symbols(watchlist: dict) -> list[dict]:
    return [
        {"symbol": symbol, "reason": pos.get("error", "unknown")}
        for symbol, pos in (watchlist or {}).items()
        if not pos or "error" in pos
    ]


def build_status(collector_errors: list, failed_symbols: list) -> dict:
    return {
        "ok": not collector_errors and not failed_symbols,
        "failed_symbols": failed_symbols,
        "collector_errors": list(collector_errors or []),
    }


def build_history_status(days_collected: int, per_band_min_samples: int) -> dict:
    return {
        "days_collected": days_collected,
        "per_band_ready_in_days": max(0, per_band_min_samples - days_collected),
    }


def build_positions(watchlist: dict, fundamentals_data: dict, profiles_by_symbol: dict) -> list[dict]:
    """Every watchlist symbol, signal or not — this is what REVIEW.md's #6
    was about: axis A gets computed either way, so the dashboard should show
    it for every symbol instead of only the ones that happened to fire a rule.
    """
    positions = []
    for symbol, pos in (watchlist or {}).items():
        if not pos or "error" in pos:
            continue
        fund = (fundamentals_data or {}).get(symbol) or {}
        entry = {
            "symbol": symbol,
            "name": fund.get("name") or "",
            "profile": (profiles_by_symbol or {}).get(symbol),
            "trailing_pe": fund.get("trailing_pe"),
            "next_earnings_date": fund.get("next_earnings_date"),
        }
        for field in _POSITION_FIELDS:
            entry[field] = pos.get(field)
        positions.append(entry)
    return positions


def build_calendar(fundamentals_data: dict, names: dict, today: date) -> list[dict]:
    entries = []
    for symbol, fund in (fundamentals_data or {}).items():
        if not fund or "error" in fund:
            continue
        label = names.get(symbol, symbol)

        edate = _parse_date(fund.get("next_earnings_date"))
        if edate and 0 <= (edate - today).days <= CALENDAR_LOOKAHEAD_DAYS:
            entries.append({"date": edate.isoformat(), "weekday": _weekday_kr(edate),
                             "label": f"{label} 실적", "kind": "earnings"})

        exdiv = _parse_date(fund.get("ex_dividend_date"))
        if exdiv and 0 <= (exdiv - today).days <= CALENDAR_LOOKAHEAD_DAYS:
            entries.append({"date": exdiv.isoformat(), "weekday": _weekday_kr(exdiv),
                             "label": f"{label} 배당락", "kind": "ex_dividend"})

    entries.sort(key=lambda e: e["date"])
    return entries


def build_latest(*, market_date: str, trigger: str, collector_errors: list, watchlist: dict,
                  fundamentals_data: dict, profiles_by_symbol: dict, history_status: dict,
                  focus: list, discovery: list, calendar: list) -> dict:
    failed_symbols = build_failed_symbols(watchlist)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "market_date": market_date,
        "trigger": trigger,
        "status": build_status(collector_errors, failed_symbols),
        "history_status": history_status,
        "focus": focus,
        "positions": build_positions(watchlist, fundamentals_data, profiles_by_symbol),
        "discovery": discovery,
        "calendar": calendar,
    }


def save_latest(data: dict):
    DATA_DIR.mkdir(exist_ok=True)
    LATEST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_latest() -> dict | None:
    if not LATEST_FILE.exists():
        return None
    return json.loads(LATEST_FILE.read_text(encoding="utf-8"))
