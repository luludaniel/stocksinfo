import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("store.WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr("store.RECIPIENTS_FILE", tmp_path / "recipients.json")
    from web.app import app
    return TestClient(app, follow_redirects=True)


def test_dashboard_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "StocksInfo" in resp.text


def test_add_us_stock(client):
    resp = client.post("/watchlist/add", data={"market": "us", "symbol": "tsla"})
    assert resp.status_code == 200
    assert "TSLA" in resp.text


def test_delete_us_stock(client):
    client.post("/watchlist/add", data={"market": "us", "symbol": "NVDA"})
    resp = client.post("/watchlist/delete", data={"market": "us", "symbol": "NVDA"})
    assert resp.status_code == 200
    # hidden input value로 확인 (상태 메시지와 구분)
    assert 'value="NVDA"' not in resp.text


def test_add_recipient(client):
    resp = client.post("/recipients/add", data={"email": "test@gmail.com"})
    assert resp.status_code == 200
    assert "test@gmail.com" in resp.text


def test_delete_recipient(client):
    client.post("/recipients/add", data={"email": "del@gmail.com"})
    resp = client.post("/recipients/delete", data={"email": "del@gmail.com"})
    assert resp.status_code == 200
    assert "del@gmail.com" not in resp.text


def test_add_empty_stock_redirects(client):
    resp = client.post("/watchlist/add", data={"market": "us", "symbol": "  "})
    assert resp.status_code == 200


def test_no_duplicate_stock(client):
    client.post("/watchlist/add", data={"market": "us", "symbol": "MSFT"})
    client.post("/watchlist/add", data={"market": "us", "symbol": "MSFT"})
    resp = client.get("/")
    # hidden input value 기준으로 중복 여부 확인
    assert resp.text.count('value="MSFT"') == 1
