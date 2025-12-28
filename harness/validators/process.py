"""Process validators for Task Harness.

These validators check for external commands and processes.
"""

from __future__ import annotations

import shutil
from typing import Any

from harness.models import ValidationResult
from harness.validators.base import Validator


class CommandAvailable(Validator):
    """Check if an external command is available in PATH.

    Example:
        preconditions = [
            CommandAvailable("git"),
            CommandAvailable("python"),
            CommandAvailable("ffmpeg"),
        ]
    """

    name = "CommandAvailable"

    def __init__(self, command: str):
        """Initialize the validator.

        Args:
            command: Name of the command to check for.
        """
        if not command:
            raise ValueError("command name is required")
        self.command = command

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the command is available."""
        path = shutil.which(self.command)

        if path is None:
            return ValidationResult.failure(
                self.name,
                f"Command not found in PATH: {self.command}",
                details={"command": self.command},
            )

        return ValidationResult.success(
            self.name,
            f"Command available: {self.command} ({path})",
        )

    def __repr__(self) -> str:
        return f"CommandAvailable({self.command!r})"
