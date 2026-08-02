from __future__ import annotations

import logging
from datetime import datetime

import yfinance as yf

log = logging.getLogger(__name__)


def _next_earnings_date(ticker) -> str | None:
    try:
        cal = ticker.calendar
    except Exception:
        return None
    if not cal:
        return None
    try:
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date") or []
        else:
            dates = cal.loc["Earnings Date"].dropna().tolist() if "Earnings Date" in cal.index else []
        return str(dates[0]) if dates else None
    except Exception:
        return None


def _ex_dividend_date(info: dict) -> str | None:
    ts = info.get("exDividendDate")
    if not ts:
        return None
    try:
        return datetime.utcfromtimestamp(ts).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def fetch(symbols: list) -> dict:
    """Axis C ('fundamentals'): valuation, analyst targets, earnings/dividend dates.

    yfinance already carries all of this for free — the old pipeline never
    read it. This is where "PER 28배, 5년 평균 대비 27% 프리미엄" style
    signals (things that don't show up in any news feed) come from.
    """
    if not symbols:
        return {}

    result = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info or {}

            result[sym] = {
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "price_to_book": info.get("priceToBook"),
                "dividend_yield": info.get("dividendYield"),
                "ex_dividend_date": _ex_dividend_date(info),
                "debt_to_equity": info.get("debtToEquity"),
                "free_cashflow": info.get("freeCashflow"),
                "target_mean_price": info.get("targetMeanPrice"),
                "target_high_price": info.get("targetHighPrice"),
                "target_low_price": info.get("targetLowPrice"),
                "recommendation": info.get("recommendationKey"),
                "num_analyst_opinions": info.get("numberOfAnalystOpinions"),
                "next_earnings_date": _next_earnings_date(ticker),
            }
        except Exception as e:
            result[sym] = {"error": str(e)}

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(["NVDA", "AAPL", "005930.KS"]), indent=2, ensure_ascii=False))
