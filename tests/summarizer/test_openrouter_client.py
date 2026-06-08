import pytest
from unittest.mock import patch, MagicMock


def _mock_response(text):
    resp = MagicMock()
    resp.choices[0].message.content = text
    return resp


def test_summarize_returns_text(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    import importlib
    import summarizer.openrouter_client as oc
    importlib.reload(oc)

    with patch.object(oc.client.chat.completions, "create",
                      return_value=_mock_response("모닝 브리핑 내용")):
        result = oc.summarize({"us_market": {}, "kr_market": {}})

    assert result == "모닝 브리핑 내용"


def test_summarize_falls_back_on_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    import importlib
    import summarizer.openrouter_client as oc
    importlib.reload(oc)

    call_count = 0

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < len(oc.MODELS):
            raise Exception("rate limit")
        return _mock_response("폴백 결과")

    with patch.object(oc.client.chat.completions, "create", side_effect=mock_create):
        result = oc.summarize({})

    assert result == "폴백 결과"
    assert call_count > 1


def test_summarize_raises_when_all_models_fail(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    import importlib
    import summarizer.openrouter_client as oc
    importlib.reload(oc)

    with patch.object(oc.client.chat.completions, "create",
                      side_effect=Exception("all failed")):
        with pytest.raises(RuntimeError, match="모든 모델 실패"):
            oc.summarize({})
