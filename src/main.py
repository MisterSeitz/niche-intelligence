import asyncio
from typing import TypedDict, List
from apify import Actor
from langgraph.graph import StateGraph, END
import os 

from .models import InputConfig, ArticleCandidate, DatasetRecord
from .services.feeds import fetch_feed_data
from .services.scraper import scrape_article_content
from .services.search import brave_search_fallback, find_relevant_image
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
        schema_name = "public"
        table_name = full_table_name
        
        if "." in full_table_name:
            schema_name, table_name = full_table_name.split(".", 1)
        
        # Strip whitespace just in case
        schema_name = schema_name.strip()
        table_name = table_name.strip()

        Actor.log.info(f"🔄 Syncing to Supabase - Schema: '{schema_name}', Table: '{table_name}'")

        if schema_name != "public":
            # Use the .schema() method to switch context
            query = supabase.schema(schema_name).table(table_name)
        else:
            # Default to public schema
            query = supabase.table(table_name)
        
        # 2. Perform Upsert
        data_to_upsert = record_dict.copy()
        # Remove any None values if necessary, or ensure schema allows nulls
        # record_dict is standard, so we assume it fits.
        
        try:
            query.upsert(data_to_upsert, on_conflict="url").execute()
            Actor.log.info(f"✅ Upsert successful for {full_table_name}: {record_dict.get('title', 'No Title')[:30]}...")
        except Exception as upsert_err:
             # Extract error details if possible
            Actor.log.error(f"❌ Upsert Error Details: {upsert_err}")
            if hasattr(upsert_err, 'code'):
                 Actor.log.error(f"Error Code: {upsert_err.code}")
            if hasattr(upsert_err, 'details'):
                 Actor.log.error(f"Error Details: {upsert_err.details}")
            if hasattr(upsert_err, 'hint'):
                 Actor.log.error(f"Error Hint: {upsert_err.hint}")
            raise upsert_err

    except Exception as e:
        Actor.log.error(f"❌ Supabase Sync Failed Main Block: {e}")

def check_url_exists(url: str, full_table_name: str) -> bool:
    """Checks if a URL already exists in the target table."""
    api_url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not api_url or not key:
        return False

    try:
        supabase: Client = create_client(api_url, key)
        
        schema_name = "public"
        table_name = full_table_name
        
        if "." in full_table_name:
            schema_name, table_name = full_table_name.split(".", 1)
            
        schema_name = schema_name.strip()
        table_name = table_name.strip()
            
        if schema_name != "public":
            query = supabase.schema(schema_name).table(table_name)
        else:
            query = supabase.table(table_name)
            
        # Check for existence
        response = query.select("url").eq("url", url).execute()
        return len(response.data) > 0
    except Exception as e:
        Actor.log.warning(f"⚠️ Failed to check duplicate for {url} in {schema_name}.{table_name}: {e}")
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
    context, scraped_image = scrape_article_content(article.url, config.runTestMode)
    method = "scraped"
    
    # Image Priority: Feed > Scraped > Brave Backfill
    final_image_url = article.image_url or scraped_image

    # 2. STRATEGY: Search Fallback
    if not context:
        Actor.log.info("⚠️ Scraping failed/blocked. Engaging Brave Search Fallback.")
        context = brave_search_fallback(article.title, config.runTestMode)
        method = "search_fallback"
        
    # 3. STRATEGY: Brave Image Backfill (If enabled and still no image)
    if not final_image_url and config.enableBraveImageBackfill:
         Actor.log.info(f"🖼️ Backfilling image for: {article.title}")
         final_image_url = find_relevant_image(article.title, config.runTestMode)

    # 3. STRATEGY: AI Analysis
    if context:
        try:
            analysis = analyze_content(context, niche=article_niche, run_test_mode=config.runTestMode)
            
            # --- DYNAMIC ROUTING ---
            # If the LLM detects a better niche, we re-route.
            if analysis.detected_niche:
                valid_niches = ['general', 'gaming', 'crypto', 'tech', 'nuclear', 'energy', 'education', 'foodtech', 'health', 'luxury', 'realestate', 'retail', 'social', 'vc', 'web3']
                clean_detected = analysis.detected_niche.lower().strip()
                if clean_detected in valid_niches and clean_detected != article_niche:
                    Actor.log.info(f"🔀 Re-routing article: '{article_niche}' -> '{clean_detected}'")
                    article_niche = clean_detected
                    target_table = f"ai_intelligence.{article_niche}"

            # 4. 💰 MONETIZATION 💰
            # We charge the user only when the 'summarize_snippets_with_llm' event succeeds.
            if not config.runTestMode:
                await Actor.charge(event_name="summarize_snippets_with_llm") #

            record = DatasetRecord(
                niche=article_niche, # Use specific niche
                source_feed=article.source,
                title=article.title,
                url=article.url,
                image_url=final_image_url,
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
                regulatory_impact=analysis.regulatory_impact,
                
                energy_type=analysis.energy_type,
                infrastructure_project=analysis.infrastructure_project,
                capacity=analysis.capacity,
                status=analysis.status
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