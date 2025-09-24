-- News Aggregator Database Schema
-- Run this in Supabase SQL Editor to set up the database

-- Articles table (deduplicated storage)
CREATE TABLE articles (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  link TEXT UNIQUE NOT NULL,
  source VARCHAR(50) NOT NULL,
  summary TEXT,
  published_at TIMESTAMP WITH TIME ZONE,
  content_hash VARCHAR(64) UNIQUE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient querying
CREATE INDEX idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_content_hash ON articles(content_hash);

-- Analysis results table
CREATE TABLE analyses (
  id SERIAL PRIMARY KEY,
  run_id VARCHAR(50) NOT NULL,
  analysis_type VARCHAR(20) NOT NULL, -- 'thematic' or 'updates'
  summary TEXT,
  key_topics TEXT[],
  bulletins TEXT,
  confidence DECIMAL(3,2),
  articles_analyzed INTEGER,
  has_new_content BOOLEAN DEFAULT FALSE,
  analysis_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient analysis querying
CREATE INDEX idx_analyses_analysis_timestamp ON analyses(analysis_timestamp DESC);
CREATE INDEX idx_analyses_run_id ON analyses(run_id);

-- Known items for novelty detection
CREATE TABLE known_items (
  id SERIAL PRIMARY KEY,
  item_hash VARCHAR(64) UNIQUE NOT NULL,
  item_type VARCHAR(20) NOT NULL, -- 'article', 'event', etc.
  last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient novelty checking
CREATE INDEX idx_known_items_hash ON known_items(item_hash);
CREATE INDEX idx_known_items_last_seen ON known_items(last_seen DESC);

-- Run metrics table
CREATE TABLE run_metrics (
  id SERIAL PRIMARY KEY,
  run_id VARCHAR(50) NOT NULL,
  command_used TEXT,
  articles_scraped INTEGER,
  articles_after_dedup INTEGER,
  processing_time_seconds DECIMAL(10,3),
  success BOOLEAN NOT NULL,
  error_message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security on all tables
ALTER TABLE public.articles    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analyses    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.known_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.run_metrics ENABLE ROW LEVEL SECURITY;

-- RLS Policies for service role access
CREATE POLICY service_role_full_access_articles
  ON public.articles
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY service_role_full_access_analyses
  ON public.analyses
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY service_role_full_access_known_items
  ON public.known_items
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY service_role_full_access_run_metrics
  ON public.run_metrics
  FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Index for metrics analysis
CREATE INDEX idx_run_metrics_created_at ON run_metrics(created_at DESC);
CREATE INDEX idx_run_metrics_success ON run_metrics(success);

-- Data retention function (cleanup old records)
CREATE OR REPLACE FUNCTION cleanup_old_records()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER := 0;
  temp_count INTEGER;
BEGIN
  -- Delete articles older than 90 days
  DELETE FROM articles 
  WHERE created_at < NOW() - INTERVAL '90 days';
  GET DIAGNOSTICS temp_count = ROW_COUNT;
  deleted_count := deleted_count + temp_count;
  
  -- Delete analyses older than 30 days
  DELETE FROM analyses 
  WHERE created_at < NOW() - INTERVAL '30 days';
  GET DIAGNOSTICS temp_count = ROW_COUNT;
  deleted_count := deleted_count + temp_count;
  
  -- Delete known_items not seen for 60 days
  DELETE FROM known_items 
  WHERE last_seen < NOW() - INTERVAL '60 days';
  GET DIAGNOSTICS temp_count = ROW_COUNT;
  deleted_count := deleted_count + temp_count;
  
  -- Delete run_metrics older than 30 days
  DELETE FROM run_metrics 
  WHERE created_at < NOW() - INTERVAL '30 days';
  GET DIAGNOSTICS temp_count = ROW_COUNT;
  deleted_count := deleted_count + temp_count;
  
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
