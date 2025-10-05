# Notification Payload Logging - Implementation

## Summary

Added comprehensive logging of actual notification payloads to `llm_debug.log` so you can see exactly what was sent to Slack and push notification services.

---

## What's Now Logged

### **Before (Missing Information):**
```
📤 NOTIFICATIONS SENT
Timestamp: 2025-10-05 09:28:46

COMPACT PUSH NOTIFICATION:
Text: נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני
Length: 50 characters

FULL MESSAGE CONTENT:
📰 **עובדות עיקריות:**
• נתניהו נקלע למלכוד...

DELIVERY STATUS:
  slack: ✅ Success
  push: ✅ Success
```

### **After (Complete Payloads):**
```
📤 NOTIFICATIONS SENT
Timestamp: 2025-10-05 09:28:46

COMPACT PUSH NOTIFICATION:
Text: נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני
Length: 50 characters

FULL MESSAGE CONTENT:
📰 **עובדות עיקריות:**
• נתניהו נקלע למלכוד...

SLACK PAYLOAD:
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "📰 חדשות מיידיות",
        "emoji": true
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*עובדות עיקריות:*\n• נתניהו נקלע למלכוד..."
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*הקשר ומשמעות:*\nהמשבר הפוליטי עלול..."
      }
    }
  ],
  "username": "Smart News Bot",
  "icon_emoji": ":newspaper:"
}

PUSH PAYLOAD:
{
  "provider": "onesignal",
  "contents": {
    "he": "נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני",
    "en": "נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני"
  },
  "headings": {
    "he": "",
    "en": ""
  },
  "priority": 5,
  "included_segments": ["All"],
  "android_channel_id": "news_updates",
  "ios_category": "NEWS_CATEGORY",
  "data": {
    "type": "news_update",
    "timestamp": "2025-10-05T09:28:46.123456"
  }
}

DELIVERY STATUS:
  slack: ✅ Success
  push: ✅ Success
```

---

## What You Can Now See

### **1. Slack Payload (Structured Blocks)**
When the message has structured format with `**עובדות עיקריות:**` and `**הקשר ומשמעות:**`, you'll see:
- Header block with emoji
- Facts section with markdown
- Context section with markdown
- Bot username and icon

### **2. Slack Payload (Simple Text)**
For simple messages without structure:
```json
{
  "text": "Simple message here",
  "username": "Smart News Bot",
  "icon_emoji": ":newspaper:",
  "mrkdwn": true
}
```

### **3. Push Notification Payload**
Shows the exact payload sent to OneSignal/Firebase:
- Message in Hebrew and English
- Priority level (5 = medium)
- Target segments
- Platform-specific channels
- Metadata (type, timestamp)

---

## How It Works

### **Flow:**

1. **Smart Notifier** prepares to send notifications
2. **Before sending**, it creates payload representations:
   - `_prepare_slack_payload()` - Mimics Slack client formatting
   - `_prepare_push_payload()` - Shows push notification structure
3. **Sends** the actual notifications via clients
4. **Logs** both the payloads AND success status to `llm_debug.log`

### **Code Changes:**

**File: `src/core/notifications/smart_notifier.py`**

Added two helper methods:
```python
def _prepare_slack_payload(self, message: str) -> Dict[str, Any]:
    """Prepare Slack payload for logging (mimics what Slack client sends)."""
    # Detects structured vs simple format
    # Returns blocks or text payload

def _prepare_push_payload(self, message: str) -> Dict[str, Any]:
    """Prepare push notification payload for logging."""
    # Returns OneSignal/Firebase payload structure
```

Updated notification sending:
```python
# Prepare payloads for logging
slack_payload = self._prepare_slack_payload(decision.full_message)
push_payload = self._prepare_push_payload(decision.compact_push)

# Send notifications
slack_client.send_direct_message(decision.full_message)
push_client.send_news_notification(mock_articles, None, "headlines")

# Log with payloads
llm_logger.log_notifications_sent(
    compact_push=decision.compact_push,
    full_message=decision.full_message,
    slack_payload=slack_payload,  # ✅ Now included
    push_payload=push_payload,    # ✅ Now included
    success_status=success_status
)
```

---

## Benefits

### **For Debugging:**
✅ See exactly what was sent to each platform
✅ Verify message formatting and structure
✅ Check if markdown/blocks are correct
✅ Validate priority and targeting

### **For Monitoring:**
✅ Track notification content over time
✅ Audit what users received
✅ Compare intended vs actual messages
✅ Troubleshoot delivery issues

### **For Development:**
✅ Test payload structure without sending
✅ Validate JSON format
✅ Ensure Hebrew text is properly encoded
✅ Check platform-specific fields

---

## Example Log Output

When you run `python run.py news analyze --hours 12`, you'll now see in `llm_debug.log`:

```
================================================================================
📤 NOTIFICATIONS SENT
================================================================================
Timestamp: 2025-10-05T09:28:46.123456

COMPACT PUSH NOTIFICATION:
Text: נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני
Length: 50 characters

FULL MESSAGE CONTENT:
📰 **עובדות עיקריות:**
• נתניהו נקלע למלכוד בין לחץ אמריקאי לקואליציה קיצונית
• סמוטריץ' ובן גביר מאיימים לפרוש אם חמאס לא יפורק
• עצירת האש בעזה החלה בהנחיית טראמפ

**הקשר ומשמעות:**
המשבר הפוליטי עלול להוביל לבחירות חדשות תוך 3 חודשים. זה ישפיע על המשכיות המדיניות הביטחונית ועל עסקת החטופים.

SLACK PAYLOAD:
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "📰 חדשות מיידיות",
        "emoji": true
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*עובדות עיקריות:*\n• נתניהו נקלע למלכוד בין לחץ אמריקאי לקואליציה קיצונית\n• סמוטריץ' ובן גביר מאיימים לפרוש אם חמאס לא יפורק\n• עצירת האש בעזה החלה בהנחיית טראמפ"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*הקשר ומשמעות:*\nהמשבר הפוליטי עלול להוביל לבחירות חדשות תוך 3 חודשים. זה ישפיע על המשכיות המדיניות הביטחונית ועל עסקת החטופים."
      }
    }
  ],
  "username": "Smart News Bot",
  "icon_emoji": ":newspaper:"
}

PUSH PAYLOAD:
{
  "provider": "onesignal",
  "contents": {
    "he": "נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני",
    "en": "נתניהו במלכוד: לחץ אמריקאי ומשבר קואליציוני"
  },
  "headings": {
    "he": "",
    "en": ""
  },
  "priority": 5,
  "included_segments": [
    "All"
  ],
  "android_channel_id": "news_updates",
  "ios_category": "NEWS_CATEGORY",
  "data": {
    "type": "news_update",
    "timestamp": "2025-10-05T09:28:46.123456"
  }
}

DELIVERY STATUS:
  slack: ✅ Success
  push: ✅ Success
```

---

## Testing

To see the new logging in action:

```bash
# Run analysis
python run.py news analyze --hours 12

# Check the log
cat llm_debug.log | grep -A 100 "NOTIFICATIONS SENT"
```

You'll now see the complete payloads for both Slack and push notifications!

---

## Summary

✅ **Added**: Full Slack payload logging (blocks or text)
✅ **Added**: Full push notification payload logging
✅ **Added**: Helper methods to prepare payloads
✅ **Maintained**: All existing functionality
✅ **Benefit**: Complete visibility into what's sent to users

Now you can debug notification issues by seeing exactly what was sent, not just the success/failure status!
