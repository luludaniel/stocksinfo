from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from datetime import date, datetime

import history
import report
import signals as signal_engine
from collectors import economic_cal, fundamentals, news
from collectors import watchlist_stocks
from delivery.email_sender import send, send_error
from store import load_recipients, load_watchlist
from summarizer.openrouter_client import interpret_signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
CALENDAR_LOOKAHEAD_DAYS = 7
COLLECT_TIMEOUT_SECONDS = 120


def collect_all(all_symbols: list) -> dict:
    # Raw index/sector data (us_market, kr_market) is deliberately not
    # collected here — REDESIGN.md's whole thesis is that daily index % moves
    # are noise for a long-term holder, and nothing downstream ever read it.
    collectors = {
        "news": news.fetch,
        "economic_cal": economic_cal.fetch,
    }

    results = {}
    errors = []

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): name for name, fn in collectors.items()}
        if all_symbols:
            futures[pool.submit(watchlist_stocks.fetch, all_symbols)] = "watchlist"
            futures[pool.submit(fundamentals.fetch, all_symbols)] = "fundamentals"

        # as_completed() only ever yields futures that already finished, so a
        # per-future timeout passed to future.result() never actually blocks
        # anything — the timeout has to be on as_completed() itself. Anything
        # still outstanding when it fires is recorded as failed below.
        try:
            for future in as_completed(futures, timeout=COLLECT_TIMEOUT_SECONDS):
                name = futures[future]
                try:
                    results[name] = future.result()
                    log.info(f"[OK] {name}")
                except Exception as e:
                    log.error(f"[FAIL] {name}: {e}")
                    errors.append(f"{name}: {e}")
                    results[name] = None
        except FutureTimeoutError:
            pass

        for future, name in futures.items():
            if name not in results:
                log.error(f"[FAIL] {name}: timed out after {COLLECT_TIMEOUT_SECONDS}s")
                errors.append(f"{name}: timed out after {COLLECT_TIMEOUT_SECONDS}s")
                results[name] = None

    for name in ("news", "economic_cal"):
        collector_result = results.get(name)
        if isinstance(collector_result, dict):
            errors.extend(collector_result.get("errors", []))

    results["_errors"] = errors
    results["_collected_at"] = datetime.utcnow().isoformat()
    return results


def _weekday_kr(d: date) -> str:
    return WEEKDAY_KR[d.weekday()]


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _ticker_calendar_events(fundamentals_data: dict, names: dict, today: date) -> list:
    events = []
    for symbol, fund in (fundamentals_data or {}).items():
        if not fund or "error" in fund:
            continue
        label = names.get(symbol, symbol)

        edate = _parse_date(fund.get("next_earnings_date"))
        if edate and 0 <= (edate - today).days <= CALENDAR_LOOKAHEAD_DAYS:
            events.append(f"{label} 실적({_weekday_kr(edate)})")

        exdiv = _parse_date(fund.get("ex_dividend_date"))
        if exdiv and 0 <= (exdiv - today).days <= CALENDAR_LOOKAHEAD_DAYS:
            events.append(f"{label} 배당락({_weekday_kr(exdiv)})")

    return events


def _save_snapshots(watchlist: dict, fundamentals_data: dict, today_str: str):
    for symbol, pos in (watchlist or {}).items():
        if not pos or "error" in pos:
            continue
        fund = (fundamentals_data or {}).get(symbol) or {}
        history.save_snapshot(today_str, symbol, {
            "last_close": pos.get("last_close"),
            "trailing_pe": fund.get("trailing_pe"),
            "target_mean_price": fund.get("target_mean_price"),
            "volume": pos.get("volume"),
        })


def _symbol_names(fundamentals_data: dict) -> dict:
    return {
        sym: fund["name"]
        for sym, fund in (fundamentals_data or {}).items()
        if fund and fund.get("name")
    }


def _match_related_articles(symbol: str, name: str, articles: list) -> list:
    """Substring-match general market news titles against a symbol's ticker
    root / display name — a cheap secondary source on top of the per-ticker
    yfinance news already used, so the RSS feeds collected in collect_all
    don't just get thrown away after being fetched.
    """
    needles = {symbol.split(".")[0].lower()}
    if name:
        needles.add(name.lower())
    matches = []
    for article in articles or []:
        title = (article.get("title") or "").lower()
        if any(needle and needle in title for needle in needles):
            matches.append(article)
    return matches


def _attach_related_news(detected_signals: list, watchlist: dict, names: dict, general_articles: list) -> list:
    enriched = []
    for sig in detected_signals:
        symbol = sig["symbol"]
        pos = (watchlist or {}).get(symbol) or {}
        related = list(pos.get("news") or [])
        seen_urls = {a.get("url") for a in related}
        for article in _match_related_articles(symbol, names.get(symbol), general_articles):
            if article.get("url") not in seen_urls:
                related.append(article)
                seen_urls.add(article.get("url"))
        enriched.append({**sig, "related_news": related[:3]})
    return enriched


def _history_note(today_str: str) -> str:
    days_collected = history.get_distinct_dates_count()
    ready_in = max(0, signal_engine.PER_BAND_MIN_SAMPLES - days_collected)
    note = f"히스토리 축적 {days_collected}일차"
    if ready_in > 0:
        note += f" · PER 밴드 활성화까지 {ready_in}일"
    return note


def build_email(watchlist: dict, fundamentals_data: dict, econ_cal: dict, news_data: dict) -> str:
    today = date.today()
    today_str = today.isoformat()
    names = _symbol_names(fundamentals_data)

    detected_signals = signal_engine.evaluate(watchlist, fundamentals_data, today_str)

    calendar_events = _ticker_calendar_events(fundamentals_data, names, today)
    calendar_events += [ev["name"] for ev in (econ_cal or {}).get("events", []) if ev.get("name")]

    detail_text = ""
    if detected_signals:
        general_articles = (news_data or {}).get("articles", [])
        enriched_signals = _attach_related_news(detected_signals, watchlist, names, general_articles)
        detail_text = interpret_signals(enriched_signals)

    return report.build_report(
        detected_signals, watchlist, names, today_str, calendar_events,
        detail_text=detail_text, history_note=_history_note(today_str),
    )


def main():
    from config import validate
    validate()
    log.info("StocksInfo morning report starting...")
    try:
        wl = load_watchlist()
        all_symbols = wl.get("us", []) + wl.get("kr", [])

        data = collect_all(all_symbols)

        if data.get("_errors"):
            log.warning(f"Partial data — errors: {data['_errors']}")

        watchlist = data.get("watchlist") or {}
        fundamentals_data = data.get("fundamentals") or {}

        email_body = build_email(
            watchlist, fundamentals_data, data.get("economic_cal") or {}, data.get("news") or {},
        )

        # Persisted regardless of email outcome — the snapshot history matters
        # even if delivery fails, and shouldn't be a hidden side effect of
        # "building an email".
        _save_snapshots(watchlist, fundamentals_data, date.today().isoformat())

        # 수신자 목록에서 발송 (없으면 .env의 EMAIL_RECEIVER로 fallback)
        recipients = load_recipients()
        emails = recipients.get("emails", [])
        if not emails:
            from config import EMAIL_RECEIVER
            emails = [EMAIL_RECEIVER]

        for email in emails:
            send(email_body, to=email)
            log.info(f"Delivered to {email}")

    except Exception:
        err = traceback.format_exc()
        log.error(f"Fatal error:\n{err}")
        try:
            send_error(err)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
