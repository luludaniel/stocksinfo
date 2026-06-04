import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from collectors import us_market, kr_market, news, economic_cal
from summarizer.openrouter_client import summarize
from delivery.email_sender import send, send_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def collect_all() -> dict:
    collectors = {
        "us_market": us_market.fetch,
        "kr_market": kr_market.fetch,
        "news": news.fetch,
        "economic_cal": economic_cal.fetch,
    }

    results = {}
    errors = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in collectors.items()}
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
        send(report)
        log.info("Report delivered successfully.")

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
