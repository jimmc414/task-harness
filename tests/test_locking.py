"""Tests for locking infrastructure."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.locking import PipelineLock, is_pipeline_locked, get_lock_holder
from harness.exceptions import PipelineAlreadyRunningError


class TestPipelineLock:
    """Tests for PipelineLock."""

    def test_acquire_and_release(self, tmp_path: Path) -> None:
        """Should acquire and release lock successfully."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)

        # Acquire
        assert lock.acquire()
        assert lock._acquired
        assert lock.lock_file.exists()

        # Release
        lock.release()
        assert not lock._acquired
        assert not lock.lock_file.exists()

    def test_context_manager(self, tmp_path: Path) -> None:
        """Should work as context manager."""
        with PipelineLock("test_pipeline", locks_dir=tmp_path) as lock:
            assert lock._acquired
            assert lock.lock_file.exists()

        assert not lock._acquired
        assert not lock.lock_file.exists()

    def test_lock_file_contains_metadata(self, tmp_path: Path) -> None:
        """Should write lock metadata to file."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.acquire()

        try:
            content = lock.lock_file.read_text()
            data = json.loads(content)

            assert "pid" in data
            assert data["pid"] == os.getpid()
            assert "started" in data
            assert "hostname" in data
        finally:
            lock.release()

    def test_double_acquire(self, tmp_path: Path) -> None:
        """Should allow double acquire from same instance."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)

        assert lock.acquire()
        assert lock.acquire()  # Should return True (already acquired)

        lock.release()

    def test_get_lock_info(self, tmp_path: Path) -> None:
        """Should return lock info when locked."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.acquire()

        try:
            info = lock.get_lock_info()
            assert info is not None
            assert info["pid"] == os.getpid()
        finally:
            lock.release()

    def test_get_lock_info_when_unlocked(self, tmp_path: Path) -> None:
        """Should return None when not locked."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        assert lock.get_lock_info() is None

    def test_is_locked(self, tmp_path: Path) -> None:
        """Should report lock status correctly."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)

        assert not lock.is_locked()

        lock.acquire()
        assert lock.is_locked()

        lock.release()
        assert not lock.is_locked()

    def test_stale_lock_detection(self, tmp_path: Path) -> None:
        """Should detect stale locks from dead processes."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)

        # Create a stale lock file with non-existent PID
        lock_data = {
            "pid": 999999,  # Very unlikely to exist
            "started": "2024-01-01T00:00:00+00:00",
            "hostname": "test",
        }
        lock.lock_file.write_text(json.dumps(lock_data))

        # Should detect as stale and acquire
        assert lock._is_stale()
        assert lock.acquire()

        lock.release()

    def test_force_acquire(self, tmp_path: Path) -> None:
        """Should forcibly remove existing lock when force=True."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)

        # Create a lock file
        lock.lock_file.write_text('{"pid": 12345}')

        # Force acquire should work
        assert lock.acquire(force=True)

        lock.release()

    def test_creates_locks_directory(self, tmp_path: Path) -> None:
        """Should create locks directory if it doesn't exist."""
        locks_dir = tmp_path / "nested" / "locks"
        lock = PipelineLock("test_pipeline", locks_dir=locks_dir)

        lock.acquire()
        try:
            assert locks_dir.exists()
        finally:
            lock.release()


class TestStaleLockHandling:
    """Tests for stale lock handling."""

    def test_stale_with_corrupt_json(self, tmp_path: Path) -> None:
        """Should treat corrupt lock file as stale."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock.lock_file.write_text("not valid json")

        assert lock._is_stale()

    def test_stale_with_empty_file(self, tmp_path: Path) -> None:
        """Should treat empty lock file as stale."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock.lock_file.touch()

        assert lock._is_stale()

    def test_stale_with_missing_pid(self, tmp_path: Path) -> None:
        """Should treat lock without PID as stale."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock.lock_file.write_text('{"hostname": "test"}')

        assert lock._is_stale()

    def test_not_stale_with_running_process(self, tmp_path: Path) -> None:
        """Should not be stale if process is running."""
        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock_data = {
            "pid": os.getpid(),  # Current process
            "started": "2024-01-01T00:00:00+00:00",
            "hostname": "test",
        }
        lock.lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock.lock_file.write_text(json.dumps(lock_data))

        assert not lock._is_stale()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_pipeline_locked(self, tmp_path: Path) -> None:
        """Should check if pipeline is locked."""
        assert not is_pipeline_locked("test_pipeline", tmp_path)

        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.acquire()

        try:
            assert is_pipeline_locked("test_pipeline", tmp_path)
        finally:
            lock.release()

    def test_get_lock_holder(self, tmp_path: Path) -> None:
        """Should get lock holder info."""
        assert get_lock_holder("test_pipeline", tmp_path) is None

        lock = PipelineLock("test_pipeline", locks_dir=tmp_path)
        lock.acquire()

        try:
            holder = get_lock_holder("test_pipeline", tmp_path)
            assert holder is not None
            assert holder["pid"] == os.getpid()
        finally:
            lock.release()
