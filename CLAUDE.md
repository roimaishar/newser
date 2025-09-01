# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a news aggregation application that fetches RSS feeds from Israeli news sources (Ynet and Walla), deduplicates articles, and provides various output formats. The app is designed to run in GitHub Actions with OpenAI API integration for analysis and Slack notifications.

## Development Commands

Run the news aggregator (now includes AI analysis by default):
```bash
source .venv/bin/activate
python run.py news fetch --hours 24 --verbose
```

Test with different parameters:
```bash
python run.py news fetch --hours 6 --similarity 0.7 --no-dedupe --no-analysis
python run.py news fetch --hours 12 --async --slack  # With async RSS and Slack
```

Install dependencies (now using uv for faster builds):
```bash
# For development with CodeArtifact
uv pip install --extra-index-url "$UV_EXTRA_INDEX_URL" -r requirements.lock

# For GitHub Actions / public environments
uv pip install --system -r requirements.lock
```

## Architecture

- **Entry Point**: `run.py` - Sets up Python path and calls main
- **Core Logic**: `src/main.py` - CLI interface and orchestration
- **Feed Parser**: `src/core/feed_parser.py` - RSS parsing with Hebrew text support and timezone handling
- **Deduplication**: `src/core/deduplication.py` - Article deduplication using title similarity and URL matching
- **Future Integrations**: `src/integrations/` - Will contain OpenAI and Slack clients

## RSS Feed Sources

- **Ynet**: `http://www.ynet.co.il/Integration/StoryRss2.xml` (Breaking News)
- **Walla**: `https://rss.walla.co.il/MainRss` (Main RSS)

## Key Technical Details

- Uses Asia/Jerusalem timezone for all date operations
- Handles Hebrew text encoding properly (UTF-8, Windows-1255, ISO-8859-8)
- Deduplication uses configurable similarity threshold (default 0.8)
- RSS parsing with feedparser library, HTTP requests with proper User-Agent
- Time window filtering for recent articles (default 24 hours)

## Current Status

✅ Core RSS parsing and deduplication working  
✅ OpenAI integration for Hebrew analysis (now default)
✅ Slack notifications for alerts
✅ GitHub Actions workflow for automation  
✅ Async RSS fetching for better performance
✅ uv package manager for faster dependency resolution
⏳ Security improvements needed before production

## Core Refactoring Plan (December 2024)

### **CRITICAL: Modular Architecture Refactoring**

**Current Issues:**
- 3 overlapping database implementations (database_adapter.py, supabase_adapter.py, database/ module)
- Hardcoded RSS feeds preventing easy source addition
- Mixed formatting responsibilities (formatters.py + smart_formatter.py)
- Legacy code and circular import issues

**Phase 1: Critical Foundation (7-9 hours)**
1. **Database Layer Consolidation** (2-3h) ⭐⭐⭐⭐⭐
   - Move `supabase_adapter.py` → `src/core/adapters/supabase_api.py`
   - Move `database_adapter.py` → `src/core/adapters/legacy_adapter.py`
   - Consolidate connection logic in `src/core/database/`

2. **News Sources Architecture** (3-4h) ⭐⭐⭐⭐⭐
   - Create `src/core/sources/` with pluggable architecture
   - Extract RSS logic: `sources/rss/ynet.py`, `sources/rss/walla.py`
   - Enable easy addition of new sources (Twitter, Telegram, etc.)
   - Create source registry for dynamic discovery

3. **Formatting Layer Consolidation** (2h) ⭐⭐⭐⭐
   - Merge `formatters.py` + `smart_formatter.py` → `src/core/formatting/`
   - Separate display vs notification formatting
   - Create reusable templates

**Phase 2: Quality & Structure (7-10 hours)**
4. **Legacy Code Removal** (1-2h) ⭐⭐⭐
5. **Data Models Separation** (2-3h) ⭐⭐⭐⭐ - Move Article to `src/core/models/`
6. **Analysis Pipeline** (4-5h) ⭐⭐⭐⭐ - Restructure `src/core/analysis/hebrew/`

**Phase 3: Advanced Features (7-10 hours)**
7. **Notification System** (3-4h) ⭐⭐⭐⭐ - Create `src/core/notifications/`
8. **Caching Strategy** (2-3h) ⭐⭐⭐
9. **Error Handling** (2-3h) ⭐⭐⭐

**Target Architecture:**
```
src/core/
├── adapters/          # Database implementations
├── sources/           # Pluggable news sources
├── models/           # Data structures (Article, Analysis, etc.)
├── analysis/         # AI analysis pipeline
├── formatting/       # Display and notification formatting
├── notifications/    # Smart notification system
└── database/         # Core database layer (existing)
```

**Benefits:** Easy source addition, plugin-based analysis, better testability, production readiness

## Development Notes

The application currently uses relative imports within `src/` directory. The `run.py` script handles Python path setup to allow running from project root.

When adding new integrations, follow the pattern of creating separate modules in `src/integrations/` and importing them in `main.py`.