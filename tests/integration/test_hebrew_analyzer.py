from datetime import datetime, timezone

import pytest

from core.analysis.hebrew.analyzer import HebrewNewsAnalyzer
from core.models.article import Article


def test_thematic_analysis_uses_structured_output(state_manager, sample_articles, fake_openai_client_factory):
    analyzer = HebrewNewsAnalyzer(state_manager, openai_client=fake_openai_client_factory())

    result = analyzer.analyze_articles_thematic(sample_articles)

    assert result.analysis_type == "thematic"
    assert "כותרת" in result.summary
    assert "רקע" in result.summary
    assert result.bulletins.splitlines()[0] == "כותרת לדוגמה"
    assert result.insights == ["השפעה על הציבור", "מגמה חדשה"]
    assert result.has_new_content is True


def test_novelty_analysis_updates_state(state_manager, sample_articles, fake_openai_client_factory):
    analyzer = HebrewNewsAnalyzer(state_manager, openai_client=fake_openai_client_factory())

    result = analyzer.analyze_articles_with_novelty(sample_articles)

    assert result.analysis_type == "updates"
    assert result.has_new_content is True
    assert len(result.new_events) == 1
    assert len(result.updated_events) == 1
    assert "זוהו" in result.summary
    assert state_manager.recorded_updates


@pytest.mark.parametrize("articles", [[], None])
def test_empty_articles_return_default(articles, state_manager):
    analyzer = HebrewNewsAnalyzer(state_manager)

    result_thematic = analyzer.analyze_articles_thematic(articles or [])
    assert result_thematic.has_new_content is False
    assert result_thematic.summary == "לא נמצאו כתבות לניתוח"

    result_updates = analyzer.analyze_articles_with_novelty(articles or [])
    assert result_updates.has_new_content is False
    assert result_updates.summary == "לא נמצאו כתבות חדשות לניתוח"


def test_confidence_calculation_handles_missing_values(state_manager, sample_articles, fake_openai_client_factory):
    novelty_response = {
        "has_new": True,
        "items": [
            {"event_id": "id-1", "status": "חדש", "confidence": 1.0},
            {"event_id": "id-2", "status": "עדכון"},
        ],
        "bulletins_he": "",
    }
    analyzer = HebrewNewsAnalyzer(state_manager, openai_client=fake_openai_client_factory(novelty_response=novelty_response))

    result = analyzer.analyze_articles_with_novelty(sample_articles)

    assert pytest.approx(result.confidence, rel=1e-3) == 0.75


def test_analyzer_accepts_article_dicts_directly(state_manager, fake_openai_client_factory):
    analyzer = HebrewNewsAnalyzer(state_manager, openai_client=fake_openai_client_factory())

    now = datetime.now(timezone.utc)
    articles = [
        Article(title="1", link="l1", source="s1", published=now).to_dict(),
        Article(title="2", link="l2", source="s2", published=now).to_dict(),
    ]

    result = analyzer.analyze_articles_thematic([Article.from_dict(item) for item in articles])

    assert result.articles_analyzed == 2
