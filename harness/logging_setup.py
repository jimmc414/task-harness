"""Logging setup for Task Harness.

Provides per-run log files and console output configuration.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from harness.config import get_logs_dir


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output.

    Uses ANSI escape codes for colored output when running in a terminal.
    """

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",      # Reset
    }

    def __init__(self, fmt: str = None, datefmt: str = None, use_colors: bool = True):
        """Initialize the formatter.

        Args:
            fmt: Log format string.
            datefmt: Date format string.
            use_colors: Whether to use ANSI color codes.
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()

        # Try to enable colors on Windows
        if self.use_colors and sys.platform == "win32":
            try:
                import colorama

                colorama.init()
            except ImportError:
                self.use_colors = False

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional colors."""
        result = super().format(record)

        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            result = f"{color}{result}{reset}"

        return result


def create_file_handler(
    log_file: Path,
    level: int = logging.DEBUG,
) -> logging.FileHandler:
    """Create a file handler for logging to a file.

    Args:
        log_file: Path to the log file.
        level: Logging level for this handler.

    Returns:
        Configured FileHandler.
    """
    # Ensure parent directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    return handler


def create_console_handler(
    level: int = logging.INFO,
    use_colors: bool = True,
    stream: TextIO | None = None,
) -> logging.StreamHandler:
    """Create a console handler for logging to stdout/stderr.

    Args:
        level: Logging level for this handler.
        use_colors: Whether to use colored output.
        stream: Output stream (default: sys.stdout).

    Returns:
        Configured StreamHandler.
    """
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setLevel(level)

    formatter = ColoredFormatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        use_colors=use_colors,
    )
    handler.setFormatter(formatter)

    return handler


def setup_logging(
    pipeline_name: str,
    run_id: str,
    logs_dir: Path | None = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    verbose: bool = True,
    use_colors: bool = True,
) -> tuple[logging.Logger, Path]:
    """Set up logging for a pipeline run.

    Creates:
    - A per-run log file at logs/<pipeline>/<timestamp>.log
    - Console output with optional colors

    Args:
        pipeline_name: Name of the pipeline.
        run_id: Unique run identifier.
        logs_dir: Base directory for logs.
        console_level: Logging level for console output.
        file_level: Logging level for file output.
        verbose: Whether to show console output.
        use_colors: Whether to use colored console output.

    Returns:
        Tuple of (logger, log_file_path).
    """
    if logs_dir is None:
        logs_dir = get_logs_dir()

    # Create pipeline-specific log directory
    pipeline_logs = logs_dir / pipeline_name
    pipeline_logs.mkdir(parents=True, exist_ok=True)

    # Create log file with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_file = pipeline_logs / f"{timestamp}.log"

    # Get or create logger for this pipeline
    logger_name = f"harness.{pipeline_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    logger.handlers.clear()

    # Add file handler
    file_handler = create_file_handler(log_file, file_level)
    logger.addHandler(file_handler)

    # Add console handler if verbose
    if verbose:
        console_handler = create_console_handler(console_level, use_colors)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Log initial message
    logger.info(f"Starting pipeline run: {run_id}")
    logger.debug(f"Log file: {log_file}")

    return logger, log_file


def get_logger(name: str = "harness") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (default: "harness").

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)


def setup_root_logger(
    level: int = logging.WARNING,
    use_colors: bool = True,
) -> logging.Logger:
    """Set up the root harness logger for general use.

    This is used for CLI output and general logging before
    a specific pipeline run is started.

    Args:
        level: Logging level.
        use_colors: Whether to use colored output.

    Returns:
        The root harness logger.
    """
    logger = logging.getLogger("harness")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Add console handler
    handler = create_console_handler(level, use_colors)
    logger.addHandler(handler)

    # Prevent propagation
    logger.propagate = False

    return logger


class TaskLogger:
    """Context-aware logger for task execution.

    Prefixes log messages with the task name for easy identification.
    """

    def __init__(self, logger: logging.Logger, task_name: str):
        """Initialize task logger.

        Args:
            logger: Parent logger to use.
            task_name: Name of the task for prefixing.
        """
        self._logger = logger
        self.task_name = task_name

    def _format(self, message: str) -> str:
        """Format message with task prefix."""
        return f"[{self.task_name}] {message}"

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._logger.debug(self._format(message), *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message."""
        self._logger.info(self._format(message), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._logger.warning(self._format(message), *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        self._logger.error(self._format(message), *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        self._logger.exception(self._format(message), *args, **kwargs)
