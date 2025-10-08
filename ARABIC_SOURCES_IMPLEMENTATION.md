# Arabic News Sources - Implementation Complete ✅

## Summary

Successfully added **Al Jazeera Arabic** and **BBC Arabic** as news sources. The system now aggregates both Israeli (Hebrew) and Arab (Arabic) media, with automatic translation to Hebrew in the analysis.

---

## What Was Implemented

### **1. New Source Classes** ✅

**Created:**
- `src/core/sources/rss/aljazeera.py` - Al Jazeera Arabic RSS source
- `src/core/sources/rss/bbc_arabic.py` - BBC Arabic RSS source

**Features:**
- RSS feed parsing for Arabic content
- Metadata marking articles as Arabic (`language='ar'`)
- Automatic flagging for translation (`requires_translation=True`)

### **2. Source Registration** ✅

**Updated:** `src/core/sources/auto_register.py`
- Added imports for `AlJazeeraSource` and `BBCArabicSource`
- Registered both sources in the source registry
- Now available via `--sources aljazeera` or `--sources bbc_arabic`

### **3. CLI Integration** ✅

**Updated:** `src/cli_router.py`
- Added `aljazeera` and `bbc_arabic` to source choices
- Available in both `fetch` and `analyze` commands
- Usage: `python run.py news analyze --sources aljazeera bbc_arabic --hours 12`

### **4. LLM Prompt Enhancement** ✅

**Updated:** `src/core/analysis/hebrew/prompts.py`

**Added Multi-Source Analysis Instructions:**
```
MULTI-SOURCE ANALYSIS:
• You will receive articles from BOTH Israeli media (Hebrew) AND Arab media (Arabic)
• Israeli sources: Ynet, Walla, Haaretz, Globes
• Arab sources: Al Jazeera Arabic, BBC Arabic
• ALWAYS translate Arabic content to Hebrew in your analysis
• ALWAYS attribute claims to source: 'לפי אל-ג'זירה' / 'לפי ynet' / 'לפי BBC ערבית'
• Highlight narrative differences between Israeli and Arab coverage
• Note when Arab media reports something Israeli media doesn't
• Flag potential bias or propaganda from ANY source
```

**Key Features:**
- LLM automatically translates Arabic to Hebrew
- Source attribution in Hebrew
- Narrative comparison between Israeli and Arab media
- Bias detection for all sources

### **5. Notification Icons** ✅

**Updated:** `src/integrations/notification_formatter.py`

**Added Arabic Source Icons:**
```python
'aljazeera': '🇶🇦',  # Qatar flag
'bbc_arabic': '🌍',   # Globe (international)
```

**Example Output:**
```
🇮🇱 מקורות ישראליים:
🔴 ynet: נתניהו במלכוד
🟢 walla: משבר קואליציוני

🌍 מקורות ערביים:
🇶🇦 אל-ג'זירה: ישראל מפרה הפסקת אש
🌍 BBC ערבית: נתניהו מתחייב לחזרה לעזה
```

---

## RSS Feed URLs

### **Al Jazeera Arabic**
- URL: `https://www.aljazeera.net/xml/rss/all.xml`
- Language: Arabic
- Update Frequency: ~15 minutes
- Status: ✅ Working

### **BBC Arabic**
- URL: `https://feeds.bbci.co.uk/arabic/rss.xml`
- Language: Arabic
- Update Frequency: ~30 minutes
- Status: ✅ Working

### **Note on Al Arabiya**
- Al Arabiya has Cloudflare protection blocking automated access
- Skipped for now - can revisit with Cloudflare bypass if needed
- Alternative: Use Al Jazeera + BBC Arabic for Arab perspective

---

## How It Works

### **1. Article Fetching**
```bash
python run.py news fetch --sources aljazeera bbc_arabic --hours 12
```

- Fetches Arabic RSS feeds
- Marks articles with `language='ar'`
- Stores in database with original Arabic text

### **2. Analysis with Translation**
```bash
python run.py news analyze --sources ynet walla aljazeera --hours 12
```

**Process:**
1. Fetches articles from all sources (Hebrew + Arabic)
2. Sends to OpenAI GPT-4 with multi-source prompt
3. LLM automatically translates Arabic to Hebrew
4. LLM attributes sources: "לפי אל-ג'זירה" / "לפי ynet"
5. LLM highlights narrative differences
6. Returns Hebrew analysis with source attribution

### **3. Example Analysis Output**

```
📰 חדשות ישראל + אזור - 12 שעות אחרונות

💡 סיכום:
נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני

מאחורי הכותרות:
• לפי ynet: נתניהו נקלע למלכוד בין לחץ אמריקאי לקואליציה קיצונית
• לפי אל-ג'זירה: ישראל מפרה הפסקת אש תוך שעות מהכרזתה
• לפי BBC ערבית: נתניהו מתחייב לחזרה לעזה לאחר שחרור חטופים

🔍 פער נרטיבי:
התקשורת הישראלית מתמקדת במשבר הפוליטי הפנימי.
התקשורת הערבית מדגישה את המשך הפצצות בעזה.
```

---

## Testing

### **Test Source Registration**
```bash
cd /Users/roi.maishar/dev/Cascade/newser
PYTHONPATH=./src python -c "
from core.sources import list_available_sources
sources = list_available_sources()
print('Available sources:', sources)
assert 'aljazeera' in sources
assert 'bbc_arabic' in sources
print('✅ Arabic sources registered successfully')
"
```

### **Test RSS Fetching**
```bash
python run.py news fetch --sources aljazeera --hours 24 --verbose
```

### **Test Full Analysis**
```bash
python run.py news analyze --sources ynet aljazeera bbc_arabic --hours 12
```

---

## Cost Implications

### **Translation Costs**
- Arabic text is ~2x tokens vs English (due to UTF-8 encoding)
- Estimate per article: ~$0.01-0.03
- For 20 Arabic articles/day: ~$0.60/day = $18/month
- **Total increase: ~$20-30/month**

### **Optimization Strategies**
1. **Relevance Filtering**: Only fetch articles mentioning Israel/Palestine
2. **Summary-Only**: Translate summaries, not full text
3. **Caching**: Cache translations to avoid re-translating
4. **Batch Processing**: Process multiple articles in one API call

---

## Files Modified

1. ✅ `src/core/sources/rss/aljazeera.py` (created)
2. ✅ `src/core/sources/rss/bbc_arabic.py` (created)
3. ✅ `src/core/sources/auto_register.py` (updated)
4. ✅ `src/cli_router.py` (updated)
5. ✅ `src/core/analysis/hebrew/prompts.py` (updated)
6. ✅ `src/integrations/notification_formatter.py` (updated)

---

## Next Steps (Optional Enhancements)

### **Phase 2: Database Schema**
Add language tracking fields:
```sql
ALTER TABLE articles 
ADD COLUMN language VARCHAR(5) DEFAULT 'he',
ADD COLUMN original_language VARCHAR(5),
ADD COLUMN requires_translation BOOLEAN DEFAULT FALSE;
```

### **Phase 3: Relevance Filtering**
Only fetch Arabic articles mentioning:
- Israel (إسرائيل)
- Palestine (فلسطين)
- Gaza (غزة)
- Jerusalem (القدس)

### **Phase 4: Advanced Features**
- Sentiment analysis (Israeli vs Arab framing)
- Trend detection across sources
- Alert on narrative divergence
- Translation confidence scores

---

## Usage Examples

### **Hebrew Sources Only (Current)**
```bash
python run.py news analyze --sources ynet walla --hours 12
```

### **Arabic Sources Only**
```bash
python run.py news analyze --sources aljazeera bbc_arabic --hours 12
```

### **Combined Analysis (Recommended)**
```bash
python run.py news analyze --sources all --hours 12
```

This will fetch from ALL sources (Hebrew + Arabic) and provide 360° perspective.

---

## Commit Message

```
feat: add Al Jazeera Arabic and BBC Arabic news sources

- Created AlJazeeraSource and BBCArabicSource RSS implementations
- Registered Arabic sources in source registry
- Updated CLI to support --sources aljazeera bbc_arabic
- Enhanced LLM prompt for multi-source analysis with translation
- Added automatic Arabic→Hebrew translation in analysis
- Added source attribution (לפי אל-ג'זירה / לפי ynet)
- Added Arabic source icons (🇶🇦 🌍) to notifications
- LLM now highlights narrative differences between sources

Benefits:
- 360° regional perspective on Israeli events
- Understand Arab media framing
- Early warning of regional tensions
- Unique competitive advantage

Cost: ~$20-30/month for translation
```

---

## Ready to Test! 🚀

Run this to test the full implementation:
```bash
python run.py news analyze --sources ynet aljazeera bbc_arabic --hours 12
```

You should see Arabic articles translated to Hebrew with proper source attribution!
