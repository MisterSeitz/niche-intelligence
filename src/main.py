import asyncio
from typing import TypedDict, List
from apify import Actor
from langgraph.graph import StateGraph, END
import os 

from .models import InputConfig, ArticleCandidate, DatasetRecord
from .services.feeds import fetch_feed_data
from .services.scraper import scrape_article_content
from .services.search import brave_search_fallback
from .services.search import brave_search_fallback
from .services.llm import analyze_content
from .services.notifications import send_discord_alert
from supabase import create_client, Client

# --- HELPER FUNCTION (Corrected for Schemas) ---
def sync_to_supabase(record_dict: dict, full_table_name: str): 
    """
    Push data to a specific Supabase table, handling custom schemas.
    Args:
        record_dict: The data to insert.
        full_table_name: Format 'schema.table' (e.g., 'intelligence.web3') or just 'table'.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    """
    if key:
        if key.startswith("sbp_") or key.startswith("eyJ"): # eyJ usually implies the old anon JWT
            Actor.log.warning(f"⚠️ POTENTIAL KEY ERROR: Your key starts with '{key[:7]}...'. This looks like a PUBLIC key. You need the SECRET key (starts with 'sb_secret_' or is the 'service_role' key).")
        else:
            Actor.log.info(f"🔑 Key check passed: Starts with '{key[:7]}...'")
    """
    
    if not url or not key:
        Actor.log.warning("⚠️ Supabase credentials missing. Skipping sync.")
        return

    try:
        supabase: Client = create_client(url, key)
        
        # 1. Parse Schema and Table
        if "." in full_table_name:
            schema_name, table_name = full_table_name.split(".", 1)
            # Use the .schema() method to switch context
            query = supabase.schema(schema_name).table(table_name)
        else:
            # Default to public schema
            query = supabase.table(full_table_name)
        
        # 2. Perform Upsert
        query.upsert(record_dict, on_conflict="url").execute()
        
        Actor.log.info(f"🔄 All processes complete for {full_table_name}: {record_dict.get('title', 'No Title')[:30]}...")
        
    except Exception as e:
        Actor.log.error(f"❌ Supabase Sync Failed: {e}")

def check_url_exists(url: str, full_table_name: str) -> bool:
    """Checks if a URL already exists in the target table."""
    api_url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not api_url or not key:
        return False

    try:
        supabase: Client = create_client(api_url, key)
        if "." in full_table_name:
            schema_name, table_name = full_table_name.split(".", 1)
            query = supabase.schema(schema_name).table(table_name)
        else:
            query = supabase.table(full_table_name)
            
        # Check for existence
        response = query.select("url").eq("url", url).execute()
        return len(response.data) > 0
    except Exception as e:
        Actor.log.warning(f"⚠️ Failed to check duplicate for {url}: {e}")
        return False

# --- State Definition ---
class WorkflowState(TypedDict):
    config: InputConfig
    articles: List[ArticleCandidate]
    current_index: int

# --- Nodes ---

async def fetch_feeds_node(state: WorkflowState):
    """Initializes and fetches RSS data."""
    config = state['config']
    articles = fetch_feed_data(config)
    Actor.log.info(f"📚 Queued {len(articles)} articles for analysis.")
    return {"articles": articles, "current_index": 0}

async def process_article_node(state: WorkflowState):
    """The Core Logic: Scrape -> Fallback -> AI -> Save"""
    config = state['config']
    idx = state['current_index']
    articles = state['articles']
    
    if idx >= len(articles):
        return {"current_index": idx} 

    article = articles[idx]
    Actor.log.info(f"👉 [{idx+1}/{len(articles)}] Processing: {article.title}")

    # 0. STRATEGY: Deduplication Check
    # Determine table based on article niche or config niche
    article_niche = getattr(article, 'niche', None) or config.niche
    # If niche is 'all', specific article niche should be set. If not, fallback to config (which shouldn't happen if feeds.py is right)
    if article_niche == 'all':
        article_niche = 'general' # Safe fallback

    target_table = f"ai_intelligence.{article_niche}"
    
    # Check for existing unless Force Refresh is ON
    if not config.runTestMode and not config.forceRefresh:
        exists = await asyncio.to_thread(check_url_exists, article.url, target_table)
        if exists:
            Actor.log.info(f"⏭️ Skipping duplicate: {article.title}")
            return {"current_index": idx + 1}

    # 1. STRATEGY: Scrape First
    context = scrape_article_content(article.url, config.runTestMode)
    method = "scraped"

    # 2. STRATEGY: Search Fallback
    if not context:
        Actor.log.info("⚠️ Scraping failed/blocked. Engaging Brave Search Fallback.")
        context = brave_search_fallback(article.title, config.runTestMode)
        method = "search_fallback"

    # 3. STRATEGY: AI Analysis
    if context:
        try:
            analysis = analyze_content(context, niche=article_niche, run_test_mode=config.runTestMode)
            
            # 4. 💰 MONETIZATION 💰
            # We charge the user only when the 'summarize_snippets_with_llm' event succeeds.
            if not config.runTestMode:
                await Actor.charge(event_name="summarize_snippets_with_llm") #

            record = DatasetRecord(
                niche=article_niche, # Use specific niche
                source_feed=article.source,
                title=article.title,
                url=article.url,
                published=article.published,
                method=method,
                sentiment=analysis.sentiment,
                category=analysis.category,
                key_entities=analysis.key_entities,
                ai_summary=analysis.summary,
                location=analysis.location,
                city=analysis.city,
                country=analysis.country,
                is_south_africa=analysis.is_south_africa,
                raw_context_source=context[:200] + "...",

                # Niche Specific Mapping
                game_studio=analysis.game_studio,
                game_genre=analysis.game_genre,
                platform=analysis.platform,
                release_status=analysis.release_status,
                
                property_type=analysis.property_type,
                listing_price=analysis.listing_price,
                sqft=analysis.sqft,
                market_status=analysis.market_status,
                
                company_name=analysis.company_name,
                round_type=analysis.round_type,
                funding_amount=analysis.funding_amount,
                investor_list=analysis.investor_list,
                
                token_symbol=analysis.token_symbol,
                market_trend=analysis.market_trend,
                regulatory_impact=analysis.regulatory_impact
            )
            
            await Actor.push_data(record.model_dump())
            Actor.log.info("✅ Data pushed to dataset.")
            
            await asyncio.to_thread(sync_to_supabase, record.model_dump(), target_table)
            
            # 5. 📢 NOTIFICATIONS
            if config.discordWebhookUrl and "High Hype" in record.sentiment:
                await send_discord_alert(config.discordWebhookUrl, record.model_dump())
            
        except Exception as e:
            Actor.log.error(f"Analysis loop failed for {article.title}: {e}")
    else:
        Actor.log.error("❌ Failed to gather ANY context. Skipping.")

    return {"current_index": idx + 1}

def should_continue(state: WorkflowState):
    if state['current_index'] < len(state['articles']):
        return "process_article"
    return END

# --- Main Entry ---

async def main():
    async with Actor:
        raw_input = await Actor.get_input() or {}
        config = InputConfig(**raw_input)
        
        # --- MAINTENANCE FIX ---
        if not config.runTestMode:
            if not os.getenv("OPENROUTER_API_KEY"):
                Actor.log.warning("⚠️ OPENROUTER_API_KEY not found. Switching to TEST MODE.")
                config.runTestMode = True
            elif not os.getenv("BRAVE_API_KEY"):
                Actor.log.warning("⚠️ BRAVE_API_KEY missing. Search fallback disabled.")

        # Graph Setup
        workflow = StateGraph(WorkflowState)
        workflow.add_node("fetch_feeds", fetch_feeds_node)
        workflow.add_node("process_article", process_article_node)
        
        workflow.set_entry_point("fetch_feeds")
        workflow.add_conditional_edges("fetch_feeds", lambda x: "process_article")
        workflow.add_conditional_edges("process_article", should_continue)
        
        app = workflow.compile()
        
        await app.ainvoke({
            "config": config,
            "articles": [],
            "current_index": 0
        })

if __name__ == '__main__':
    asyncio.run(main())