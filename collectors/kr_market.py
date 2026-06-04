import yfinance as yf
from datetime import datetime


KR_INDICES = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "USD/KRW": "KRW=X",
}

KR_ETFS = {
    "KODEX 삼성그룹 (105560.KS)": "105560.KS",
    "KODEX 200 (069500.KS)": "069500.KS",
    "KODEX 레버리지 (122630.KS)": "122630.KS",
}


def _pct(prev, curr):
    if prev and prev != 0:
        return round((curr - prev) / prev * 100, 2)
    return None


def fetch() -> dict:
    result = {"indices": {}, "etfs": {}, "fetched_at": datetime.utcnow().isoformat()}

    all_syms = list(KR_INDICES.values()) + list(KR_ETFS.values())
    data = yf.download(all_syms, period="2d", interval="1d", progress=False, auto_adjust=True)
    close = data["Close"]

    for name, sym in KR_INDICES.items():
        if sym not in close.columns:
            continue
        series = close[sym].dropna()
        if len(series) < 2:
            continue
        prev, curr = float(series.iloc[-2]), float(series.iloc[-1])
        result["indices"][name] = {
            "symbol": sym,
            "prev_close": round(prev, 2),
            "last_close": round(curr, 2),
            "change_pct": _pct(prev, curr),
        }

    for name, sym in KR_ETFS.items():
        if sym not in close.columns:
            continue
        series = close[sym].dropna()
        if len(series) < 2:
            continue
        prev, curr = float(series.iloc[-2]), float(series.iloc[-1])
        result["etfs"][name] = {
            "symbol": sym,
            "change_pct": _pct(prev, curr),
        }

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), indent=2, ensure_ascii=False))
