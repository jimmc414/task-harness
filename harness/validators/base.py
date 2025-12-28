"""Base validator class for Task Harness.

All validators inherit from the Validator abstract base class and implement
the check() method to perform their specific validation logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.models import ValidationResult


class Validator(ABC):
    """Abstract base class for all validators.

    Validators are used as preconditions and postconditions for tasks.
    They check whether certain conditions are met before or after task execution.

    Subclasses must implement:
        - check(context) -> ValidationResult

    Subclasses should define:
        - name: str - Human-readable name for the validator

    Example:
        class FileExists(Validator):
            name = "FileExists"

            def __init__(self, path: str):
                self.path = path

            def check(self, context: dict) -> ValidationResult:
                if Path(self.path).exists():
                    return ValidationResult.success(self.name)
                return ValidationResult.failure(
                    self.name, f"File not found: {self.path}"
                )
    """

    name: str = "Validator"

    @abstractmethod
    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Perform the validation check.

        Args:
            context: Shared context dictionary containing data from previous tasks
                    and initial context values.

        Returns:
            ValidationResult indicating whether the check passed or failed.

        Note:
            If this method raises an exception, the runner will catch it and
            convert it to a failed ValidationResult with the exception message.
        """
        pass

    def __repr__(self) -> str:
        """Return a string representation of the validator."""
        return f"{self.__class__.__name__}()"

    def _resolve_path(
        self, path: str | Path, context: dict[str, Any], from_context: bool = False
    ) -> Path:
        """Resolve a path, optionally looking it up from context.

        Args:
            path: The path string or key name if from_context is True.
            context: The context dictionary.
            from_context: If True, treat path as a context key to look up.

        Returns:
            Resolved Path object.

        Raises:
            KeyError: If from_context is True and the key is not in context.
            ValueError: If from_context is True and the value is not a valid path.
        """
        if from_context:
            if path not in context:
                raise KeyError(f"Context key not found: {path}")
            path_value = context[path]
            if not isinstance(path_value, (str, Path)):
                raise ValueError(
                    f"Context key '{path}' must be a string or Path, got {type(path_value)}"
                )
            return Path(path_value)
        return Path(path)


class ValidatorGroup(ABC):
    """Base class for composite validators that combine multiple validators.

    Subclasses implement different combination logic (AnyOf, AllOf, etc.).
    """

    name: str = "ValidatorGroup"

    def __init__(self, *validators: Validator, name: str | None = None):
        """Initialize with child validators.

        Args:
            validators: Child validators to combine.
            name: Optional custom name for this validator group.
        """
        if not validators:
            raise ValueError("At least one validator is required")
        self.validators = validators
        if name:
            self.name = name

    @abstractmethod
    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Perform the combined validation check."""
        pass

    def __repr__(self) -> str:
        """Return a string representation of the validator group."""
        validator_reprs = ", ".join(repr(v) for v in self.validators)
        return f"{self.__class__.__name__}({validator_reprs})"
