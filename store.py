import json
from pathlib import Path

BASE = Path(__file__).parent
WATCHLIST_FILE = BASE / "watchlist.json"
RECIPIENTS_FILE = BASE / "recipients.json"

_DEFAULT_WATCHLIST = {"us": ["NVDA", "AAPL", "TSLA"], "kr": ["005930.KS", "000660.KS"]}
_DEFAULT_RECIPIENTS = {"emails": []}


def load_watchlist() -> dict:
    if not WATCHLIST_FILE.exists():
        save_watchlist(_DEFAULT_WATCHLIST)
    return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))


def save_watchlist(data: dict):
    WATCHLIST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_recipients() -> dict:
    if not RECIPIENTS_FILE.exists():
        save_recipients(_DEFAULT_RECIPIENTS)
    return json.loads(RECIPIENTS_FILE.read_text(encoding="utf-8"))


def save_recipients(data: dict):
    RECIPIENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
