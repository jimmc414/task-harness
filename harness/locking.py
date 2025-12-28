"""Locking infrastructure for Task Harness.

Provides file-based locking to prevent concurrent pipeline runs.
Uses OS-level file locking to prevent race conditions.
"""

from __future__ import annotations

import atexit
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

import psutil

from harness.config import get_locks_dir
from harness.exceptions import LockAcquisitionError, PipelineAlreadyRunningError, StaleLockError


# Cross-platform file locking
if sys.platform == "win32":
    import msvcrt

    def _lock_file(f: IO) -> None:
        """Acquire exclusive lock on file (Windows)."""
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(f: IO) -> None:
        """Release lock on file (Windows)."""
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass  # Ignore errors on unlock
else:
    import fcntl

    def _lock_file(f: IO) -> None:
        """Acquire exclusive lock on file (Unix)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_file(f: IO) -> None:
        """Release lock on file (Unix)."""
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass  # Ignore errors on unlock


class PipelineLock:
    """File-based lock for preventing concurrent pipeline runs.

    Uses OS-level file locking to prevent race conditions. The lock file
    contains metadata about the lock holder (PID, hostname, start time).

    Stale lock detection uses psutil to check if the lock holder process
    is still running. If the process is dead, the lock is considered stale
    and can be safely acquired.

    Example:
        lock = PipelineLock("my_pipeline")
        if lock.acquire():
            try:
                # Run pipeline
                pass
            finally:
                lock.release()
    """

    def __init__(
        self,
        pipeline_name: str,
        locks_dir: Path | None = None,
        retry_attempts: int = 3,
        retry_delay_seconds: float = 60.0,
    ):
        """Initialize the lock.

        Args:
            pipeline_name: Name of the pipeline to lock.
            locks_dir: Directory for lock files (default: from config).
            retry_attempts: Number of times to retry lock acquisition.
            retry_delay_seconds: Delay between retry attempts.
        """
        self.pipeline_name = pipeline_name
        self.locks_dir = Path(locks_dir) if locks_dir else get_locks_dir()
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds

        self.lock_file = self.locks_dir / f"{pipeline_name}.lock"
        self._file: IO | None = None
        self._acquired = False

    def acquire(self, force: bool = False) -> bool:
        """Attempt to acquire the lock.

        Args:
            force: If True, remove any existing lock (dangerous).

        Returns:
            True if lock was acquired, False if lock is held by another process.

        Raises:
            LockAcquisitionError: If lock cannot be acquired after retries.
        """
        if self._acquired:
            return True

        # Ensure locks directory exists
        self.locks_dir.mkdir(parents=True, exist_ok=True)

        if force:
            self._force_remove_lock()

        import time

        for attempt in range(self.retry_attempts):
            try:
                success = self._try_acquire()
                if success:
                    # Register cleanup on exit
                    atexit.register(self.release)
                    return True
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    raise LockAcquisitionError(self.pipeline_name, str(e))

            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay_seconds)

        return False

    def _try_acquire(self) -> bool:
        """Single attempt to acquire the lock.

        Returns:
            True if acquired, False if held by another process.
        """
        try:
            # Open in append mode to create if not exists
            self._file = open(self.lock_file, "a+")
        except Exception as e:
            raise LockAcquisitionError(self.pipeline_name, f"Could not open lock file: {e}")

        try:
            # Try to acquire OS-level exclusive lock
            _lock_file(self._file)
        except (BlockingIOError, OSError):
            # Lock is held by another process
            self._file.close()
            self._file = None

            # Check if it's stale
            if self._is_stale():
                self._handle_stale_lock()
                return self._try_acquire()  # Retry after handling stale lock

            return False

        # We have the lock - check if there's existing content (stale)
        self._file.seek(0)
        content = self._file.read()

        if content:
            try:
                data = json.loads(content)
                if psutil.pid_exists(data.get("pid", 0)):
                    # Another process has the lock (shouldn't happen with proper locking)
                    _unlock_file(self._file)
                    self._file.close()
                    self._file = None
                    raise PipelineAlreadyRunningError(
                        self.pipeline_name, data.get("pid")
                    )
            except json.JSONDecodeError:
                pass  # Corrupt lock file, treat as stale

        # Write our lock info
        self._file.seek(0)
        self._file.truncate()
        lock_data = {
            "pid": os.getpid(),
            "started": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
        }
        self._file.write(json.dumps(lock_data))
        self._file.flush()
        os.fsync(self._file.fileno())

        self._acquired = True
        return True

    def _is_stale(self) -> bool:
        """Check if the existing lock is stale (held by dead process).

        Returns:
            True if the lock is stale (safe to acquire).
        """
        if not self.lock_file.exists():
            return True

        try:
            content = self.lock_file.read_text()
            if not content:
                return True

            data = json.loads(content)
            pid = data.get("pid")
            if pid is None:
                return True

            # Check if process exists
            return not psutil.pid_exists(pid)

        except (json.JSONDecodeError, OSError):
            return True  # Corrupt or unreadable = stale

    def _handle_stale_lock(self) -> None:
        """Handle a stale lock by removing the lock file."""
        try:
            self.lock_file.unlink(missing_ok=True)
        except OSError as e:
            raise StaleLockError(self.pipeline_name, str(self.lock_file))

    def _force_remove_lock(self) -> None:
        """Forcibly remove the lock file (dangerous)."""
        try:
            self.lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    def release(self) -> None:
        """Release the lock."""
        if not self._acquired:
            return

        try:
            if self._file:
                _unlock_file(self._file)
                self._file.close()
                self._file = None

            # Remove lock file
            self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass  # Ignore errors during cleanup
        finally:
            self._acquired = False

            # Unregister cleanup
            try:
                atexit.unregister(self.release)
            except Exception:
                pass

    def is_locked(self) -> bool:
        """Check if the pipeline is currently locked.

        Returns:
            True if locked (by any process, including stale).
        """
        return self.lock_file.exists()

    def get_lock_info(self) -> dict[str, Any] | None:
        """Get information about the current lock holder.

        Returns:
            Lock info dict or None if not locked.
        """
        if not self.lock_file.exists():
            return None

        try:
            content = self.lock_file.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return None

    def __enter__(self) -> PipelineLock:
        """Context manager entry."""
        if not self.acquire():
            raise PipelineAlreadyRunningError(self.pipeline_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()


def is_pipeline_locked(pipeline_name: str, locks_dir: Path | None = None) -> bool:
    """Check if a pipeline is currently locked.

    Args:
        pipeline_name: Name of the pipeline.
        locks_dir: Directory for lock files.

    Returns:
        True if the pipeline is locked.
    """
    lock = PipelineLock(pipeline_name, locks_dir)
    return lock.is_locked() and not lock._is_stale()


def get_lock_holder(pipeline_name: str, locks_dir: Path | None = None) -> dict[str, Any] | None:
    """Get information about who is holding a pipeline lock.

    Args:
        pipeline_name: Name of the pipeline.
        locks_dir: Directory for lock files.

    Returns:
        Dict with pid, started, hostname or None if not locked.
    """
    lock = PipelineLock(pipeline_name, locks_dir)
    return lock.get_lock_info()
