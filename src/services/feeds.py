import feedparser
from apify import Actor
from typing import List
from ..models import ArticleCandidate, InputConfig

# Map of standard feeds (Preserving your list)
# Multi-Niche Feed Map
NICHE_FEED_MAP = {
    # 📰 Major News (Fallback/General)
    "general": {
         "cnn": "http://rss.cnn.com/rss/edition.rss",
         "bbc": "http://feeds.bbci.co.uk/news/rss.xml",
    },
    
    # 🎮 Gaming & Esports
    "gaming": {
        "esportsinsider": "https://esportsinsider.com/feed",
        "ign-articles": "https://www.ign.com/rss/v2/articles/feed",
        "pcgamer": "https://www.pcgamer.com/feeds.xml",
        "polygon": "https://www.polygon.com/feed/",
        "gamespot-news": "https://www.gamespot.com/feeds/game-news",
        "kotaku": "https://kotaku.com/feed",
        "vgc-news": "https://www.videogameschronicle.com/category/news/feed/",
        "gematsu": "https://www.gematsu.com/feed",
        "nintendo-life": "https://www.nintendolife.com/feeds/latest",
    },

    # 💰 Crypto & DeFi
    "crypto": {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "decrypt": "https://decrypt.co/feed",
        "the-defiant": "https://thedefiant.io/api/feed",
        "blockonomi": "https://blockonomi.com/feed/",
        "cryptoslate": "https://cryptoslate.com/feed/",
        "bitcoin-magazine": "https://bitcoinmagazine.com/feed",
        "unchained-crypto": "https://unchainedcrypto.com/feed/",
        "zerohedge": "https://cms.zerohedge.com/fullrss2.xml",
        "messari": "https://messari.io/rss",
        "yearn-finance": "https://paragraph.com/api/blogs/rss/@yearn",
        "axie-infinity": "https://blog.axieinfinity.com/feed"
    },

    # 💻 Tech & Dev
    "tech": {
        "aws-web3": "https://aws.amazon.com/blogs/web3/feed/",
        "hackernoon": "https://hackernoon.com/feed",
        "ethereum-foundation": "https://blog.ethereum.org/en/feed.xml",
        "web3-labs": "https://blog.web3labs.com/rss/",
        "chainlink": "https://blog.chain.link/feed/",
        "metamask": "https://metamask.io/news-rss.xml",
        "blockchain-solutions": "https://blockchainsolutions.com.sa/feed/",
        "tekrevol": "https://www.tekrevol.com/blogs/feed/",
        "futuramo": "https://futuramo.com/blog/feed/",
    },

    # ⚛️ Nuclear Energy
    "nuclear": {
        "dmre": "https://www.dmre.gov.za/DesktopModules/Blog/API/RSS/Get?tabid=161&moduleid=1292&blog=3",
        "necsa": "https://www.necsa.co.za/feed",
        "eskom": "https://www.eskom.co.za/feed",
        "energy-council": "https://www.energycouncil.org.za/feed",
        "crses": "https://www.crses.sun.ac.za/feed",
        "gov-blog": "https://www.gov.za/blog-feeds",
        "gov-news": "https://www.gov.za/news-feed",
        "nnr": "https://nnr.co.za/feed",
        "engineering-news": "https://www.engineeringnews.co.za/page/energy/feed",
        "esi-africa": "https://www.esi-africa.com/news/feed/",
        "world-nuclear": "https://world-nuclear-news.org/?rss=feed",
        "iaea-news": "https://www.iaea.org/feeds/topnews",
        "iaea-press": "https://www.iaea.org/feeds/pressalerts",
        "nucnet": "https://www.nucnet.org/feed.rss"
    },

    # 🎓 Education
    "education": {
        "brainscape": "https://www.brainscape.com/academy/rss/",
        "edweek": "https://www.edweek.org/index.rss",
        "edsurge": "https://www.edsurge.com/articles_rss",
        "stevehargadon": "https://www.stevehargadon.com/feeds/posts/default?alt=rss",
        "classwork": "https://classwork.com/feed/",
        "kqed": "https://ww2.kqed.org/news/feed/",
        "edcircuit": "https://edcircuit.com/feed/",
        "ednewsdaily": "https://www.ednewsdaily.com/feed/",
        "theedublogger": "https://www.theedublogger.com/feed/",
        "edtechdigest": "https://www.edtechdigest.com/feed/",
        "edtechreview": "https://www.edtechreview.in/feed/",
        "fortelabs": "https://fortelabs.com/feed/",
        "fenews": "https://www.fenews.co.uk/feed/",
        "charteredcollege": "https://chartered.college/feed/",
        "elearningindustry": "https://feeds.feedburner.com/elearningindustry",
    },

    # 🌾 FoodTech & Agri
    "foodtech": {
        "agfundernews": "https://agfundernews.com/feed",
        "igrownews": "https://igrownews.com/feed/",
        "foodtechconnect": "https://foodtechconnect.com/feed/",
        "agriculturedive": "https://www.agriculturedive.com/feeds/news/",
        "agrivi": "https://www.agrivi.com/feed/",
        "thriveagrifood": "https://thriveagrifood.com/sitemap-custom-posts.xml?type=articles",
        "foodnavigator": "https://www.foodnavigator.com/arc/outboundfeeds/rss/",
        "ifarm": "https://ifarm.fi/rss.xml",
        "icl_planet": "https://www.icl-planet.com/feed/",
        "forwardfooding": "https://forwardfooding.com/feed/",
        "branchfood": "https://www.branchfood.com/blog?format=rss",
        "futurefoodinstitute": "https://futurefoodinstitute.org/feed/",
        "thespoon": "https://thespoon.tech/feed/",
        "fooddive": "https://www.fooddive.com/feeds/news/",
        "agritechtomorrow": "https://www.agritechtomorrow.com/rss/news/",
        "vertical_farming": "https://vertical-farming.net/feed/",
        "agdaily": "https://www.agdaily.com/category/news/feed/",
        "freightfarms": "https://www.freightfarms.com/blog?format=rss",
        "urbanagnews": "https://urbanagnews.com/feed/",
        "foodbusinessnews": "https://www.foodbusinessnews.net/rss/articles",
        "agri_pulse": "https://www.agri-pulse.com/rss/articles",
        "greenqueen": "https://www.greenqueen.com.hk/feed/",
        "agrigateone": "https://agrigateone.com/blog/rss.xml"
    },

    # 💪 Health & Wellness
    "health": {
        "mens-health": "https://www.menshealth.com/rss/all.xml/",
        "myfitnesspal": "https://blog.myfitnesspal.com/feed",
        "born-fitness": "https://www.bornfitness.com/feed/",
        "breaking-muscle": "https://breakingmuscle.com/feed/",
        "fitnessista": "https://fitnessista.com/feed/",
        "nasm": "https://blog.nasm.org/rss.xml",
        "popsugar-fitness": "https://www.popsugar.com/feed",
        "health": "https://feeds-api.dotdashmeredith.com/v1/rss/google/3a6c43d9-d394-4797-9855-97f429e5b1ff",
        "healthshots": "https://www.healthshots.com/rss-feeds/",
        "mommypotamus": "https://mommypotamus.com/feed",
        "natural-living-ideas": "https://www.naturallivingideas.com/feed",
    },

    # 💎 Luxury & Lifestyle
    "luxury": {
        "trulyclassy": "https://www.trulyclassy.com/feed/",
        "luxurylaunches": "https://luxurylaunches.com/web-stories/feed/",
        "robbreport": "https://robbreport.com/feed/",
        "theluxuryeditor": "https://theluxuryeditor.com/feed/",
        "luxurynewsonline": "https://luxurynewsonline.com/feed/",
        "luxuo": "https://www.luxuo.com/feed",
        "luxebible": "https://luxebible.com/category/lifestyle/feed/",
        "luxurialifestyle": "https://www.luxurialifestyle.com/feed/",
        "tempusmagazine": "https://tempusmagazine.co.uk/feed",
        # Adding a few key Luxury Daily categories (concatenated in map, but explicit here)
        "luxurydaily-news": "https://www.luxurydaily.com/category/resources/news-briefs/feed/",
    },

    # 🏠 Real Estate
    "realestate": {
        "realtor": "https://www.realtor.com/news/feed/",
        "housingwire": "https://www.housingwire.com/feed/",
        "rismedia": "https://www.rismedia.com/feed/",
        "forbes_realestate": "https://www.forbes.com/real-estate/feed/", 
        "worldpropertyjournal": "https://www.worldpropertyjournal.com/feed.xml",
        "biggerpockets": "https://www.biggerpockets.com/blog/feed",
        "sothebys": "https://www.sothebysrealty.com/extraordinary-living-blog/feed/",
        "luxurypresence": "https://www.luxurypresence.com/blogs/category/news-press/feed/",
        "therealdeal_ny": "https://therealdeal.com/new-york/feed/",
        "proptech-weekly": "https://proptechweekly.com/feed",
        "propertyweek": "https://www.propertyweek.com/feed",
    },

    # 🛍️ Retail & Ecommerce
    "retail": {
        "retailnewsai": "https://retailnews.ai/feed/",
        "retailinnovation": "https://retail-innovation.com/feed/",
        "ecommercetimes": "https://www.ecommercetimes.com/feed/",
        "ecommercenewseu": "https://ecommercenews.eu/feed/",
        "digitalcommerce360": "https://www.digitalcommerce360.com/type/news/feed/",
        "ft_ecommerce": "https://www.ft.com/ecommerce?format=rss",
        "retaildive": "https://www.retaildive.com/feeds/news/",
        "retailtechhub": "https://retailtechinnovationhub.com/home?format=rss",
        "retailtouchpoints": "https://www.retailtouchpoints.com/feed",
        "retailwire": "https://retailwire.com/feed/",
        "shopify-blog": "https://www.shopify.com/blog/feed.xml",
    },

    # 📱 Social Media
    "social": {
        "later": "https://later.com/rss.xml",
        "digital-agency-network": "https://digitalagencynetwork.com/feed",
        "influencity": "https://influencity.com/blog/en/rss.xml",
        "hootsuite": "https://blog.hootsuite.com/feed",
        "buffer": "https://buffer.com/resources/rss/",
        "social-media-examiner": "https://www.socialmediaexaminer.com/feed",
        "sproutsocial": "https://sproutsocial.com/insights/feed/",
    },

    # 🚀 VC & Startups
    "vc": {
        "techcrunch": "https://techcrunch.com/feed/",
        "venturebeat": "https://venturebeat.com/feed/",
        "sifted": "https://sifted.eu/feed",
        "ycombinator": "https://blog.ycombinator.com/rss/",
        "a16z": "https://a16z.com/feed/",
        "sequoia": "https://www.sequoiacap.com/feed/",
        "tech_eu": "https://tech.eu/feed/",
        "saastr": "https://www.saastr.com/feed/",
        "crunchbase": "https://news.crunchbase.com/feed/",
        "finsmes": "https://www.finsmes.com/feed",
    }
}

def fetch_feed_data(config: InputConfig) -> List[ArticleCandidate]:
    """Fetches articles from RSS feeds based on niche."""
    
    # 1. TEST MODE
    if config.runTestMode:
        Actor.log.info(f"🧪 TEST MODE: Generating dummy feed data for niche '{config.niche}'.")
        return [
            ArticleCandidate(
                title=f"[{config.niche.upper()}] Major Industry Annoucement",
                url="https://example.com/breaking-news",
                source="TestFeed",
                published="Fri, 01 Dec 2025 12:00:00 GMT",
                original_summary="A major event has occurred in the industry."
            ),
             ArticleCandidate(
                title=f"[{config.niche.upper()}] New Innovation Revealed",
                url="https://example.com/innovation",
                source="TestFeed",
                published="Fri, 01 Dec 2025 14:00:00 GMT"
            )
        ]

    # 2. REAL MODE
    urls = []
    
    # Logic to determine which niches to fetch
    target_niches = []
    if config.niche == "all":
        target_niches = [k for k in NICHE_FEED_MAP.keys() if k != "all"]
    else:
        target_niches = [config.niche]
    
    Actor.log.info(f"Fetching feeds for niches: {target_niches}")

    for niche in target_niches:
        feed_map = NICHE_FEED_MAP.get(niche, {})
        
        if config.source == "custom" and config.customFeedUrl:
             if not urls: # Only add once
                 urls.append({"url": config.customFeedUrl, "niche": config.niche if config.niche != "all" else "general"})
             break
        
        elif config.source == "all":
            for url in feed_map.values():
                urls.append({"url": url, "niche": niche})
        
        elif config.source in feed_map:
            urls.append({"url": feed_map[config.source], "niche": niche})

    Actor.log.info(f"Found {len(urls)} feeds to process. Starting parallel fetch...")

    feed_data = []
    
    # helper for parallel execution
    def process_feed_url(entry):
        url = entry["url"]
        niche_context = entry["niche"]
        local_results = []
        try:
            # Actor.log.info(f"Fetching RSS: {url} [{niche_context}]") # Reduced noise
            feed = feedparser.parse(url)
            
            for entry_data in feed.entries:
                # Basic validation
                if not hasattr(entry_data, 'title') or not hasattr(entry_data, 'link'):
                    continue

                # TIME FILTERING
                if not is_recent(entry_data.get('published'), config.timeLimit):
                    continue
                    
                local_results.append(
                    ArticleCandidate(
                        title=entry_data.title,
                        url=entry_data.link,
                        source=feed.feed.get('title', 'Unknown Feed'),
                        published=entry_data.get('published'),
                        original_summary=entry_data.get('summary') or entry_data.get('description'),
                        niche=niche_context 
                    )
                )
        except Exception as e:
            Actor.log.error(f"Failed to fetch {url}: {e}")
        return local_results

    # Parallel Execution
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_feed_url, u) for u in urls]
        for future in concurrent.futures.as_completed(futures):
            feed_data.extend(future.result())

    # Deduplicate by URL
    seen = set()
    unique_articles = []
    for art in feed_data:
        if art.url not in seen:
            unique_articles.append(art)
            seen.add(art.url)
    
    Actor.log.info(f"✅ Fetched {len(unique_articles)} recent unique articles (after time filter).")
    return unique_articles[:config.maxArticles]

# --- Helper ---
from dateutil import parser
from datetime import datetime, timedelta, timezone

def is_recent(date_str: str, time_limit: str) -> bool:
    """
    Checks if article date is within the time limit.
    """
    if not date_str: return True # If no date, assume recent/relevant
    
    try:
        pub_date = parser.parse(date_str)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        
        limit_hours = 24 * 7 # Default 1 week
        if time_limit == "24h": limit_hours = 24
        elif time_limit == "48h": limit_hours = 48
        elif time_limit == "1w": limit_hours = 24 * 7
        elif time_limit == "1m": limit_hours = 24 * 30
        
        cutoff = now - timedelta(hours=limit_hours)
        
        return pub_date >= cutoff
    except:
        return True # If parse fails, include it just in case