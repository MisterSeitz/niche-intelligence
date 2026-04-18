import os
import requests
from apify import Actor
from typing import Optional, Dict, Any

async def rag_browser_fallback(query_title: str, run_test_mode: bool) -> str:
    """
    Step B: Paid Fallback using RAG Web Browser.
    Used when direct scraping fails.
    """
    if run_test_mode:
        return "Source A: Valve announces HL3. Source B: Release date set for 2026."

    # Clean title for query
    clean_query = query_title.replace('"', '').replace("'", "")
    
    Actor.log.info(f"🌐 RAG Web Browser Fallback for: {clean_query}")
    
    run_input = {
        "desiredConcurrency": 5,
        "htmlTransformer": "none",
        "proxyConfiguration": {
            "useApifyProxy": True
        },
        "query": clean_query,
        "removeElementsCssSelector": "nav, footer, script, style, noscript, svg, img[src^='data:'],\n[role=\"alert\"],\n[role=\"banner\"],\n[role=\"dialog\"],\n[role=\"alertdialog\"],\n[role=\"region\"][aria-label*=\"skip\" i],\n[aria-modal=\"true\"]",
        "requestTimeoutSecs": 40,
        "removeCookieWarnings": True,
        "debugMode": False
    }

    try:
        run = await Actor.call(actor_id='za_intelligence/rag-web-browser', run_input=run_input)
        if run and run.get('defaultDatasetId'):
            dataset_id = run['defaultDatasetId']
            items_page = await Actor.apify_client.dataset(dataset_id).list_items()
            items = items_page.items
            
            # Aggregate snippets
            context = "Search Results:\n"
            for item in items:
                title = item.get('title', 'No Title')
                url = item.get('url', '')
                text = item.get('text', '') or item.get('markdown', '') or ''
                context += f"- Title: {title}\n  URL: {url}\n  Content: {text[:1000]}...\n\n"
            
            return context[:6000]
        else:
            Actor.log.warning("RAG Browser returned no dataset.")
            return ""
    except Exception as e:
        Actor.log.error(f"Failed to perform RAG browser fallback: {e}")
        return ""

async def find_relevant_image(query: str, run_test_mode: bool) -> str | None:
    """
    Step C: This was previously finding relevant images using Brave.
    Since Brave API was removed, we just return None.
    """
    return None
