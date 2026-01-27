import os
import json
from openai import OpenAI
from apify import Actor
from ..models import AnalysisResult

def analyze_content(context: str, run_test_mode: bool) -> AnalysisResult:
    """
    Step C: OpenRouter AI Analysis.
    """
    if run_test_mode:
        return AnalysisResult(
            sentiment="High Hype",
            category="Game Announcement",
            key_entities=["Half-Life 3", "Valve"],
            summary="Valve has officially announced Half-Life 3 VR.",
            location="Global",
            city=None,
            country=None,
            is_south_africa=False
        )

    api_key = os.getenv("ALIBABA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("ALIBABA_CLOUD_API_KEY missing in Secrets.")

    client = OpenAI(
        base_url="https://coding-intl.dashscope.aliyuncs.com/v1",
        api_key=api_key,
    )

    prompt = f"""
    You are an expert Gaming & Esports Intelligence Analyst.
    Analyze the following text (which is either a full article or search snippets).
    
    CONTEXT:
    {context}
    
    TASK:
    Return a JSON object with:
    1. 'sentiment': One of [High Hype, Moderate Interest, Informational, Negative].
    2. 'category': One of [Esports Results, Game Review, Industry News, New Release, Patch Notes, Rumor].
    3. 'key_entities': List of top 3 entities (Games, Teams, Corps).
    4. 'summary': A dense, professional, 2-sentence summary of the core news.
    5. 'location': General location context (e.g. "Cape Town, SA", "Global", "USA").
    6. 'city': Specific city if mentioned, else null.
    7. 'country': Specific country if mentioned, else null.
    8. 'is_south_africa': Boolean, true if the event/news is specific to South Africa.
    """

    content = None
    # Primary Provider: Alibaba Cloud Qwen
    try:
        completion = client.chat.completions.create(
            model="qwen3-coder-plus",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analyze this content:\n\n{context}"}
            ],
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content

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
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Analyze this content:\n\n{context}"}
                ],
                extra_headers={
                    "HTTP-Referer": "https://github.com/MisterSeitz/niche-intelligence",
                    "X-Title": "Niche Intelligence Actor"
                },
                response_format={"type": "json_object"}
            )
            content = completion.choices[0].message.content
            
        except Exception as e2:
            Actor.log.error(f"❌ OpenRouter Fallback failed: {e2}")
            return AnalysisResult(
                sentiment="Error",
                category="Error",
                key_entities=[],
                summary=f"Analysis failed. Primary: {e}, Fallback: {e2}",
                location=None,
                city=None,
                country=None,
                is_south_africa=False
            )

    try:
        data = json.loads(content)
        return AnalysisResult(**data)
    except Exception as e:
        Actor.log.error(f"JSON Parse failed: {e} | Content: {content}")
        return AnalysisResult(
            sentiment="Error",
            category="Error",
            key_entities=[],
            summary="Invalid JSON response from LLM",
            location=None,
            city=None,
            country=None,
            is_south_africa=False
        )