import feedparser
from datetime import datetime, timezone


RSS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/companyNews"),
    ("Investing.com KR", "https://kr.investing.com/rss/news.rss"),
    ("Naver Finance", "https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258"),
]

MAX_PER_FEED = 5


def fetch() -> list[dict]:
    articles = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:MAX_PER_FEED]:
                published = entry.get("published", "")
                articles.append({
                    "source": source_name,
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "published": published,
                })
        except Exception:
            pass

    return articles


if __name__ == "__main__":
    import json
    for a in fetch():
        print(json.dumps(a, ensure_ascii=False))
