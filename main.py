import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from collectors import us_market, kr_market, news, economic_cal
from collectors import watchlist_stocks
from summarizer.openrouter_client import summarize
from delivery.email_sender import send, send_error
from store import load_watchlist, load_recipients

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def collect_all() -> dict:
    wl = load_watchlist()
    all_symbols = wl.get("us", []) + wl.get("kr", [])

    collectors = {
        "us_market": us_market.fetch,
        "kr_market": kr_market.fetch,
        "news": news.fetch,
        "economic_cal": economic_cal.fetch,
    }

    results = {}
    errors = []

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fn): name for name, fn in collectors.items()}
        if all_symbols:
            futures[pool.submit(watchlist_stocks.fetch, all_symbols)] = "watchlist"

        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result(timeout=30)
                log.info(f"[OK] {name}")
            except Exception as e:
                log.error(f"[FAIL] {name}: {e}")
                errors.append(f"{name}: {e}")
                results[name] = None

    results["_errors"] = errors
    results["_collected_at"] = datetime.utcnow().isoformat()
    return results


def main():
    log.info("StocksInfo morning report starting...")
    try:
        data = collect_all()

        if data.get("_errors"):
            log.warning(f"Partial data — errors: {data['_errors']}")

        report = summarize(data)

        # 수신자 목록에서 발송 (없으면 .env의 EMAIL_RECEIVER로 fallback)
        recipients = load_recipients()
        emails = recipients.get("emails", [])
        if not emails:
            from config import EMAIL_RECEIVER
            emails = [EMAIL_RECEIVER]

        for email in emails:
            send(report, to=email)
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
