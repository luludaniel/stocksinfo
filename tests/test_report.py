import report


def _sig(symbol, severity, message="테스트 신호"):
    return {"symbol": symbol, "severity": severity, "type": "x", "message": message}


def _pos(**overrides):
    base = {"week52_pct": 41.0, "pct_vs_ma200": -3.0, "relative_strength_6m_pct": 12.0}
    base.update(overrides)
    return base


def test_no_signal_day_has_reassurance_line_and_no_detail_section():
    watchlist = {"NVDA": _pos(), "AAPL": _pos()}
    text = report.build_report([], watchlist, {}, "2026-08-02", [])
    assert "신호 0건" in text
    assert "오늘은 관심종목에 특이사항이 없습니다" in text
    assert "상세" not in text


def test_build_header_groups_by_severity():
    watchlist = {"NVDA": _pos(), "AAPL": _pos(), "TSLA": _pos()}
    signals = [_sig("NVDA", "red", "200일선 하향 이탈"), _sig("AAPL", "yellow", "PER 밴드 상단")]
    header = report.build_header(signals, watchlist, {}, "2026-08-02")
    assert "🔴 확인 필요 (1)" in header
    assert "🟡 관찰 (1)" in header
    assert "⚪ 정상 범위 (1)" in header
    assert "TSLA" in header
    assert "신호 2건" in header


def test_build_header_omits_empty_groups():
    header = report.build_header([], {"NVDA": _pos()}, {}, "2026-08-02")
    assert "🔴" not in header
    assert "🟡" not in header
    assert "⚪ 정상 범위 (1)" in header


def test_build_header_shows_position_summary_for_normal_symbols():
    watchlist = {"NVDA": _pos(week52_pct=41.0, pct_vs_ma200=-3.0, relative_strength_6m_pct=12.0)}
    header = report.build_header([], watchlist, {}, "2026-08-02")
    assert "52주 41%" in header
    assert "200일선 -3%" in header
    assert "6M +12%p" in header


def test_build_header_shows_failed_symbols_separately_from_normal():
    watchlist = {"NVDA": {"error": "rate limited"}, "AAPL": _pos()}
    header = report.build_header([], watchlist, {}, "2026-08-02")
    assert "⚠️ 수집 실패 (1)" in header
    assert "NVDA" in header
    assert "⚪ 정상 범위 (1)" in header
    assert "AAPL" in header


def test_all_symbols_failed_is_not_reported_as_quiet_day():
    # Regression: a total collection failure must not read identical to a
    # genuinely quiet day just because zero real signals were produced.
    watchlist = {"NVDA": {"error": "boom"}, "AAPL": {"error": "boom"}}
    text = report.build_report([], watchlist, {}, "2026-08-02", [])
    assert "오늘은 관심종목에 특이사항이 없습니다" not in text
    assert "⚠️ 수집 실패 (2)" in text


def test_build_header_uses_display_names_when_available():
    watchlist = {"005930.KS": _pos()}
    names = {"005930.KS": "삼성전자"}
    header = report.build_header([], watchlist, names, "2026-08-02")
    assert "005930.KS 삼성전자" in header


def test_build_header_never_drops_unknown_severity():
    watchlist = {"NVDA": _pos()}
    signals = [_sig("NVDA", "purple", "미래에 추가될 심각도")]
    header = report.build_header(signals, watchlist, {}, "2026-08-02")
    assert "purple" in header
    assert "미래에 추가될 심각도" in header


def test_build_report_includes_calendar_history_note_and_detail():
    watchlist = {"NVDA": _pos()}
    signals = [_sig("NVDA", "yellow")]
    text = report.build_report(
        signals, watchlist, {}, "2026-08-02", ["NVDA 실적(수)"],
        detail_text="NVDA — 해설", history_note="히스토리 축적 5일차",
    )
    assert "📅 이번 주  NVDA 실적(수)" in text
    assert "상세" in text
    assert "NVDA — 해설" in text
    assert "히스토리 축적 5일차" in text
    assert "투자 참고용" in text


def test_build_report_without_detail_has_no_detail_section():
    watchlist = {"NVDA": _pos()}
    signals = [_sig("NVDA", "yellow")]
    text = report.build_report(signals, watchlist, {}, "2026-08-02", [])
    assert "상세" not in text


def test_symbol_label_alignment_does_not_break_on_long_tickers():
    # Regression: fixed-width padding (`{symbol:<8}`) breaks visually once a
    # ticker/name is longer than the padding width — use a plain separator
    # instead of column alignment that silently corrupts for longer labels.
    watchlist = {"005930.KS": _pos()}
    header = report.build_header([], watchlist, {}, "2026-08-02")
    assert "005930.KS — 52주" in header


def _focus(symbol, rank, score, message="200일선 상향 돌파"):
    return {"symbol": symbol, "rank": rank, "score": score, "signals": [{"message": message}]}


def test_focus_block_replaces_severity_groups_with_ranked_list():
    watchlist = {"NVDA": _pos(), "AAPL": _pos(), "TSLA": _pos()}
    signals = [_sig("NVDA", "red"), _sig("AAPL", "yellow")]
    focus = [_focus("NVDA", 1, 3.5), _focus("AAPL", 2, 1.0, "PER 밴드 상단")]
    header = report.build_header(signals, watchlist, {}, "2026-08-02", blocks={"focus", "positions"}, focus=focus)
    assert "🎯 오늘 볼 순서 (2)" in header
    assert "1. NVDA (점수 3.5) — 200일선 상향 돌파" in header
    assert "🔴 확인 필요" not in header
    assert "⚪ 정상 범위 (1)" in header  # TSLA still shows, it's not in focus


def test_without_focus_block_falls_back_to_severity_groups():
    watchlist = {"NVDA": _pos()}
    signals = [_sig("NVDA", "red")]
    focus = [_focus("NVDA", 1, 3.0)]
    header = report.build_header(signals, watchlist, {}, "2026-08-02", blocks={"positions"}, focus=focus)
    assert "🎯" not in header
    assert "🔴 확인 필요 (1)" in header


def test_positions_block_disabled_hides_normal_section():
    watchlist = {"NVDA": _pos()}
    header = report.build_header([], watchlist, {}, "2026-08-02", blocks={"focus"}, focus=[])
    assert "정상 범위" not in header


def test_calendar_block_disabled_hides_calendar_line_even_when_events_exist():
    watchlist = {"NVDA": _pos()}
    text = report.build_report([_sig("NVDA", "yellow")], watchlist, {}, "2026-08-02",
                                ["NVDA 실적(수)"], blocks={"positions"})
    assert "이번 주" not in text


def test_discovery_block_renders_candidates_with_warning():
    watchlist = {"NVDA": _pos()}
    discovery = [{"symbol": "AMD", "why": "NVDA와 동일 섹터 · 기사 4건"}]
    text = report.build_report([], watchlist, {}, "2026-08-02", [], blocks={"positions", "discovery"}, discovery=discovery)
    assert "🔎 오늘 기사에서 뜬 종목 (1)" in text
    assert "AMD — NVDA와 동일 섹터" in text
    assert report.DISCOVERY_WARNING in text


def test_discovery_block_disabled_hides_section_even_with_candidates():
    watchlist = {"NVDA": _pos()}
    discovery = [{"symbol": "AMD", "why": "reason"}]
    text = report.build_report([], watchlist, {}, "2026-08-02", [], blocks={"positions"}, discovery=discovery)
    assert "AMD" not in text


def test_default_blocks_preserve_pre_phase9_behavior():
    # No blocks passed at all -> identical to the old hardcoded behavior.
    watchlist = {"NVDA": _pos()}
    signals = [_sig("NVDA", "red")]
    text = report.build_report(signals, watchlist, {}, "2026-08-02", ["NVDA 실적(수)"])
    assert "🔴 확인 필요 (1)" in text
    assert "이번 주  NVDA 실적(수)" in text
