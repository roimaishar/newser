# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a news aggregation application that fetches RSS feeds from Israeli news sources (Ynet and Walla), deduplicates articles, and provides various output formats. The app is designed to run in GitHub Actions with OpenAI API integration for analysis and Slack notifications.

## Development Commands

Run the news aggregator:
```bash
source .venv/bin/activate
python run.py --hours 24 --verbose
```

Test with different parameters:
```bash
python run.py --hours 6 --similarity 0.7 --no-dedupe
```

Install dependencies:
```bash
pip install -r requirements.txt
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
⏳ Security improvements needed before production
⏳ OpenAI integration for article summarization
⏳ Slack notifications for alerts
⏳ GitHub Actions workflow for automation

## Development Notes

The application currently uses relative imports within `src/` directory. The `run.py` script handles Python path setup to allow running from project root.

When adding new integrations, follow the pattern of creating separate modules in `src/integrations/` and importing them in `main.py`.