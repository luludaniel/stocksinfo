from unittest.mock import patch, MagicMock


def _make_ticker(info, calendar=None):
    ticker = MagicMock()
    ticker.info = info
    ticker.calendar = calendar
    return ticker


def test_fetch_extracts_valuation_and_targets():
    from collectors.fundamentals import fetch

    info = {
        "trailingPE": 28.5,
        "forwardPE": 24.1,
        "priceToBook": 12.3,
        "dividendYield": 0.005,
        "debtToEquity": 45.2,
        "freeCashflow": 5_000_000_000,
        "marketCap": 2_500_000_000_000,
        "targetMeanPrice": 150.0,
        "targetHighPrice": 200.0,
        "targetLowPrice": 100.0,
        "recommendationKey": "buy",
        "numberOfAnalystOpinions": 42,
    }
    ticker = _make_ticker(info, calendar={"Earnings Date": ["2026-08-10"]})

    with patch("yfinance.Ticker", return_value=ticker):
        result = fetch(["NVDA"])

    m = result["NVDA"]
    assert m["trailing_pe"] == 28.5
    assert m["target_mean_price"] == 150.0
    assert m["recommendation"] == "buy"
    assert m["next_earnings_date"] == "2026-08-10"
    assert m["market_cap"] == 2_500_000_000_000


def test_fetch_empty_symbols():
    from collectors.fundamentals import fetch
    assert fetch([]) == {}


def test_fetch_handles_missing_info_fields_gracefully():
    from collectors.fundamentals import fetch
    ticker = _make_ticker({}, calendar=None)

    with patch("yfinance.Ticker", return_value=ticker):
        result = fetch(["NVDA"])

    m = result["NVDA"]
    assert m["trailing_pe"] is None
    assert m["next_earnings_date"] is None


def test_fetch_handles_ticker_error():
    from collectors.fundamentals import fetch

    with patch("yfinance.Ticker", side_effect=Exception("network error")):
        result = fetch(["FAIL"])

    assert "error" in result["FAIL"]


def test_fetch_handles_calendar_exception():
    from collectors.fundamentals import fetch

    ticker = MagicMock()
    ticker.info = {"trailingPE": 20.0}
    type(ticker).calendar = property(lambda self: (_ for _ in ()).throw(Exception("boom")))

    with patch("yfinance.Ticker", return_value=ticker):
        result = fetch(["NVDA"])

    assert result["NVDA"]["next_earnings_date"] is None
    assert result["NVDA"]["trailing_pe"] == 20.0


def test_fetch_extracts_ex_dividend_date():
    from collectors.fundamentals import fetch

    info = {"exDividendDate": 1770595200}  # 2026-02-09 UTC
    ticker = _make_ticker(info)

    with patch("yfinance.Ticker", return_value=ticker):
        result = fetch(["AAPL"])

    assert result["AAPL"]["ex_dividend_date"] == "2026-02-09"
