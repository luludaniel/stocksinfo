import pytest
from unittest.mock import patch, MagicMock


def _make_feed(entries, bozo=False):
    feed = MagicMock()
    feed.entries = entries
    feed.bozo = bozo
    feed.bozo_exception = Exception("parse error") if bozo else None
    return feed


def _make_entry(title, link, published="2026-06-08"):
    e = MagicMock()
    e.get = lambda k, d="": {"title": title, "link": link, "published": published}.get(k, d)
    return e


def test_fetch_returns_dict_with_articles():
    from collectors.news import fetch
    entries = [_make_entry(f"News {i}", f"http://test.com/{i}") for i in range(3)]
    with patch("feedparser.parse", return_value=_make_feed(entries)):
        result = fetch()
    assert isinstance(result, dict)
    assert "articles" in result
    assert "errors" in result
    assert len(result["articles"]) > 0


def test_fetch_limits_per_feed():
    from collectors.news import MAX_PER_FEED, RSS_FEEDS, fetch
    entries = [_make_entry(f"News {i}", f"http://test.com/{i}") for i in range(20)]
    with patch("feedparser.parse", return_value=_make_feed(entries)):
        result = fetch()
    assert len(result["articles"]) <= MAX_PER_FEED * len(RSS_FEEDS)


def test_fetch_records_feed_error_without_raising():
    from collectors.news import RSS_FEEDS, fetch
    with patch("feedparser.parse", side_effect=Exception("network error")):
        result = fetch()
    assert result["articles"] == []
    assert len(result["errors"]) == len(RSS_FEEDS)


def test_fetch_records_bozo_feed_as_error():
    from collectors.news import fetch
    with patch("feedparser.parse", return_value=_make_feed([], bozo=True)):
        result = fetch()
    assert result["articles"] == []
    assert len(result["errors"]) > 0
