import yfinance as yf
from datetime import datetime


def _pct(prev, curr):
    if prev and prev != 0:
        return round((curr - prev) / prev * 100, 2)
    return None


def fetch(symbols: list) -> dict:
    if not symbols:
        return {}

    result = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d", auto_adjust=True)
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

            result[sym] = {
                "prev_close": round(prev, 2),
                "last_close": round(curr, 2),
                "change_pct": _pct(prev, curr),
                "volume": vol,
                "news": news,
            }
        except Exception as e:
            result[sym] = {"error": str(e)}

    return result


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(["NVDA", "AAPL", "005930.KS"]), indent=2, ensure_ascii=False))
