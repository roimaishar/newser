#!/usr/bin/env python3
"""
Metrics Collection for News Aggregation Performance Tracking.

Collects and stores performance metrics, timing data, and operational
statistics to track system health and optimization opportunities.
"""

import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class TimingMetrics:
    """Performance timing metrics for a single operation."""
    operation: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "success": self.success,
            "error_message": self.error_message
        }


@dataclass
class RunMetrics:
    """Complete metrics for a single run."""
    run_id: str
    timestamp: datetime
    command: str
    total_duration: float
    operations: List[TimingMetrics]
    articles_scraped: int
    articles_after_dedup: int
    analysis_completed: bool
    slack_sent: bool
    success: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "command": self.command,
            "total_duration": self.total_duration,
            "operations": [op.to_dict() for op in self.operations],
            "articles_scraped": self.articles_scraped,
            "articles_after_dedup": self.articles_after_dedup,
            "analysis_completed": self.analysis_completed,
            "slack_sent": self.slack_sent,
            "success": self.success
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunMetrics':
        """Create from dictionary loaded from JSON."""
        operations = []
        for op_data in data.get("operations", []):
            operations.append(TimingMetrics(
                operation=op_data["operation"],
                start_time=op_data["start_time"],
                end_time=op_data["end_time"],
                duration=op_data["duration"],
                success=op_data["success"],
                error_message=op_data.get("error_message")
            ))
        
        return cls(
            run_id=data["run_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            command=data["command"],
            total_duration=data["total_duration"],
            operations=operations,
            articles_scraped=data["articles_scraped"],
            articles_after_dedup=data["articles_after_dedup"],
            analysis_completed=data["analysis_completed"],
            slack_sent=data["slack_sent"],
            success=data["success"]
        )


class MetricsCollector:
    """
    Collects and manages performance metrics and operational statistics.
    
    Provides timing context managers, aggregation functions, and storage
    to daily JSON files for analysis and monitoring.
    """
    
    def __init__(self, base_path: Union[str, Path] = "data"):
        """Initialize metrics collector."""
        self.base_path = Path(base_path)
        self.metrics_dir = self.base_path / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Current run tracking
        self._current_run_id: Optional[str] = None
        self._current_command: Optional[str] = None
        self._run_start_time: Optional[float] = None
        self._current_operations: List[TimingMetrics] = []
        self._run_stats: Dict[str, Any] = {}
        
        logger.debug("MetricsCollector initialized")
    
    def start_run(self, run_id: str, command: str) -> None:
        """Start tracking a new run."""
        self._current_run_id = run_id
        self._current_command = command
        self._run_start_time = time.time()
        self._current_operations = []
        self._run_stats = {
            "articles_scraped": 0,
            "articles_after_dedup": 0,
            "analysis_completed": False,
            "slack_sent": False,
            "success": True
        }
        
        logger.debug(f"Started tracking run {run_id} for command '{command}'")
    
    def end_run(self, success: bool = True) -> Optional[RunMetrics]:
        """End tracking the current run and return metrics."""
        if not self._current_run_id or self._run_start_time is None:
            logger.warning("No active run to end")
            return None
        
        total_duration = time.time() - self._run_start_time
        
        run_metrics = RunMetrics(
            run_id=self._current_run_id,
            timestamp=datetime.now(),
            command=self._current_command or "unknown",
            total_duration=total_duration,
            operations=self._current_operations.copy(),
            articles_scraped=self._run_stats.get("articles_scraped", 0),
            articles_after_dedup=self._run_stats.get("articles_after_dedup", 0),
            analysis_completed=self._run_stats.get("analysis_completed", False),
            slack_sent=self._run_stats.get("slack_sent", False),
            success=success and self._run_stats.get("success", True)
        )
        
        # Store metrics
        self._store_run_metrics(run_metrics)
        
        # Reset tracking
        self._current_run_id = None
        self._current_command = None
        self._run_start_time = None
        self._current_operations = []
        self._run_stats = {}
        
        logger.info(f"Completed run {run_metrics.run_id} in {total_duration:.2f}s")
        return run_metrics
    
    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        start_time = time.time()
        success = True
        error_message = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            timing = TimingMetrics(
                operation=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=success,
                error_message=error_message
            )
            
            self._current_operations.append(timing)
            logger.debug(f"Operation '{operation_name}' took {duration:.2f}s (success: {success})")
    
    def record_stat(self, key: str, value: Any) -> None:
        """Record a statistic for the current run."""
        self._run_stats[key] = value
        logger.debug(f"Recorded stat {key} = {value}")
    
    def increment_stat(self, key: str, amount: int = 1) -> None:
        """Increment a counter statistic."""
        current = self._run_stats.get(key, 0)
        self._run_stats[key] = current + amount
        logger.debug(f"Incremented stat {key} to {self._run_stats[key]}")
    
    def _store_run_metrics(self, run_metrics: RunMetrics) -> None:
        """Store run metrics to daily JSON file."""
        date = run_metrics.timestamp.date()
        file_path = self.metrics_dir / f"{date.strftime('%Y-%m-%d')}.json"
        
        # Load or create daily metrics file
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    daily_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading metrics file {file_path}: {e}")
                daily_data = self._create_empty_daily_metrics(date)
        else:
            daily_data = self._create_empty_daily_metrics(date)
        
        # Add this run to daily data
        daily_data["runs"].append(run_metrics.to_dict())
        
        # Update daily totals
        self._update_daily_totals(daily_data, run_metrics)
        
        # Save atomically
        temp_path = file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(daily_data, f, ensure_ascii=False, indent=2)
            temp_path.replace(file_path)
            logger.debug(f"Stored metrics for run {run_metrics.run_id}")
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to store metrics: {e}") from e
    
    def _create_empty_daily_metrics(self, date) -> Dict[str, Any]:
        """Create empty daily metrics structure."""
        return {
            "date": date.strftime("%Y-%m-%d"),
            "created": datetime.now().isoformat(),
            "daily_totals": {
                "runs": 0,
                "articles_scraped": 0,
                "articles_after_dedup": 0,
                "analyses_completed": 0,
                "slack_messages_sent": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "avg_runtime": 0.0,
                "avg_fetch_time": 0.0,
                "avg_analysis_time": 0.0
            },
            "runs": []
        }
    
    def _update_daily_totals(self, daily_data: Dict[str, Any], run_metrics: RunMetrics) -> None:
        """Update daily totals with new run metrics."""
        totals = daily_data["daily_totals"]
        
        # Increment counters
        totals["runs"] += 1
        totals["articles_scraped"] += run_metrics.articles_scraped
        totals["articles_after_dedup"] += run_metrics.articles_after_dedup
        
        if run_metrics.analysis_completed:
            totals["analyses_completed"] += 1
        
        if run_metrics.slack_sent:
            totals["slack_messages_sent"] += 1
        
        if run_metrics.success:
            totals["successful_runs"] += 1
        else:
            totals["failed_runs"] += 1
        
        # Calculate averages
        all_runs = daily_data["runs"] + [run_metrics.to_dict()]
        
        # Average runtime
        runtimes = [run["total_duration"] for run in all_runs]
        totals["avg_runtime"] = sum(runtimes) / len(runtimes) if runtimes else 0.0
        
        # Average fetch time (RSS fetching operations)
        fetch_times = []
        analysis_times = []
        
        for run in all_runs:
            for op in run.get("operations", []):
                if "fetch" in op["operation"].lower() and op["success"]:
                    fetch_times.append(op["duration"])
                elif "analysis" in op["operation"].lower() and op["success"]:
                    analysis_times.append(op["duration"])
        
        totals["avg_fetch_time"] = sum(fetch_times) / len(fetch_times) if fetch_times else 0.0
        totals["avg_analysis_time"] = sum(analysis_times) / len(analysis_times) if analysis_times else 0.0
        
        daily_data["last_updated"] = datetime.now().isoformat()
    
    def get_daily_metrics(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific day."""
        file_path = self.metrics_dir / f"{date.strftime('%Y-%m-%d')}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading metrics for {date.strftime('%Y-%m-%d')}: {e}")
            return None
    
    def get_recent_metrics(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get metrics for the last N days."""
        metrics = []
        end_date = datetime.now()
        
        for i in range(days):
            date = end_date - timedelta(days=i)
            daily_metrics = self.get_daily_metrics(date)
            if daily_metrics:
                metrics.append(daily_metrics)
        
        return sorted(metrics, key=lambda m: m["date"], reverse=True)
    
    def get_summary_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get summary statistics for the last N days."""
        recent_metrics = self.get_recent_metrics(days)
        
        if not recent_metrics:
            return {"error": "No metrics data available"}
        
        # Aggregate stats
        total_runs = sum(m["daily_totals"]["runs"] for m in recent_metrics)
        total_articles = sum(m["daily_totals"]["articles_scraped"] for m in recent_metrics)
        total_success = sum(m["daily_totals"]["successful_runs"] for m in recent_metrics)
        total_failed = sum(m["daily_totals"]["failed_runs"] for m in recent_metrics)
        
        # Calculate averages
        all_runtimes = []
        all_fetch_times = []
        all_analysis_times = []
        
        for day_metrics in recent_metrics:
            if day_metrics["daily_totals"]["avg_runtime"] > 0:
                all_runtimes.append(day_metrics["daily_totals"]["avg_runtime"])
            if day_metrics["daily_totals"]["avg_fetch_time"] > 0:
                all_fetch_times.append(day_metrics["daily_totals"]["avg_fetch_time"])
            if day_metrics["daily_totals"]["avg_analysis_time"] > 0:
                all_analysis_times.append(day_metrics["daily_totals"]["avg_analysis_time"])
        
        return {
            "period_days": days,
            "date_range": {
                "start": recent_metrics[-1]["date"] if recent_metrics else None,
                "end": recent_metrics[0]["date"] if recent_metrics else None
            },
            "totals": {
                "runs": total_runs,
                "articles_scraped": total_articles,
                "successful_runs": total_success,
                "failed_runs": total_failed,
                "success_rate": (total_success / total_runs * 100) if total_runs > 0 else 0
            },
            "averages": {
                "articles_per_run": total_articles / total_runs if total_runs > 0 else 0,
                "runtime_seconds": sum(all_runtimes) / len(all_runtimes) if all_runtimes else 0,
                "fetch_time_seconds": sum(all_fetch_times) / len(all_fetch_times) if all_fetch_times else 0,
                "analysis_time_seconds": sum(all_analysis_times) / len(all_analysis_times) if all_analysis_times else 0
            }
        }