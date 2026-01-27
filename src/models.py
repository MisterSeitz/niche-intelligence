from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Any

class InputConfig(BaseModel):
    source: str = "all"
    customFeedUrl: Optional[str] = None
    maxArticles: int = 10
    region: str = "wt-wt"
    timeLimit: str = "w"
    runTestMode: bool = False

class ArticleCandidate(BaseModel):
    title: str
    url: str
    source: str
    published: Optional[str] = None
    original_summary: Optional[str] = None

class AnalysisResult(BaseModel):
    sentiment: str = Field(description="Hype/Interest level")
    category: str = Field(description="Thematic category")
    key_entities: List[str] = Field(description="Games, Studios, or People")
    summary: str = Field(description="AI synthesized summary")
    
class DatasetRecord(BaseModel):
    source_feed: str
    title: str
    url: str
    published: Optional[str]
    method: str = Field(description="Extraction method: 'scraped' or 'search_fallback'")
    sentiment: str
    category: str
    key_entities: List[str]
    ai_summary: str
    raw_context_source: Optional[str] = None