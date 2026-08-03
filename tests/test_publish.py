from datetime import date

import pytest

import publish


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("publish.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("publish.LATEST_FILE", tmp_path / "data" / "latest.json")


def test_build_failed_symbols_extracts_error_reason():
    watchlist = {"NVDA": {"error": "rate limit (429)"}, "AAPL": {"last_close": 100.0}}
    failed = publish.build_failed_symbols(watchlist)
    assert failed == [{"symbol": "NVDA", "reason": "rate limit (429)"}]


def test_build_status_ok_when_nothing_failed():
    status = publish.build_status([], [])
    assert status["ok"] is True


def test_build_status_not_ok_on_collector_error():
    status = publish.build_status(["news: timeout"], [])
    assert status["ok"] is False
    assert status["collector_errors"] == ["news: timeout"]


def test_build_status_not_ok_on_failed_symbol():
    status = publish.build_status([], [{"symbol": "NVDA", "reason": "boom"}])
    assert status["ok"] is False


def test_build_history_status_computes_days_remaining():
    status = publish.build_history_status(days_collected=12, per_band_min_samples=20)
    assert status == {"days_collected": 12, "per_band_ready_in_days": 8}


def test_build_history_status_floors_at_zero():
    status = publish.build_history_status(days_collected=25, per_band_min_samples=20)
    assert status["per_band_ready_in_days"] == 0


def test_build_positions_includes_all_healthy_symbols_regardless_of_signals():
    watchlist = {
        "NVDA": {"last_close": 812.4, "change_pct": -1.9, "week52_pct": 22.0,
                 "pct_vs_ma200": -8.1, "drawdown_from_high_pct": -31.2,
                 "return_3m_pct": -14.0, "return_6m_pct": -22.0, "return_12m_pct": 8.0,
                 "relative_strength_6m_pct": -19.0},
    }
    fundamentals = {"NVDA": {"name": "NVIDIA Corporation", "trailing_pe": 38.2,
                              "next_earnings_date": "2026-08-05"}}
    positions = publish.build_positions(watchlist, fundamentals, {"NVDA": "core_holding"})
    assert len(positions) == 1
    p = positions[0]
    assert p["symbol"] == "NVDA"
    assert p["name"] == "NVIDIA Corporation"
    assert p["profile"] == "core_holding"
    assert p["week52_pct"] == 22.0
    assert p["trailing_pe"] == 38.2


def test_build_positions_excludes_failed_symbols():
    watchlist = {"NVDA": {"error": "boom"}}
    positions = publish.build_positions(watchlist, {}, {})
    assert positions == []


def test_build_calendar_includes_earnings_and_ex_dividend_within_lookahead():
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-05", "ex_dividend_date": None}}
    names = {"NVDA": "엔비디아"}
    calendar = publish.build_calendar(fundamentals, names, date(2026, 8, 2))
    assert len(calendar) == 1
    assert calendar[0]["label"] == "엔비디아 실적"
    assert calendar[0]["kind"] == "earnings"
    assert calendar[0]["date"] == "2026-08-05"


def test_build_calendar_excludes_events_beyond_lookahead():
    fundamentals = {"NVDA": {"next_earnings_date": "2026-09-05"}}
    calendar = publish.build_calendar(fundamentals, {}, date(2026, 8, 2))
    assert calendar == []


def test_build_calendar_sorted_by_date():
    fundamentals = {
        "NVDA": {"next_earnings_date": "2026-08-06"},
        "AAPL": {"ex_dividend_date": "2026-08-03"},
    }
    calendar = publish.build_calendar(fundamentals, {}, date(2026, 8, 2))
    assert [c["date"] for c in calendar] == ["2026-08-03", "2026-08-06"]


def test_build_latest_assembles_full_contract():
    watchlist = {"NVDA": {"last_close": 100.0}}
    fundamentals = {"NVDA": {"name": "NVIDIA"}}
    data = publish.build_latest(
        market_date="2026-08-02", trigger="schedule", collector_errors=[],
        watchlist=watchlist, fundamentals_data=fundamentals, profiles_by_symbol={},
        history_status={"days_collected": 1, "per_band_ready_in_days": 19},
        focus=[], discovery=[], calendar=[],
    )
    assert data["schema_version"] == 1
    assert data["market_date"] == "2026-08-02"
    assert data["trigger"] == "schedule"
    assert data["status"]["ok"] is True
    assert len(data["positions"]) == 1
    assert "generated_at" in data


def test_save_and_load_latest_roundtrip():
    data = {"schema_version": 1, "market_date": "2026-08-02"}
    publish.save_latest(data)
    assert publish.load_latest() == data


def test_load_latest_returns_none_when_missing():
    assert publish.load_latest() is None
