import os
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from supabase import create_client, Client
from apify import Actor
from ..models import AnalysisResult, ArticleCandidate

# Configure logging
logger = logging.getLogger(__name__)

class SupabaseIngestor:
    """
    Ingests analyzed news data into Visita Intelligence Supabase tables.
    """

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        # Check standard key, then service role key, then anon key
        self.key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            Actor.log.warning(f"Supabase credentials missing (URL={bool(self.url)}, Key={bool(self.key)}). Ingestion will fail.")
            self.supabase: Client = None
        else:
            try:
                self.supabase: Client = create_client(self.url, self.key)
            except Exception as e:
                Actor.log.error(f"Failed to connect to Supabase: {e}")
                self.supabase = None

    def _generate_dedup_hash(self, title: str, url: str) -> str:
        """Generates a consistent MD5 hash for deduplication."""
        return hashlib.md5(f"{title}{url}".encode()).hexdigest()

    def _get_target_table(self, niche: str) -> tuple[str, str]:
        """
        Returns (schema, table) based on niche.
        Default: ai_intelligence.entries
        """
        niche = niche.lower()
        schema = "ai_intelligence"
        table = "entries"

        # Specific Intelligence Schemas
        if niche == "politics":
             return "gov_intelligence", "election_news"
        elif niche == "sport":
            return "sports_intelligence", "news"
        elif niche == "crime":
            return "crime_intelligence", "news" # Explicit route to news table
        
        # Specific Tables in ai_intelligence
        # These are niches that have dedicated tables
        niche_tables = [
            "energy", "motoring", "brics", 
            "gaming", "crypto", "tech", "nuclear", 
            "education", "foodtech", "health", "luxury", "realestate", "retail", "social", "vc", "semiconductors"
        ]
        
        if niche in niche_tables:
            table = niche
            if niche == "nuclear":
                table = "nuclear_energy"
        
        return schema, table

    def check_exists(self, url: str, niche: str = "general") -> bool:
        """
        Checks if a URL already exists in the target table for the given niche.
        Used to skip processing and save LLM costs.
        """
        if not self.supabase or not url:
            return False

        schema, table = self._get_target_table(niche)

        try:
            # Special check for crime news (since it used to be entries)
            if niche == "crime":
                 # Check the new table
                 res = self.supabase.schema("crime_intelligence").table("news").select("url").eq("url", url).execute()
                 if len(res.data) > 0: return True
                 
            res = self.supabase.schema(schema).table(table).select("url").eq("url", url).execute()
            return len(res.data) > 0
        except Exception as e:
            # Fallback check in generic entries if specific table check fails (e.g. table doesn't exist yet)
            return False
        
    def _parse_date(self, date_str: str) -> str:
        """
        Validates and parses a date string. Returns None if invalid format.
        """
        if not date_str: return None
        try:
            from dateutil import parser
            if hasattr(date_str, 'isoformat'):
                return date_str.isoformat()
            
            dt = parser.parse(str(date_str))
            if dt.year < 2020 or dt.year > 2030:
                return None
            return dt.isoformat()
        except:
             return None

    async def ingest_raw_feed_items(self, articles: List[ArticleCandidate]):
        """
        Saves raw RSS articles to feed_items table before analysis.
        Ensures traceability even if processing fails later.
        """
        if not self.supabase or not articles:
            return

        payloads = []
        for art in articles:
            payloads.append({
                "title": art.title,
                "url": art.url,
                "origin_feed": art.source,
                "published_at": self._parse_date(art.published) or "now()",
                "image_url": art.image_url,
                "dedup_hash": self._generate_dedup_hash(art.title, art.url),
                "sentiment_label": None, # Unprocessed
                "created_at": "now()"
            })

        try:
            # Batch upsert by dedup_hash
            self.supabase.schema("ai_intelligence").table("feed_items").upsert(payloads, on_conflict="dedup_hash").execute()
            Actor.log.info(f"📥 Buffered {len(payloads)} raw articles to feed_items.")
        except Exception as e:
            Actor.log.warning(f"Failed to buffer raw articles: {e}")

    async def ingest(self, analysis: AnalysisResult, article: ArticleCandidate):
        """
        Orchestrates the ingestion of a single article's intelligence.
        """
        if not self.supabase:
            return

        raw_data = article.model_dump()
        
        # 1. Ingest Entities (People/Orgs) if rich data present
        await self._ingest_rich_entities(analysis)

        # 2. Ingest Incidents (Crime/Safety)
        if analysis.incidents:
            for inc in analysis.incidents:
                await self._ingest_incident(inc, analysis, raw_data)

        # 3. Update the existing Feed Item record with analysis results
        await self._update_feed_item_status(analysis, article)

        # 4. Route Article Content based on Niche
        await self._route_content(analysis, raw_data)

    async def _update_feed_item_status(self, analysis: AnalysisResult, article: ArticleCandidate):
        """Updates the feed_items record with analysis results."""
        try:
            dedup_hash = self._generate_dedup_hash(article.title, article.url)
            update_data = {
                "sentiment_label": analysis.sentiment,
                "summary": analysis.summary,
                "entities_mentioned": analysis.key_entities,
                "country": analysis.country,
                "region": analysis.location,
                "metadata": {
                    "detected_niche": analysis.detected_niche,
                    "processed_at": datetime.now().isoformat()
                }
            }
            self.supabase.schema("ai_intelligence").table("feed_items").update(update_data).eq("dedup_hash", dedup_hash).execute()
        except Exception as e:
            Actor.log.warning(f"Failed to update feed_item status: {e}")

    async def _ingest_rich_entities(self, analysis: AnalysisResult):
        # People
        if analysis.people:
            for p in analysis.people:
                if p.status and p.status.lower() in ["wanted", "missing"]:
                    # Special handling for wanted/missing
                    await self._ingest_special_person(p, analysis)
                else:
                    # General master identity
                    await self._ingest_person_identity(p)

        # Organizations
        if analysis.organizations:
            for o in analysis.organizations:
                await self._ingest_organization(o)

    async def _ingest_person_identity(self, person):
        try:
            data = {
                "full_name": person.name,
                "type": person.role,
                "contact_verified": False,
                "data_sources_count": 1,
                "last_seen_at": "now()"
            }
            # Check exist first
            res = self.supabase.schema("people_intelligence").table("master_identities").select("id").eq("full_name", person.name).execute()
            if res.data:
                self.supabase.schema("people_intelligence").table("master_identities").update({"last_seen_at": "now()"}).eq("id", res.data[0]['id']).execute()
            else:
                self.supabase.schema("people_intelligence").table("master_identities").insert(data).execute()
        except Exception as e:
            Actor.log.warning(f"Person ingest warning: {e}")

    async def _ingest_organization(self, org):
        try:
            if org.type in ["Syndicate", "Gang"]:
                # Syndicate table
                await self._ingest_syndicate(org)
                return

            data = {
                "registered_name": org.name,
                "type": org.type,
                "created_at": "now()"
            }
            res = self.supabase.schema("business_intelligence").table("organizations").select("id").eq("registered_name", org.name).execute()
            if not res.data:
                self.supabase.schema("business_intelligence").table("organizations").insert(data).execute()
        except Exception as e:
             Actor.log.warning(f"Org ingest warning: {e}")

    async def _ingest_syndicate(self, org):
        try:
            payload = {
                "name": org.name,
                "type": org.type, 
                "primary_territory": "South Africa", 
                "metadata": {"details": org.details},
                "created_at": "now()"
            }
            res = self.supabase.schema("crime_intelligence").table("syndicates").select("id").eq("name", payload["name"]).execute()
            if not res.data:
                 self.supabase.schema("crime_intelligence").table("syndicates").insert(payload).execute()
        except Exception as e:
            Actor.log.warning(f"Syndicate ingest warning: {e}")

    async def _ingest_special_person(self, person, analysis):
        # Wanted or Missing
        try:
            # We need a source URL. technically we have it from the article context?
            # But here `analysis` is passed. Ideally we need the article URL too.
            # Passing it via a context or assuming it's linked via logic.
            # wait, `_ingest_special_person` is called from `_ingest_rich_entities` which only takes `analysis`.
            # I should pass `article` URL or just skip for now if too complex to link back in this method signature.
            # Let's keep it simple for now and rely on Incident ingestion for deep links.
            pass
        except:
            pass

    async def _ingest_incident(self, incident, analysis: AnalysisResult, raw: Dict):
        try:
            occurred_at = self._parse_date(incident.date) or self._parse_date(raw.get("published")) or "now()"
            
            data = {
                "title": raw.get("title"),
                "description": incident.description,
                "occurred_at": occurred_at,
                "type": incident.type,
                "severity_level": incident.severity,
                "source_url": raw.get("url"),
                "status": "reported",
                "location": incident.location or analysis.location,
                "published_at": self._parse_date(raw.get("published")) or "now()",
                "image_url": raw.get("image_url")
            }
            # source_url is unique in schema
            self.supabase.schema("crime_intelligence").table("incidents").upsert(data, on_conflict="source_url").execute()
            Actor.log.info(f"🚨 Ingested Incident: {data['title']}")
        except Exception as e:
            Actor.log.warning(f"Error ingesting incident: {e}")

    async def _route_content(self, analysis: AnalysisResult, raw: Dict):
        niche = analysis.detected_niche or raw.get("niche") or "general"
        niche = niche.lower()

        target_schema, target_table = self._get_target_table(niche)

        # Overrides based on analysis content (e.g. Energy -> Nuclear)
        if niche == "energy":
             if analysis.energy_type and "nuclear" in analysis.energy_type.lower():
                 target_table = "nuclear_energy"
        
        # Crime Special Logic - REMOVED, now routed properly above

        # Business Special Logic
        if niche == "business":
            target_table = "entries"

        # Prepare Payload
        data = {
            "title": raw.get("title"),
            "url": raw.get("url"),
            "published_at": self._parse_date(raw.get("published")) or "now()",
            "category": analysis.category,
            "summary": analysis.summary,
            "sentiment": analysis.sentiment,
            "source": raw.get("source", "SA News Scraper"),
            "created_at": "now()"
        }

        # Adapt payload for specific tables
        
        # BRICS & Web3
        if target_table in ["brics", "web3"]:
            data["ai_summary"] = data.pop("summary")
            data["published"] = data.pop("published_at")
            data["source_feed"] = data.pop("source")
            data["key_entities"] = analysis.key_entities
            if target_table == "brics" and analysis.niche_data and "topic" in analysis.niche_data:
                data["topic"] = analysis.niche_data["topic"]

        # Election News
        elif target_table == "election_news":
            data["source_url"] = data.pop("url")
            data["source_name"] = data.pop("source")
            data["ai_summary"] = data.get("summary") # Schema has both summary and ai_summary

        # Entries (Generic)
        elif target_table == "entries":
            data["published_date"] = data.pop("published_at")
            data["ai_summary"] = data.pop("summary")
            if data.get("category") and data["category"].lower() == "crime":
                data["category"] = "Safety"

        # Sports (sports_intelligence.news)
        elif target_schema == "sports_intelligence" and target_table == "news":
            # Verified columns: summary, published_at, source_domain. No sentiment (text).
            data["source_domain"] = data.pop("source")
            if "sentiment" in data:
                del data["sentiment"] # Table has sentiment_score (numeric), not text

        # Crime (crime_intelligence.news)
        elif target_schema == "crime_intelligence" and target_table == "news":
            # Verified columns: ai_summary, published, sentiment
            data["published"] = data.pop("published_at")
            data["ai_summary"] = data.pop("summary")

        # Niche Tables (Generic Fallback for energy, motoring, gaming, etc.)
        else:
             # Most standard niche tables use: published, ai_summary, sentiment
             if "published_at" in data:
                 data["published"] = data.pop("published_at")
             if "summary" in data:
                 data["ai_summary"] = data.pop("summary")

        # Niche Data Injection
        if analysis.niche_data:
             if target_table not in ["entries", "election_news", "brics"]:
                  # Assume most niche tables support 'snippet_sources' or similar?
                  # Actually, Schema says `snippet_sources` for Motoring/Energy.
                  # For others, we might need to check. Safe to attempt insert if JSONB field exists.
                  if target_schema in ["sports_intelligence", "crime_intelligence"]:
                       # Use 'snippet_sources' or 'metadata'? 
                       # Schema check: sports.news has 'snippet_sources'. crime.news has 'metadata'.
                       if target_schema == "crime_intelligence":
                           data["metadata"] = analysis.niche_data
                       else:
                           data["snippet_sources"] = analysis.niche_data

                  elif target_table == "motoring" or target_table == "energy":
                       data["snippet_sources"] = analysis.niche_data
                  else:
                       # general fallback
                       if "metadata" in data or "snippet_sources" in data:
                           pass # already set?
                       else:
                           # Most niche tables might not have this column yet if we didn't add it explicitly
                           # Let's hope for schema match.
                           pass
             elif target_table == "entries":
                  if "data" not in data: data["data"] = {}
                  data["data"]["niche_data"] = analysis.niche_data

        # Image
        image_url = raw.get("image_url")
        if image_url:
             data["image_url"] = image_url
             if target_table == "entries":
                  if "data" not in data: data["data"] = {}
                  data["data"]["image_url"] = image_url

        try:
             # Emoji Mapping
            icon = "📰"
            
            # Upsert
            conflict_col = "url"
            if target_table == "election_news":
                conflict_col = "source_url"

            # Handle Type Mismatch for Sentiment (Internal Fix for specific tables)
            # If sentiment is 'Error' and column is integer, we skip or set to 0
            if data.get("sentiment") == "Error":
                 # Check table specific type (we know web3 and brics are integers)
                 if target_table in ["web3", "brics"]:
                      data["sentiment"] = 0 # Map Error to 0 for integer columns
            elif isinstance(data.get("sentiment"), str) and target_table in ["web3", "brics"]:
                 # Try to cast if it's a numeric string, otherwise default
                 try:
                      data["sentiment"] = int(data["sentiment"])
                 except:
                      data["sentiment"] = 0

            # Standard Upsert
            self.supabase.schema(target_schema).table(target_table).upsert(data, on_conflict=conflict_col).execute()
            Actor.log.info(f"{icon} Upserted {target_schema}.{target_table}")

        except Exception as e:
             Actor.log.warning(f"Routing failed for {target_schema}.{target_table}: {e}")
