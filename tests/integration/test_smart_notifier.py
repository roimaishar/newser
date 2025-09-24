from datetime import datetime, timedelta, timezone

import pytest

from core.notifications.smart_notifier import SmartNotifier


def test_bucket_preparation_splits_articles_by_timestamp(state_manager, fake_scheduler_factory):
    """Test that bucket preparation correctly splits articles by timestamp."""
    now = datetime.now(timezone.utc)
    
    # Set up state manager with articles at different times
    state_manager.recent_articles = [
        {"title": "Old article", "created_at": now - timedelta(hours=8)},
        {"title": "Recent article", "created_at": now - timedelta(hours=2)},
    ]
    
    scheduler = fake_scheduler_factory(decisions=[(True, None)])
    notifier = SmartNotifier(state_manager, scheduler=scheduler)
    _fresh, since_last, previous_24h, time_since = notifier.prepare_3_bucket_data([])
    
    assert len(since_last) == 1  # Recent article after last notification (4h ago)
    assert len(previous_24h) == 1  # Old article before last notification
    assert "hour" in time_since


def test_analyze_with_llm_validates_required_fields(state_manager, fake_openai_client_factory):
    """Test LLM analysis validates required response fields."""
    # Missing required field
    incomplete_response = {"should_notify_now": True, "compact_push": "Test"}
    client = fake_openai_client_factory(notification_response=incomplete_response)
    
    notifier = SmartNotifier(state_manager, openai_client=client)
    decision = notifier.analyze_with_llm([], [], [], "2 hours ago")
    
    assert decision is None


def test_analyze_with_llm_truncates_long_compact_push(state_manager, fake_openai_client_factory):
    """Test that long compact push messages are truncated intelligently."""
    long_response = {
        "should_notify_now": True,
        "compact_push": "This is a very long message that exceeds the 60 character limit and should be truncated.",
        "full_message": "Full message here",
    }
    client = fake_openai_client_factory(notification_response=long_response)
    
    notifier = SmartNotifier(state_manager, openai_client=client)
    decision = notifier.analyze_with_llm([], [], [], "2 hours ago")
    
    assert decision is not None
    assert len(decision.compact_push) <= 60
    assert decision.compact_push.endswith("...")


def test_send_notifications_respects_scheduler_decision(
    state_manager, fake_openai_client_factory, fake_scheduler_factory, fake_slack_client, fake_push_client
):
    """Test that notification sending respects scheduler decisions."""
    # Scheduler says don't send now, schedule for later
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    scheduler = fake_scheduler_factory(decisions=[(False, future_time)])
    
    client = fake_openai_client_factory()
    notifier = SmartNotifier(state_manager, openai_client=client, scheduler=scheduler)
    
    decision = notifier.analyze_with_llm([], [], [], "2 hours ago")
    sent = notifier.send_notifications_if_approved(decision, fake_slack_client, fake_push_client)
    
    assert not sent  # Should not send immediately
    assert len(fake_slack_client.messages) == 0
    assert len(fake_push_client.notifications) == 0


def test_send_notifications_sends_when_approved(
    state_manager, fake_openai_client_factory, fake_scheduler_factory, fake_slack_client, fake_push_client
):
    """Test that notifications are sent when scheduler approves."""
    scheduler = fake_scheduler_factory(decisions=[(True, None)])  # Send now
    
    client = fake_openai_client_factory()
    notifier = SmartNotifier(state_manager, openai_client=client, scheduler=scheduler)
    
    decision = notifier.analyze_with_llm([], [], [], "2 hours ago")
    sent = notifier.send_notifications_if_approved(decision, fake_slack_client, fake_push_client)
    
    assert sent
    assert len(fake_slack_client.messages) == 1
    assert len(fake_push_client.notifications) == 1
    assert len(state_manager.notification_updates) == 1  # Timestamp updated


def test_urgency_classification(state_manager, fake_openai_client_factory, fake_scheduler_factory):
    """Test that urgency is classified correctly based on message content."""
    urgent_response = {
        "should_notify_now": True,
        "compact_push": "פיגוע בירושלים",
        "full_message": "דיווח על פיגוע חמור",
    }
    
    client = fake_openai_client_factory(notification_response=urgent_response)
    scheduler = fake_scheduler_factory()
    notifier = SmartNotifier(state_manager, openai_client=client, scheduler=scheduler)
    
    decision = notifier.analyze_with_llm([], [], [], "2 hours ago")
    notifier.send_notifications_if_approved(decision)
    
    # Check that scheduler was called with "breaking" urgency
    assert len(scheduler.calls) == 1
    assert scheduler.calls[0]["urgency"] == "breaking"


def test_process_news_for_notifications_end_to_end(
    state_manager, sample_articles, fake_openai_client_factory, fake_scheduler_factory, fake_slack_client
):
    """Test the complete notification workflow end-to-end."""
    client = fake_openai_client_factory()
    scheduler = fake_scheduler_factory(decisions=[(True, None)])
    
    notifier = SmartNotifier(state_manager, openai_client=client, scheduler=scheduler)
    
    decision = notifier.process_news_for_notifications(
        [article.to_dict() for article in sample_articles], 
        slack_client=fake_slack_client
    )
    
    assert decision is not None
    assert decision.should_notify is True
    assert len(fake_slack_client.messages) == 1
    assert "פרטים מלאים" in fake_slack_client.messages[0]


def test_llm_decision_skip_does_not_send(state_manager, fake_openai_client_factory, fake_slack_client):
    """Test that when LLM decides not to notify, no notifications are sent."""
    no_notify_response = {
        "should_notify_now": False,
        "compact_push": "No urgent news",
        "full_message": "Nothing significant to report",
    }
    
    client = fake_openai_client_factory(notification_response=no_notify_response)
    notifier = SmartNotifier(state_manager, openai_client=client)
    
    decision = notifier.process_news_for_notifications([], slack_client=fake_slack_client)
    
    assert decision is not None
    assert decision.should_notify is False
    assert len(fake_slack_client.messages) == 0


def test_client_failure_handling(state_manager, fake_slack_client, fake_push_client, fake_scheduler_factory):
    """Test handling of client send failures."""
    failing_slack = fake_slack_client
    failing_slack.succeed = False
    
    failing_push = fake_push_client
    failing_push.succeed = False
    
    # Force scheduler to approve immediate send so we can test client failure handling
    scheduler = fake_scheduler_factory(decisions=[(True, None)])
    notifier = SmartNotifier(state_manager, scheduler=scheduler)
    
    # Create a mock decision that should notify
    from core.notifications.smart_notifier import NotificationDecision
    decision = NotificationDecision(
        should_notify=True,
        compact_push="Test message",
        full_message="Full test message",
        fresh_articles_count=1,
        since_last_count=0,
        previous_24h_count=0,
        time_since_last_notification="2 hours ago",
        analysis_timestamp=datetime.now(timezone.utc),
        raw_llm_response={},
    )
    
    sent = notifier.send_notifications_if_approved(decision, failing_slack, failing_push)
    
    assert not sent  # Should return False when all clients fail
    assert len(failing_slack.messages) == 1  # Attempt was made
    assert len(failing_push.notifications) == 1  # Attempt was made
    assert len(state_manager.notification_updates) == 0  # No timestamp update on failure
