import feedparser
from apify import Actor
from typing import List
from ..models import ArticleCandidate, InputConfig

# Map of standard feeds (Preserving your list)
FEED_MAP = {
    "esportsinsider": "https://esportsinsider.com/feed",
    "ign-articles": "https://www.ign.com/rss/v2/articles/feed",
    "pcgamer": "https://www.pcgamer.com/feeds.xml",
    "polygon": "https://www.polygon.com/feed/",
    "gamespot-news": "https://www.gamespot.com/feeds/game-news",
    "kotaku": "https://kotaku.com/feed",
    "vgc-news": "https://www.videogameschronicle.com/category/news/feed/",
    "gematsu": "https://www.gematsu.com/feed",
    "nintendo-life": "https://www.nintendolife.com/feeds/latest",
    # Add others as needed
}

def fetch_feed_data(config: InputConfig) -> List[ArticleCandidate]:
    """Fetches articles from RSS feeds."""
    
    # 1. TEST MODE
    if config.runTestMode:
        Actor.log.info("🧪 TEST MODE: Generating dummy feed data.")
        return [
            ArticleCandidate(
                title="Test Article: Half-Life 3 Announced",
                url="https://example.com/hl3",
                source="TestFeed",
                published="Fri, 01 Dec 2025 12:00:00 GMT",
                original_summary="Valve has finally announced the sequel."
            ),
            ArticleCandidate(
                title="Test Article: T1 wins Worlds 2025",
                url="https://example.com/t1-win",
                source="EsportsTest",
                published="Fri, 01 Dec 2025 10:00:00 GMT"
            )
        ]

    # 2. REAL MODE
    urls = []
    if config.source == "custom" and config.customFeedUrl:
        urls.append(config.customFeedUrl)
    elif config.source == "all":
        urls = list(FEED_MAP.values())
    elif config.source in FEED_MAP:
        urls.append(FEED_MAP[config.source])

    articles = []
    
    for url in urls:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get("title", "Unknown Source")
            
            for entry in feed.entries[:config.maxArticles]:
                articles.append(ArticleCandidate(
                    title=entry.get("title", "No Title"),
                    url=entry.get("link", ""),
                    source=source_name,
                    published=entry.get("published"),
                    original_summary=entry.get("summary", "")
                ))
        except Exception as e:
            Actor.log.warning(f"Failed to parse feed {url}: {e}")

    # Deduplicate by URL
    seen = set()
    unique_articles = []
    for art in articles:
        if art.url not in seen:
            unique_articles.append(art)
            seen.add(art.url)
            
    # Limit global total
    return unique_articles[:config.maxArticles]