import report


def _sig(symbol, severity, message="테스트 신호"):
    return {"symbol": symbol, "severity": severity, "type": "x", "message": message}


def test_build_no_signal_report_is_short_and_has_no_detail_section():
    text = report.build_no_signal_report(["NVDA", "AAPL"], "2026-08-02", [])
    assert "신호 0건" in text
    assert "상세" not in text
    assert "NVDA" in text and "AAPL" in text


def test_build_header_groups_by_severity():
    signals = [_sig("NVDA", "red", "200일선 하향 이탈"), _sig("AAPL", "yellow", "PER 밴드 상단")]
    header = report.build_header(signals, ["NVDA", "AAPL", "TSLA"], "2026-08-02")
    assert "🔴 확인 필요 (1)" in header
    assert "🟡 관찰 (1)" in header
    assert "⚪ 정상 범위 (1)" in header
    assert "TSLA" in header
    assert "신호 2건" in header


def test_build_header_omits_empty_groups():
    header = report.build_header([], ["NVDA"], "2026-08-02")
    assert "🔴" not in header
    assert "🟡" not in header
    assert "⚪ 정상 범위 (1)" in header


def test_build_report_includes_calendar_and_detail():
    signals = [_sig("NVDA", "yellow")]
    text = report.build_report(signals, ["NVDA"], "2026-08-02", ["NVDA 실적(수)"], detail_text="NVDA — 해설")
    assert "📅 이번 주  NVDA 실적(수)" in text
    assert "상세" in text
    assert "NVDA — 해설" in text
    assert "투자 참고용" in text


def test_build_report_without_detail_has_no_detail_section():
    signals = [_sig("NVDA", "yellow")]
    text = report.build_report(signals, ["NVDA"], "2026-08-02", [])
    assert "상세" not in text
