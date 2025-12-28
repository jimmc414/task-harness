"""Tests for process validators."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from harness.validators.process import CommandAvailable


class TestCommandAvailable:
    """Tests for CommandAvailable validator."""

    def test_passes_when_command_exists(self) -> None:
        """Should pass when command is in PATH."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/git"

            validator = CommandAvailable("git")
            result = validator.check({})

            assert result.passed
            assert "available" in result.message.lower()
            assert "/usr/bin/git" in result.message

    def test_fails_when_command_missing(self) -> None:
        """Should fail when command is not in PATH."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None

            validator = CommandAvailable("nonexistent_command")
            result = validator.check({})

            assert not result.passed
            assert "not found" in result.message.lower()

    def test_real_python_command(self) -> None:
        """Should find python (real test, no mock)."""
        validator = CommandAvailable("python3")
        result = validator.check({})

        # This should pass in any Python environment
        assert result.passed

    def test_requires_command_name(self) -> None:
        """Should raise ValueError for empty command."""
        with pytest.raises(ValueError):
            CommandAvailable("")

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = CommandAvailable("git")
        assert "CommandAvailable" in repr(validator)
        assert "git" in repr(validator)
