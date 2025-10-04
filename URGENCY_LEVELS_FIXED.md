# Urgency Levels - Implementation Fixed ✅

## Summary

You were **absolutely correct** - the urgency system WAS already implemented, but the scheduling rules were **backwards**. I've now fixed it to match your requirements.

---

## What Was Wrong

### ❌ **Previous (Incorrect) Behavior:**
- **Business Hours** (7 AM - 11 PM): All levels allowed
- **Quiet Hours** (11 PM - 7 AM): Only breaking

This meant normal news could interrupt you at 9 PM!

---

## ✅ **Fixed Behavior (Your Requirements):**

### **Peak Hours** (8 AM, 12 PM, 6 PM) ± 30 minutes
- **Normal news**: ✅ Allowed (up to **7 stories**)
- **High/Breaking**: ✅ Allowed
- **Low priority**: ❌ Scheduled for later

### **Business Hours** (7 AM - 11 PM, excluding peaks)
- **Breaking**: ✅ Immediate
- **High/Urgent**: ✅ Immediate  
- **Normal**: ❌ Waits for next peak
- **Low**: ❌ Daily digest only

### **Quiet Hours** (11 PM - 7 AM)
- **Breaking**: ✅ Immediate (24/7)
- **Everything else**: ❌ Scheduled for morning

---

## How It Works Now

### **Example 1: Breaking News (פיגוע)**
```
Time: 2:00 AM (Quiet Hours)
Content: "פיגוע בירושלים: 3 הרוגים"
Urgency: BREAKING 🚨
Decision: SEND IMMEDIATELY
```

### **Example 2: High Priority During Business Hours**
```
Time: 3:00 PM (Business Hours, not peak)
Content: "קואליציה מתפרקת: בן גביר מאיים"
Urgency: HIGH 🔥
Decision: SEND IMMEDIATELY (business hours)
```

### **Example 3: Normal News During Business Hours**
```
Time: 3:00 PM (Business Hours, not peak)
Content: "ישראלי נעצר בקפריסין"
Urgency: NORMAL 📊
Decision: WAIT for next peak (6 PM)
```

### **Example 4: Normal News During Peak**
```
Time: 12:15 PM (Peak Hours)
Content: 5 regular news stories
Urgency: NORMAL 📊
Decision: SEND NOW (peak hours, up to 7 stories)
```

---

## Peak Hours Window

Peak hours have a **±30 minute window**:
- **Morning Peak**: 7:30 AM - 8:30 AM
- **Lunch Peak**: 11:30 AM - 12:30 PM
- **Evening Peak**: 5:30 PM - 6:30 PM

This gives flexibility for the system to catch users at convenient times.

---

## Story Limits

### **Normal Times**: Max 5 stories per notification
### **Peak Times**: Max **7 stories** per notification ✅

This is now configurable via:
```python
MAX_STORIES_NORMAL = 5
MAX_STORIES_PEAK = 7
```

---

## What You'll See in llm_debug.log

When you run the system, you'll now see:

```
================================================================================
🎯 URGENCY ANALYSIS
================================================================================
Timestamp: 2025-10-04 22:33:56
Articles Analyzed: 29

URGENCY SIGNALS:
  Content Keywords: משבר, מאיים, קואליציוני
  Volume: 29 articles
  Time Context: Peak=False, Quiet=False

CALCULATED URGENCY: HIGH 🔥

SCHEDULING DECISION:
  Should Notify: YES
  Send Timing: Immediate
  Reasoning: High volume: 29 fresh articles
```

---

## Files Modified

1. **`src/core/notifications/scheduler.py`**
   - Added `PEAK_HOURS` configuration
   - Added `is_peak_hours()` method
   - Added `get_max_stories_for_time()` method
   - Fixed `should_send_immediately()` logic
   - Updated stats to include peak hour info

2. **`src/core/llm_logger.py`**
   - Added `log_urgency_analysis()` method
   - Logs urgency calculation with icons
   - Shows scheduling decision reasoning

3. **`src/core/notifications/smart_notifier.py`**
   - Enhanced urgency keyword detection
   - Added urgency logging integration
   - Better reasoning for decisions

---

## Technical Details

### Urgency Calculation Logic

```python
# Breaking: Keywords detected
urgent_keywords = ["פיגוע", "רצח", "מלחמה", "טיל", "חירום", "דחוף", "הרוגים", "פצועים"]
if any(keyword in message):
    urgency = "breaking"

# High: Volume-based
elif fresh_articles_count >= 3:
    urgency = "high"

# Normal: Default
else:
    urgency = "normal"
```

### Scheduling Decision Logic

```python
if urgency == "breaking":
    return True  # Always immediate (24/7)

elif urgency == "high":
    return not is_quiet_hours  # Business hours only

elif urgency == "normal":
    return is_peak_hours and not is_quiet_hours  # Peak hours only

else:  # low
    return False  # Never immediate
```

---

## Testing

To test the new behavior:

```bash
# Run during peak hours (8 AM, 12 PM, 6 PM)
python run.py news analyze --hours 12

# Check llm_debug.log for urgency analysis
cat llm_debug.log | grep -A 20 "URGENCY ANALYSIS"
```

---

## Summary

✅ **Urgency levels**: Already implemented
✅ **Scheduling rules**: Now FIXED to match your requirements
✅ **Peak hours**: Normal news allowed (up to 7 stories)
✅ **Business hours**: Only urgent news
✅ **Quiet hours**: Only breaking news
✅ **Logging**: Full urgency analysis in llm_debug.log

The system now respects your time while ensuring critical news always gets through!
