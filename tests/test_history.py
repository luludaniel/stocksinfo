import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr("history.DB_FILE", tmp_path / "test.db")


def test_save_and_get_snapshot():
    import history
    history.save_snapshot("2026-08-01", "NVDA", {
        "last_close": 100.0, "trailing_pe": 30.0, "target_mean_price": 120.0, "volume": 1000,
    })
    snap = history.get_snapshot("NVDA", "2026-08-01")
    assert snap["last_close"] == 100.0
    assert snap["trailing_pe"] == 30.0


def test_save_snapshot_upserts_same_day():
    import history
    history.save_snapshot("2026-08-01", "NVDA", {"last_close": 100.0, "trailing_pe": 30.0,
                                                    "target_mean_price": 120.0, "volume": 1000})
    history.save_snapshot("2026-08-01", "NVDA", {"last_close": 105.0, "trailing_pe": 31.0,
                                                    "target_mean_price": 125.0, "volume": 2000})
    snap = history.get_snapshot("NVDA", "2026-08-01")
    assert snap["last_close"] == 105.0
    assert len(history.get_snapshots_since("NVDA", "2026-01-01")) == 1


def test_get_snapshot_missing_returns_none():
    import history
    assert history.get_snapshot("NVDA", "2026-08-01") is None


def test_get_snapshots_since_orders_oldest_first():
    import history
    history.save_snapshot("2026-08-03", "NVDA", {"last_close": 3.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    history.save_snapshot("2026-08-01", "NVDA", {"last_close": 1.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    history.save_snapshot("2026-08-02", "NVDA", {"last_close": 2.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    rows = history.get_snapshots_since("NVDA", "2026-08-01")
    assert [r["date"] for r in rows] == ["2026-08-01", "2026-08-02", "2026-08-03"]


def test_get_latest_snapshot_before():
    import history
    history.save_snapshot("2026-08-01", "NVDA", {"last_close": 1.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    history.save_snapshot("2026-08-05", "NVDA", {"last_close": 5.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    assert history.get_latest_snapshot_before("NVDA", "2026-08-06")["date"] == "2026-08-05"
    assert history.get_latest_snapshot_before("NVDA", "2026-08-05")["date"] == "2026-08-01"
    assert history.get_latest_snapshot_before("NVDA", "2026-08-01") is None


def test_snapshots_are_isolated_per_symbol():
    import history
    history.save_snapshot("2026-08-01", "NVDA", {"last_close": 1.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    history.save_snapshot("2026-08-01", "AAPL", {"last_close": 2.0, "trailing_pe": None,
                                                    "target_mean_price": None, "volume": None})
    assert history.get_snapshot("NVDA", "2026-08-01")["last_close"] == 1.0
    assert history.get_snapshot("AAPL", "2026-08-01")["last_close"] == 2.0
