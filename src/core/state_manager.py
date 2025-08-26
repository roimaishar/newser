#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State Management for News Aggregation with JSON Storage.

Handles persistent storage of known news events and analysis state to enable
novelty detection and incremental updates. Thread-safe with atomic operations.
"""

import json
import os
import threading
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@dataclass
class KnownEvent:
    """Represents a known news event for novelty detection."""
    event_id: str
    baseline: str  # Hebrew summary of what we know
    last_update: datetime
    key_facts: List[str]  # Key details already reported
    sources: List[str]  # Which sources reported it
    confidence: float  # 0-1 confidence in this being accurate
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "baseline": self.baseline,
            "last_update": self.last_update.isoformat(),
            "key_facts": self.key_facts,
            "sources": self.sources,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnownEvent':
        """Create from dictionary loaded from JSON."""
        return cls(
            event_id=data["event_id"],
            baseline=data["baseline"],
            last_update=datetime.fromisoformat(data["last_update"]),
            key_facts=data["key_facts"],
            sources=data["sources"],
            confidence=data["confidence"],
            created_at=datetime.fromisoformat(data["created_at"])
        )


class StateManager:
    """
    Manages persistent application state with JSON storage.
    
    Features:
    - Thread-safe operations with file locking
    - Atomic writes to prevent corruption
    - Automatic cleanup of old events
    - Backup and recovery mechanisms
    """
    
    def __init__(self, state_file: Union[str, Path] = "data/known_items.json", 
                 cleanup_threshold_days: int = 7):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to JSON state file
            cleanup_threshold_days: Remove events older than this many days
        """
        self.state_file = Path(state_file)
        self.cleanup_threshold_days = cleanup_threshold_days
        self._lock = threading.RLock()  # Reentrant lock for nested operations
        
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize empty state if file doesn't exist
        if not self.state_file.exists():
            self._initialize_empty_state()
    
    def _initialize_empty_state(self) -> None:
        """Create empty state file with proper structure."""
        empty_state = {
            "last_update": datetime.now().isoformat(),
            "known_items": [],
            "metadata": {
                "version": "2.0",
                "total_events": 0,
                "cleanup_threshold_days": self.cleanup_threshold_days
            }
        }
        self._write_state_atomic(empty_state)
        logger.info(f"Initialized empty state file: {self.state_file}")
    
    @contextmanager
    def _file_lock(self):
        """Context manager for thread-safe file operations."""
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()
    
    def _write_state_atomic(self, state: Dict[str, Any]) -> None:
        """
        Atomically write state to file to prevent corruption.
        Uses temporary file + move for atomic operation.
        """
        temp_file = self.state_file.with_suffix('.tmp')
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            
            # Atomic move (on most filesystems)
            temp_file.replace(self.state_file)
            
        except Exception as e:
            # Clean up temp file on failure
            if temp_file.exists():
                temp_file.unlink()
            raise RuntimeError(f"Failed to write state file: {e}") from e
    
    def _read_state(self) -> Dict[str, Any]:
        """Read and validate state from file."""
        if not self.state_file.exists():
            self._initialize_empty_state()
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Validate required fields
            required_fields = ["last_update", "known_items", "metadata"]
            for field in required_fields:
                if field not in state:
                    raise ValueError(f"Missing required field: {field}")
            
            return state
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Corrupted state file: {e}")
            # Create backup of corrupted file
            backup_file = self.state_file.with_suffix('.corrupted')
            if self.state_file.exists():
                self.state_file.rename(backup_file)
                logger.info(f"Backed up corrupted file to: {backup_file}")
            
            # Initialize fresh state
            self._initialize_empty_state()
            return self._read_state()
    
    def get_known_events(self) -> List[KnownEvent]:
        """Get all known events, sorted by last update (newest first)."""
        with self._file_lock():
            state = self._read_state()
            events = []
            
            for item_data in state["known_items"]:
                try:
                    event = KnownEvent.from_dict(item_data)
                    events.append(event)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping malformed event: {e}")
                    continue
            
            # Sort by last update, newest first
            events.sort(key=lambda e: e.last_update, reverse=True)
            return events
    
    def add_or_update_event(self, event: KnownEvent) -> None:
        """
        Add new event or update existing one.
        Events are matched by event_id.
        """
        with self._file_lock():
            state = self._read_state()
            
            # Find existing event
            existing_index = None
            for i, item in enumerate(state["known_items"]):
                if item.get("event_id") == event.event_id:
                    existing_index = i
                    break
            
            # Update or append
            event_dict = event.to_dict()
            if existing_index is not None:
                state["known_items"][existing_index] = event_dict
                logger.debug(f"Updated existing event: {event.event_id}")
            else:
                state["known_items"].append(event_dict)
                logger.debug(f"Added new event: {event.event_id}")
            
            # Update metadata
            state["last_update"] = datetime.now().isoformat()
            state["metadata"]["total_events"] = len(state["known_items"])
            
            self._write_state_atomic(state)
    
    def add_events_bulk(self, events: List[KnownEvent]) -> None:
        """Add multiple events efficiently in a single operation."""
        if not events:
            return
            
        with self._file_lock():
            state = self._read_state()
            
            # Create lookup for existing events
            existing_events = {item.get("event_id"): i 
                             for i, item in enumerate(state["known_items"])}
            
            # Process all events
            for event in events:
                event_dict = event.to_dict()
                
                if event.event_id in existing_events:
                    # Update existing
                    index = existing_events[event.event_id]
                    state["known_items"][index] = event_dict
                else:
                    # Add new
                    state["known_items"].append(event_dict)
                    existing_events[event.event_id] = len(state["known_items"]) - 1
            
            # Update metadata
            state["last_update"] = datetime.now().isoformat()
            state["metadata"]["total_events"] = len(state["known_items"])
            
            self._write_state_atomic(state)
            logger.info(f"Bulk updated {len(events)} events")
    
    def cleanup_old_events(self, threshold_days: Optional[int] = None) -> int:
        """
        Remove events older than threshold.
        
        Args:
            threshold_days: Override default cleanup threshold
            
        Returns:
            Number of events removed
        """
        days = threshold_days or self.cleanup_threshold_days
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with self._file_lock():
            state = self._read_state()
            original_count = len(state["known_items"])
            
            # Filter out old events
            state["known_items"] = [
                item for item in state["known_items"]
                if datetime.fromisoformat(item["last_update"]) >= cutoff_date
            ]
            
            removed_count = original_count - len(state["known_items"])
            
            if removed_count > 0:
                # Update metadata
                state["last_update"] = datetime.now().isoformat()
                state["metadata"]["total_events"] = len(state["known_items"])
                
                self._write_state_atomic(state)
                logger.info(f"Cleaned up {removed_count} old events (older than {days} days)")
            
            return removed_count
    
    def reset_state(self) -> None:
        """Reset to empty state (removes all known events)."""
        with self._file_lock():
            # Create backup before reset
            if self.state_file.exists():
                backup_file = self.state_file.with_suffix(f'.backup_{int(datetime.now().timestamp())}')
                self.state_file.rename(backup_file)
                logger.info(f"Created backup before reset: {backup_file}")
            
            self._initialize_empty_state()
            logger.info("Reset state to empty")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get state statistics for monitoring."""
        with self._file_lock():
            state = self._read_state()
            events = self.get_known_events()
            
            if events:
                oldest_event = min(events, key=lambda e: e.created_at)
                newest_event = max(events, key=lambda e: e.last_update)
            else:
                oldest_event = newest_event = None
            
            # Events by source
            events_by_source = {}
            for event in events:
                for source in event.sources:
                    events_by_source[source] = events_by_source.get(source, 0) + 1
            
            # Recent events (last 10)
            recent_events = sorted(events, key=lambda e: e.last_update, reverse=True)[:10]
            
            return {
                "total_events": len(events),
                "last_update": state["last_update"],
                "oldest_event_date": oldest_event.created_at.isoformat() if oldest_event else None,
                "newest_update_date": newest_event.last_update.isoformat() if newest_event else None,
                "cleanup_threshold_days": self.cleanup_threshold_days,
                "state_file_size_bytes": self.state_file.stat().st_size if self.state_file.exists() else 0,
                "events_by_source": events_by_source,
                "recent_events": recent_events
            }
    
    @staticmethod
    def generate_event_id(title: str, source: str = "", date_str: str = "") -> str:
        """
        Generate stable event ID from article metadata.
        
        Args:
            title: Article title (main identifier)
            source: News source name
            date_str: Date string for uniqueness
            
        Returns:
            Stable event ID string
        """
        # Normalize inputs
        title_clean = title.strip().lower()
        source_clean = source.strip().lower()
        date_clean = date_str.strip()
        
        # Create composite string
        composite = f"{source_clean}:{title_clean}:{date_clean}"
        
        # Generate short hash
        hash_obj = hashlib.sha256(composite.encode('utf-8'))
        short_hash = hash_obj.hexdigest()[:12]
        
        # Create readable ID
        source_prefix = source_clean[:4] if source_clean else "news"
        return f"{source_prefix}_{short_hash}"