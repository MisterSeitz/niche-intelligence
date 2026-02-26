import os
import json
from openai import OpenAI, RateLimitError
from apify import Actor
from ..models import AnalysisResult
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Global set to track models that have failed (404, 400) or been rate-limited (429)
FAILED_MODELS = set()

# --- HELPER: Niche Prompts ---
def get_niche_instructions(niche: str) -> str:
    niche = niche.lower()
    
    if niche == "gaming":
        return """
        EXTRACT GAMING INTEL:
        - game_studio: Developer or Publisher name.
        - game_genre: E.g., RPG, FPS, Strategy.
        - platform: List of platforms (PC, PS5, Xbox, Switch, Mobile).
        - release_status: Announced, Released, Delayed, Cancelled.
        """
    elif niche == "crime":
        return """
        EXTRACT CRIME & SAFETY INTEL:
        - incidents: List of specific events (Robbery, Protest, Hijacking) with:
            - type: The crime/incident type.
            - description: Brief summary of what happened.
            - location: Specific street/suburb/city.
            - severity: 1 (Minor) to 3 (Critical/Fatal).
        - people: Suspects (Wanted/Arrested), Victims, Officials.
        - organizations: Gangs (e.g. 'Fast Guns'), Security Companies, Police Units.
        """
    elif niche == "politics" or niche == "gov":
        return """
        EXTRACT POLITICAL INTEL:
        - people: Politicians, Government Officials.
        - organizations: Political Parties (ANC, DA, EFF), Government Departments.
        - sentiment: Analyze if this is positive/negative for the ruling party or opposition.
        """
    elif niche == "realestate":
        return """
        EXTRACT REAL ESTATE INTEL:
        - property_type: Residential, Commercial, Industrial, etc.
        - listing_price: Extracted price string (e.g., "$1.5M").
        - sqft: Square footage/meterage size context.
        - market_status: Hot, Cooling, Crash, Boom.
        """
    elif niche == "vc":
        return """
        EXTRACT VC / STARTUP INTEL:
        - company_name: The main startup being funded or discussed.
        - round_type: Seed, Series A, IPO, Acquisition.
        - funding_amount: Amount raised (e.g., "$10M").
        - investor_list: List of VC firms or angels mentioned.
        """
    elif niche == "crypto":
        return """
        EXTRACT CRYPTO INTEL:
        - token_symbol: Ticker symbol (BTC, ETH, SOL).
        - market_trend: Bullish, Bearish, Neutral.
        - regulatory_impact: High, Medium, Low (regarding laws/sec).
        """
    elif niche == "energy":
        return """
        EXTRACT ENERGY INTEL:
        - energy_type: Solar, Wind, Hydro, Coal, Nuclear, Gas, Grid.
        - infrastructure_project: Name of power plant or project.
        - capacity: Capacity in MW or GW (e.g. "500MW").
        - status: Planned, Construction, Operational, Decommissioned.
        - organizations: Energy companies (Eskom), IPPs.
        """
    elif niche == "motoring":
        return """
        EXTRACT MOTORING INTEL:
        - vehicle_make: Toyota, BMW, Ford, etc.
        - vehicle_model: Corolla, M3, F-150.
        - vehicle_type: SUV, Sedan, EV, Truck, Hatchback.
        - price_range: Estimated cost or listed price (e.g. "R500,000", "$30k").
        """
    
    return "Extract People and Organizations mentioned."

def analyze_content(content: str, niche: str = "general", run_test_mode: bool = False) -> AnalysisResult:
    """
    Analyzes content using LLM to extract structured intelligence.
    """
    if run_test_mode:
        # Return mock data based on niche
        if niche == "gaming":
            return AnalysisResult(
                sentiment="High Hype",
                category="New Release",
                key_entities=["Bethesda", "Elder Scrolls 6"],
                summary="Bethesda announces new delay for Elder Scrolls 6.",
                location="USA", city="Rockville", country="USA", is_south_africa=False,
                game_studio="Bethesda", game_genre="RPG", platform=["PC", "Xbox"], release_status="Delayed"
            )
        # Default mock
        return AnalysisResult(
            sentiment="Neutral",
            category="General News",
            key_entities=["Test Entity"],
            summary="This is a test summary.",
            location="Global",
            city=None,
            country=None,
            is_south_africa=False
        )

    parser = PydanticOutputParser(pydantic_object=AnalysisResult)
    
    niche_instructions = get_niche_instructions(niche)

    # Construct the System Prompt
    system_prompt = f"""
    You are an expert Intelligence Analyst designated to the '{niche}' sector. 
    Your goal is to extract structured, actionable intelligence from the provided article content.

    MANDATORY EXTRACTION:
    1. Sentiment: Is this 'High Hype' (viral/major news) or 'Low Hype'?
    2. Category: Thematic classification (Technology, Business, Politics, Sports, etc.).
    3. Entities: Key organizations, people, or products.
    4. Geolocation: Identify the location context (City, Country). If relevant to South Africa, flag is_south_africa=True.
    5. Detected Niche: If the article clearly belongs to a specific niche different from '{niche}', specify it (e.g. 'gaming', 'crypto', 'tech', 'nuclear', 'energy', 'education', 'foodtech', 'health', 'luxury', 'realestate', 'retail', 'social', 'vc', 'web3', 'politics', 'crime', 'sport'). Otherwise, leave null or repeat '{niche}'.
    
    RICH INTELLIGENCE (Populate these lists if applicable):
    - incidents: detailed list of crime/safety incidents (type, description, severity 1-3 from context).
    - people: detailed list of key figures (name, role, status e.g. 'Suspect', 'Official').
    - organizations: detailed list of companies/groups (name, type e.g. 'Syndicate', 'Party').

    NICHE SPECIFIC INSTRUCTIONS:
    {niche_instructions}

    OUTPUT FORMAT:
    {parser.get_format_instructions()}
    """

    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not openrouter_key:
        Actor.log.error("❌ OPENROUTER_API_KEY missing.")
        return AnalysisResult(sentiment="Error", category="Error", key_entities=[], summary="Missing API Keys", is_south_africa=False)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
    )

    llm_content = None
    
    # Models to try in sequence (OpenRouter Free -> Cheap Capable)
    # Updated based on availability and reliability
    models_sequence = [
        "google/gemma-3-27b-it:free",              # Free - New Google model
        "meta-llama/llama-3.3-70b-instruct:free",  # Free - Llama 3.3
        "openai/gpt-oss-120b:free",               # Free - OpenAI OSS
        "nvidia/nemotron-3-nano-30b-a3b:free",     # Free - Nvidia
        "google/gemini-2.0-flash-001",             # Cheap Fallback - Reliable
        "meta-llama/llama-3.3-70b-instruct"        # Cheap Fallback
    ]

    last_exception = None
    for attempt_idx, model_name in enumerate(models_sequence):
        # Skip if model is already marked as failed/rate-limited
        if model_name in FAILED_MODELS:
            Actor.log.info(f"⏭️ Skipping failed/rate-limited model: {model_name}")
            continue

        try:
            Actor.log.info(f"🤖 Attempting analysis with OpenRouter Model: {model_name}")
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this content:\n\n{content[:15000]}"}
                ],
                extra_headers={
                    "HTTP-Referer": "https://github.com/MisterSeitz/niche-intelligence",
                    "X-Title": "Niche Intelligence Actor"
                },
                response_format={"type": "json_object"}
            )
            llm_content = completion.choices[0].message.content
            Actor.log.info(f"✅ Successfully used model: {model_name}")
            break # Success!
        except RateLimitError as e:
            last_exception = e
            Actor.log.warning(f"⏳ RateLimitError with {model_name}: {e}. Marking as failed for this run.")
            FAILED_MODELS.add(model_name)
            continue # Try the next model
        except Exception as e:
            last_exception = e
            # If 404 (Not Found) or 400 (Bad Request), mark as failed permanently
            error_str = str(e)
            if "404" in error_str or "400" in error_str or "not a valid model ID" in error_str:
                 Actor.log.error(f"❌ Invalid Model {model_name}: {e}. Marking as failed for this run.")
                 FAILED_MODELS.add(model_name)
            else:
                 Actor.log.error(f"❌ Error with {model_name}: {e}. Trying next model...")
            continue # Try the next model
            
    if llm_content is None:
        Actor.log.error(f"❌ All OpenRouter Models failed. Last error: {last_exception}")
        return AnalysisResult(
            sentiment="Error",
            category="Error",
            key_entities=[],
            summary=f"All models failed. Last error: {last_exception}",
            location=None, city=None, country=None, is_south_africa=False
        )

    try:
        # Check if content is wrapped in markdown code blocks
        clean_content = llm_content.strip()
        if clean_content.startswith('```json'):
            clean_content = clean_content[7:]
        if clean_content.startswith('```'):
            clean_content = clean_content[3:]
        if clean_content.endswith('```'):
            clean_content = clean_content[:-3]
        
        # Only take the FIRST valid JSON block if multiple exist
        # Sometimes LLMs output explanations after the code block
        if "```" in clean_content:
             clean_content = clean_content.split("```")[0]

        # Use regex to extract the JSON object if there's still garbage around it
        import re
        json_match = re.search(r'(\{.*\})', clean_content, re.DOTALL)
        if json_match:
            clean_content = json_match.group(1)

        data = json.loads(clean_content.strip())
        return AnalysisResult(**data)
    except Exception as e:
        # If the LLM refused to answer (e.g. encrypted content), return a specific error result
        if "I cannot analyze" in llm_content or "encrypted" in llm_content.lower():
             return AnalysisResult(
                sentiment="Skipped",
                category="Encrypted/Obfuscated",
                key_entities=[],
                summary="Content was encrypted or obfuscated, analysis skipped.",
                location=None, city=None, country=None
            )
            
        Actor.log.error(f"JSON Parse failed: {e} | Content: {llm_content[:200]}...")
        return AnalysisResult(
            sentiment="Error",
            category="Error",
            key_entities=[],
            summary="Invalid JSON response from LLM",
            location=None, city=None, country=None, is_south_africa=False
        )