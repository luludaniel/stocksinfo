import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


def _make_ticker_mock(prev, curr, volume, news):
    ticker = MagicMock()
    hist = pd.DataFrame({"Close": [prev, curr], "Volume": [volume, volume]})
    ticker.history.return_value = hist
    ticker.news = news
    return ticker


def test_fetch_single_symbol():
    from collectors.watchlist_stocks import fetch

    mock_ticker = _make_ticker_mock(100.0, 110.0, 1000000, [
        {"content": {"title": "Test news", "canonicalUrl": {"url": "http://test.com"}}}
    ])

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = fetch(["NVDA"])

    assert "NVDA" in result
    assert result["NVDA"]["change_pct"] == 10.0
    assert result["NVDA"]["last_close"] == 110.0
    assert len(result["NVDA"]["news"]) == 1
    assert result["NVDA"]["news"][0]["title"] == "Test news"


def test_fetch_empty_symbols():
    from collectors.watchlist_stocks import fetch
    assert fetch([]) == {}


def test_fetch_handles_error():
    from collectors.watchlist_stocks import fetch

    with patch("yfinance.Ticker", side_effect=Exception("network error")):
        result = fetch(["FAIL"])

    assert "FAIL" in result
    assert "error" in result["FAIL"]


def test_fetch_insufficient_history():
    from collectors.watchlist_stocks import fetch

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame({"Close": [100.0], "Volume": [500000]})
    mock_ticker.news = []

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = fetch(["AAPL"])

    assert "AAPL" not in result
