import json
import pytest
from pathlib import Path
from unittest.mock import patch


def test_load_watchlist_creates_default(tmp_path, monkeypatch):
    monkeypatch.setattr("store.WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr("store.RECIPIENTS_FILE", tmp_path / "recipients.json")
    from store import load_watchlist
    wl = load_watchlist()
    assert "us" in wl
    assert "kr" in wl
    assert isinstance(wl["us"], list)


def test_save_and_load_watchlist(tmp_path, monkeypatch):
    monkeypatch.setattr("store.WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr("store.RECIPIENTS_FILE", tmp_path / "recipients.json")
    from store import save_watchlist, load_watchlist
    data = {"us": ["NVDA", "AAPL"], "kr": ["005930.KS"]}
    save_watchlist(data)
    assert load_watchlist() == data


def test_load_recipients_creates_default(tmp_path, monkeypatch):
    monkeypatch.setattr("store.WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr("store.RECIPIENTS_FILE", tmp_path / "recipients.json")
    from store import load_recipients
    r = load_recipients()
    assert "emails" in r
    assert isinstance(r["emails"], list)


def test_save_and_load_recipients(tmp_path, monkeypatch):
    monkeypatch.setattr("store.WATCHLIST_FILE", tmp_path / "watchlist.json")
    monkeypatch.setattr("store.RECIPIENTS_FILE", tmp_path / "recipients.json")
    from store import save_recipients, load_recipients
    data = {"emails": ["a@test.com", "b@test.com"]}
    save_recipients(data)
    assert load_recipients() == data
