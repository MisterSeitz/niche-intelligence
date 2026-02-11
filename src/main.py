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
from .services.ingestor import SupabaseIngestor

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

    # Initialize Ingestor
    ingestor = SupabaseIngestor()

    # 0. STRATEGY: Deduplication Check
    # Determine table based on article niche or config niche
    article_niche = getattr(article, 'niche', None) or config.niche
    # If niche is 'all', specific article niche should be set. If not, fallback to general.
    if article_niche == 'all':
        article_niche = 'general' 

    # Check for existing unless Force Refresh is ON
    if not config.runTestMode and not config.forceRefresh:
        exists = ingestor.check_exists(article.url, niche=article_niche)
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
                valid_niches = ['general', 'gaming', 'crypto', 'tech', 'nuclear', 'energy', 'education', 'foodtech', 'health', 'luxury', 'realestate', 'retail', 'social', 'vc', 'brics', 'politics', 'crime', 'sport', 'business', 'semiconductors']
                clean_detected = analysis.detected_niche.lower().strip()
                if clean_detected in valid_niches and clean_detected != article_niche:
                    Actor.log.info(f"🔀 Re-routing article: '{article_niche}' -> '{clean_detected}'")
                    article_niche = clean_detected
            
            # 4. 💰 MONETIZATION 💰
            # We charge the user only when the 'summarize_snippets_with_llm' event succeeds.
            if not config.runTestMode:
                await Actor.charge(event_name="summarize_snippets_with_llm") 

            # 5. DATASET & SUPABASE INGESTION
            
            # Create Dataset Record (Standardized)
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

                # Rich Data (Dicts for dataset compatibility)
                incidents=[i.model_dump() for i in analysis.incidents] if analysis.incidents else None,
                people=[p.model_dump() for p in analysis.people] if analysis.people else None,
                organizations=[o.model_dump() for o in analysis.organizations] if analysis.organizations else None,

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
                status=analysis.status,

                # Motoring
                vehicle_make=analysis.vehicle_make,
                vehicle_model=analysis.vehicle_model,
                vehicle_type=analysis.vehicle_type,
                price_range=analysis.price_range
            )
            
            # Push to Apify Dataset
            await Actor.push_data(record.model_dump())
            
            # Ingest to Supabase (Intelligent Routing)
            await ingestor.ingest(analysis, article)
            
            # 6. 📢 NOTIFICATIONS
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