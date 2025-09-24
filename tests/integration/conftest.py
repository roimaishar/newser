import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Also add the project root to handle absolute imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models.article import Article  # noqa: E402


@dataclass
class DummyKnownEvent:
    event_id: str
    baseline: str
    last_update: datetime
    key_facts: List[str]


class FakeStateManager:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.known_events: List[DummyKnownEvent] = [
            DummyKnownEvent(
                event_id="event-alpha",
                baseline="Baseline summary",
                last_update=now - timedelta(hours=6),
                key_facts=["fact-a"],
            )
        ]
        self.recent_articles: List[Dict[str, Any]] = []
        self.last_notification_timestamp: datetime = now - timedelta(hours=4)
        self.recorded_updates: List[Dict[str, Any]] = []
        self.notification_updates: List[datetime] = []

    def get_known_events(self) -> List[DummyKnownEvent]:
        return self.known_events

    def update_known_items(self, item_hashes: List[str], item_type: str = "event") -> None:
        self.recorded_updates.append({"item_type": item_type, "hashes": list(item_hashes)})

    def get_last_notification_timestamp(self) -> Optional[datetime]:
        return self.last_notification_timestamp

    def get_articles_since_timestamp(self, since_timestamp: datetime, hours_limit: int = 24) -> List[Dict[str, Any]]:
        del hours_limit
        return [article for article in self.recent_articles if article["created_at"] > since_timestamp]

    def update_last_notification_timestamp(self, timestamp: Optional[datetime] = None) -> None:
        timestamp = timestamp or datetime.now(timezone.utc)
        self.last_notification_timestamp = timestamp
        self.notification_updates.append(timestamp)


class FakeOpenAIClient:
    def __init__(
        self,
        thematic_response: Optional[Dict[str, Any]] = None,
        novelty_response: Optional[Dict[str, Any]] = None,
        notification_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.thematic_response = thematic_response or {
            "mobile_headline": "כותרת לדוגמה",
            "story_behind_story": "רקע מפורט",
            "connection_threads": ["פוליטיקה"],
            "reader_impact": "השפעה על הציבור",
            "trend_signal": "מגמה חדשה",
        }
        self.novelty_response = novelty_response or {
            "has_new": True,
            "items": [
                {
                    "event_id": "event-new",
                    "status": "חדש",
                    "lede_he": "עדכון ממשלתי",
                    "significance_he": "מעדכן את הציבור",
                    "confidence": 0.9,
                },
                {
                    "event_id": "event-update",
                    "status": "עדכון",
                    "lede_he": "נתון ביטחוני",
                    "significance_he": "חשיבות גבוהה",
                    "confidence": 0.8,
                },
            ],
            "bulletins_he": "",
        }
        self.notification_response = notification_response or {
            "should_notify_now": True,
            "compact_push": "התראה חשובה על התפתחויות באזור",
            "full_message": "פרטים מלאים על ההתפתחויות האחרונות באזור",
        }
        self.calls: Dict[str, List[Any]] = {"thematic": [], "novelty": [], "notification": []}

    def analyze_thematic(self, articles: List[Dict[str, Any]], hours: int = 24) -> Dict[str, Any]:
        self.calls["thematic"].append({"articles": articles, "hours": hours})
        return self.thematic_response

    def analyze_novelty(
        self,
        articles: List[Dict[str, Any]],
        known_items: List[Dict[str, Any]],
        hours: int = 12,
    ) -> Dict[str, Any]:
        self.calls["novelty"].append({"articles": articles, "known_items": known_items, "hours": hours})
        return self.novelty_response

    def analyze_notification_decision(
        self,
        fresh_articles: List[Dict[str, Any]],
        since_last_articles: List[Dict[str, Any]],
        previous_24h_articles: List[Dict[str, Any]],
        time_since_last: str,
    ) -> Dict[str, Any]:
        self.calls["notification"].append(
            {
                "fresh": fresh_articles,
                "since_last": since_last_articles,
                "previous_24h": previous_24h_articles,
                "time_since_last": time_since_last,
            }
        )
        return self.notification_response


class FakeNotificationScheduler:
    def __init__(self, decisions: Optional[List[Tuple[bool, Optional[datetime]]]] = None) -> None:
        self.decisions = decisions or []
        self.calls: List[Dict[str, Any]] = []

    def get_notification_decision(self, urgency: str) -> Tuple[bool, Optional[datetime]]:
        decision = self.decisions.pop(0) if self.decisions else (True, None)
        self.calls.append({"urgency": urgency, "decision": decision})
        return decision


class FakeSlackClient:
    def __init__(self, succeed: bool = True) -> None:
        self.succeed = succeed
        self.messages: List[str] = []

    def send_direct_message(self, message: str) -> bool:
        self.messages.append(message)
        return self.succeed


class FakePushClient:
    def __init__(self, succeed: bool = True) -> None:
        self.succeed = succeed
        self.notifications: List[Dict[str, Any]] = []

    def send_news_notification(self, articles: List[Dict[str, Any]], *_args) -> bool:
        self.notifications.append({"articles": articles})
        return self.succeed


@pytest.fixture
def state_manager() -> FakeStateManager:
    return FakeStateManager()


@pytest.fixture
def sample_articles() -> List[Article]:
    now = datetime.now(timezone.utc)
    return [
        Article(title="כתבה ראשונה", link="https://example.com/1", source="חדשות", published=now),
        Article(title="כתבה שנייה", link="https://example.com/2", source="חדשות", published=now - timedelta(hours=1)),
    ]


@pytest.fixture
def fake_openai_client_factory():
    def _factory(
        thematic_response: Optional[Dict[str, Any]] = None,
        novelty_response: Optional[Dict[str, Any]] = None,
        notification_response: Optional[Dict[str, Any]] = None,
    ) -> FakeOpenAIClient:
        return FakeOpenAIClient(thematic_response, novelty_response, notification_response)

    return _factory


@pytest.fixture
def fake_scheduler_factory():
    def _factory(decisions: Optional[List[Tuple[bool, Optional[datetime]]]] = None) -> FakeNotificationScheduler:
        return FakeNotificationScheduler(decisions)

    return _factory


@pytest.fixture
def fake_slack_client():
    return FakeSlackClient()


@pytest.fixture
def fake_push_client():
    return FakePushClient()
