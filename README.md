# 🎮 Gaming & Esports News Intelligence Pipeline

**Turn raw RSS feeds into structured AI intelligence. Scrape, summarize, and analyze Gaming & Esports news without configuring external API keys.**

-----

## What is the Gaming & Esports News Intelligence Pipeline?

This Actor is a specialized **Gaming News API** and **Esports Scraper** designed for analysts, content creators, and market researchers. Unlike standard RSS readers that only give you a headline and a link, this tool uses a sophisticated **AI Pipeline** to read the article for you.

It automatically fetches news from top sources (IGN, Kotaku, Esports Insider), attempts to scrape the full content, and uses a Large Language Model (LLM) to generate **structured intelligence**: sentiment analysis, hype ratings, categorical tagging, and key entity extraction.

### Why use this Actor?

  * **🔋 Batteries Included:** You do **not** need your own OpenAI or Brave Search API keys. We handle the infrastructure; you just pay for the results.
  * **🧠 AI-Powered Analysis:** Every article is processed by an LLM to extract "High Hype" events, identify "Game Reviews" vs. "Industry News," and summarize the core facts.
  * **🛡️ Resilient "Scrape-First" Engine:** The actor first attempts to scrape the article directly (free). If blocked, it automatically falls back to a paid **Brave Search** snippet extraction to ensure you almost always get context for the AI.
  * **📊 Structured JSON:** Get clean data ready for dashboards, automated newsletters, or competitor analysis.

## What data can this Actor extract?

This tool transforms unstructured web content into a structured dataset. Here is the data model you can expect:

| Field | Description |
| :--- | :--- |
| **Title** | The original headline of the news article. |
| **AI Summary** | A dense, 2-sentence professional summary of the event. |
| **Sentiment** | The "Hype" level (e.g., `High Hype`, `Moderate Interest`, `Informational`). |
| **Category** | The thematic tag (e.g., `Esports Results`, `Game Review`, `New Release`). |
| **Key Entities** | A list of specific games (e.g., *GTA VI*), teams (e.g., *T1*), or studios involved. |
| **Source Feed** | The origin of the news (e.g., *IGN*, *PC Gamer*). |
| **Extraction Method** | Indicates if the data came from direct scraping or search fallback. |

## How to use the Gaming News Pipeline

This Actor is designed to be "plug and play."

1.  **Select a Source:** Choose a preset (e.g., `ign-articles`, `esportsinsider`) or select `all` to aggregate from major gaming outlets. You can also provide a `custom` RSS feed URL.
2.  **Set Volume:** Define the `maxArticles` you want to analyze (e.g., 10 recent articles).
3.  **Run:** Click Start. The Actor will handle the scraping, fallback searching, and AI analysis automatically.

> **Tip:** Enable `Run Test Mode` in the input settings to generate dummy data. This allows you to test your integration pipelines without incurring any costs.

## Pricing

**How much does it cost to analyze gaming news?**

This Actor uses the **Pay-per-event** pricing model. This ensures you only pay when the AI successfully generates intelligence.

  * **Usage Cost:** You pay a small fee per **successful AI Analysis event**.
  * **Platform Cost:** Standard Apify platform usage fees apply for the compute time (duration of the run).

**Why this model?**
We pay for the underlying LLM (OpenRouter) and the Search API (Brave) so you don't have to manage subscriptions. The Pay-per-event fee covers these API costs. You are not charged the event fee for articles that fail to be analyzed.

## Input and Output

### Input Configuration

The input is simple and requires no API keys.

  * **News Source**: Select from a dropdown of top gaming sites.
  * **Max Articles**: Limit the number of items to control costs.
  * **Region/Time**: (Optional) Filter results if falling back to search.

### Output Example

The Actor stores results in the default Apify Dataset. You can export this as JSON, CSV, or Excel.

```json
{
  "title": "Valve Announces Half-Life 3 VR Exclusive",
  "source_feed": "IGN Articles",
  "published": "2025-12-01T12:00:00Z",
  "sentiment": "High Hype",
  "category": "Game Announcement",
  "key_entities": [
    "Half-Life 3",
    "Valve",
    "Steam Deck"
  ],
  "ai_summary": "Valve has officially announced the sequel, confirming it will be a VR-exclusive title launching in late 2026. Market analysts predict this will drive significant hardware sales for the new Deckard headset.",
  "method": "scraped",
  "url": "https://ign.com/articles/valve-announcement..."
}
```

## FAQ & Troubleshooting

**Is scraping these news sites legal?**
Our scrapers collect data from publicly available RSS feeds and news articles. We do not extract private user data. However, you should ensure your use of the data complies with copyright laws and the Terms of Service of the target websites.

**Why did some articles return "Method: search\_fallback"?**
Some gaming websites have strict anti-scraping protections. When our direct scraper is blocked, the Actor automatically queries the **Brave Search API** to find snippets and summaries of the article from across the web. This ensures you still get an AI analysis even if the direct link was inaccessible.

**Can I use a custom RSS feed?**
Yes. Select `custom` in the Source dropdown and paste any valid RSS XML URL into the `customFeedUrl` field.

**I am getting a "Maintenance" warning or empty results?**
Check if you have `runTestMode` enabled. If you are running this locally or via API, ensure you are respecting the schema. If the issue persists, please open an Issue in the Console tab.

## Advanced: The Intelligence Pipeline

For developers integrating this into a larger system (e.g., an automated WordPress blog or a Discord bot), it helps to understand the flow:

1.  **Ingest:** Fetch `N` items from the RSS feed.
2.  **Deduplicate:** Check against previous runs to avoid analyzing the same story twice (saving you money).
3.  **Scrape (Tier 1):** Attempt fast, direct HTML extraction.
4.  **Fallback (Tier 2):** If Tier 1 fails (403/429), perform a semantic search for the headline.
5.  **Synthesize:** Feed the best available text context to the LLM for structured extraction.