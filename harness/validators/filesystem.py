"""Filesystem validators for Task Harness.

These validators check file and directory existence, modification times, and sizes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from harness.models import ValidationResult
from harness.validators.base import Validator


class FileExists(Validator):
    """Check if a file exists.

    Example:
        preconditions = [
            FileExists("data/input.csv"),
            FileExists("output_file", from_context=True),  # Get path from context
        ]
    """

    name = "FileExists"

    def __init__(self, path: str | Path, from_context: bool = False):
        """Initialize the validator.

        Args:
            path: Path to the file, or context key if from_context is True.
            from_context: If True, look up the path from context[path].
        """
        self.path = str(path)
        self.from_context = from_context

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the file exists."""
        try:
            resolved_path = self._resolve_path(self.path, context, self.from_context)
        except (KeyError, ValueError) as e:
            return ValidationResult.failure(self.name, str(e))

        if not resolved_path.exists():
            return ValidationResult.failure(
                self.name,
                f"File not found: {resolved_path}",
            )

        if not resolved_path.is_file():
            return ValidationResult.failure(
                self.name,
                f"Path exists but is not a file: {resolved_path}",
            )

        return ValidationResult.success(
            self.name,
            f"File exists: {resolved_path}",
        )

    def __repr__(self) -> str:
        if self.from_context:
            return f"FileExists({self.path!r}, from_context=True)"
        return f"FileExists({self.path!r})"


class DirectoryExists(Validator):
    """Check if a directory exists.

    Example:
        preconditions = [
            DirectoryExists("./output"),
            DirectoryExists("work_dir", from_context=True),
        ]
    """

    name = "DirectoryExists"

    def __init__(self, path: str | Path, from_context: bool = False):
        """Initialize the validator.

        Args:
            path: Path to the directory, or context key if from_context is True.
            from_context: If True, look up the path from context[path].
        """
        self.path = str(path)
        self.from_context = from_context

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the directory exists."""
        try:
            resolved_path = self._resolve_path(self.path, context, self.from_context)
        except (KeyError, ValueError) as e:
            return ValidationResult.failure(self.name, str(e))

        if not resolved_path.exists():
            return ValidationResult.failure(
                self.name,
                f"Directory not found: {resolved_path}",
            )

        if not resolved_path.is_dir():
            return ValidationResult.failure(
                self.name,
                f"Path exists but is not a directory: {resolved_path}",
            )

        return ValidationResult.success(
            self.name,
            f"Directory exists: {resolved_path}",
        )

    def __repr__(self) -> str:
        if self.from_context:
            return f"DirectoryExists({self.path!r}, from_context=True)"
        return f"DirectoryExists({self.path!r})"


class FileModifiedWithin(Validator):
    """Check if a file was modified within a specified time window.

    Uses timezone-aware datetimes (UTC) for consistent behavior.

    Example:
        preconditions = [
            # File modified in last hour
            FileModifiedWithin("data/latest.csv", max_age=timedelta(hours=1)),
            # File modified in last 24 hours
            FileModifiedWithin("report.pdf", max_age=timedelta(days=1)),
        ]
    """

    name = "FileModifiedWithin"

    def __init__(
        self,
        path: str | Path,
        max_age: timedelta,
        from_context: bool = False,
    ):
        """Initialize the validator.

        Args:
            path: Path to the file, or context key if from_context is True.
            max_age: Maximum age of the file (how recently it must have been modified).
            from_context: If True, look up the path from context[path].
        """
        self.path = str(path)
        self.max_age = max_age
        self.from_context = from_context

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the file was modified recently enough."""
        try:
            resolved_path = self._resolve_path(self.path, context, self.from_context)
        except (KeyError, ValueError) as e:
            return ValidationResult.failure(self.name, str(e))

        if not resolved_path.exists():
            return ValidationResult.failure(
                self.name,
                f"File not found: {resolved_path}",
            )

        if not resolved_path.is_file():
            return ValidationResult.failure(
                self.name,
                f"Path is not a file: {resolved_path}",
            )

        # Get file modification time (timezone-aware UTC)
        mtime = datetime.fromtimestamp(
            resolved_path.stat().st_mtime, tz=timezone.utc
        )
        now = datetime.now(tz=timezone.utc)
        age = now - mtime

        if age > self.max_age:
            return ValidationResult.failure(
                self.name,
                f"File is too old: {resolved_path} "
                f"(modified {self._format_age(age)} ago, max {self._format_age(self.max_age)})",
                details={
                    "path": str(resolved_path),
                    "mtime": mtime.isoformat(),
                    "age_seconds": age.total_seconds(),
                    "max_age_seconds": self.max_age.total_seconds(),
                },
            )

        return ValidationResult.success(
            self.name,
            f"File was modified {self._format_age(age)} ago: {resolved_path}",
        )

    @staticmethod
    def _format_age(td: timedelta) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        if total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        if total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h"
        days = total_seconds // 86400
        return f"{days}d"

    def __repr__(self) -> str:
        parts = [f"{self.path!r}", f"max_age={self.max_age!r}"]
        if self.from_context:
            parts.append("from_context=True")
        return f"FileModifiedWithin({', '.join(parts)})"


class FileSizeInRange(Validator):
    """Check if a file size is within a specified range.

    Example:
        preconditions = [
            # File is at least 1KB
            FileSizeInRange("data.csv", min_bytes=1024),
            # File is at most 10MB
            FileSizeInRange("upload.zip", max_bytes=10 * 1024 * 1024),
            # File is between 1KB and 10MB
            FileSizeInRange("report.pdf", min_bytes=1024, max_bytes=10485760),
        ]
    """

    name = "FileSizeInRange"

    def __init__(
        self,
        path: str | Path,
        min_bytes: int = 0,
        max_bytes: int | None = None,
        from_context: bool = False,
    ):
        """Initialize the validator.

        Args:
            path: Path to the file, or context key if from_context is True.
            min_bytes: Minimum file size in bytes (default 0).
            max_bytes: Maximum file size in bytes (None = no limit).
            from_context: If True, look up the path from context[path].
        """
        if min_bytes < 0:
            raise ValueError("min_bytes cannot be negative")
        if max_bytes is not None and max_bytes < min_bytes:
            raise ValueError("max_bytes cannot be less than min_bytes")

        self.path = str(path)
        self.min_bytes = min_bytes
        self.max_bytes = max_bytes
        self.from_context = from_context

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the file size is within the specified range."""
        try:
            resolved_path = self._resolve_path(self.path, context, self.from_context)
        except (KeyError, ValueError) as e:
            return ValidationResult.failure(self.name, str(e))

        if not resolved_path.exists():
            return ValidationResult.failure(
                self.name,
                f"File not found: {resolved_path}",
            )

        if not resolved_path.is_file():
            return ValidationResult.failure(
                self.name,
                f"Path is not a file: {resolved_path}",
            )

        size = resolved_path.stat().st_size

        if size < self.min_bytes:
            return ValidationResult.failure(
                self.name,
                f"File too small: {resolved_path} "
                f"({self._format_size(size)} < {self._format_size(self.min_bytes)})",
                details={
                    "path": str(resolved_path),
                    "size": size,
                    "min_bytes": self.min_bytes,
                },
            )

        if self.max_bytes is not None and size > self.max_bytes:
            return ValidationResult.failure(
                self.name,
                f"File too large: {resolved_path} "
                f"({self._format_size(size)} > {self._format_size(self.max_bytes)})",
                details={
                    "path": str(resolved_path),
                    "size": size,
                    "max_bytes": self.max_bytes,
                },
            )

        return ValidationResult.success(
            self.name,
            f"File size is {self._format_size(size)}: {resolved_path}",
        )

    @staticmethod
    def _format_size(size: int) -> str:
        """Format a size in bytes as a human-readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}" if size != int(size) else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def __repr__(self) -> str:
        parts = [f"{self.path!r}"]
        if self.min_bytes > 0:
            parts.append(f"min_bytes={self.min_bytes}")
        if self.max_bytes is not None:
            parts.append(f"max_bytes={self.max_bytes}")
        if self.from_context:
            parts.append("from_context=True")
        return f"FileSizeInRange({', '.join(parts)})"
