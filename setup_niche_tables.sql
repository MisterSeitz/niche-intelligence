-- Create Schema (if strictly needed, though 'ai_intelligence' likely exists)
CREATE SCHEMA IF NOT EXISTS ai_intelligence;

-- Function to create the standard table structure for a niche
CREATE OR REPLACE FUNCTION ai_intelligence.create_niche_table(table_name text)
RETURNS void AS $$
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS ai_intelligence.%I (
            url text PRIMARY KEY,
            niche text,
            source_feed text,
            title text,
            published text,
            method text,
            sentiment text,
            category text,
            key_entities text[],
            ai_summary text,
            location text,
            city text,
            country text,
            is_south_africa boolean DEFAULT false,
            raw_context_source text,
            created_at timestamptz DEFAULT now()
        );
    ', table_name);
END;
$$ LANGUAGE plpgsql;

-- Initialize Tables for all Niches
SELECT ai_intelligence.create_niche_table('gaming');
SELECT ai_intelligence.create_niche_table('crypto');
SELECT ai_intelligence.create_niche_table('tech');
SELECT ai_intelligence.create_niche_table('nuclear');
SELECT ai_intelligence.create_niche_table('education');
SELECT ai_intelligence.create_niche_table('foodtech');
SELECT ai_intelligence.create_niche_table('health');
SELECT ai_intelligence.create_niche_table('nutrition');
SELECT ai_intelligence.create_niche_table('luxury');
SELECT ai_intelligence.create_niche_table('realestate');
SELECT ai_intelligence.create_niche_table('retail');
SELECT ai_intelligence.create_niche_table('social');
SELECT ai_intelligence.create_niche_table('vc');
SELECT ai_intelligence.create_niche_table('web3');
SELECT ai_intelligence.create_niche_table('general');
