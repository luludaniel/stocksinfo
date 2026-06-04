import yfinance as yf
from datetime import datetime, timedelta


INDICES = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "VIX": "^VIX",
    "USD/KRW": "KRW=X",
    "Gold": "GC=F",
    "Oil (WTI)": "CL=F",
}

SECTOR_ETFS = {
    "Tech (XLK)": "XLK",
    "Finance (XLF)": "XLF",
    "Energy (XLE)": "XLE",
    "Healthcare (XLV)": "XLV",
    "Consumer (XLY)": "XLY",
}


def _pct(prev, curr):
    if prev and prev != 0:
        return round((curr - prev) / prev * 100, 2)
    return None


def fetch() -> dict:
    result = {"indices": {}, "sectors": {}, "fetched_at": datetime.utcnow().isoformat()}

    tickers = list(INDICES.values()) + list(SECTOR_ETFS.values())
    data = yf.download(tickers, period="2d", interval="1d", progress=False, auto_adjust=True)

    close = data["Close"]

    for name, sym in INDICES.items():
        if sym not in close.columns:
            continue
        series = close[sym].dropna()
        if len(series) < 2:
            continue
        prev, curr = float(series.iloc[-2]), float(series.iloc[-1])
        result["indices"][name] = {
            "symbol": sym,
            "prev_close": round(prev, 4),
            "last_close": round(curr, 4),
            "change_pct": _pct(prev, curr),
        }

    for name, sym in SECTOR_ETFS.items():
        if sym not in close.columns:
            continue
        series = close[sym].dropna()
        if len(series) < 2:
            continue
        prev, curr = float(series.iloc[-2]), float(series.iloc[-1])
        result["sectors"][name] = {
            "symbol": sym,
            "change_pct": _pct(prev, curr),
        }

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), indent=2, ensure_ascii=False))
