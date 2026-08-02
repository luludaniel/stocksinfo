import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr("history.DB_FILE", tmp_path / "test.db")


def _pos(**overrides):
    base = {
        "last_close": 100.0, "volume": 1_000_000, "news": [],
        "ma200_cross": None, "ma200_cross_months_since_prior": None,
        "is_new_52w_high": False, "is_new_52w_low": False,
        "volume_ratio": 1.0,
    }
    base.update(overrides)
    return base


def test_build_email_no_signals_skips_llm():
    import main

    watchlist = {"NVDA": _pos()}
    with patch("main.interpret_signals") as mock_interpret:
        body = main.build_email(watchlist, {}, {})

    mock_interpret.assert_not_called()
    assert "신호 0건" in body


def test_build_email_with_signal_calls_llm_and_saves_snapshot():
    import main
    import history

    watchlist = {"NVDA": _pos(ma200_cross="golden", ma200_cross_months_since_prior=2.0)}
    fundamentals = {"NVDA": {"trailing_pe": 30.0, "target_mean_price": 150.0}}

    with patch("main.interpret_signals", return_value="해설") as mock_interpret:
        body = main.build_email(watchlist, fundamentals, {})

    mock_interpret.assert_called_once()
    assert "200일선 상향 돌파" in body
    assert "해설" in body

    snap = history.get_snapshot("NVDA", __import__("datetime").date.today().isoformat())
    assert snap["last_close"] == 100.0
    assert snap["trailing_pe"] == 30.0


def test_build_email_attaches_related_news_to_llm_payload():
    import main

    watchlist = {"NVDA": _pos(
        ma200_cross="golden", ma200_cross_months_since_prior=1.0,
        news=[{"title": "NVDA rallies", "url": "http://test.com"}],
    )}

    captured = {}

    def fake_interpret(signals):
        captured["signals"] = signals
        return "해설"

    with patch("main.interpret_signals", side_effect=fake_interpret):
        main.build_email(watchlist, {}, {})

    assert captured["signals"][0]["related_news"][0]["title"] == "NVDA rallies"


def test_build_email_skips_errored_watchlist_symbols_in_snapshot():
    import main
    import history

    watchlist = {"NVDA": {"error": "boom"}}
    with patch("main.interpret_signals"):
        main.build_email(watchlist, {}, {})

    today_str = __import__("datetime").date.today().isoformat()
    assert history.get_snapshot("NVDA", today_str) is None


def test_ticker_calendar_events_within_lookahead():
    import main
    from datetime import date, timedelta

    today = date(2026, 8, 2)  # Sunday
    soon = (today + timedelta(days=3)).isoformat()
    far = (today + timedelta(days=30)).isoformat()

    fundamentals = {
        "NVDA": {"next_earnings_date": soon, "ex_dividend_date": None},
        "AAPL": {"next_earnings_date": far, "ex_dividend_date": None},
    }
    events = main._ticker_calendar_events(fundamentals, today)
    assert any("NVDA 실적" in e for e in events)
    assert not any("AAPL" in e for e in events)


def test_ticker_calendar_events_skips_errored_symbols():
    import main
    from datetime import date

    events = main._ticker_calendar_events({"NVDA": {"error": "boom"}}, date(2026, 8, 2))
    assert events == []


def test_collect_all_merges_news_errors_into_top_level_errors():
    import main

    with patch("main.us_market.fetch", return_value={}), \
         patch("main.kr_market.fetch", return_value={}), \
         patch("main.news.fetch", return_value={"articles": [], "errors": ["feed X failed"]}), \
         patch("main.economic_cal.fetch", return_value={}):
        result = main.collect_all([])

    assert "feed X failed" in result["_errors"]


def test_collect_all_records_collector_exception():
    import main

    with patch("main.us_market.fetch", side_effect=Exception("boom")), \
         patch("main.kr_market.fetch", return_value={}), \
         patch("main.news.fetch", return_value={"articles": [], "errors": []}), \
         patch("main.economic_cal.fetch", return_value={}):
        result = main.collect_all([])

    assert any("us_market" in e for e in result["_errors"])
    assert result["us_market"] is None
