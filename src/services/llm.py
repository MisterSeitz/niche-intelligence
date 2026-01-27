import os
import json
from openai import OpenAI
from apify import Actor
from ..models import AnalysisResult
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

# --- HELPER: Niche Prompts ---
def get_niche_instructions(niche: str) -> str:
    if niche == "gaming":
        return """
        EXTRACT GAMING INTEL:
        - game_studio: Developer or Publisher name.
        - game_genre: E.g., RPG, FPS, Strategy.
        - platform: List of platforms (PC, PS5, Xbox, Switch, Mobile).
        - release_status: Announced, Released, Delayed, Cancelled.
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
    return ""

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
    2. Category: Thematic classification.
    3. Entities: Key organizations, people, or products.
    4. Geolocation: Identify the location context (City, Country). If relevant to South Africa, flag is_south_africa=True.
    
    {niche_instructions}

    OUTPUT FORMAT:
    {parser.get_format_instructions()}
    """

    api_key = os.getenv("ALIBABA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("ALIBABA_CLOUD_API_KEY missing in Secrets.")

    # We use standard OpenAI client for Alibaba Qwen compatibility
    client = OpenAI(
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        api_key=api_key,
    )

    llm_content = None
    
    # Primary Provider: Alibaba Cloud Qwen
    try:
        completion = client.chat.completions.create(
            model="qwen-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this content:\n\n{content[:15000]}"}
            ],
            response_format={"type": "json_object"}
        )
        llm_content = completion.choices[0].message.content

    except Exception as e:
        Actor.log.warning(f"⚠️ Alibaba Cloud failed: {e}. Falling back to OpenRouter (Free Tier)...")
        
        try:
            # Fallback Provider: OpenRouter (Free)
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if not openrouter_key:
                raise ValueError("OPENROUTER_API_KEY missing.")
                
            fallback_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
            
            completion = fallback_client.chat.completions.create(
                model="google/gemini-2.0-flash-exp:free",
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
            
        except Exception as e2:
            Actor.log.error(f"❌ OpenRouter Fallback failed: {e2}")
            return AnalysisResult(
                sentiment="Error",
                category="Error",
                key_entities=[],
                summary=f"Analysis failed. Primary: {e}, Fallback: {e2}",
                location=None, city=None, country=None, is_south_africa=False
            )

    try:
        data = json.loads(llm_content)
        return AnalysisResult(**data)
    except Exception as e:
        Actor.log.error(f"JSON Parse failed: {e} | Content: {llm_content}")
        return AnalysisResult(
            sentiment="Error",
            category="Error",
            key_entities=[],
            summary="Invalid JSON response from LLM",
            location=None, city=None, country=None, is_south_africa=False
        )