from __future__ import annotations

import copy
import json
from pathlib import Path

BASE = Path(__file__).parent
CONFIG_DIR = BASE / "config"
WATCHLIST_FILE = CONFIG_DIR / "watchlist.json"
REPORT_CONFIG_FILE = CONFIG_DIR / "report.json"

# v1 lived at repo root as {"us": [...], "kr": [...]} + a separate recipients.json.
# Read once for migration, then config/ becomes the only source of truth.
_LEGACY_WATCHLIST_FILE = BASE / "watchlist.json"
_LEGACY_RECIPIENTS_FILE = BASE / "recipients.json"

WATCHLIST_SCHEMA_VERSION = 2
REPORT_SCHEMA_VERSION = 1

DEFAULT_PROFILES = {
    "core_holding": {
        "label": "핵심보유",
        "signals": ["ma200_cross", "earnings_soon", "valuation_band", "target_price_change"],
        "thresholds": {"volume_spike_ratio": 3.0, "earnings_lookahead_days": 7},
    },
    "watching": {
        "label": "관찰중",
        "signals": ["ma200_cross", "week52_high", "week52_low", "volume_spike",
                    "earnings_soon", "valuation_band", "target_price_change"],
        "thresholds": {"volume_spike_ratio": 2.0, "earnings_lookahead_days": 7},
    },
    "accumulating": {
        "label": "장기적립",
        "signals": ["earnings_soon", "valuation_band"],
        "thresholds": {"earnings_lookahead_days": 3},
    },
}

_DEFAULT_REPORT_CONFIG = {
    "version": REPORT_SCHEMA_VERSION,
    "email": {
        "blocks": ["focus", "positions", "calendar"],
        "send_when_no_signal": "one_line",
        "send_time_kst": "07:30",
        "recipients": [],
    },
    "discovery": {
        "enabled": True,
        "max_candidates": 3,
        "min_article_mentions": 2,
        "min_market_cap_usd": 1_000_000_000,
    },
    "focus": {
        "severity_weight": {"red": 3.0, "yellow": 1.0},
        "news_weight": 0.5,
        "event_bonus": {"earnings_d3": 2.0, "ex_dividend_d2": 1.0},
    },
}

_DEFAULT_LEGACY_WATCHLIST = {"us": ["NVDA", "AAPL", "TSLA"], "kr": ["005930.KS", "000660.KS"]}


def _market_for(symbol: str) -> str:
    return "kr" if symbol.upper().endswith((".KS", ".KQ")) else "us"


def _migrate_v1_watchlist(v1: dict) -> dict:
    symbols = []
    for market in ("us", "kr"):
        for sym in v1.get(market, []):
            symbols.append({
                "symbol": sym, "name": "", "market": market,
                "profile": "watching", "memo": "",
            })
    return {"version": WATCHLIST_SCHEMA_VERSION, "profiles": copy.deepcopy(DEFAULT_PROFILES), "symbols": symbols}


def load_watchlist() -> dict:
    if WATCHLIST_FILE.exists():
        return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))

    if _LEGACY_WATCHLIST_FILE.exists():
        v1 = json.loads(_LEGACY_WATCHLIST_FILE.read_text(encoding="utf-8"))
    else:
        v1 = _DEFAULT_LEGACY_WATCHLIST

    migrated = _migrate_v1_watchlist(v1)
    save_watchlist(migrated)
    return migrated


def save_watchlist(data: dict):
    CONFIG_DIR.mkdir(exist_ok=True)
    WATCHLIST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def watchlist_symbols(watchlist: dict) -> list[str]:
    return [entry["symbol"] for entry in watchlist.get("symbols", [])]


def resolve_symbol_config(watchlist: dict, symbol_entry: dict) -> dict:
    """Shallow-merge a symbol's profile with its own overrides.

    `signals` is a full-array replace (an override either opts a symbol into
    a different signal set entirely, or it doesn't); `thresholds` merges key
    by key so overriding one threshold doesn't reset the rest of the profile.
    """
    profile_name = symbol_entry.get("profile")
    profile = (watchlist.get("profiles") or {}).get(profile_name, {})
    overrides = symbol_entry.get("overrides") or {}

    signals = overrides.get("signals", profile.get("signals", []))
    thresholds = {**profile.get("thresholds", {}), **overrides.get("thresholds", {})}

    return {"signals": signals, "thresholds": thresholds}


def resolve_all_symbols(watchlist: dict) -> dict:
    """{symbol: resolved per-symbol config} for every entry in the watchlist,
    used by signals.py to decide which rules apply and at what threshold.
    """
    resolved = {}
    for entry in watchlist.get("symbols", []):
        cfg = resolve_symbol_config(watchlist, entry)
        resolved[entry["symbol"]] = {
            **cfg,
            "market": entry.get("market") or _market_for(entry["symbol"]),
            "name": entry.get("name", ""),
            "memo": entry.get("memo", ""),
            "profile": entry.get("profile"),
        }
    return resolved


def load_report_config() -> dict:
    if REPORT_CONFIG_FILE.exists():
        return json.loads(REPORT_CONFIG_FILE.read_text(encoding="utf-8"))

    default = copy.deepcopy(_DEFAULT_REPORT_CONFIG)
    if _LEGACY_RECIPIENTS_FILE.exists():
        legacy = json.loads(_LEGACY_RECIPIENTS_FILE.read_text(encoding="utf-8"))
        default["email"]["recipients"] = legacy.get("emails", [])

    save_report_config(default)
    return default


def save_report_config(data: dict):
    CONFIG_DIR.mkdir(exist_ok=True)
    REPORT_CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
