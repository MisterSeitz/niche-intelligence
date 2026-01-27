-- Create Schema
CREATE SCHEMA IF NOT EXISTS intelligence;

-- Function to create the standard table structure for a niche
CREATE OR REPLACE FUNCTION intelligence.create_niche_table(table_name text)
RETURNS void AS $$
BEGIN
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS intelligence.%I (
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
SELECT intelligence.create_niche_table('gaming');
SELECT intelligence.create_niche_table('crypto');
SELECT intelligence.create_niche_table('tech');
SELECT intelligence.create_niche_table('nuclear');
SELECT intelligence.create_niche_table('education');
SELECT intelligence.create_niche_table('foodtech');
SELECT intelligence.create_niche_table('health');
SELECT intelligence.create_niche_table('nutrition');
SELECT intelligence.create_niche_table('luxury');
SELECT intelligence.create_niche_table('realestate');
SELECT intelligence.create_niche_table('retail');
SELECT intelligence.create_niche_table('social');
SELECT intelligence.create_niche_table('vc');
SELECT intelligence.create_niche_table('web3');
