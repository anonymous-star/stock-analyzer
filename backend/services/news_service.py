import feedparser
import httpx
from urllib.parse import quote
from datetime import datetime


def _parse_entry(entry: dict) -> dict:
    """Parse a single RSS feed entry into a news item."""
    published = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            published = None

    return {
        "title": entry.get("title", ""),
        "url": entry.get("link", ""),
        "source": entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else "",
        "published_at": published,
        "summary": entry.get("summary", "")[:300] if entry.get("summary") else "",
    }


def get_news(ticker: str, limit: int = 10) -> list[dict]:
    """Fetch news for a ticker via Google News RSS."""
    # Strip exchange suffix for better search results
    search_ticker = ticker.split(".")[0] if "." in ticker else ticker

    # Build search query
    query = quote(search_ticker + " stock")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

    news_items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            item = _parse_entry(entry)
            if item["title"]:
                news_items.append(item)
    except Exception:
        pass

    # Also try English news if we have fewer than desired
    if len(news_items) < limit // 2:
        try:
            en_query = quote(search_ticker + " stock news")
            en_url = f"https://news.google.com/rss/search?q={en_query}&hl=en&gl=US&ceid=US:en"
            en_feed = feedparser.parse(en_url)
            seen_titles = {item["title"] for item in news_items}
            for entry in en_feed.entries[:limit]:
                item = _parse_entry(entry)
                if item["title"] and item["title"] not in seen_titles:
                    news_items.append(item)
                    seen_titles.add(item["title"])
                if len(news_items) >= limit:
                    break
        except Exception:
            pass

    return news_items[:limit]


def get_news_headlines(ticker: str, limit: int = 5) -> list[str]:
    """Get just the headlines for AI analysis."""
    news = get_news(ticker, limit=limit)
    return [item["title"] for item in news if item["title"]]
