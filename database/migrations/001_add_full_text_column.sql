-- Migration: Add full_text column to articles table
-- Date: 2025-09-29
-- Purpose: Store full article content for enhanced LLM analysis

-- Add full_text column to articles table
ALTER TABLE articles 
ADD COLUMN full_text TEXT,
ADD COLUMN full_text_fetched_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN fetch_status VARCHAR(20) DEFAULT 'pending'; -- 'pending', 'fetched', 'failed'

-- Add index for efficient querying of articles with full text
CREATE INDEX idx_articles_fetch_status ON articles(fetch_status);
CREATE INDEX idx_articles_full_text_fetched_at ON articles(full_text_fetched_at DESC);

-- Add comments for documentation
COMMENT ON COLUMN articles.full_text IS 'Full article content extracted from HTML';
COMMENT ON COLUMN articles.full_text_fetched_at IS 'Timestamp when full text was successfully fetched';
COMMENT ON COLUMN articles.fetch_status IS 'Status of full text fetching: pending, fetched, failed';
