import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr("history.DB_FILE", tmp_path / "test.db")


def _pos(**overrides):
    base = {
        "ma200_cross": None, "ma200_cross_months_since_prior": None,
        "is_new_52w_high": False, "is_new_52w_low": False,
        "volume_ratio": 1.0,
    }
    base.update(overrides)
    return base


def test_no_signals_on_quiet_day():
    import signals
    watchlist = {"NVDA": _pos()}
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    assert result == []


def test_golden_cross_produces_yellow_signal():
    import signals
    watchlist = {"NVDA": _pos(ma200_cross="golden", ma200_cross_months_since_prior=3.5)}
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    assert len(result) == 1
    assert result[0]["severity"] == "yellow"
    assert result[0]["type"] == "ma200_cross"
    assert "3.5개월" in result[0]["message"]


def test_death_cross_produces_red_signal():
    import signals
    watchlist = {"NVDA": _pos(ma200_cross="death", ma200_cross_months_since_prior=6.0)}
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    assert result[0]["severity"] == "red"


def test_new_52w_low_is_red_high_is_yellow():
    import signals
    watchlist = {
        "A": _pos(is_new_52w_high=True),
        "B": _pos(is_new_52w_low=True),
    }
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    by_symbol = {s["symbol"]: s for s in result}
    assert by_symbol["A"]["severity"] == "yellow"
    assert by_symbol["B"]["severity"] == "red"


def test_volume_spike_signal():
    import signals
    watchlist = {"NVDA": _pos(volume_ratio=3.2)}
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    assert result[0]["type"] == "volume_spike"
    assert "3.2배" in result[0]["message"]


def test_volume_below_threshold_no_signal():
    import signals
    watchlist = {"NVDA": _pos(volume_ratio=1.5)}
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    assert result == []


def test_errored_symbol_is_skipped():
    import signals
    watchlist = {"NVDA": {"error": "boom"}}
    result = signals.evaluate(watchlist, {}, "2026-08-02")
    assert result == []


def test_earnings_within_7_days_signal():
    import signals
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-08"}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert result[0]["type"] == "earnings_soon"
    assert "D-6" in result[0]["message"]


def test_earnings_beyond_lookahead_no_signal():
    import signals
    fundamentals = {"NVDA": {"next_earnings_date": "2026-09-08"}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert result == []


def test_earnings_bad_date_does_not_crash():
    import signals
    fundamentals = {"NVDA": {"next_earnings_date": "not-a-date"}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert result == []


def test_valuation_band_skipped_without_enough_history():
    import signals
    fundamentals = {"NVDA": {"trailing_pe": 50.0}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert result == []


def test_valuation_band_signal_with_enough_history():
    import signals
    import history

    for i in range(25):
        d = f"2026-06-{i + 1:02d}"
        pe = 19.0 + (i % 3)  # small variance so std > 0
        history.save_snapshot(d, "NVDA", {
            "last_close": 100.0, "trailing_pe": pe,
            "target_mean_price": None, "volume": None,
        })

    fundamentals = {"NVDA": {"trailing_pe": 50.0}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert any(s["type"] == "valuation_band" for s in result)


def test_target_price_weekly_change_signal():
    import signals
    import history

    history.save_snapshot("2026-07-25", "NVDA", {
        "last_close": 100.0, "trailing_pe": None,
        "target_mean_price": 100.0, "volume": None,
    })

    fundamentals = {"NVDA": {"target_mean_price": 110.0}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert any(s["type"] == "target_price_change" for s in result)
    sig = next(s for s in result if s["type"] == "target_price_change")
    assert "상향" in sig["message"]
    assert "8일간" in sig["message"]  # 2026-07-25 -> 2026-08-02


def test_target_price_change_ignores_stale_snapshot():
    # Regression: with a sparse DB, "most recent snapshot before 6 days ago"
    # could be months old — that shouldn't be reported as a recent change.
    import signals
    import history

    history.save_snapshot("2026-05-01", "NVDA", {
        "last_close": 100.0, "trailing_pe": None,
        "target_mean_price": 100.0, "volume": None,
    })

    fundamentals = {"NVDA": {"target_mean_price": 200.0}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert result == []


def test_target_price_small_change_no_signal():
    import signals
    import history

    history.save_snapshot("2026-07-25", "NVDA", {
        "last_close": 100.0, "trailing_pe": None,
        "target_mean_price": 100.0, "volume": None,
    })

    fundamentals = {"NVDA": {"target_mean_price": 101.0}}
    result = signals.evaluate({}, fundamentals, "2026-08-02")
    assert result == []


def test_fundamentals_error_symbol_is_skipped():
    import signals
    result = signals.evaluate({}, {"NVDA": {"error": "boom"}}, "2026-08-02")
    assert result == []


def test_profile_excludes_signal_type_entirely():
    import signals
    watchlist = {"NVDA": _pos(volume_ratio=5.0)}
    cfg = {"NVDA": {"signals": ["ma200_cross"], "thresholds": {}}}  # volume_spike not allowed
    result = signals.evaluate(watchlist, {}, "2026-08-02", resolved_config=cfg)
    assert result == []


def test_profile_allows_only_listed_signal_types():
    import signals
    watchlist = {"NVDA": _pos(
        volume_ratio=5.0,
        ma200_cross="golden", ma200_cross_months_since_prior=1.0,
    )}
    cfg = {"NVDA": {"signals": ["ma200_cross"], "thresholds": {}}}
    result = signals.evaluate(watchlist, {}, "2026-08-02", resolved_config=cfg)
    assert [s["type"] for s in result] == ["ma200_cross"]


def test_no_resolved_config_allows_all_signal_types():
    import signals
    watchlist = {"NVDA": _pos(volume_ratio=5.0)}
    result = signals.evaluate(watchlist, {}, "2026-08-02", resolved_config=None)
    assert any(s["type"] == "volume_spike" for s in result)


def test_per_symbol_threshold_override_applies():
    import signals
    watchlist = {"NVDA": _pos(volume_ratio=2.5)}
    # global default (2.0) would fire; a stricter per-symbol override (3.0) shouldn't
    cfg = {"NVDA": {"signals": None, "thresholds": {"volume_spike_ratio": 3.0}}}
    result = signals.evaluate(watchlist, {}, "2026-08-02", resolved_config=cfg)
    assert result == []


def test_per_symbol_earnings_lookahead_override():
    import signals
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-05"}}  # D-3
    cfg = {"NVDA": {"signals": None, "thresholds": {"earnings_lookahead_days": 2}}}
    result = signals.evaluate({}, fundamentals, "2026-08-02", resolved_config=cfg)
    assert result == []  # 3 days out, but this profile only looks ahead 2
