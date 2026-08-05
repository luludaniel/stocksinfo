from __future__ import annotations

import logging

from collectors import fundamentals as fundamentals_collector
from collectors import watchlist_stocks
from summarizer.openrouter_client import extract_tickers_from_headlines

log = logging.getLogger(__name__)

MAX_HEADLINES = 30
MAX_RAW_CANDIDATES = 15  # cap how many LLM-suggested tickers we bother validating
DEFAULT_MIN_ARTICLE_MENTIONS = 2
DEFAULT_MIN_MARKET_CAP_USD = 1_000_000_000
DEFAULT_MAX_CANDIDATES = 3


def _collect_headlines(watchlist: dict, general_articles: list) -> list[str]:
    """RSS headlines + every watchlist symbol's own yfinance news, deduped
    and capped — the same pool of titles the LLM extraction call sees.
    """
    titles = [a.get("title") for a in (general_articles or []) if a.get("title")]
    for pos in (watchlist or {}).values():
        if not pos or "error" in pos:
            continue
        titles.extend(n.get("title") for n in (pos.get("news") or []) if n.get("title"))

    seen = set()
    deduped = []
    for title in titles:
        if title not in seen:
            seen.add(title)
            deduped.append(title)
    return deduped[:MAX_HEADLINES]


_CORP_SUFFIX_WORDS = {"inc", "incorporated", "corp", "corporation", "co", "company",
                       "ltd", "limited", "plc", "holdings", "holding"}


def _simplify_name(name: str) -> str:
    """Headlines say "Broadcom", not "Broadcom Inc." or "Samsung Electronics
    Co., Ltd." — strip trailing corporate-entity words so matching against
    plain headline text actually has a chance of hitting.
    """
    words = (name or "").lower().replace(",", " ").split()
    while words and words[-1].strip(".") in _CORP_SUFFIX_WORDS:
        words.pop()
    return " ".join(words)


def _matching_headlines(ticker: str, name: str, headlines: list[str]) -> list[dict]:
    needle = ticker.split(".")[0].lower()
    name_needle = _simplify_name(name)
    return [
        {"title": h} for h in headlines
        if needle in h.lower() or (name_needle and name_needle in h.lower())
    ][:3]


def build_discovery(watchlist: dict, general_articles: list, discovery_config: dict | None) -> list[dict]:
    """SPEC-DASHBOARD.md §6.2 "신규 발굴": symbols outside the watchlist that
    today's news is actually talking about.

    Article frequency isn't a valuation judgment — it's explicitly a
    candidate list, not a buy signal (see report.py's DISCOVERY_WARNING /
    the dashboard's own "매수 추천 아님" notice). The one thing that IS
    non-negotiable here is that every ticker the LLM proposes gets checked
    against yfinance before it's shown to anyone: watchlist_stocks.fetch()
    silently drops any symbol it can't pull real price history for, which is
    exactly the hallucination guard this feature needs — a made-up or
    mismatched ticker just doesn't survive that call.
    """
    config = discovery_config or {}
    if not config.get("enabled", True):
        return []

    excluded = set(watchlist or {})
    headlines = _collect_headlines(watchlist, general_articles)
    if not headlines:
        return []

    raw_candidates = extract_tickers_from_headlines(headlines, excluded)
    if not raw_candidates:
        return []

    min_mentions = config.get("min_article_mentions", DEFAULT_MIN_ARTICLE_MENTIONS)
    min_market_cap = config.get("min_market_cap_usd", DEFAULT_MIN_MARKET_CAP_USD)
    max_candidates = config.get("max_candidates", DEFAULT_MAX_CANDIDATES)

    filtered = {}
    for cand in raw_candidates:
        ticker = str(cand.get("ticker", "")).strip().upper()
        mentions = cand.get("mentions", 0)
        if not ticker or ticker in excluded or ticker in filtered:
            continue
        if not isinstance(mentions, (int, float)) or mentions < min_mentions:
            continue
        filtered[ticker] = {"name": cand.get("name", ""), "mentions": mentions}
        if len(filtered) >= MAX_RAW_CANDIDATES:
            break

    if not filtered:
        return []

    tickers = list(filtered.keys())
    positions = watchlist_stocks.fetch(tickers)
    fund_data = fundamentals_collector.fetch(tickers)

    candidates = []
    for ticker, meta in filtered.items():
        pos = positions.get(ticker)
        if not pos or "error" in pos:
            continue  # no real price history -> the LLM's ticker doesn't hold up

        fund = fund_data.get(ticker) or {}
        market_cap = fund.get("market_cap")
        if market_cap is not None and market_cap < min_market_cap:
            continue

        name = fund.get("name") or meta["name"] or ticker
        candidates.append({
            "symbol": ticker,
            "name": name,
            "why": f"당일 기사 {int(meta['mentions'])}건 언급",
            "headlines": _matching_headlines(ticker, name, headlines),
            "basic": {
                "trailing_pe": fund.get("trailing_pe"),
                "week52_pct": pos.get("week52_pct"),
                "market_cap_usd": market_cap,
            },
        })

    candidates.sort(key=lambda c: c["basic"].get("market_cap_usd") or 0, reverse=True)
    return candidates[:max_candidates]
