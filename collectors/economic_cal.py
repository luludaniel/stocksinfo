"""
Key US economic events fetched from FRED API. FRED requires an api_key on every
endpoint (including this one) — without FRED_API_KEY set, this call always 400s
and only the curated recurring-events fallback below actually runs. Register a
free key at https://fred.stlouisfed.org/docs/api/api_key.html to enable it.
"""
import logging
from datetime import date, datetime

import requests

from config import FRED_API_KEY

log = logging.getLogger(__name__)


# High-impact recurring US economic releases by typical weekday pattern
RECURRING_EVENTS = [
    {"day": 0, "name": "ISM 제조업 PMI (월 초 월요일)"},  # Mon
    {"day": 1, "name": "JOLTS 구인건수"},                  # Tue
    {"day": 2, "name": "ADP 민간고용"},                    # Wed
    {"day": 2, "name": "FOMC 회의록 / 연준 발언"},
    {"day": 3, "name": "주간 실업수당 청구건수"},           # Thu
    {"day": 4, "name": "비농업 고용(NFP) / 실업률"},       # Fri
]

FRED_RELEASES_URL = "https://api.stlouisfed.org/fred/releases/dates"


def fetch() -> dict:
    today = date.today()
    weekday = today.weekday()  # 0=Mon, 6=Sun

    scheduled = []
    errors = []

    # Today's recurring high-impact events
    for ev in RECURRING_EVENTS:
        if ev["day"] == weekday:
            scheduled.append({"name": ev["name"], "source": "recurring"})

    if not FRED_API_KEY:
        log.info("[economic_cal] FRED_API_KEY not set — using recurring-events fallback only")
    else:
        try:
            resp = requests.get(
                FRED_RELEASES_URL,
                params={
                    "realtime_start": str(today),
                    "realtime_end": str(today),
                    "file_type": "json",
                    "api_key": FRED_API_KEY,
                },
                timeout=5,
            )
            resp.raise_for_status()
            releases = resp.json().get("release_dates", [])
            for r in releases[:10]:
                scheduled.append({"name": r.get("release_name", ""), "source": "FRED"})
        except Exception as e:
            log.warning(f"[economic_cal] FRED fetch failed: {e}")
            errors.append(f"FRED: {e}")

    return {
        "date": str(today),
        "events": scheduled,
        "errors": errors,
        "fetched_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), indent=2, ensure_ascii=False))
