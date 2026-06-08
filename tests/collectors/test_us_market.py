import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


def _mock_download(close_data):
    mock = MagicMock()
    mock.__getitem__ = lambda self, key: pd.DataFrame(close_data)
    return mock


def test_fetch_returns_indices(monkeypatch):
    import collectors.us_market as us

    close_df = pd.DataFrame(
        {"^GSPC": [5000.0, 5100.0], "^IXIC": [16000.0, 16200.0],
         "^DJI": [40000.0, 40500.0], "^VIX": [15.0, 16.0],
         "KRW=X": [1300.0, 1320.0], "GC=F": [2000.0, 2010.0],
         "CL=F": [80.0, 81.0], "XLK": [200.0, 205.0],
         "XLF": [40.0, 41.0], "XLE": [90.0, 91.0],
         "XLV": [130.0, 131.0], "XLY": [170.0, 172.0]}
    )
    mock_data = MagicMock()
    mock_data.__getitem__ = lambda self, key: close_df

    with patch("yfinance.download", return_value=mock_data):
        result = us.fetch()

    assert "indices" in result
    assert "sectors" in result
    assert "S&P 500" in result["indices"]
    assert result["indices"]["S&P 500"]["change_pct"] == 2.0


def test_fetch_handles_missing_symbol(monkeypatch):
    import collectors.us_market as us

    empty_df = pd.DataFrame({"^GSPC": [5000.0, 5100.0]})
    mock_data = MagicMock()
    mock_data.__getitem__ = lambda self, key: empty_df

    with patch("yfinance.download", return_value=mock_data):
        result = us.fetch()

    assert "indices" in result
