#!/usr/bin/env python3
"""
Daily JSON Data Manager for News Aggregation.

Manages daily-split JSON files for articles, analyses, and metrics with
automatic cleanup and efficient access patterns.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import logging
import uuid
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    """Represents a single execution run."""
    run_id: str
    timestamp: datetime
    hours_window: int
    command_used: str
    raw_articles: List[Dict[str, Any]]
    after_dedup: int
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "hours_window": self.hours_window,
            "command_used": self.command_used,
            "raw_articles": self.raw_articles,
            "after_dedup": self.after_dedup,
            "success": self.success,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunRecord':
        """Create from dictionary loaded from JSON."""
        return cls(
            run_id=data["run_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            hours_window=data["hours_window"],
            command_used=data["command_used"],
            raw_articles=data["raw_articles"],
            after_dedup=data["after_dedup"],
            success=data["success"],
            error_message=data.get("error_message")
        )


@dataclass
class AnalysisRecord:
    """Represents a single analysis result."""
    run_id: str
    timestamp: datetime
    analysis_type: str  # "thematic" or "updates"
    hebrew_result: Optional[Dict[str, Any]]
    slack_payload: Optional[Dict[str, Any]]
    articles_analyzed: int
    confidence: float
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "analysis_type": self.analysis_type,
            "hebrew_result": self.hebrew_result,
            "slack_payload": self.slack_payload,
            "articles_analyzed": self.articles_analyzed,
            "confidence": self.confidence,
            "processing_time": self.processing_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisRecord':
        """Create from dictionary loaded from JSON."""
        return cls(
            run_id=data["run_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            analysis_type=data["analysis_type"],
            hebrew_result=data.get("hebrew_result"),
            slack_payload=data.get("slack_payload"),
            articles_analyzed=data["articles_analyzed"],
            confidence=data["confidence"],
            processing_time=data["processing_time"]
        )


class DataManager:
    """
    Manages daily-split JSON data files with automatic cleanup.
    
    Organizes data into:
    - data/articles/YYYY-MM-DD.json (raw scraped articles by day)
    - data/analyses/YYYY-MM-DD.json (analysis results by day)
    - data/metrics/YYYY-MM-DD.json (performance metrics by day)
    """
    
    def __init__(self, base_path: Union[str, Path] = "data", retention_days: int = 30):
        """
        Initialize data manager.
        
        Args:
            base_path: Base directory for data storage
            retention_days: How many days to keep data
        """
        self.base_path = Path(base_path)
        self.retention_days = retention_days
        
        # Create directory structure
        self.articles_dir = self.base_path / "articles"
        self.analyses_dir = self.base_path / "analyses"
        self.metrics_dir = self.base_path / "metrics"
        
        for directory in [self.articles_dir, self.analyses_dir, self.metrics_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"DataManager initialized with base_path={self.base_path}")
    
    def _get_daily_file_path(self, data_type: str, date: datetime) -> Path:
        """Get the file path for a specific data type and date."""
        date_str = date.strftime("%Y-%m-%d")
        
        if data_type == "articles":
            return self.articles_dir / f"{date_str}.json"
        elif data_type == "analyses":
            return self.analyses_dir / f"{date_str}.json"
        elif data_type == "metrics":
            return self.metrics_dir / f"{date_str}.json"
        else:
            raise ValueError(f"Unknown data type: {data_type}")
    
    def _load_daily_file(self, data_type: str, date: datetime) -> Dict[str, Any]:
        """Load a daily JSON file, creating it if it doesn't exist."""
        file_path = self._get_daily_file_path(data_type, date)
        
        if not file_path.exists():
            # Create empty structure
            empty_data = {
                "date": date.strftime("%Y-%m-%d"),
                "created": datetime.now().isoformat(),
                "runs" if data_type in ["articles", "analyses"] else "daily_totals": []
            }
            
            if data_type == "metrics":
                empty_data.update({
                    "daily_totals": {
                        "runs": 0,
                        "articles_scraped": 0,
                        "analyses_completed": 0,
                        "avg_runtime": 0.0
                    },
                    "runs": []
                })
            
            self._save_daily_file(data_type, date, empty_data)
            return empty_data
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading {file_path}: {e}")
            # Return empty structure on error
            return {"date": date.strftime("%Y-%m-%d"), "runs": []}
    
    def _save_daily_file(self, data_type: str, date: datetime, data: Dict[str, Any]):
        """Save data to a daily JSON file atomically."""
        file_path = self._get_daily_file_path(data_type, date)
        temp_path = file_path.with_suffix('.tmp')
        
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Atomic move
            temp_path.replace(file_path)
            logger.debug(f"Saved {data_type} data for {date.strftime('%Y-%m-%d')}")
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to save {data_type} data: {e}") from e
    
    def store_run_record(self, run_record: RunRecord) -> None:
        """Store a run record in the daily articles file."""
        date = run_record.timestamp.date()
        daily_data = self._load_daily_file("articles", run_record.timestamp)
        
        # Add this run to the daily data
        daily_data["runs"].append(run_record.to_dict())
        daily_data["last_updated"] = datetime.now().isoformat()
        
        self._save_daily_file("articles", run_record.timestamp, daily_data)
        logger.info(f"Stored run record {run_record.run_id}")
    
    def store_analysis_record(self, analysis_record: AnalysisRecord) -> None:
        """Store an analysis record in the daily analyses file."""
        daily_data = self._load_daily_file("analyses", analysis_record.timestamp)
        
        # Add this analysis to the daily data
        daily_data["runs"].append(analysis_record.to_dict())
        daily_data["last_updated"] = datetime.now().isoformat()
        
        self._save_daily_file("analyses", analysis_record.timestamp, daily_data)
        logger.info(f"Stored analysis record {analysis_record.run_id}")
    
    def get_recent_runs(self, days: int = 7, data_type: str = "articles") -> List[Union[RunRecord, AnalysisRecord]]:
        """Get recent runs from the last N days."""
        records = []
        end_date = datetime.now()
        
        for i in range(days):
            date = end_date - timedelta(days=i)
            try:
                daily_data = self._load_daily_file(data_type, date)
                
                for run_data in daily_data.get("runs", []):
                    if data_type == "articles":
                        records.append(RunRecord.from_dict(run_data))
                    elif data_type == "analyses":
                        records.append(AnalysisRecord.from_dict(run_data))
                        
            except Exception as e:
                logger.warning(f"Error loading {data_type} for {date.strftime('%Y-%m-%d')}: {e}")
                continue
        
        # Sort by timestamp, newest first
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records
    
    def cleanup_old_data(self, older_than_days: int = None) -> Dict[str, int]:
        """
        Clean up data files older than the specified number of days.
        
        Returns:
            Dictionary with counts of files removed by type
        """
        days_threshold = older_than_days or self.retention_days
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        removed_counts = {"articles": 0, "analyses": 0, "metrics": 0}
        
        for data_type in ["articles", "analyses", "metrics"]:
            directory = getattr(self, f"{data_type}_dir")
            
            for file_path in directory.glob("*.json"):
                try:
                    # Extract date from filename (YYYY-MM-DD.json)
                    date_str = file_path.stem
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if file_date < cutoff_date:
                        file_path.unlink()
                        removed_counts[data_type] += 1
                        logger.info(f"Removed old {data_type} file: {file_path.name}")
                        
                except ValueError:
                    # Skip files that don't match the date pattern
                    logger.warning(f"Skipping file with invalid date format: {file_path.name}")
                    continue
                except Exception as e:
                    logger.error(f"Error removing {file_path}: {e}")
                    continue
        
        total_removed = sum(removed_counts.values())
        if total_removed > 0:
            logger.info(f"Cleanup completed: removed {total_removed} old files")
        
        return removed_counts
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about stored data."""
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {}
        }
        
        for data_type in ["articles", "analyses", "metrics"]:
            directory = getattr(self, f"{data_type}_dir")
            type_stats = {
                "files": 0,
                "size_bytes": 0,
                "date_range": {"oldest": None, "newest": None}
            }
            
            json_files = list(directory.glob("*.json"))
            type_stats["files"] = len(json_files)
            
            dates = []
            for file_path in json_files:
                try:
                    type_stats["size_bytes"] += file_path.stat().st_size
                    
                    # Extract date from filename
                    date_str = file_path.stem
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    dates.append(file_date)
                    
                except (ValueError, OSError):
                    continue
            
            if dates:
                dates.sort()
                type_stats["date_range"]["oldest"] = dates[0].strftime("%Y-%m-%d")
                type_stats["date_range"]["newest"] = dates[-1].strftime("%Y-%m-%d")
            
            stats["by_type"][data_type] = type_stats
            stats["total_files"] += type_stats["files"]
            stats["total_size_bytes"] += type_stats["size_bytes"]
        
        return stats
    
    @staticmethod
    def generate_run_id() -> str:
        """Generate a unique run ID."""
        return str(uuid.uuid4())[:8]