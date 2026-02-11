import requests
from bs4 import BeautifulSoup
from apify import Actor
import re
import json

def scrape_article_content(url: str, run_test_mode: bool) -> tuple[str | None, str | None]:
    """
    Step A: Attempt to scrape the direct URL.
    Returns (cleaned_text, image_url) or (None, None) if failed/blocked.
    """
    if run_test_mode:
        return (
            "<p>Test Content: Valve announced Half-Life 3 today. It is a VR exclusive.</p>",
            "https://placehold.co/600x400/png"
        )

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        Actor.log.info(f"🕷️ Attempting to scrape: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check for soft blocks or errors
        if response.status_code in [403, 429, 401]:
            Actor.log.warning(f"🛡️ Anti-bot trigger ({response.status_code}) on {url}. Switching to Fallback.")
            return None, None
            
        if response.status_code != 200:
            return None, None

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Scrape Image (OpenGraph > Twitter > JSON-LD > Body Heuristic)
        image_url = None
        
        # 1.1 OpenGraph
        og_image = soup.find('meta', property='og:image')
        if og_image:
            image_url = og_image.get('content')
            
        # 1.2 Twitter Card
        if not image_url:
            twitter_image = soup.find('meta', name='twitter:image')
            if twitter_image:
                 image_url = twitter_image.get('content')
                 
        # 1.3 JSON-LD (Schema.org)
        if not image_url:
            try:
                scripts = soup.find_all('script', type='application/ld+json')
                for script in scripts:
                    if not script.string: continue
                    try:
                        data = json.loads(script.string)
                    except json.JSONDecodeError:
                        continue
                        
                    # Handle both list and dict logic (some schemas are arrays)
                    items = data if isinstance(data, list) else [data]
                    
                    for item in items:
                        # Direct ImageObject or Article.image
                        img = item.get('image')
                        if img:
                            if isinstance(img, str):
                                image_url = img
                                break
                            elif isinstance(img, dict) and 'url' in img:
                                image_url = img['url']
                                break
                            elif isinstance(img, list) and len(img) > 0:
                                # Could be a list of strings or objects
                                first = img[0]
                                if isinstance(first, str):
                                    image_url = first
                                elif isinstance(first, dict) and 'url' in first:
                                    image_url = first['url']
                                break
                        
                        # Check nested "thumbnailUrl"
                        thumb = item.get('thumbnailUrl')
                        if thumb:
                            image_url = thumb
                            break
                            
                    if image_url: break
            except Exception as e:
                Actor.log.debug(f"JSON-LD parsing error: {e}")

        # 1.4 Body Heuristic (First large image)
        if not image_url:
             article = soup.find('article') or soup.find('main') or soup.find(class_=re.compile(r'post|article|content'))
             if article:
                 images = article.find_all('img')
                 for img in images:
                     src = img.get('src')
                     # Filter out common small icons/pixels
                     if src and not src.endswith('.svg') and 'icon' not in src.lower() and 'logo' not in src.lower():
                         image_url = src
                         break
        
        # Heuristics for article body
        article_body = soup.find('article') or soup.find('main') or soup.find(class_=re.compile(r'content|post|article'))
        
        if article_body:
            text = article_body.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)
            
        # Cleanup
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        # Quality check: if text is too short, it's likely a cookie wall or error
        if len(clean_text) < 300:
            Actor.log.warning(f"⚠️ Scraped content too short ({len(clean_text)} chars). Likely failed.")
            return None, None

        return clean_text[:8000], image_url # Truncate for LLM context limits

    except Exception as e:
        Actor.log.warning(f"Scrape error on {url}: {e}")
        return None, None