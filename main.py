from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import history
import report
import signals as signal_engine
from collectors import economic_cal, fundamentals, kr_market, news, us_market
from collectors import watchlist_stocks
from delivery.email_sender import send, send_error
from store import load_recipients, load_watchlist
from summarizer.openrouter_client import interpret_signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
CALENDAR_LOOKAHEAD_DAYS = 7


def collect_all(all_symbols: list) -> dict:
    collectors = {
        "us_market": us_market.fetch,
        "kr_market": kr_market.fetch,
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

        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result(timeout=30)
                log.info(f"[OK] {name}")
            except Exception as e:
                log.error(f"[FAIL] {name}: {e}")
                errors.append(f"{name}: {e}")
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


def _ticker_calendar_events(fundamentals_data: dict, today: date) -> list:
    events = []
    for symbol, fund in (fundamentals_data or {}).items():
        if not fund or "error" in fund:
            continue

        edate = _parse_date(fund.get("next_earnings_date"))
        if edate and 0 <= (edate - today).days <= CALENDAR_LOOKAHEAD_DAYS:
            events.append(f"{symbol} 실적({_weekday_kr(edate)})")

        exdiv = _parse_date(fund.get("ex_dividend_date"))
        if exdiv and 0 <= (exdiv - today).days <= CALENDAR_LOOKAHEAD_DAYS:
            events.append(f"{symbol} 배당락({_weekday_kr(exdiv)})")

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


def _attach_related_news(detected_signals: list, watchlist: dict) -> list:
    enriched = []
    for sig in detected_signals:
        pos = (watchlist or {}).get(sig["symbol"]) or {}
        enriched.append({**sig, "related_news": (pos.get("news") or [])[:3]})
    return enriched


def build_email(watchlist: dict, fundamentals_data: dict, econ_cal: dict) -> str:
    today = date.today()
    today_str = today.isoformat()

    detected_signals = signal_engine.evaluate(watchlist, fundamentals_data, today_str)
    _save_snapshots(watchlist, fundamentals_data, today_str)

    watchlist_symbols = list((watchlist or {}).keys())
    calendar_events = _ticker_calendar_events(fundamentals_data, today)
    calendar_events += [ev["name"] for ev in (econ_cal or {}).get("events", []) if ev.get("name")]

    if not detected_signals:
        return report.build_no_signal_report(watchlist_symbols, today_str, calendar_events)

    enriched_signals = _attach_related_news(detected_signals, watchlist)
    detail_text = interpret_signals(enriched_signals)
    return report.build_report(detected_signals, watchlist_symbols, today_str, calendar_events, detail_text)


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

        email_body = build_email(
            data.get("watchlist") or {},
            data.get("fundamentals") or {},
            data.get("economic_cal") or {},
        )

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
