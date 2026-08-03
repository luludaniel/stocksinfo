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
        "week52_pct": 41.0, "pct_vs_ma200": -3.0, "relative_strength_6m_pct": 12.0,
    }
    base.update(overrides)
    return base


def test_build_email_no_signals_skips_llm():
    import main

    watchlist = {"NVDA": _pos()}
    with patch("main.interpret_signals") as mock_interpret:
        body = main.build_email(watchlist, {}, {}, {})

    mock_interpret.assert_not_called()
    assert "신호 0건" in body


def test_build_email_passes_resolved_config_to_signal_evaluation():
    # Regression: build_email must actually forward per-symbol profile config
    # through to signals.evaluate, not just accept and ignore the parameter.
    import main

    watchlist = {"NVDA": _pos(volume_ratio=5.0)}  # would fire volume_spike globally
    resolved_config = {"NVDA": {"signals": ["ma200_cross"], "thresholds": {}}}

    with patch("main.interpret_signals") as mock_interpret:
        body = main.build_email(watchlist, {}, {}, {}, resolved_config)

    mock_interpret.assert_not_called()
    assert "거래량" not in body


def test_build_email_with_signal_calls_llm():
    import main

    watchlist = {"NVDA": _pos(ma200_cross="golden", ma200_cross_months_since_prior=2.0)}
    fundamentals = {"NVDA": {"trailing_pe": 30.0, "target_mean_price": 150.0}}

    with patch("main.interpret_signals", return_value="해설") as mock_interpret:
        body = main.build_email(watchlist, fundamentals, {}, {})

    mock_interpret.assert_called_once()
    assert "200일선 상향 돌파" in body
    assert "해설" in body


def test_build_email_does_not_write_snapshots_as_a_side_effect():
    # Regression: build_email used to save history rows itself. That's now
    # main()'s job (a fixed pipeline step, not hidden inside "build the email").
    import main
    import history

    watchlist = {"NVDA": _pos()}
    fundamentals = {"NVDA": {"trailing_pe": 30.0}}
    with patch("main.interpret_signals"):
        main.build_email(watchlist, fundamentals, {}, {})

    today_str = __import__("datetime").date.today().isoformat()
    assert history.get_snapshot("NVDA", today_str) is None


def test_save_snapshots_persists_position_and_fundamentals():
    import main
    import history

    watchlist = {"NVDA": _pos(last_close=100.0)}
    fundamentals = {"NVDA": {"trailing_pe": 30.0, "target_mean_price": 150.0}}
    today_str = __import__("datetime").date.today().isoformat()

    main._save_snapshots(watchlist, fundamentals, today_str)

    snap = history.get_snapshot("NVDA", today_str)
    assert snap["last_close"] == 100.0
    assert snap["trailing_pe"] == 30.0


def test_save_snapshots_skips_errored_symbols():
    import main
    import history

    watchlist = {"NVDA": {"error": "boom"}}
    today_str = __import__("datetime").date.today().isoformat()

    main._save_snapshots(watchlist, {}, today_str)

    assert history.get_snapshot("NVDA", today_str) is None


def test_build_email_attaches_yfinance_news_to_llm_payload():
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
        main.build_email(watchlist, {}, {}, {})

    assert captured["signals"][0]["related_news"][0]["title"] == "NVDA rallies"


def test_build_email_matches_general_news_by_symbol_and_dedupes():
    import main

    watchlist = {"NVDA": _pos(
        ma200_cross="golden", ma200_cross_months_since_prior=1.0,
        news=[{"title": "NVDA existing", "url": "http://a.com"}],
    )}
    news_data = {"articles": [
        {"title": "NVDA rallies on earnings", "url": "http://b.com"},
        {"title": "Completely unrelated market news", "url": "http://c.com"},
        {"title": "NVDA existing", "url": "http://a.com"},  # duplicate url
    ]}

    captured = {}

    def fake_interpret(signals):
        captured["signals"] = signals
        return "해설"

    with patch("main.interpret_signals", side_effect=fake_interpret):
        main.build_email(watchlist, {}, {}, news_data)

    related = captured["signals"][0]["related_news"]
    urls = [a["url"] for a in related]
    assert "http://b.com" in urls
    assert "http://c.com" not in urls
    assert urls.count("http://a.com") == 1


def test_build_email_shows_failed_symbols_when_no_real_signals():
    # Regression: total collection failure must not look identical to a
    # genuinely quiet day.
    import main

    watchlist = {"NVDA": {"error": "boom"}}
    with patch("main.interpret_signals") as mock_interpret:
        body = main.build_email(watchlist, {}, {}, {})

    mock_interpret.assert_not_called()
    assert "수집 실패" in body
    assert "오늘은 관심종목에 특이사항이 없습니다" not in body


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
    events = main._ticker_calendar_events(fundamentals, {}, today)
    assert any("NVDA 실적" in e for e in events)
    assert not any("AAPL" in e for e in events)


def test_ticker_calendar_events_uses_display_name():
    import main
    from datetime import date, timedelta

    today = date(2026, 8, 2)
    soon = (today + timedelta(days=3)).isoformat()
    fundamentals = {"005930.KS": {"next_earnings_date": soon, "ex_dividend_date": None}}
    names = {"005930.KS": "삼성전자"}

    events = main._ticker_calendar_events(fundamentals, names, today)
    assert any("삼성전자" in e for e in events)


def test_ticker_calendar_events_skips_errored_symbols():
    import main
    from datetime import date

    events = main._ticker_calendar_events({"NVDA": {"error": "boom"}}, {}, date(2026, 8, 2))
    assert events == []


def test_symbol_names_extracts_from_fundamentals():
    import main

    fundamentals = {
        "NVDA": {"name": "NVIDIA Corporation"},
        "AAPL": {"error": "boom"},
        "TSLA": {"name": None},
    }
    names = main._symbol_names(fundamentals)
    assert names == {"NVDA": "NVIDIA Corporation"}


def test_build_latest_payload_includes_positions_and_focus_and_status():
    import main

    watchlist = {"NVDA": _pos(ma200_cross="golden", ma200_cross_months_since_prior=1.0),
                 "AAPL": {"error": "rate limited"}}
    fundamentals = {"NVDA": {"name": "NVIDIA", "trailing_pe": 30.0}}
    resolved_config = {"NVDA": {"signals": None, "thresholds": {}, "profile": "core_holding"}}

    payload = main.build_latest_payload(
        watchlist, fundamentals, {}, {}, resolved_config, [], None,
    )

    assert payload["schema_version"] == 1
    assert payload["status"]["ok"] is False
    assert payload["status"]["failed_symbols"] == [{"symbol": "AAPL", "reason": "rate limited"}]
    assert len(payload["positions"]) == 1
    assert payload["positions"][0]["symbol"] == "NVDA"
    assert payload["positions"][0]["profile"] == "core_holding"
    assert len(payload["focus"]) == 1
    assert payload["focus"][0]["symbol"] == "NVDA"


def test_build_latest_payload_ok_status_when_nothing_failed():
    import main

    watchlist = {"NVDA": _pos()}
    payload = main.build_latest_payload(watchlist, {}, {}, {}, {}, [], None)
    assert payload["status"]["ok"] is True
    assert payload["focus"] == []


def test_collect_all_merges_news_and_economic_cal_errors():
    import main

    with patch("main.news.fetch", return_value={"articles": [], "errors": ["feed X failed"]}), \
         patch("main.economic_cal.fetch", return_value={"events": [], "errors": ["FRED: timeout"]}):
        result = main.collect_all([])

    assert "feed X failed" in result["_errors"]
    assert "FRED: timeout" in result["_errors"]


def test_collect_all_records_collector_exception():
    import main

    with patch("main.news.fetch", side_effect=Exception("boom")), \
         patch("main.economic_cal.fetch", return_value={}):
        result = main.collect_all([])

    assert any("news" in e for e in result["_errors"])
    assert result["news"] is None


def test_collect_all_records_timeout_for_outstanding_futures():
    import time
    import main

    def slow_fetch():
        time.sleep(0.3)
        return {}

    with patch("main.news.fetch", side_effect=slow_fetch), \
         patch("main.economic_cal.fetch", return_value={}), \
         patch("main.COLLECT_TIMEOUT_SECONDS", 0.01):
        result = main.collect_all([])

    assert any("timed out" in e for e in result["_errors"])
    assert result["news"] is None


def test_collect_all_does_not_reference_removed_market_collectors():
    import main
    assert not hasattr(main, "us_market")
    assert not hasattr(main, "kr_market")
