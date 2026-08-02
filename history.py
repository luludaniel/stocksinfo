from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE = Path(__file__).parent
DB_FILE = BASE / "stocksinfo.db"

_COLUMNS = ["date", "symbol", "last_close", "trailing_pe", "target_mean_price", "volume"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_snapshot (
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    last_close REAL,
    trailing_pe REAL,
    target_mean_price REAL,
    volume INTEGER,
    PRIMARY KEY (date, symbol)
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    return dict(zip(_COLUMNS, row))


def save_snapshot(date: str, symbol: str, metrics: dict):
    """Upsert today's daily_snapshot row for a symbol.

    This is the memory Axis B (signal detection) and the valuation-band /
    analyst-target signals in signals.py rely on — without it every run
    starts from zero and "what changed since yesterday" is unanswerable.
    """
    with _connect() as conn:
        conn.execute(
            """INSERT INTO daily_snapshot (date, symbol, last_close, trailing_pe, target_mean_price, volume)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(date, symbol) DO UPDATE SET
                 last_close=excluded.last_close,
                 trailing_pe=excluded.trailing_pe,
                 target_mean_price=excluded.target_mean_price,
                 volume=excluded.volume""",
            (
                date,
                symbol,
                metrics.get("last_close"),
                metrics.get("trailing_pe"),
                metrics.get("target_mean_price"),
                metrics.get("volume"),
            ),
        )


def get_snapshot(symbol: str, date: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM daily_snapshot WHERE symbol = ? AND date = ?",
            (symbol, date),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_snapshots_since(symbol: str, since_date: str) -> list[dict]:
    """All snapshots for a symbol on/after since_date, oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM daily_snapshot "
            "WHERE symbol = ? AND date >= ? ORDER BY date ASC",
            (symbol, since_date),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_latest_snapshot_before(symbol: str, before_date: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM daily_snapshot "
            "WHERE symbol = ? AND date < ? ORDER BY date DESC LIMIT 1",
            (symbol, before_date),
        ).fetchone()
    return _row_to_dict(row) if row else None
