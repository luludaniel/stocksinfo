from datetime import date

import recommend


def _sig(symbol, severity):
    return {"symbol": symbol, "severity": severity, "type": "x", "message": "m"}


def test_zero_score_symbol_is_excluded():
    focus = recommend.build_focus([], {"NVDA": {}}, {}, {}, date(2026, 8, 2))
    assert focus == []


def test_red_signal_scores_higher_than_yellow():
    signals = [_sig("NVDA", "red"), _sig("AAPL", "yellow")]
    focus = recommend.build_focus(signals, {"NVDA": {}, "AAPL": {}}, {}, {}, date(2026, 8, 2))
    by_symbol = {f["symbol"]: f for f in focus}
    assert by_symbol["NVDA"]["score"] > by_symbol["AAPL"]["score"]


def test_focus_is_ranked_and_sorted_descending():
    signals = [_sig("AAPL", "yellow"), _sig("NVDA", "red")]
    focus = recommend.build_focus(signals, {"NVDA": {}, "AAPL": {}}, {}, {}, date(2026, 8, 2))
    assert [f["symbol"] for f in focus] == ["NVDA", "AAPL"]
    assert [f["rank"] for f in focus] == [1, 2]


def test_news_count_is_capped_at_three():
    related = {"NVDA": [{"title": f"n{i}"} for i in range(10)]}
    focus = recommend.build_focus([], {"NVDA": {}}, {}, related, date(2026, 8, 2))
    assert focus[0]["score_breakdown"]["news"] == recommend.MAX_NEWS_COUNTED * recommend.DEFAULT_FOCUS_CONFIG["news_weight"]
    assert len(focus[0]["news"]) == recommend.MAX_NEWS_COUNTED


def test_earnings_within_3_days_gets_event_bonus():
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-04"}}  # D-2
    focus = recommend.build_focus([], {"NVDA": {}}, fundamentals, {}, date(2026, 8, 2))
    assert focus[0]["score_breakdown"]["event"] == 2.0


def test_earnings_beyond_3_days_gets_no_bonus():
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-10"}}  # D-8
    focus = recommend.build_focus([], {"NVDA": {}}, fundamentals, {}, date(2026, 8, 2))
    assert focus == []


def test_ex_dividend_within_2_days_gets_event_bonus():
    fundamentals = {"NVDA": {"ex_dividend_date": "2026-08-03"}}  # D-1
    focus = recommend.build_focus([], {"NVDA": {}}, fundamentals, {}, date(2026, 8, 2))
    assert focus[0]["score_breakdown"]["event"] == 1.0


def test_both_event_bonuses_can_stack():
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-04", "ex_dividend_date": "2026-08-03"}}
    focus = recommend.build_focus([], {"NVDA": {}}, fundamentals, {}, date(2026, 8, 2))
    assert focus[0]["score_breakdown"]["event"] == 3.0


def test_errored_fundamentals_symbol_gets_no_event_bonus():
    fundamentals = {"NVDA": {"error": "boom"}}
    signals = [_sig("NVDA", "yellow")]
    focus = recommend.build_focus(signals, {"NVDA": {}}, fundamentals, {}, date(2026, 8, 2))
    assert focus[0]["score_breakdown"]["event"] == 0.0


def test_symbol_can_score_purely_from_news_with_no_signal():
    related = {"AMD": [{"title": "AMD news"}]}
    focus = recommend.build_focus([], {"AMD": {}}, {}, related, date(2026, 8, 2))
    assert len(focus) == 1
    assert focus[0]["symbol"] == "AMD"
    assert focus[0]["score_breakdown"]["severity"] == 0.0


def test_custom_focus_config_changes_weights():
    signals = [_sig("NVDA", "red")]
    custom_cfg = {"severity_weight": {"red": 10.0, "yellow": 1.0}, "news_weight": 0.5,
                  "event_bonus": {"earnings_d3": 2.0, "ex_dividend_d2": 1.0}}
    focus = recommend.build_focus(signals, {"NVDA": {}}, {}, {}, date(2026, 8, 2), focus_config=custom_cfg)
    assert focus[0]["score"] == 10.0


def test_score_breakdown_sums_to_total_score():
    signals = [_sig("NVDA", "red")]
    fundamentals = {"NVDA": {"next_earnings_date": "2026-08-04"}}
    related = {"NVDA": [{"title": "n1"}, {"title": "n2"}]}
    focus = recommend.build_focus(signals, {"NVDA": {}}, fundamentals, related, date(2026, 8, 2))
    b = focus[0]["score_breakdown"]
    assert focus[0]["score"] == round(b["severity"] + b["news"] + b["event"], 2)
