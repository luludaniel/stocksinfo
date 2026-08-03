import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


def _make_ticker_mock(prev, curr, volume, news):
    ticker = MagicMock()
    hist = pd.DataFrame({"Close": [prev, curr], "Volume": [volume, volume]})
    ticker.history.return_value = hist
    ticker.news = news
    return ticker


def _make_linear_ticker_mock(n=300, start=100.0, volume=1_000_000, spike_last_volume=None):
    close = pd.Series([start + i for i in range(n)])
    volumes = pd.Series([volume] * n)
    if spike_last_volume is not None:
        volumes.iloc[-1] = spike_last_volume
    hist = pd.DataFrame({"Close": close, "Volume": volumes})
    ticker = MagicMock()
    ticker.history.return_value = hist
    ticker.news = []
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


def test_fetch_short_history_omits_position_fields_gracefully():
    from collectors.watchlist_stocks import fetch

    mock_ticker = _make_ticker_mock(100.0, 110.0, 1000000, [])
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = fetch(["NVDA"])

    # not enough history for a 200dma or 3/6/12m returns -> None, not a crash
    assert result["NVDA"]["ma200"] is None
    assert result["NVDA"]["return_3m_pct"] is None
    assert result["NVDA"]["relative_strength_6m_pct"] is None
    # but 52-week band is still derivable from whatever history exists
    assert result["NVDA"]["week52_high"] == 110.0
    assert result["NVDA"]["week52_pct"] == 100.0


def test_fetch_computes_position_metrics_with_full_year_history():
    from collectors.watchlist_stocks import fetch, TRADING_DAYS

    mock_ticker = _make_linear_ticker_mock(n=300, start=100.0, spike_last_volume=5_000_000)
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = fetch(["NVDA"])

    m = result["NVDA"]
    # monotonically increasing series -> today's close is the 52w high; the
    # 52w low is anchored to the trailing 252-day window, not the full series.
    assert m["week52_high"] == pytest.approx(399.0)
    assert m["week52_low"] == pytest.approx(148.0)
    assert m["week52_pct"] == pytest.approx(100.0)
    assert m["drawdown_from_high_pct"] == pytest.approx(0.0)

    assert m["ma200"] is not None
    assert m["pct_vs_ma200"] > 0  # price above its own 200dma on a rising series

    assert m["return_3m_pct"] == pytest.approx(18.75, abs=0.1)
    assert m["return_6m_pct"] == pytest.approx(46.15, abs=0.1)
    assert m["return_12m_pct"] == pytest.approx(171.43, abs=0.1)

    assert m["volume_avg_20d"] is not None
    assert m["volume_ratio"] > 1  # last-day volume spike vs 20d average


def test_volume_ratio_excludes_todays_spike_from_the_average():
    # Regression: averaging in today's own spike dilutes the ratio — a true
    # 10x day would previously read as ~6.9x instead of ~10x.
    from collectors.watchlist_stocks import fetch

    mock_ticker = _make_linear_ticker_mock(n=300, start=100.0, spike_last_volume=10_000_000)
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = fetch(["NVDA"])

    m = result["NVDA"]
    assert m["volume_avg_20d"] == pytest.approx(1_000_000)
    assert m["volume_ratio"] == pytest.approx(10.0)


def test_fetch_requests_two_years_so_12m_return_is_computable():
    # yfinance's period="1y" only returns ~251 rows, one short of the 252
    # trading days a full 12-month lookback needs -> return_12m_pct would
    # always be None. Regression guard for that off-by-one.
    from collectors.watchlist_stocks import fetch, FETCH_PERIOD

    mock_ticker = _make_linear_ticker_mock(n=300, start=100.0)
    with patch("yfinance.Ticker", return_value=mock_ticker):
        fetch(["NVDA"])

    assert FETCH_PERIOD != "1y"
    mock_ticker.history.assert_called_with(period=FETCH_PERIOD, auto_adjust=True)


def test_fetch_computes_relative_strength_vs_benchmark():
    from collectors.watchlist_stocks import fetch, BENCHMARKS

    stock_ticker = _make_linear_ticker_mock(n=300, start=100.0)
    benchmark_ticker = _make_linear_ticker_mock(n=300, start=100.0)
    # flatten the benchmark's own trailing return to 0% so relative strength ==
    # the stock's own 6m return exactly.
    benchmark_ticker.history.return_value["Close"] = 100.0

    def side_effect(sym):
        return benchmark_ticker if sym == BENCHMARKS["us"] else stock_ticker

    with patch("yfinance.Ticker", side_effect=side_effect):
        result = fetch(["NVDA"])

    m = result["NVDA"]
    assert m["relative_strength_6m_pct"] == pytest.approx(m["return_6m_pct"])


def test_fetch_detects_golden_cross():
    from collectors.watchlist_stocks import fetch

    close = pd.Series([100.0] * 299 + [150.0])
    volume = pd.Series([1_000_000] * 300)
    hist = pd.DataFrame({"Close": close, "Volume": volume})
    ticker = MagicMock()
    ticker.history.return_value = hist
    ticker.news = []

    with patch("yfinance.Ticker", return_value=ticker):
        result = fetch(["NVDA"])

    assert result["NVDA"]["ma200_cross"] == "golden"
    assert result["NVDA"]["ma200_cross_months_since_prior"] > 0


def test_fetch_detects_death_cross():
    from collectors.watchlist_stocks import fetch

    close = pd.Series([100.0 + i for i in range(299)] + [50.0])
    volume = pd.Series([1_000_000] * 300)
    hist = pd.DataFrame({"Close": close, "Volume": volume})
    ticker = MagicMock()
    ticker.history.return_value = hist
    ticker.news = []

    with patch("yfinance.Ticker", return_value=ticker):
        result = fetch(["NVDA"])

    assert result["NVDA"]["ma200_cross"] == "death"
    assert result["NVDA"]["ma200_cross_months_since_prior"] > 0


def test_fetch_no_cross_when_side_unchanged():
    from collectors.watchlist_stocks import fetch

    mock_ticker = _make_linear_ticker_mock(n=300, start=100.0)
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = fetch(["NVDA"])

    assert result["NVDA"]["ma200_cross"] is None


def test_fetch_flags_fresh_52w_high_and_low():
    from collectors.watchlist_stocks import fetch

    rising_ticker = _make_linear_ticker_mock(n=300, start=100.0)
    with patch("yfinance.Ticker", return_value=rising_ticker):
        result = fetch(["NVDA"])
    assert result["NVDA"]["is_new_52w_high"] is True
    assert result["NVDA"]["is_new_52w_low"] is False

    close = pd.Series([100.0 + i for i in range(299)] + [1.0])
    volume = pd.Series([1_000_000] * 300)
    hist = pd.DataFrame({"Close": close, "Volume": volume})
    falling_ticker = MagicMock()
    falling_ticker.history.return_value = hist
    falling_ticker.news = []
    with patch("yfinance.Ticker", return_value=falling_ticker):
        result = fetch(["NVDA"])
    assert result["NVDA"]["is_new_52w_low"] is True
    assert result["NVDA"]["is_new_52w_high"] is False


def test_fetch_benchmark_failure_does_not_break_symbol_fetch():
    from collectors.watchlist_stocks import fetch, BENCHMARKS

    stock_ticker = _make_linear_ticker_mock(n=300, start=100.0)

    def side_effect(sym):
        if sym in BENCHMARKS.values():
            raise Exception("benchmark unavailable")
        return stock_ticker

    with patch("yfinance.Ticker", side_effect=side_effect):
        result = fetch(["NVDA"])

    assert "NVDA" in result
    assert "error" not in result["NVDA"]
    assert result["NVDA"]["relative_strength_6m_pct"] is None
