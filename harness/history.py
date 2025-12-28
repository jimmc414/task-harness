"""History infrastructure for Task Harness.

Provides JSON Lines based storage for run history records.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterator

from harness.config import get_history_file
from harness.models import RunRecord


# Cross-platform file locking for history
if sys.platform == "win32":
    import msvcrt

    def _lock_file_shared(f):
        """Acquire shared lock on file (Windows)."""
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(f):
        """Release lock on file (Windows)."""
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
else:
    import fcntl

    def _lock_file_shared(f):
        """Acquire shared lock on file (Unix)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)

    def _unlock_file(f):
        """Release lock on file (Unix)."""
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass


class RunHistory:
    """JSON Lines based run history storage.

    Records are stored one per line in JSON format, making it easy
    to append new records and read them back efficiently.

    Example:
        history = RunHistory()

        # Record a run
        record = RunRecord(pipeline_name="my_pipeline")
        history.record(record)

        # Get recent runs
        recent = history.get_recent(limit=10)
    """

    def __init__(self, history_file: Path | None = None):
        """Initialize the history store.

        Args:
            history_file: Path to the history file.
                         Default: from config (run_history.jsonl).
        """
        self.history_file = Path(history_file) if history_file else get_history_file()

    def record(self, run: RunRecord) -> None:
        """Record a run to history.

        Args:
            run: The run record to save.
        """
        # Ensure parent directory exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON line
        line = json.dumps(run.to_dict()) + "\n"

        # Append atomically with locking
        with open(self.history_file, "a") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def get_all(self) -> list[RunRecord]:
        """Get all run records.

        Returns:
            List of all RunRecord objects, oldest first.
        """
        return list(self._iter_records())

    def get_recent(
        self,
        limit: int = 10,
        pipeline: str | None = None,
        status: str | None = None,
    ) -> list[RunRecord]:
        """Get recent run records with optional filtering.

        Args:
            limit: Maximum number of records to return.
            pipeline: Filter by pipeline name.
            status: Filter by status ("success", "failed", etc.).

        Returns:
            List of RunRecord objects, newest first.
        """
        records = []

        for record in self._iter_records():
            # Apply filters
            if pipeline and record.pipeline_name != pipeline:
                continue
            if status and record.status != status:
                continue

            records.append(record)

        # Return newest first, limited
        return list(reversed(records))[:limit]

    def get_by_pipeline(self, pipeline_name: str) -> list[RunRecord]:
        """Get all runs for a specific pipeline.

        Args:
            pipeline_name: Name of the pipeline.

        Returns:
            List of RunRecord objects for the pipeline, newest first.
        """
        return self.get_recent(limit=9999, pipeline=pipeline_name)

    def get_by_run_id(self, run_id: str) -> RunRecord | None:
        """Get a specific run by its ID.

        Args:
            run_id: The run ID to find.

        Returns:
            The RunRecord or None if not found.
        """
        for record in self._iter_records():
            if record.run_id == run_id:
                return record
        return None

    def _iter_records(self) -> Iterator[RunRecord]:
        """Iterate over all records in the history file.

        Yields:
            RunRecord objects.
        """
        if not self.history_file.exists():
            return

        try:
            with open(self.history_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        yield RunRecord.from_dict(data)
                    except (json.JSONDecodeError, TypeError):
                        # Skip malformed lines
                        continue
        except OSError:
            return

    def count(self, pipeline: str | None = None, status: str | None = None) -> int:
        """Count records matching the filter.

        Args:
            pipeline: Filter by pipeline name.
            status: Filter by status.

        Returns:
            Number of matching records.
        """
        count = 0
        for record in self._iter_records():
            if pipeline and record.pipeline_name != pipeline:
                continue
            if status and record.status != status:
                continue
            count += 1
        return count

    def clear(self) -> None:
        """Clear all history (use with caution).

        This deletes the history file.
        """
        if self.history_file.exists():
            self.history_file.unlink()

    def get_last_run(self, pipeline_name: str) -> RunRecord | None:
        """Get the most recent run for a pipeline.

        Args:
            pipeline_name: Name of the pipeline.

        Returns:
            Most recent RunRecord or None.
        """
        runs = self.get_recent(limit=1, pipeline=pipeline_name)
        return runs[0] if runs else None

    def get_stats(self, pipeline_name: str | None = None) -> dict:
        """Get statistics about run history.

        Args:
            pipeline_name: Optional pipeline to filter by.

        Returns:
            Dict with counts by status, total count, etc.
        """
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "cancelled": 0,
            "other": 0,
        }

        for record in self._iter_records():
            if pipeline_name and record.pipeline_name != pipeline_name:
                continue

            stats["total"] += 1
            if record.status == "success":
                stats["success"] += 1
            elif record.status == "failed":
                stats["failed"] += 1
            elif record.status == "cancelled":
                stats["cancelled"] += 1
            else:
                stats["other"] += 1

        if stats["total"] > 0:
            stats["success_rate"] = stats["success"] / stats["total"]
        else:
            stats["success_rate"] = 0.0

        return stats
