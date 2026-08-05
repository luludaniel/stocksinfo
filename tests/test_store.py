import json

import pytest


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("store.CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr("store.WATCHLIST_FILE", tmp_path / "config" / "watchlist.json")
    monkeypatch.setattr("store.REPORT_CONFIG_FILE", tmp_path / "config" / "report.json")
    monkeypatch.setattr("store._LEGACY_WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr("store._LEGACY_RECIPIENTS_FILE", tmp_path / "recipients.json")


def test_load_watchlist_creates_default_v2_when_nothing_exists():
    from store import load_watchlist, WATCHLIST_FILE
    wl = load_watchlist()
    assert wl["version"] == 2
    assert "profiles" in wl
    assert isinstance(wl["symbols"], list)
    assert len(wl["symbols"]) > 0
    assert WATCHLIST_FILE.exists()


def test_load_watchlist_migrates_v1_to_v2(tmp_path):
    from store import load_watchlist, _LEGACY_WATCHLIST_FILE

    _LEGACY_WATCHLIST_FILE.write_text(json.dumps({"us": ["NVDA", "AAPL"], "kr": ["005930.KS"]}))

    wl = load_watchlist()
    assert wl["version"] == 2
    symbols = {e["symbol"]: e for e in wl["symbols"]}
    assert set(symbols) == {"NVDA", "AAPL", "005930.KS"}
    assert symbols["NVDA"]["market"] == "us"
    assert symbols["005930.KS"]["market"] == "kr"
    assert symbols["NVDA"]["profile"] == "watching"


def test_migration_only_happens_once(tmp_path):
    # Once config/watchlist.json exists, it is authoritative even if the
    # legacy file is still sitting around (it always will be, briefly).
    from store import load_watchlist, save_watchlist, _LEGACY_WATCHLIST_FILE

    _LEGACY_WATCHLIST_FILE.write_text(json.dumps({"us": ["NVDA"], "kr": []}))
    save_watchlist({"version": 2, "profiles": {}, "symbols": [{"symbol": "CUSTOM", "market": "us"}]})

    wl = load_watchlist()
    assert [e["symbol"] for e in wl["symbols"]] == ["CUSTOM"]


def test_save_and_load_watchlist_roundtrip():
    from store import save_watchlist, load_watchlist
    data = {"version": 2, "profiles": {}, "symbols": [{"symbol": "NVDA", "market": "us", "profile": "watching"}]}
    save_watchlist(data)
    assert load_watchlist() == data


def test_watchlist_symbols_returns_flat_ticker_list():
    from store import watchlist_symbols
    wl = {"symbols": [{"symbol": "NVDA"}, {"symbol": "005930.KS"}]}
    assert watchlist_symbols(wl) == ["NVDA", "005930.KS"]


def test_resolve_symbol_config_uses_profile_when_no_override():
    from store import resolve_symbol_config
    watchlist = {
        "profiles": {"watching": {"signals": ["ma200_cross"], "thresholds": {"volume_spike_ratio": 2.0}}},
    }
    entry = {"symbol": "NVDA", "profile": "watching"}
    cfg = resolve_symbol_config(watchlist, entry)
    assert cfg["signals"] == ["ma200_cross"]
    assert cfg["thresholds"]["volume_spike_ratio"] == 2.0


def test_resolve_symbol_config_override_replaces_signals_entirely():
    from store import resolve_symbol_config
    watchlist = {
        "profiles": {"watching": {"signals": ["ma200_cross", "volume_spike"], "thresholds": {}}},
    }
    entry = {"symbol": "NVDA", "profile": "watching", "overrides": {"signals": ["earnings_soon"]}}
    cfg = resolve_symbol_config(watchlist, entry)
    assert cfg["signals"] == ["earnings_soon"]


def test_resolve_symbol_config_override_merges_thresholds_by_key():
    from store import resolve_symbol_config
    watchlist = {
        "profiles": {"core_holding": {
            "signals": ["volume_spike"],
            "thresholds": {"volume_spike_ratio": 3.0, "earnings_lookahead_days": 7},
        }},
    }
    entry = {"symbol": "NVDA", "profile": "core_holding",
              "overrides": {"thresholds": {"volume_spike_ratio": 3.5}}}
    cfg = resolve_symbol_config(watchlist, entry)
    # overridden key changes, sibling key from the profile survives
    assert cfg["thresholds"]["volume_spike_ratio"] == 3.5
    assert cfg["thresholds"]["earnings_lookahead_days"] == 7


def test_resolve_all_symbols_includes_market_name_memo():
    from store import resolve_all_symbols
    watchlist = {
        "profiles": {"watching": {"signals": [], "thresholds": {}}},
        "symbols": [{"symbol": "005930.KS", "name": "삼성전자", "market": "kr",
                     "profile": "watching", "memo": "장기 보유"}],
    }
    resolved = resolve_all_symbols(watchlist)
    assert resolved["005930.KS"]["market"] == "kr"
    assert resolved["005930.KS"]["name"] == "삼성전자"
    assert resolved["005930.KS"]["memo"] == "장기 보유"


def test_resolve_all_symbols_infers_market_when_missing():
    from store import resolve_all_symbols
    watchlist = {"profiles": {}, "symbols": [{"symbol": "NVDA"}, {"symbol": "000660.KS"}]}
    resolved = resolve_all_symbols(watchlist)
    assert resolved["NVDA"]["market"] == "us"
    assert resolved["000660.KS"]["market"] == "kr"


def test_resolve_all_symbols_passes_through_shares_and_avg_price():
    from store import resolve_all_symbols
    watchlist = {"profiles": {}, "symbols": [{"symbol": "NVDA", "shares": 10, "avg_price": 150.5}]}
    resolved = resolve_all_symbols(watchlist)
    assert resolved["NVDA"]["shares"] == 10
    assert resolved["NVDA"]["avg_price"] == 150.5


def test_resolve_all_symbols_shares_and_avg_price_default_to_none():
    from store import resolve_all_symbols
    watchlist = {"profiles": {}, "symbols": [{"symbol": "NVDA"}]}
    resolved = resolve_all_symbols(watchlist)
    assert resolved["NVDA"]["shares"] is None
    assert resolved["NVDA"]["avg_price"] is None


def test_load_report_config_creates_default():
    from store import load_report_config, REPORT_CONFIG_FILE
    cfg = load_report_config()
    assert cfg["version"] == 1
    assert cfg["email"]["recipients"] == []
    assert cfg["discovery"]["enabled"] is True
    assert REPORT_CONFIG_FILE.exists()


def test_load_report_config_migrates_legacy_recipients():
    from store import load_report_config, _LEGACY_RECIPIENTS_FILE
    _LEGACY_RECIPIENTS_FILE.write_text(json.dumps({"emails": ["a@test.com", "b@test.com"]}))
    cfg = load_report_config()
    assert cfg["email"]["recipients"] == ["a@test.com", "b@test.com"]


def test_save_and_load_report_config_roundtrip():
    from store import save_report_config, load_report_config
    data = {"version": 1, "email": {"recipients": ["x@test.com"], "blocks": ["focus"],
                                      "send_when_no_signal": "skip", "send_time_kst": "08:00"},
            "discovery": {"enabled": False}, "focus": {}}
    save_report_config(data)
    assert load_report_config() == data
