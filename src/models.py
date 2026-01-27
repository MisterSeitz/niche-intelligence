from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Any

class InputConfig(BaseModel):
    niche: str = "gaming"
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
    niche: Optional[str] = None

class AnalysisResult(BaseModel):
    sentiment: str = Field(description="Hype/Interest level")
    category: str = Field(description="Thematic category")
    key_entities: List[str] = Field(description="Games, Studios, or People")
    summary: str = Field(description="AI synthesized summary")
    location: Optional[str] = Field(description="General location context")
    city: Optional[str] = Field(description="Specific city if mentioned")
    country: Optional[str] = Field(description="Country context")
    is_south_africa: bool = Field(description="True if content is relevant to South Africa")
    
class DatasetRecord(BaseModel):
    niche: str
    source_feed: str
    title: str
    url: str
    published: Optional[str]
    method: str = Field(description="Extraction method: 'scraped' or 'search_fallback'")
    sentiment: str
    category: str
    key_entities: List[str]
    ai_summary: str
    location: Optional[str]
    city: Optional[str]
    country: Optional[str]
    is_south_africa: bool
    raw_context_source: Optional[str] = None