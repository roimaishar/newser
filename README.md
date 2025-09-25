# Israeli News Aggregator 📰🇮🇱

A Python application that aggregates news headlines from Israeli news sources (Ynet and Walla), deduplicates articles, and provides AI-powered analysis with Slack notifications.

## Features

- ✅ **RSS Feed Parsing** - Fetches from Ynet and Walla news sources
- ✅ **Hebrew Text Support** - Proper encoding handling for Hebrew content
- ✅ **Deduplication** - Smart duplicate detection using title similarity and URL matching
- ✅ **Security Validation** - Input sanitization and URL validation
- ✅ **AI Analysis** - OpenAI-powered summarization and insights (optional)
- ✅ **Structured LLM Outputs** - JSON-schema validation with Hebrew text sanitization
- ✅ **Slack Integration** - Formatted notifications with rich content (optional)
- ✅ **GitHub Actions** - Automated scheduling and deployment
- ✅ **Timezone Handling** - Asia/Jerusalem timezone support

## Quick Start

### Local Usage

```bash
# Clone and setup
git clone <repository>
cd newser
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Basic usage
python run.py --hours 24

# With AI analysis and Slack (requires API keys)
export OPENAI_API_KEY="your-openai-api-key"
export SLACK_WEBHOOK_URL="your-slack-webhook-url"
python run.py --hours 6 --ai-analysis --slack
```

### Command Options

```bash
python run.py [OPTIONS]

Options:
  --hours N           Look back N hours for articles (default: 24)
  --similarity X      Deduplication threshold 0-1 (default: 0.8)
  --no-dedupe         Skip deduplication
  --ai-analysis       Enable OpenAI analysis (requires OPENAI_API_KEY)
  --slack             Send to Slack (requires SLACK_WEBHOOK_URL)
  --test-integrations Test API connections
  --verbose, -v       Verbose logging
```

## GitHub Actions Setup

### 1. Repository Secrets

Go to your repository **Settings > Secrets and variables > Actions** and add:

```
OPENAI_API_KEY=sk-your-openai-api-key-here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 2. Workflow Schedule

The GitHub Actions workflow runs automatically:
- **Every 4 hours** during Israel business hours
- **Manual trigger** with custom parameters
- **Error alerts** sent to Slack on failures

### 3. Manual Trigger

1. Go to **Actions** tab in your repository
2. Select **"Israeli News Aggregator"** workflow  
3. Click **"Run workflow"**
4. Adjust parameters as needed

## API Keys Setup

### OpenAI API Key
1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Add to GitHub Secrets as `OPENAI_API_KEY`

### Slack Webhook URL
1. Go to [Slack Apps](https://api.slack.com/apps)
2. Create new app > Incoming Webhooks
3. Add to workspace and copy webhook URL
4. Add to GitHub Secrets as `SLACK_WEBHOOK_URL`

## Testing

```bash
python -m pytest tests/integration -v
```

Run inside the project virtualenv after installing `requirements.txt`. The integration suite covers the OpenAI structured output flow, smart notification scheduler, and Hebrew text sanitization.

## Architecture

```
newser/
├── src/
│   ├── core/
│   │   ├── feed_parser.py      # RSS parsing with Hebrew support
│   │   ├── deduplication.py    # Content deduplication
│   │   ├── security.py         # Input validation & sanitization
│   │   ├── text_sanitizer.py   # Hebrew quote normalization & preprocessing
│   │   └── schemas.py          # Central JSON schemas for LLM outputs
│   ├── integrations/
│   │   ├── openai_client.py    # AI analysis integration
│   │   └── slack_notifier.py   # Slack notifications
│   └── main.py                 # CLI and orchestration
├── tests/
│   └── integration/            # Integration tests for analysis & notifications
├── .github/workflows/
│   └── news-aggregator.yml     # Automated workflow
├── run.py                      # Entry point
└── requirements.txt            # Dependencies
```

## Security Features

- **URL Validation** - Only allows trusted news domains
- **Content Sanitization** - Removes HTML tags and suspicious content  
- **Rate Limiting** - Prevents abuse and API overuse
- **Input Validation** - Validates all external data
- **Secure Defaults** - Conservative security settings

## Examples

### Basic News Aggregation
```bash
python run.py --hours 6
```
```
=== Israeli News Headlines - Last 6 Hours ===
Generated at: 2025-08-21 22:36:51
Total articles: 8

[2025-08-21 22:27] [YNET] ההודעה הדרמטית והמסר המעומעם
    https://www.ynet.co.il/news/article/r1vqaankge
...
```

### With AI Analysis
```bash  
python run.py --hours 12 --ai-analysis
```
```
=== AI ANALYSIS ===
Summary: Current Israeli headlines focus on political negotiations, security concerns, and domestic policy debates.
Key Topics: politics, security, diplomacy, domestic affairs
Sentiment: neutral
Key Insights:
  • Ongoing negotiation efforts for conflict resolution
  • Political tensions around military service requirements
  • Security incidents continue to shape public discourse
```

### Slack Notification
Rich formatted messages sent to your Slack channel with:
- 📊 Article count and sources
- 🤖 AI-generated summary and insights  
- 📰 Top headlines with direct links
- 🕐 Timestamps in Israel timezone

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development guidance.

## License

MIT License - see LICENSE file for details.