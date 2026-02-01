-- Migration to Unify 'ai_intelligence.entries' with the Standard Niche Schema
-- This ensures 'general' news can be upserted using the standard code logic while maintaining the table expected by the View.

DO $$
BEGIN
    -- 1. Rename 'canonical_url' to 'url' if it exists and 'url' does not
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ai_intelligence' AND table_name='entries' AND column_name='canonical_url') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ai_intelligence' AND table_name='entries' AND column_name='url') THEN
        ALTER TABLE ai_intelligence.entries RENAME COLUMN canonical_url TO url;
    END IF;

    -- 2. Rename 'summary' to 'ai_summary' if it exists and 'ai_summary' does not
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ai_intelligence' AND table_name='entries' AND column_name='summary') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ai_intelligence' AND table_name='entries' AND column_name='ai_summary') THEN
        ALTER TABLE ai_intelligence.entries RENAME COLUMN summary TO ai_summary;
    END IF;

    -- 3. Rename 'sentiment_label' to 'sentiment' if it exists and 'sentiment' does not
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ai_intelligence' AND table_name='entries' AND column_name='sentiment_label') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ai_intelligence' AND table_name='entries' AND column_name='sentiment') THEN
        ALTER TABLE ai_intelligence.entries RENAME COLUMN sentiment_label TO sentiment;
    END IF;

END $$;

-- 4. Add Missing Standard Columns
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS niche text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS source_feed text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS method text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS key_entities text[];
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS location text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS city text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS country text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS is_south_africa boolean DEFAULT false;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS raw_context_source text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS image_url text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS published text; -- Adding 'published' as text to match other tables

-- 5. Add Niche-Specific Sparse Columns (Gaming, Real Estate, Motoring, etc.)
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS game_studio text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS game_genre text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS platform text[];
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS release_status text;

ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS property_type text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS listing_price text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS sqft text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS market_status text;

ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS company_name text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS round_type text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS funding_amount text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS investor_list text[];

ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS token_symbol text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS market_trend text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS regulatory_impact text;

ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS energy_type text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS infrastructure_project text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS capacity text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS status text;

ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS vehicle_make text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS vehicle_model text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS vehicle_type text;
ALTER TABLE ai_intelligence.entries ADD COLUMN IF NOT EXISTS price_range text;

-- 6. Add Unique Constraint on URL if it doesn't exist (for UPSERT)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'entries_url_unique') THEN
        ALTER TABLE ai_intelligence.entries ADD CONSTRAINT entries_url_unique UNIQUE (url);
    END IF;
END $$;
