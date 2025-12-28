"""Notification system for Task Harness.

Notifications are sent when pipelines complete (success or failure).
The default implementation is a no-op; real implementations can be
added later (email, Slack, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness.models import RunRecord
    from harness.pipeline import Pipeline


class Notifier(ABC):
    """Abstract base class for notification handlers.

    Subclasses implement specific notification mechanisms
    (email, Slack, webhook, etc.).
    """

    @abstractmethod
    def notify_success(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Send notification for successful pipeline completion.

        Args:
            pipeline: The pipeline that completed.
            record: The run record with details.

        Note:
            This method should not raise exceptions. Notification failures
            are logged but do not affect pipeline status.
        """
        pass

    @abstractmethod
    def notify_failure(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Send notification for pipeline failure.

        Args:
            pipeline: The pipeline that failed.
            record: The run record with failure details.

        Note:
            This method should not raise exceptions. Notification failures
            are logged but do not affect pipeline status.
        """
        pass


class NoOpNotifier(Notifier):
    """No-operation notifier that does nothing.

    This is the default notifier used when no real notification
    mechanism is configured. Useful for testing or when notifications
    are not needed.
    """

    def notify_success(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Do nothing on success."""
        pass

    def notify_failure(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Do nothing on failure."""
        pass


class LoggingNotifier(Notifier):
    """Notifier that logs notifications to the standard logger.

    Useful for development and debugging, or as a fallback when
    other notification mechanisms fail.
    """

    def __init__(self, logger_name: str = "harness.notification"):
        """Initialize with a logger name.

        Args:
            logger_name: Name of the logger to use.
        """
        import logging

        self._logger = logging.getLogger(logger_name)

    def notify_success(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Log successful pipeline completion."""
        duration = record.duration_seconds or 0
        self._logger.info(
            f"Pipeline '{pipeline.name}' completed successfully "
            f"({record.tasks_completed} tasks in {duration:.1f}s)"
        )

    def notify_failure(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Log pipeline failure."""
        self._logger.error(
            f"Pipeline '{pipeline.name}' failed: {record.error_message} "
            f"({record.tasks_completed} completed, {record.tasks_failed} failed)"
        )


# Placeholder for future email notifier
class EmailNotifier(Notifier):
    """Email notifier (placeholder for future implementation).

    This is a stub that will be implemented in a future version.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        sender: str = "",
        recipients: list[str] | None = None,
        username: str = "",
        password: str = "",
        use_tls: bool = True,
    ):
        """Initialize email notifier (placeholder).

        Args:
            smtp_host: SMTP server hostname.
            smtp_port: SMTP server port (default 587).
            sender: Email address to send from.
            recipients: List of email addresses to send to.
            username: SMTP authentication username.
            password: SMTP authentication password.
            use_tls: Whether to use TLS (default True).
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipients = recipients or []
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def notify_success(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Send success email (not implemented)."""
        # TODO: Implement in future version
        pass

    def notify_failure(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Send failure email (not implemented)."""
        # TODO: Implement in future version
        pass
