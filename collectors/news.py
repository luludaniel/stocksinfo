import logging

import feedparser

log = logging.getLogger(__name__)

# Reuters RSS was discontinued in 2020 (404) and the old Naver Finance URL is an
# HTML page, not RSS, so feedparser can't parse it — both were replaced with
# feeds that are actually alive.
RSS_FEEDS = [
    ("Investing.com KR", "https://kr.investing.com/rss/news.rss"),
    ("Google News - KR 증시", "https://news.google.com/rss/search?q=%EC%BD%94%EC%8A%A4%ED%94%BC+OR+%EC%A6%9D%EC%8B%9C&hl=ko&gl=KR&ceid=KR:ko"),
    ("Google News - US Markets", "https://news.google.com/rss/search?q=stock+market+OR+S%26P+500&hl=en-US&gl=US&ceid=US:en"),
]

MAX_PER_FEED = 5


def fetch() -> dict:
    """Fetch market news from RSS feeds.

    Returns {"articles": [...], "errors": [...]} instead of silently dropping
    failed feeds — a dead feed used to fail invisibly (`except: pass`), so
    "today's key issues" would go quietly empty with nothing in the logs.
    """
    articles = []
    errors = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                raise feed.bozo_exception or ValueError("feed parse error")
            for entry in feed.entries[:MAX_PER_FEED]:
                articles.append({
                    "source": source_name,
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            log.warning(f"[news] feed failed: {source_name}: {e}")
            errors.append(f"{source_name}: {e}")

    return {"articles": articles, "errors": errors}


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), indent=2, ensure_ascii=False))
