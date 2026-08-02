from unittest.mock import patch, MagicMock


def test_fetch_uses_recurring_fallback_without_api_key(monkeypatch):
    import collectors.economic_cal as ec
    monkeypatch.setattr(ec, "FRED_API_KEY", "")

    with patch("requests.get") as mock_get:
        result = ec.fetch()

    mock_get.assert_not_called()
    assert result["errors"] == []
    assert isinstance(result["events"], list)


def test_fetch_calls_fred_with_api_key_when_set(monkeypatch):
    import collectors.economic_cal as ec
    monkeypatch.setattr(ec, "FRED_API_KEY", "test-fred-key")

    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json.return_value = {"release_dates": [{"release_name": "CPI"}]}

    with patch("requests.get", return_value=resp) as mock_get:
        result = ec.fetch()

    assert mock_get.call_args.kwargs["params"]["api_key"] == "test-fred-key"
    assert any(e["name"] == "CPI" for e in result["events"])
    assert result["errors"] == []


def test_fetch_records_fred_failure_in_errors(monkeypatch):
    import collectors.economic_cal as ec
    monkeypatch.setattr(ec, "FRED_API_KEY", "test-fred-key")

    with patch("requests.get", side_effect=Exception("network error")):
        result = ec.fetch()

    assert len(result["errors"]) == 1
    assert "FRED" in result["errors"][0]
