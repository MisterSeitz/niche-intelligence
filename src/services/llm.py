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
            summary="Valve has officially announced Half-Life 3 VR."
        )

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY missing in Secrets.")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
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
    """

    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://apify.com/",
                "X-Title": "Apify Gaming Pipeline",
            },
            model="google/gemini-2.0-flash-001", # Cost-effective, high context
            messages=[
                {"role": "system", "content": "You are a JSON-only output machine."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_json = completion.choices[0].message.content
        data = json.loads(raw_json)
        
        return AnalysisResult(**data)

    except Exception as e:
        Actor.log.error(f"LLM Analysis failed: {e}")
        # Return fallback for safety
        return AnalysisResult(
            sentiment="Error",
            category="Error",
            key_entities=[],
            summary="Analysis failed due to API error."
        )