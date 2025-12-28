"""Tests for filesystem validators."""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import pytest

from harness.validators.filesystem import (
    DirectoryExists,
    FileExists,
    FileModifiedWithin,
    FileSizeInRange,
)


class TestFileExists:
    """Tests for FileExists validator."""

    def test_passes_when_file_exists(self, tmp_path: Path) -> None:
        """Should pass when file exists."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        validator = FileExists(str(test_file))
        result = validator.check({})

        assert result.passed
        assert "exists" in result.message.lower()

    def test_fails_when_file_missing(self, tmp_path: Path) -> None:
        """Should fail when file doesn't exist."""
        validator = FileExists(str(tmp_path / "nonexistent.txt"))
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_fails_when_path_is_directory(self, tmp_path: Path) -> None:
        """Should fail when path is a directory, not a file."""
        validator = FileExists(str(tmp_path))
        result = validator.check({})

        assert not result.passed
        assert "not a file" in result.message.lower()

    def test_from_context(self, tmp_path: Path) -> None:
        """Should read path from context when from_context is True."""
        test_file = tmp_path / "context_file.txt"
        test_file.write_text("content")

        validator = FileExists("file_path", from_context=True)
        result = validator.check({"file_path": str(test_file)})

        assert result.passed

    def test_from_context_missing_key(self) -> None:
        """Should fail when context key is missing."""
        validator = FileExists("missing_key", from_context=True)
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_repr(self) -> None:
        """Should have correct string representation."""
        assert "test.txt" in repr(FileExists("test.txt"))
        assert "from_context" in repr(FileExists("key", from_context=True))


class TestDirectoryExists:
    """Tests for DirectoryExists validator."""

    def test_passes_when_directory_exists(self, tmp_path: Path) -> None:
        """Should pass when directory exists."""
        test_dir = tmp_path / "subdir"
        test_dir.mkdir()

        validator = DirectoryExists(str(test_dir))
        result = validator.check({})

        assert result.passed
        assert "exists" in result.message.lower()

    def test_fails_when_directory_missing(self, tmp_path: Path) -> None:
        """Should fail when directory doesn't exist."""
        validator = DirectoryExists(str(tmp_path / "nonexistent"))
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_fails_when_path_is_file(self, tmp_path: Path) -> None:
        """Should fail when path is a file, not a directory."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        validator = DirectoryExists(str(test_file))
        result = validator.check({})

        assert not result.passed
        assert "not a directory" in result.message.lower()

    def test_from_context(self, tmp_path: Path) -> None:
        """Should read path from context when from_context is True."""
        test_dir = tmp_path / "context_dir"
        test_dir.mkdir()

        validator = DirectoryExists("dir_path", from_context=True)
        result = validator.check({"dir_path": str(test_dir)})

        assert result.passed

    def test_repr(self) -> None:
        """Should have correct string representation."""
        assert "mydir" in repr(DirectoryExists("mydir"))
        assert "from_context" in repr(DirectoryExists("key", from_context=True))


class TestFileModifiedWithin:
    """Tests for FileModifiedWithin validator."""

    def test_passes_when_recently_modified(self, tmp_path: Path) -> None:
        """Should pass when file was recently modified."""
        test_file = tmp_path / "recent.txt"
        test_file.write_text("content")

        validator = FileModifiedWithin(str(test_file), max_age=timedelta(hours=1))
        result = validator.check({})

        assert result.passed

    def test_fails_when_file_too_old(self, tmp_path: Path) -> None:
        """Should fail when file is too old."""
        test_file = tmp_path / "old.txt"
        test_file.write_text("content")

        # Set modification time to 2 hours ago
        import os

        old_time = time.time() - 7200  # 2 hours ago
        os.utime(test_file, (old_time, old_time))

        validator = FileModifiedWithin(str(test_file), max_age=timedelta(hours=1))
        result = validator.check({})

        assert not result.passed
        assert "too old" in result.message.lower()

    def test_fails_when_file_missing(self, tmp_path: Path) -> None:
        """Should fail when file doesn't exist."""
        validator = FileModifiedWithin(
            str(tmp_path / "nonexistent.txt"), max_age=timedelta(hours=1)
        )
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_fails_when_path_is_directory(self, tmp_path: Path) -> None:
        """Should fail when path is a directory."""
        validator = FileModifiedWithin(str(tmp_path), max_age=timedelta(hours=1))
        result = validator.check({})

        assert not result.passed
        assert "not a file" in result.message.lower()

    def test_from_context(self, tmp_path: Path) -> None:
        """Should read path from context when from_context is True."""
        test_file = tmp_path / "context_file.txt"
        test_file.write_text("content")

        validator = FileModifiedWithin(
            "file_path", max_age=timedelta(hours=1), from_context=True
        )
        result = validator.check({"file_path": str(test_file)})

        assert result.passed

    def test_format_age(self) -> None:
        """Should format age correctly."""
        assert FileModifiedWithin._format_age(timedelta(seconds=30)) == "30s"
        assert FileModifiedWithin._format_age(timedelta(minutes=5)) == "5m"
        assert FileModifiedWithin._format_age(timedelta(hours=2)) == "2h"
        assert FileModifiedWithin._format_age(timedelta(days=3)) == "3d"

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = FileModifiedWithin("test.txt", max_age=timedelta(hours=1))
        assert "test.txt" in repr(validator)
        assert "max_age" in repr(validator)


class TestFileSizeInRange:
    """Tests for FileSizeInRange validator."""

    def test_passes_when_size_in_range(self, tmp_path: Path) -> None:
        """Should pass when file size is within range."""
        test_file = tmp_path / "sized.txt"
        test_file.write_text("x" * 100)  # 100 bytes

        validator = FileSizeInRange(str(test_file), min_bytes=50, max_bytes=200)
        result = validator.check({})

        assert result.passed

    def test_fails_when_file_too_small(self, tmp_path: Path) -> None:
        """Should fail when file is smaller than minimum."""
        test_file = tmp_path / "small.txt"
        test_file.write_text("x" * 10)  # 10 bytes

        validator = FileSizeInRange(str(test_file), min_bytes=100)
        result = validator.check({})

        assert not result.passed
        assert "too small" in result.message.lower()

    def test_fails_when_file_too_large(self, tmp_path: Path) -> None:
        """Should fail when file is larger than maximum."""
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 1000)  # 1000 bytes

        validator = FileSizeInRange(str(test_file), max_bytes=100)
        result = validator.check({})

        assert not result.passed
        assert "too large" in result.message.lower()

    def test_passes_with_min_only(self, tmp_path: Path) -> None:
        """Should pass when only min_bytes is set and met."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("x" * 100)

        validator = FileSizeInRange(str(test_file), min_bytes=50)
        result = validator.check({})

        assert result.passed

    def test_passes_with_max_only(self, tmp_path: Path) -> None:
        """Should pass when only max_bytes is set and not exceeded."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("x" * 100)

        validator = FileSizeInRange(str(test_file), max_bytes=200)
        result = validator.check({})

        assert result.passed

    def test_fails_when_file_missing(self, tmp_path: Path) -> None:
        """Should fail when file doesn't exist."""
        validator = FileSizeInRange(str(tmp_path / "nonexistent.txt"))
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_fails_when_path_is_directory(self, tmp_path: Path) -> None:
        """Should fail when path is a directory."""
        validator = FileSizeInRange(str(tmp_path))
        result = validator.check({})

        assert not result.passed
        assert "not a file" in result.message.lower()

    def test_from_context(self, tmp_path: Path) -> None:
        """Should read path from context when from_context is True."""
        test_file = tmp_path / "context_file.txt"
        test_file.write_text("x" * 100)

        validator = FileSizeInRange("file_path", min_bytes=50, from_context=True)
        result = validator.check({"file_path": str(test_file)})

        assert result.passed

    def test_invalid_min_bytes(self) -> None:
        """Should raise ValueError for negative min_bytes."""
        with pytest.raises(ValueError):
            FileSizeInRange("test.txt", min_bytes=-1)

    def test_invalid_max_less_than_min(self) -> None:
        """Should raise ValueError when max_bytes < min_bytes."""
        with pytest.raises(ValueError):
            FileSizeInRange("test.txt", min_bytes=100, max_bytes=50)

    def test_format_size(self) -> None:
        """Should format size correctly."""
        assert FileSizeInRange._format_size(500) == "500B"
        assert "KB" in FileSizeInRange._format_size(5000)
        assert "MB" in FileSizeInRange._format_size(5000000)
        assert "GB" in FileSizeInRange._format_size(5000000000)

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = FileSizeInRange("test.txt", min_bytes=100, max_bytes=1000)
        assert "test.txt" in repr(validator)
        assert "min_bytes" in repr(validator)
        assert "max_bytes" in repr(validator)
