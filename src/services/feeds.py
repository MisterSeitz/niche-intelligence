import feedparser
from apify import Actor
from typing import List
from ..models import ArticleCandidate, InputConfig
import concurrent.futures
import random
import socket
from dateutil import parser
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Multi-Niche Feed Map (Merged from Niche + SA News)
NICHE_FEED_MAP = {
    # 🌍 General / All
    "general": {
         "cnn": "http://rss.cnn.com/rss/edition.rss",
         "bbc": "http://feeds.bbci.co.uk/news/rss.xml",
         "enca": "https://www.enca.com/rss.xml",
         "citizen": "https://www.citizen.co.za/feed",
         "dailymaverick": "https://www.dailymaverick.co.za/rss", 
    },

    # 🚨 Crime & Safety
    "crime": {
        "iol-crime": "https://iol.co.za/rss/iol/news/crime-and-courts/"
    },

    # 🇿🇦 South Africa (National News)
    "south_africa": {
        "iol-sa": "https://iol.co.za/rss/iol/news/south-africa/",
        "citizen-sa": "https://www.citizen.co.za/news/south-africa/feed/",
        "news24-top": "https://feeds.24.com/articles/news24/topstories/rss"
    },

    # 🧱 BRICS / Geopolitics
    "brics": {
        "iol-brics": "https://iol.co.za/rss/iol/news/brics/"
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
        "iol-tech": "https://iol.co.za/rss/iol/technology/"
    },

    # ⚡ Energy (General: Solar, Grid, Renewables)
    "energy": {
        "dmre": "https://www.dmre.gov.za/DesktopModules/Blog/API/RSS/Get?tabid=161&moduleid=1292&blog=3",
        "eskom": "https://www.eskom.co.za/feed",
        "energy-council": "https://www.energycouncil.org.za/feed",
        "crses": "https://www.crses.sun.ac.za/feed",
        "gov-blog": "https://www.gov.za/blog-feeds",
        "gov-news": "https://www.gov.za/news-feed",
        "engineering-news": "https://www.engineeringnews.co.za/page/energy/feed",
        "esi-africa": "https://www.esi-africa.com/news/feed/",
        "iol-energy": "https://iol.co.za/rss/iol/news/energy/"
    },

    # ⚛️ Nuclear Energy (Strictly Nuclear)
    "nuclear": {
        "necsa": "https://www.necsa.co.za/feed",
        "nnr": "https://nnr.co.za/feed",
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
    },

    # 🚗 Motoring & Automotive
    "motoring": {
        "topauto": "https://topauto.co.za/feed",
        "autoblog": "https://www.autoblog.com/.rss/feed/3d70fbb5-ef5e-44f3-a547-e60939496e82.xml",
        "caranddriver": "https://www.caranddriver.com/rss/all.xml",
        "motor1": "https://www.motor1.com/rss/news/all/",
        "carmag": "https://www.carmag.co.za/feed/",
        "carscoops": "https://www.carscoops.com/feed/",
        "thedrive": "https://www.thedrive.com/feed",
        "carbuzz": "https://carbuzz.com/feed",
        "businesstech-motoring": "https://businesstech.co.za/news/motoring/feed/",
        "iol-motoring": "https://iol.co.za/rss/iol/motoring/",
        "carsite": "https://carsite.co.za/feed/",
    },

    # 🏉 Sport
    "sport": {
        "iol-sport": "https://iol.co.za/rss/iol/sport/",
        "news24-sport": "https://feeds.24.com/articles/sport/topstories/rss"
    },

    # 🎬 Entertainment
    "entertainment": {
        "iol-entertainment": "https://iol.co.za/rss/iol/entertainment/"
    },

    # 🏖️ Lifestyle
    "lifestyle": {
        "news24-life": "https://feeds.24.com/articles/life/topstories/rss"
    },

    # 💼 Business
    "business": {
        "iol-business": "https://iol.co.za/business/",
        "citizen-business": "https://www.citizen.co.za/business/feed/",
        "news24-business": "https://feeds.24.com/articles/business/topstories/rss" 
    },

    # 🗣️ Opinion
    "opinion": {
        "iol-opinion": "https://iol.co.za/opinion/"
    },

    # 🗳️ Politics
    "politics": {
        "iol-politics": "https://iol.co.za/news/politics/",
        "news24-politics": "https://feeds.24.com/articles/news24/topstories/rss" 
    }
}

def fetch_feed_data(config: InputConfig) -> List[ArticleCandidate]:
    """Fetches articles from RSS feeds based on niche."""
    
    # Set global default timeout for socket operations (underlying feedparser usage)
    socket.setdefaulttimeout(15)

    # 1. TEST MODE
    if config.runTestMode:
        Actor.log.info(f"🧪 TEST MODE: Generating dummy feed data for niche '{config.niche}'.")
        return [
            ArticleCandidate(
                title=f"[{config.niche.upper()}] Major Industry Annoucement",
                url="https://example.com/breaking-news",
                source="TestFeed",
                published="Fri, 01 Dec 2025 12:00:00 GMT",
                original_summary="A major event has occurred in the industry.",
                image_url="https://placehold.co/600x400/png"
            ),
             ArticleCandidate(
                title=f"[{config.niche.upper()}] New Innovation Revealed",
                url="https://example.com/innovation",
                source="TestFeed",
                published="Fri, 01 Dec 2025 14:00:00 GMT",
                image_url="https://placehold.co/600x400/png"
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

    total_feeds = len(urls)
    Actor.log.info(f"So, we found {total_feeds} feeds to process. Starting parallel fetch with 20 workers...")

    # Shuffle initially to prevent hitting one slow domain concurrently
    random.shuffle(urls)

    feed_data = []
    
    # helper for parallel execution
    def process_feed_url(entry):
        url = entry["url"]
        niche_context = entry["niche"]
        local_results = []
        try:
            # Verbose logging to debug stalling
            # Actor.log.info(f"⏳ processing: {url} [{niche_context}]")
            
            # feedparser can timeout if socket timeout is set globally (above)
            feed = feedparser.parse(url)
            
            # Check for bozo (malformed XML) or errors
            if feed.bozo and hasattr(feed, 'bozo_exception'):
                # Log but try to continue if entries exist
                 pass 

            for entry_data in feed.entries:
                # Basic validation
                if not hasattr(entry_data, 'title') or not hasattr(entry_data, 'link'):
                    continue

                # TIME FILTERING
                if not is_recent(entry_data.get('published'), config.timeLimit):
                    continue
                    
                # IMAGE EXTRACTION
                image_url = None
                
                # Check 1: Media Content (often in standard RSS)
                if 'media_content' in entry_data:
                    media = entry_data.media_content
                    if isinstance(media, list) and len(media) > 0:
                         image_url = media[0].get('url')

                # Check 2: Media Thumbnail (YouTube/News style)
                if not image_url and 'media_thumbnail' in entry_data:
                    thumbnails = entry_data.media_thumbnail
                    if isinstance(thumbnails, list) and len(thumbnails) > 0:
                        image_url = thumbnails[0].get('url')

                # Check 3: Enclosures (Podcasts/legacy)
                if not image_url and 'enclosures' in entry_data:
                     for enc in entry_data.enclosures:
                         if enc.get('type', '').startswith('image/'):
                             image_url = enc.get('href')
                             break

                # Check 4: Links (Atom style)
                if not image_url and 'links' in entry_data:
                     for link in entry_data.links:
                         if link.get('type', '').startswith('image/'):
                             image_url = link.get('href')
                             break

                local_results.append(
                    ArticleCandidate(
                        title=entry_data.title,
                        url=entry_data.link,
                        source=feed.feed.get('title', 'Unknown Feed'),
                        published=normalize_date(entry_data.get('published')),
                        original_summary=entry_data.get('summary') or entry_data.get('description'),
                        niche=niche_context,
                        image_url=image_url
                    )
                )
        except Exception as e:
            Actor.log.error(f"Failed to fetch {url}: {e}")
            
        return local_results

    # Increased workers to 20 to prevent bottlenecks
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_feed_url, u): u for u in urls}
        
        completed_count = 0
        for future in concurrent.futures.as_completed(futures):
            completed_count += 1
            if completed_count % 20 == 0:
                Actor.log.info(f"📊 Progress: {completed_count}/{total_feeds} feeds processed...")
            
            try:
                res = future.result(timeout=20) # Enforce a timeout on getting valid result
                feed_data.extend(res)
            except concurrent.futures.TimeoutError:
                Actor.log.warning(f"⚠️ A feed task timed out.")
            except Exception as e:
                Actor.log.error(f"⚠️ Worker exception: {e}")

    # Deduplicate by URL
    seen = set()
    unique_articles = []
    for art in feed_data:
        if art.url not in seen:
            unique_articles.append(art)
            seen.add(art.url)
            
    # BALANCED SELECTION for 'all' mode
    if config.niche == "all":
        by_niche = defaultdict(list)
        for art in unique_articles:
            by_niche[art.niche].append(art)
        
        # Shuffle within niches to avoid feed bias
        for n in by_niche:
            random.shuffle(by_niche[n])
            
        balanced = []
        # Round Robin Interleave
        # We process until we hit maxArticles or run out of content
        max_possible_depth = max((len(l) for l in by_niche.values()), default=0)
        
        for i in range(max_possible_depth):
            for niche_key in by_niche:
                if len(balanced) >= config.maxArticles:
                    break
                if niche_key in by_niche and i < len(by_niche[niche_key]):  # Corrected logic
                    balanced.append(by_niche[niche_key][i])
            if len(balanced) >= config.maxArticles:
                break
                
        Actor.log.info(f"✅ Selected {len(balanced)} balanced articles across {len(by_niche)} niches.")
        return balanced
    
    random.shuffle(unique_articles)
    Actor.log.info(f"✅ Fetched {len(unique_articles)} recent unique articles (after time filter).")
    return unique_articles[:config.maxArticles]

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

def normalize_date(date_str: str) -> str:
    """Standardizes date string to ISO 8601."""
    if not date_str: return None
    try:
        dt = parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return date_str