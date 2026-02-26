# Niche Intelligence Actor - Source of Truth

This document serves as the source of truth for the architecture, workflow, and components of the **Niche Intelligence Actor** (Visita Intelligence).

## 🎯 Overview
The Niche Intelligence Actor is a multi-vertical intelligence scout designed to aggregate, deduplicate, and analyze global news feeds. It uses AI to extract structured intelligence (entities, sentiment, niche-specific data) from articles and syncs this data to a Supabase database while pushing standardized records to an Apify Dataset.

## 🏗️ Architecture & Workflow

The actor is built using **LangGraph** to orchestrate a state-driven workflow. The execution flow is defined in `src/main.py`.

### 1. Initialization & Fetching (`fetch_feeds_node`)
- **Input Configuration**: Reads parameters like `niche`, `source`, `timeLimit`, and `maxArticles` (defined in `src/models.py` as `InputConfig`).
- **RSS Aggregation**: Fetches RSS feeds concurrently based on the `NICHE_FEED_MAP` defined in `src/services/feeds.py`. Supported niches include Gaming, Crypto, Tech, Energy, Nuclear, Crime, Real Estate, and more.
- **Raw Buffering**: Before processing, raw articles are buffered to the `ai_intelligence.feed_items` table in Supabase for traceability.

### 2. Processing Loop (`process_article_node`)
For each fetched article, the actor performs the following steps:

#### A. Deduplication
- Checks if the article URL already exists in the target Supabase table for the specific niche (`check_exists` in `src/services/ingestor.py`).
- If it exists, the article is skipped to save LLM costs and compute time (unless `forceRefresh` is enabled).

#### B. Content Extraction (Scraping & Fallback)
- **Primary (Scraping)**: Attempts to scrape the full article text and image using `requests` and `BeautifulSoup` (`src/services/scraper.py`). It uses heuristics to find images via OpenGraph, Twitter Cards, JSON-LD, or body tags.
- **Fallback (Search)**: If scraping fails (e.g., due to anti-bot protection or paywalls), it falls back to using the Brave Search API to retrieve a summary of the article (`src/services/search.py`).
- **Image Backfill**: If no image is found and `enableBraveImageBackfill` is true, it uses Brave Image Search to find a relevant image.

#### C. AI Analysis (`src/services/llm.py`)
- The extracted content is passed to an LLM to extract structured intelligence.
- **Providers**:
  - **Primary**: OpenRouter Free Models (e.g., Google Gemma 3 27B, Llama 3.3 70B, OpenAI GPT-OSS 120B, Nvidia Nemotron) to maximize the free tier usage.
  - **Fallback**: OpenRouter Cheap Capable Models (e.g., Gemini 2.0 Flash, Llama 3.3 70B) if rate limits are hit on the free tier.
- **Circuit Breaker**: Models that return Rate Limit (429) or Invalid (400/404) errors are automatically marked as failed for the duration of the run to prevent wasted retries.
- **Extraction Goals**:
  - **General**: Sentiment (Hype level), Category, Key Entities, Geolocation (City, Country, `is_south_africa` flag), and an AI Summary.
  - **Rich Data**: Specific incidents (e.g., crime severity), people (e.g., suspects, officials), and organizations.
  - **Niche-Specific**: Tailored prompts extract specific fields based on the niche (e.g., `game_studio` for Gaming, `token_symbol` for Crypto, `listing_price` for Real Estate).
- **Dynamic Routing**: If the LLM detects that the article belongs to a different niche than originally categorized, it dynamically re-routes it to the correct niche.

#### D. Storage & Sync (`src/services/ingestor.py`)
- **Apify Dataset**: Pushes a standardized `DatasetRecord` to the Apify platform.
- **Supabase Ingestion**:
  - Updates the raw `feed_items` record with the analysis results.
  - Ingests rich entities (People, Organizations, Incidents) into dedicated tables.
  - Routes the main article content to specific niche tables (e.g., `crime_intelligence.news`, `ai_intelligence.gaming`, `ai_intelligence.energy`).

#### E. Notifications
- If a `discordWebhookUrl` is provided and the article's sentiment is classified as "High Hype", a real-time alert is sent to Discord (`src/services/notifications.py`).

#### F. Monetization
- The actor charges the user via Apify's Pay-Per-Event model (`Actor.charge`) only when an LLM summary is successfully generated.

## 📂 Directory Structure & Key Components

*   **`src/main.py`**: The entry point and LangGraph state machine orchestrating the entire workflow.
*   **`src/models.py`**: Pydantic models defining the data schema (`InputConfig`, `ArticleCandidate`, `AnalysisResult`, `DatasetRecord`, etc.). Ensures strict typing for LLM outputs and database ingestion.
*   **`src/services/feeds.py`**: Contains the `NICHE_FEED_MAP`, a comprehensive dictionary mapping niches to their respective RSS feed URLs. Handles concurrent fetching and parsing.
*   **`src/services/scraper.py`**: Logic for HTTP requests and HTML parsing to extract clean text and images from article URLs.
*   **`src/services/search.py`**: Integration with Brave Search API for content fallback and image backfilling.
*   **`src/services/llm.py`**: Manages LLM prompts, API calls (Perplexity/OpenRouter), and structured JSON parsing using LangChain's `PydanticOutputParser`.
*   **`src/services/ingestor.py`**: The `SupabaseIngestor` class. Handles database connections, deduplication hashing, and complex relational inserts across multiple schemas and tables.
*   **`src/services/notifications.py`**: Logic for formatting and sending Discord webhook payloads.

## 🔑 Required Environment Variables
- `SUPABASE_URL`: URL of the target Supabase instance.
- `SUPABASE_KEY` / `SUPABASE_SERVICE_ROLE_KEY`: Authentication key for Supabase.
- `OPENROUTER_API_KEY`: Primary LLM provider key (used for both free and fallback models).
- `BRAVE_API_KEY`, `BRAVE_FREE_AI`, `BRAVE_BASE_KEY`: Required for search fallback and image backfilling (rotates automatically on rate limits).
