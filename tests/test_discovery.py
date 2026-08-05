from unittest.mock import patch

import discovery


def _pos(week52_pct=50.0, error=None):
    if error:
        return {"error": error}
    return {"week52_pct": week52_pct}


def test_disabled_config_returns_empty_without_any_calls():
    with patch("discovery.extract_tickers_from_headlines") as mock_extract:
        result = discovery.build_discovery({}, [{"title": "news"}], {"enabled": False})
    assert result == []
    mock_extract.assert_not_called()


def test_no_headlines_returns_empty_without_llm_call():
    with patch("discovery.extract_tickers_from_headlines") as mock_extract:
        result = discovery.build_discovery({}, [], None)
    assert result == []
    mock_extract.assert_not_called()


def test_hallucinated_ticker_is_dropped_when_price_history_unresolvable():
    # The core hallucination guard: watchlist_stocks.fetch() returning
    # nothing for a ticker (no real price history) means it never appears
    # in the final candidate list, no matter what the LLM claimed.
    general_articles = [{"title": "FAKECO surges on rumors"}]
    with patch("discovery.extract_tickers_from_headlines",
               return_value=[{"ticker": "FAKECO", "name": "Fake Co", "mentions": 5}]), \
         patch("discovery.watchlist_stocks.fetch", return_value={}), \
         patch("discovery.fundamentals_collector.fetch", return_value={}):
        result = discovery.build_discovery({}, general_articles, None)
    assert result == []


def test_valid_candidate_passes_through_with_metrics():
    general_articles = [{"title": "AMD launches new chip"}, {"title": "AMD stock jumps"}]
    with patch("discovery.extract_tickers_from_headlines",
               return_value=[{"ticker": "AMD", "name": "AMD", "mentions": 3}]), \
         patch("discovery.watchlist_stocks.fetch", return_value={"AMD": _pos(week52_pct=76.0)}), \
         patch("discovery.fundamentals_collector.fetch",
               return_value={"AMD": {"name": "Advanced Micro Devices", "trailing_pe": 42.1, "market_cap": 2.6e11}}):
        result = discovery.build_discovery({}, general_articles, None)

    assert len(result) == 1
    c = result[0]
    assert c["symbol"] == "AMD"
    assert c["name"] == "Advanced Micro Devices"
    assert c["basic"]["trailing_pe"] == 42.1
    assert c["basic"]["week52_pct"] == 76.0
    assert "3건" in c["why"]


def test_matching_headlines_strips_corporate_suffix():
    # Regression: yfinance's formal name ("Broadcom Inc.") almost never
    # appears verbatim in a headline ("AMD Vs. Broadcom") — matching has to
    # drop the corporate suffix or it silently finds nothing.
    headlines = ["AMD Vs. Broadcom: Why Broadcom is Actually Nvidia's Biggest Problem"]
    matches = discovery._matching_headlines("AVGO", "Broadcom Inc.", headlines)
    assert len(matches) == 1


def test_simplify_name_strips_known_suffixes():
    assert discovery._simplify_name("Broadcom Inc.") == "broadcom"
    assert discovery._simplify_name("Advanced Micro Devices, Inc") == "advanced micro devices"
    assert discovery._simplify_name("Samsung Electronics Co., Ltd.") == "samsung electronics"
    assert discovery._simplify_name("") == ""


def test_already_watchlisted_ticker_is_excluded():
    watchlist = {"NVDA": _pos()}
    with patch("discovery.extract_tickers_from_headlines") as mock_extract, \
         patch("discovery.watchlist_stocks.fetch", return_value={}), \
         patch("discovery.fundamentals_collector.fetch", return_value={}):
        mock_extract.return_value = [{"ticker": "NVDA", "name": "NVIDIA", "mentions": 5}]
        result = discovery.build_discovery(watchlist, [{"title": "NVDA news"}], None)

    assert result == []
    # excluded set should have been passed through to the LLM call too
    assert mock_extract.call_args[0][1] == {"NVDA"}


def test_below_min_mentions_is_filtered_out():
    with patch("discovery.extract_tickers_from_headlines",
               return_value=[{"ticker": "AMD", "name": "AMD", "mentions": 1}]), \
         patch("discovery.watchlist_stocks.fetch", return_value={"AMD": _pos()}), \
         patch("discovery.fundamentals_collector.fetch", return_value={"AMD": {"market_cap": 1e10}}):
        result = discovery.build_discovery({}, [{"title": "AMD news"}], {"min_article_mentions": 2})
    assert result == []


def test_below_min_market_cap_is_filtered_out():
    with patch("discovery.extract_tickers_from_headlines",
               return_value=[{"ticker": "SMALLCO", "name": "Small Co", "mentions": 5}]), \
         patch("discovery.watchlist_stocks.fetch", return_value={"SMALLCO": _pos()}), \
         patch("discovery.fundamentals_collector.fetch", return_value={"SMALLCO": {"market_cap": 1_000_000}}):
        result = discovery.build_discovery({}, [{"title": "news"}], {"min_market_cap_usd": 1_000_000_000})
    assert result == []


def test_max_candidates_caps_results_sorted_by_market_cap():
    with patch("discovery.extract_tickers_from_headlines", return_value=[
        {"ticker": "A", "name": "A", "mentions": 3},
        {"ticker": "B", "name": "B", "mentions": 3},
        {"ticker": "C", "name": "C", "mentions": 3},
    ]), \
         patch("discovery.watchlist_stocks.fetch", return_value={
             "A": _pos(), "B": _pos(), "C": _pos(),
         }), \
         patch("discovery.fundamentals_collector.fetch", return_value={
             "A": {"market_cap": 1e9}, "B": {"market_cap": 3e9}, "C": {"market_cap": 2e9},
         }):
        result = discovery.build_discovery({}, [{"title": "news"}], {"max_candidates": 2})

    assert [c["symbol"] for c in result] == ["B", "C"]


def test_duplicate_tickers_from_llm_are_deduped():
    with patch("discovery.extract_tickers_from_headlines", return_value=[
        {"ticker": "AMD", "name": "AMD", "mentions": 3},
        {"ticker": "AMD", "name": "AMD", "mentions": 5},
    ]), \
         patch("discovery.watchlist_stocks.fetch", return_value={"AMD": _pos()}), \
         patch("discovery.fundamentals_collector.fetch", return_value={"AMD": {"market_cap": 1e10}}):
        result = discovery.build_discovery({}, [{"title": "news"}], None)
    assert len(result) == 1


def test_error_position_is_treated_as_unresolvable():
    with patch("discovery.extract_tickers_from_headlines",
               return_value=[{"ticker": "AMD", "name": "AMD", "mentions": 3}]), \
         patch("discovery.watchlist_stocks.fetch", return_value={"AMD": {"error": "boom"}}), \
         patch("discovery.fundamentals_collector.fetch", return_value={"AMD": {"market_cap": 1e10}}):
        result = discovery.build_discovery({}, [{"title": "news"}], None)
    assert result == []
