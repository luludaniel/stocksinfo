"""
Key US economic events fetched from FRED API (free, no key required for basic endpoints).
Falls back to a curated static list of recurring weekly/monthly events.
"""
import requests
from datetime import datetime, date


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

    # Today's recurring high-impact events
    for ev in RECURRING_EVENTS:
        if ev["day"] == weekday:
            scheduled.append({"name": ev["name"], "source": "recurring"})

    # Try FRED for today's actual releases (no API key needed for public endpoint)
    try:
        resp = requests.get(
            FRED_RELEASES_URL,
            params={"realtime_start": str(today), "realtime_end": str(today), "file_type": "json"},
            timeout=5,
        )
        if resp.ok:
            releases = resp.json().get("release_dates", [])
            for r in releases[:10]:
                scheduled.append({"name": r.get("release_name", ""), "source": "FRED"})
    except Exception:
        pass

    return {
        "date": str(today),
        "events": scheduled,
        "fetched_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), indent=2, ensure_ascii=False))
