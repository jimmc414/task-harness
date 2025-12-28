"""Core data models for Task Harness.

This module contains all the dataclasses used throughout the framework:
- ValidationResult: Result of a validator check
- TaskConfig: Configuration for task execution
- TaskResult: Result of task execution
- PipelineConfig: Configuration for pipeline execution
- RunRecord: Historical record of a pipeline run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid


@dataclass(frozen=True)
class ValidationResult:
    """Result of a validator's check() method.

    Attributes:
        passed: Whether the validation passed.
        message: Human-readable description of the result.
        validator_name: Name of the validator that produced this result.
        details: Optional additional details (e.g., actual vs expected values).
    """

    passed: bool
    message: str
    validator_name: str
    details: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow using ValidationResult directly in boolean contexts."""
        return self.passed

    @classmethod
    def success(
        cls,
        validator_name: str,
        message: str = "Validation passed",
        details: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Create a successful validation result."""
        return cls(
            passed=True,
            message=message,
            validator_name=validator_name,
            details=details or {},
        )

    @classmethod
    def failure(
        cls, validator_name: str, message: str, details: dict[str, Any] | None = None
    ) -> ValidationResult:
        """Create a failed validation result."""
        return cls(
            passed=False,
            message=message,
            validator_name=validator_name,
            details=details or {},
        )


@dataclass
class TaskConfig:
    """Configuration for task execution.

    Attributes:
        timeout_seconds: Maximum time for task execution (default: 300s / 5 min).
        retries: Number of additional attempts after initial failure (default: 0).
        retry_delay_seconds: Time to wait between retry attempts (default: 5s).
        retry_on_postcondition_failure: Whether to retry if postconditions fail (default: True).
        log_level: Logging level for this task (default: "INFO").
        notify_on_failure: Whether to send notification on failure (default: True).
    """

    timeout_seconds: float = 300.0
    retries: int = 0
    retry_delay_seconds: float = 5.0
    retry_on_postcondition_failure: bool = True
    log_level: str = "INFO"
    notify_on_failure: bool = True

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retries < 0:
            raise ValueError("retries cannot be negative")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log_level: {self.log_level}")


@dataclass
class TaskResult:
    """Result of a task's run() method.

    Attributes:
        success: Whether the task completed successfully.
        message: Human-readable description of the result.
        data: Optional data to pass to subsequent tasks via context.
        error: Optional exception that caused failure.
        duration_seconds: How long the task took to execute.
    """

    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None
    duration_seconds: float = 0.0

    def __bool__(self) -> bool:
        """Allow using TaskResult directly in boolean contexts."""
        return self.success

    @classmethod
    def ok(cls, message: str = "Success", data: dict[str, Any] | None = None) -> TaskResult:
        """Create a successful task result."""
        return cls(success=True, message=message, data=data or {})

    @classmethod
    def fail(
        cls, message: str, error: Exception | None = None, data: dict[str, Any] | None = None
    ) -> TaskResult:
        """Create a failed task result."""
        return cls(success=False, message=message, error=error, data=data or {})


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution.

    Attributes:
        name: Unique identifier for the pipeline.
        description: Human-readable description.
        default_timeout_seconds: Default timeout for tasks without explicit config.
        default_retries: Default retry count for tasks without explicit config.
        default_log_level: Default log level for tasks without explicit config.
        max_runtime_seconds: Maximum total pipeline runtime (None = no limit).
        lock_retry_attempts: How many times to retry acquiring the lock.
        lock_retry_delay_seconds: Time between lock acquisition attempts.
        log_directory: Where to store log files.
        history_file: Path to the run history file.
        notify_on_failure: Send notification when pipeline fails.
        notify_on_success: Send notification when pipeline succeeds.
    """

    name: str
    description: str = ""
    default_timeout_seconds: float = 300.0
    default_retries: int = 0
    default_log_level: str = "INFO"
    max_runtime_seconds: float | None = None
    lock_retry_attempts: int = 3
    lock_retry_delay_seconds: float = 60.0
    log_directory: Path = field(default_factory=lambda: Path("./logs"))
    history_file: Path = field(default_factory=lambda: Path("./run_history.jsonl"))
    notify_on_failure: bool = True
    notify_on_success: bool = False

    def __post_init__(self) -> None:
        """Validate and normalize configuration values."""
        if not self.name:
            raise ValueError("Pipeline name is required")
        if not self.name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                f"Pipeline name must be alphanumeric with underscores/hyphens: {self.name}"
            )
        if self.default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        if self.default_retries < 0:
            raise ValueError("default_retries cannot be negative")
        if self.max_runtime_seconds is not None and self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be positive if set")

        # Normalize paths
        if isinstance(self.log_directory, str):
            object.__setattr__(self, "log_directory", Path(self.log_directory))
        if isinstance(self.history_file, str):
            object.__setattr__(self, "history_file", Path(self.history_file))


@dataclass
class RunRecord:
    """Record of a pipeline run for history tracking.

    Attributes:
        run_id: Unique identifier for this run.
        pipeline_name: Name of the pipeline that was run.
        status: Final status ("success", "failed", "cancelled").
        started_at: When the run started (ISO format).
        completed_at: When the run completed (ISO format, None if still running).
        tasks_completed: Number of tasks that completed successfully.
        tasks_failed: Number of tasks that failed.
        tasks_skipped: Number of tasks that were skipped (--start-from).
        error_message: Error message if the run failed.
        context: Final context state after pipeline completion.
        dry_run: Whether this was a dry run.
    """

    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    pipeline_name: str = ""
    status: str = "running"  # "running", "success", "failed", "cancelled"
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    error_message: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False

    def mark_complete(self, status: str, error_message: str | None = None) -> None:
        """Mark the run as complete with final status."""
        self.status = status
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if error_message:
            self.error_message = error_message

    def increment_completed(self) -> None:
        """Increment the count of completed tasks."""
        self.tasks_completed += 1

    def increment_failed(self) -> None:
        """Increment the count of failed tasks."""
        self.tasks_failed += 1

    def increment_skipped(self) -> None:
        """Increment the count of skipped tasks."""
        self.tasks_skipped += 1

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if not self.completed_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "tasks_skipped": self.tasks_skipped,
            "error_message": self.error_message,
            "dry_run": self.dry_run,
            # Note: context is intentionally excluded from history
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        """Create from dictionary (e.g., from JSON)."""
        return cls(
            run_id=data.get("run_id", ""),
            pipeline_name=data.get("pipeline_name", ""),
            status=data.get("status", "unknown"),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
            tasks_skipped=data.get("tasks_skipped", 0),
            error_message=data.get("error_message"),
            dry_run=data.get("dry_run", False),
        )
