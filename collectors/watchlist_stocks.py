import logging

import yfinance as yf

log = logging.getLogger(__name__)

# Trailing trading-day offsets used for the 3/6/12-month return window.
TRADING_DAYS = {"3m": 63, "6m": 126, "12m": 252}

# yfinance's period="1y" returns ~251 rows — one short of the 252 trading days
# needed for a full 12-month lookback, so return_12m_pct would always be None.
# Fetch 2 years and derive the 52-week window from the trailing slice instead.
FETCH_PERIOD = "2y"
WEEK52_TRADING_DAYS = 252

# Benchmark used for relative-strength comparison, keyed by market suffix.
BENCHMARKS = {"us": "^GSPC", "kr": "^KS11"}


def _pct(prev, curr):
    if prev and prev != 0:
        return round((curr - prev) / prev * 100, 2)
    return None


def _benchmark_for(symbol: str) -> str:
    return BENCHMARKS["kr"] if symbol.upper().endswith((".KS", ".KQ")) else BENCHMARKS["us"]


def _fetch_benchmark_returns() -> dict:
    """6-month return for each benchmark index, fetched once and reused across symbols."""
    returns = {}
    for sym in set(BENCHMARKS.values()):
        try:
            hist = yf.Ticker(sym).history(period="1y", auto_adjust=True)
            days = TRADING_DAYS["6m"]
            if len(hist) > days:
                past = float(hist["Close"].iloc[-days - 1])
                curr = float(hist["Close"].iloc[-1])
                returns[sym] = _pct(past, curr)
        except Exception as e:
            log.warning(f"[watchlist_stocks] benchmark fetch failed: {sym}: {e}")
    return returns


def _ma200_cross_info(close):
    """Detect whether today is the day price crossed its own 200dma, and how
    many trading days (~/21 = months) it had spent on the other side before that.

    Returns (direction, months_since_prior) where direction is "golden"
    (crossed above), "death" (crossed below), or None if no cross today.
    """
    ma200_series = close.rolling(200).mean().dropna()
    if len(ma200_series) < 2:
        return None, None

    above = (close.loc[ma200_series.index] > ma200_series).astype(int)
    if above.iloc[-1] == above.iloc[-2]:
        return None, None

    direction = "golden" if above.iloc[-1] == 1 else "death"
    prior_side = above.iloc[-2]
    streak = 0
    for v in above.iloc[:-1].iloc[::-1]:
        if v == prior_side:
            streak += 1
        else:
            break
    months = round(streak / 21, 1) if streak else None
    return direction, months


def _position_metrics(hist) -> dict:
    """Axis A ('position') metrics: where a stock sits relative to its own trailing history.

    A 1-day change % tells a long-term holder nothing; 52-week percentile, 200dma
    distance, and multi-month returns are what actually carries signal for them.
    """
    close = hist["Close"]
    volume = hist["Volume"]
    n = len(close)
    curr = float(close.iloc[-1])

    week52_window = close.iloc[-WEEK52_TRADING_DAYS:] if n >= WEEK52_TRADING_DAYS else close
    week52_high = float(week52_window.max())
    week52_low = float(week52_window.min())
    week52_span = week52_high - week52_low
    week52_pct = round((curr - week52_low) / week52_span * 100, 1) if week52_span > 0 else None
    drawdown_from_high_pct = round((curr - week52_high) / week52_high * 100, 2) if week52_high else None

    # A "new 52w high" only means something the day it first happens — being
    # today's close vs everything BEFORE today within the 52-week window (not
    # including today) is what makes it a fresh event rather than "still near
    # the top since 3 weeks ago".
    prior_window = week52_window.iloc[:-1]
    is_new_52w_high = len(prior_window) > 0 and curr > float(prior_window.max())
    is_new_52w_low = len(prior_window) > 0 and curr < float(prior_window.min())

    ma200 = None
    pct_vs_ma200 = None
    ma200_cross = None
    ma200_cross_months_since_prior = None
    if n >= 200:
        ma200 = float(close.rolling(200).mean().iloc[-1])
        pct_vs_ma200 = round((curr - ma200) / ma200 * 100, 2) if ma200 else None
        ma200_cross, ma200_cross_months_since_prior = _ma200_cross_info(close)

    returns = {}
    for label, days in TRADING_DAYS.items():
        if n > days:
            past = float(close.iloc[-days - 1])
            returns[label] = _pct(past, curr)
        else:
            returns[label] = None

    # Excludes today: including it drags the average toward today's own spike
    # and understates the ratio (a 10x day would read as ~6.9x, not ~10x).
    volume_avg_20d = None
    volume_ratio = None
    if len(volume) >= 21:
        volume_avg_20d = float(volume.iloc[-21:-1].mean())
        last_vol = float(volume.iloc[-1])
        volume_ratio = round(last_vol / volume_avg_20d, 2) if volume_avg_20d else None

    return {
        "week52_high": round(week52_high, 2),
        "week52_low": round(week52_low, 2),
        "week52_pct": week52_pct,
        "drawdown_from_high_pct": drawdown_from_high_pct,
        "is_new_52w_high": is_new_52w_high,
        "is_new_52w_low": is_new_52w_low,
        "ma200": round(ma200, 2) if ma200 is not None else None,
        "pct_vs_ma200": pct_vs_ma200,
        "ma200_cross": ma200_cross,
        "ma200_cross_months_since_prior": ma200_cross_months_since_prior,
        "return_3m_pct": returns["3m"],
        "return_6m_pct": returns["6m"],
        "return_12m_pct": returns["12m"],
        "volume_avg_20d": round(volume_avg_20d) if volume_avg_20d is not None else None,
        "volume_ratio": volume_ratio,
    }


def fetch(symbols: list) -> dict:
    if not symbols:
        return {}

    benchmark_returns = _fetch_benchmark_returns()

    result = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period=FETCH_PERIOD, auto_adjust=True)
            if len(hist) < 2:
                continue

            prev = float(hist["Close"].iloc[-2])
            curr = float(hist["Close"].iloc[-1])
            vol = int(hist["Volume"].iloc[-1])

            # 종목별 최신 뉴스 (최대 5개)
            raw_news = ticker.news or []
            news = []
            for n in raw_news[:5]:
                content = n.get("content", {})
                title = content.get("title") or n.get("title", "")
                url = content.get("canonicalUrl", {}).get("url") or n.get("link", "")
                news.append({"title": title, "url": url})

            position = _position_metrics(hist)
            bench_return_6m = benchmark_returns.get(_benchmark_for(sym))
            stock_return_6m = position["return_6m_pct"]
            position["relative_strength_6m_pct"] = (
                round(stock_return_6m - bench_return_6m, 2)
                if stock_return_6m is not None and bench_return_6m is not None
                else None
            )

            result[sym] = {
                "prev_close": round(prev, 2),
                "last_close": round(curr, 2),
                "change_pct": _pct(prev, curr),
                "volume": vol,
                "news": news,
                **position,
            }
        except Exception as e:
            result[sym] = {"error": str(e)}

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(["NVDA", "AAPL", "005930.KS"]), indent=2, ensure_ascii=False))
