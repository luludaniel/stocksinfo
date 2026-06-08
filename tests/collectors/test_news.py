import pytest
from unittest.mock import patch, MagicMock


def _make_feed(entries):
    feed = MagicMock()
    feed.entries = entries
    return feed


def _make_entry(title, link, published="2026-06-08"):
    e = MagicMock()
    e.get = lambda k, d="": {"title": title, "link": link, "published": published}.get(k, d)
    return e


def test_fetch_returns_list():
    from collectors.news import fetch
    entries = [_make_entry(f"News {i}", f"http://test.com/{i}") for i in range(3)]
    with patch("feedparser.parse", return_value=_make_feed(entries)):
        result = fetch()
    assert isinstance(result, list)


def test_fetch_limits_per_feed():
    from collectors.news import MAX_PER_FEED, fetch
    entries = [_make_entry(f"News {i}", f"http://test.com/{i}") for i in range(20)]
    with patch("feedparser.parse", return_value=_make_feed(entries)):
        result = fetch()
    assert len(result) <= MAX_PER_FEED * 4  # 4 feeds


def test_fetch_handles_feed_error():
    from collectors.news import fetch
    with patch("feedparser.parse", side_effect=Exception("network error")):
        result = fetch()
    assert result == []
