#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Prompts for Israeli news analysis — Hebrew-first, novelty-aware.

This module centralizes all prompt templates for an LLM that ingests RSS headlines
and outputs clear, newspaper-quality Hebrew summaries — **only when there's new info**.
"""

from typing import List, Dict, Any

# Toggle if you prefer Hebrew field names in JSON (advanced)
USE_HEBREW_KEYS = False  # keep keys stable in English; values are always Hebrew


def _k(en: str, he: str) -> str:
    """Return key name based on USE_HEBREW_KEYS."""
    return he if USE_HEBREW_KEYS else en


class NewsAnalysisPrompts:
    """Collection of prompts for news analysis (Hebrew content)."""

    # ---------- SYSTEM PROMPT ----------
    SYSTEM_PROMPT = (
        "אתה עורך חדשות בכיר המתמחה באקטואליה ישראלית, בסגנון העיתונאים המובילים בעולם. "
        "תפקידך: לחשוב כמו עורך ראשי של הארץ/וול סטריט ג'ורנל - לזהות את הסיפור האמיתי מאחורי הכותרות. "
        "עקרונות עבודה: (1) פירמידה הפוכה - הדבר החשוב ביותר קודם (2) למה זה חשוב לקוראים ישראלים? "
        "(3) איך הסיפורים מתחברים זה לזה? (4) איזה טרנד גדול יותר זה מסמל? "
        "החזר JSON תקין בעברית עיתונאית חדה. כשאין מידע משמעותי - אל תמציא. "
        "התמקד בהשפעה על החיים של אנשים, לא רק בעובדות יבשות. ציין ודאות כשיש ספק."
    )

    # ---------- MAIN ANALYSIS (thematic) ----------
    @classmethod
    def _get_analysis_template(cls) -> str:
        """Get the analysis template with proper field names."""
        return """אתה עורך חדשות בכיר. נתח את החדשות מה-{{hours}} השעות האחרונות כמו שהיית כותב מאמר מערכת מובילים:

🎯 **מה הסיפור האמיתי?** (לא רק סיכום - איזה נרטיב גדול יותר מסתמן?)
📱 **בשורה אחת למובייל:** מה הדבר הכי חשוב שקורא צריך לדעת?
🔗 **איך זה מתחבר?** אילו חוטים משותפים יש בין הסיפורים?
⚡ **למה זה משנה לי?** איך זה משפיע על החיים של ישראלים?
🔮 **לאן זה מוביל?** איזה טרנד זה מסמל?

כותרות לניתוח:
{{articles_text}}

החזר JSON במבנה עיתונאי מקצועי:
{{{{
    "{mobile_headline}": "כותרת מובייל חדה (עד 60 תווים) - הדבר החשוב ביותר",
    "{story_behind_story}": "הנרטיו הגדול - מה באמת קורה כאן?",
    "{connection_threads}": ["חוט משותף 1", "דפוס חוזר 2", "קשר נסתר 3"],
    "{reader_impact}": "איך זה משפיע על חיי הקוראים הישראלים?",
    "{trend_signal}": "איזה טרנד גדול יותר זה מייצג?",
    "{editorial_judgment}": "מה כדאי לקוראים להתעדכן בו ומה לא?"
}}}}""".format(
            mobile_headline=_k("mobile_headline", "כותרת_מובייל"),
            story_behind_story=_k("story_behind_story", "הסיפור_האמיתי"),
            connection_threads=_k("connection_threads", "חוטים_משותפים"),
            reader_impact=_k("reader_impact", "השפעה_על_קוראים"),
            trend_signal=_k("trend_signal", "איתות_טרנד"),
            editorial_judgment=_k("editorial_judgment", "שיקול_מערכתי"),
        )

    # ---------- DELTA/UPDATES (novelty filter) ----------
    @classmethod
    def _get_update_template(cls) -> str:
        """Get the update template with proper field names."""
        return """אתה עורך חדשות בכיר שמסנן רעש מאיתותים. השווה החדשות החדשות לידע הקודם.
כמו בוב וודוורד - חפש את מה שבאמת השתנה, לא רק מה שנחזר.

🎯 **חשיבה עיתונאית מתקדמת:**
• מה באמת חדש לעומת מה שכבר ידענו?
• איזה פרט קטן עלול להיות הסיפור הגדול?
• איזה שינוי בטון או דגש מרמז על משהו?
• איך ה"עדכון הקטן" משתלב בתמונה הכללית?

כללי ליד עיתונאי מקצועי:
- משפט ראשון: מי עשה מה, מתי, איפה, ולמה זה חשוב
- דגש על מה שהשתנה מהידע הקודם
- הקשר לתמונה הגדולה
- השפעה על חיי אנשים

ידע קודם (תקצירים לבסיס השוואה):
{{known_items_text}}

כותרות חדשות להשוואה:
{{articles_text}}

החזר/י JSON תקין בלבד במבנה הבא (ערכים בעברית):
{{{{
    "{has_new}": true/false,
    "{time_window_hours}": {{hours}},
    "{items}": [
        {{{{
            "{event_id}": "מזהה יציב לקבוצת הידיעות (למשל צירוף מי-מה-איפה-תאריך)",
            "{status}": "חדש/עדכון/כפילוּת",
            "{lede_he}": "משפט פתיחה חד וברור בעברית",
            "{what_changed_he}": ["פרט חדש 1", "פרט חדש 2"],
            "{significance_he}": "למה זה חשוב לקורא בישראל",
            "{confidence}": 0.0,
            "{evidence}": ["[מקור] כותרת — פרט מפתח אחד שנוסף"]
        }}}}
    ],
    "{bulletins_he}": "• שורת עדכון קצרה לכל פריט חדש/עדכון (ללא כפילויות), בעברית."
}}}}""".format(
            has_new=_k("has_new", "יש_חדש"),
            time_window_hours=_k("time_window_hours", "חלון_זמן_בשעות"),
            items=_k("new_or_updated_items", "פריטים"),
            event_id=_k("event_id", "מזהה_אירוע"),
            status=_k("status", "מצב"),
            lede_he=_k("lede_he", "ליד"),
            what_changed_he=_k("what_changed_he", "מה_השתנה"),
            significance_he=_k("significance_he", "למה_זה_חשוב"),
            confidence=_k("confidence", "ודאות"),
            evidence=_k("evidence", "מקורות"),
            bulletins_he=_k("bulletins_he", "עדכונים_לתצוגה"),
        )




    # ---------- Builders ----------

    @classmethod
    def _format_articles_for_prompt(cls, articles: List[Dict[str, Any]], limit: int = 20) -> str:
        """Format articles to compact lines for inclusion in prompts."""
        lines = []
        for i, a in enumerate(articles[:limit], 1):
            title = (a.get("title") or "").strip()
            source = (a.get("source") or "").strip()
            summary = (a.get("summary") or "").strip()
            link = (a.get("link") or "").strip()
            published = a.get("published")
            time_str = ""
            try:
                if hasattr(published, "strftime"):
                    time_str = published.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = ""
            base = f"{i}. [{source}] {title}"
            if time_str:
                base = f"{i}. [{time_str}] [{source}] {title}"
            if summary and len(summary) <= 200:
                base += f" — {summary}"
            if link:
                base += f" (קישור: {link})"
            lines.append(base)
        return "\n".join(lines)

    @classmethod
    def _format_known_items(cls, known_items: List[Dict[str, Any]], limit: int = 30) -> str:
        """
        known_items: list of dicts you maintain in your app, e.g.:
        {
          "event_id": "...",
          "baseline": "מה כבר ידוע בקצרה בעברית",
          "last_update": "2025-08-21 14:30",
          "key_facts": ["מספרים/שמות/מיקומים שכבר דווחו"]
        }
        """
        lines = []
        for i, it in enumerate(known_items[:limit], 1):
            eid = it.get("event_id", "")
            base = it.get("baseline", "")
            last = it.get("last_update", "")
            facts = it.get("key_facts", []) or []
            facts_str = "; ".join([str(f) for f in facts]) if facts else ""
            line = f"{i}. (event_id={eid}, עדכון אחרון={last}) — {base}"
            if facts_str:
                line += f" | ידועים: {facts_str}"
            lines.append(line)
        return "\n".join(lines) if lines else "אין ידע קודם."

    # -------- Public prompt getters --------

    @classmethod
    def get_analysis_prompt(cls, articles: List[Dict[str, Any]], hours: int = 24) -> str:
        articles_text = cls._format_articles_for_prompt(articles, limit=20)
        template = cls._get_analysis_template()
        return template.format(hours=hours, articles_text=articles_text)

    @classmethod
    def get_update_prompt(
        cls,
        articles: List[Dict[str, Any]],
        known_items: List[Dict[str, Any]],
        hours: int = 12,
    ) -> str:
        """Generate the novelty-aware update prompt (core for 'tell me only what's new')."""
        articles_text = cls._format_articles_for_prompt(articles, limit=25)
        known_items_text = cls._format_known_items(known_items, limit=40)
        template = cls._get_update_template()
        return template.format(
            hours=hours,
            articles_text=articles_text,
            known_items_text=known_items_text,
        )



# Convenience aliases
SYSTEM_PROMPT = NewsAnalysisPrompts.SYSTEM_PROMPT
get_analysis_prompt = NewsAnalysisPrompts.get_analysis_prompt
get_update_prompt = NewsAnalysisPrompts.get_update_prompt