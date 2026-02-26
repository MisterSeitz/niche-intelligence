import os
import requests
from apify import Actor
from typing import Optional, Dict, Any

# --- Helper Logic for Key Rotation ---
def perform_brave_request(endpoint: str, params: Dict[str, Any]) -> Optional[requests.Response]:
    """
    Tries to execute a Brave API request using a specific key priority order:
    1. BRAVE_API_KEY (Free, 2k req/mo, 1 req/s)
    2. BRAVE_FREE_AI (Free, 2k req/mo, 1 req/s)
    3. BRAVE_BASE_KEY (Paid)
    
    If a key fails with 429 (Rate Limit) or 401/403 (Auth), it rotates to the next.
    """
    keys_to_try = ["BRAVE_API_KEY", "BRAVE_FREE_AI", "BRAVE_BASE_KEY"]
    
    for key_name in keys_to_try:
        # Get key directly from env, stripping whitespace just in case
        api_key = (os.getenv(key_name) or "").strip()
        if not api_key:
            continue
            
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        
        try:
            # Actor.log.info(f"🔑 Trying Brave Key: {key_name}...") 
            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response
                
            elif response.status_code in [401, 403, 429]:
                 Actor.log.warning(f"⚠️ Key {key_name} failed with {response.status_code}. Rotating...")
                 continue # Try next key
            else:
                # Other server errors (500, etc) might not be solved by rotation, but let's try anyway or just log
                Actor.log.warning(f"⚠️ Key {key_name} encountered error {response.status_code}.")
                continue

        except Exception as e:
            Actor.log.error(f"❌ Error using {key_name}: {e}")
            continue
            
    Actor.log.error("❌ All Brave keys exhausted or failed.")
    return None

def brave_search_fallback(query_title: str, run_test_mode: bool) -> str:
    """
    Step B: Paid Fallback using Brave Search API.
    Used when direct scraping fails.
    """
    if run_test_mode:
        return "Source A: Valve announces HL3. Source B: Release date set for 2026."

    # Clean title for query
    clean_query = query_title.replace('"', '').replace("'", "")
    
    Actor.log.info(f"🦁 Brave Search Fallback for: {clean_query}")
    
    response = perform_brave_request(
        "https://api.search.brave.com/res/v1/web/search",
        params={
            "q": clean_query,
            "count": 5,
            "extra_snippets": True, 
            "search_lang": "en"
        }
    )
        
    if response and response.status_code == 200:
        try:
            data = response.json()
            results = data.get('web', {}).get('results', [])
            
            # Aggregate snippets
            context = "Search Results:\n"
            for item in results:
                title = item.get('title', 'No Title')
                desc = item.get('description', '')
                extra = " ".join(item.get('extra_snippets', []))
                context += f"- Title: {title}\n  Snippet: {desc} {extra}\n\n"
            
            return context[:6000]
        except Exception as e:
            Actor.log.error(f"Failed to parse Brave response: {e}")
            return ""
    else:
        return ""

def find_relevant_image(query: str, run_test_mode: bool) -> str | None:
    """
    Step C: Find a relevant image using Brave Search.
    """
    if run_test_mode:
        return "https://placehold.co/600x400/png?text=Brave+Backfill"
        
    clean_query = query.replace('"', '').replace("'", "")
    
    response = perform_brave_request(
        "https://api.search.brave.com/res/v1/images/search",
        params={
            "q": clean_query,
            "count": 1,
            "search_lang": "en"
        }
    )
    
    if response and response.status_code == 200:
        try:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0].get('properties', {}).get('url') 
        except Exception as e:
             Actor.log.warning(f"Brave Image Parse failed: {e}")
             
    return None
