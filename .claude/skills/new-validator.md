# New Validator

Generate a new validator for Task Harness.

## Instructions

Ask the user for:
1. **Validator name** (PascalCase, e.g., `DatabaseConnectable`)
2. **Category** (environment, filesystem, tabular, network, process, or new category)
3. **Parameters** (what the validator needs to check)
4. **Check logic** (what condition must be true for validation to pass)

Then generate the validator class and test file.

## Validator Template

```python
from harness.validators.base import Validator
from harness.models import ValidationResult


class <ValidatorName>(Validator):
    """<Description of what this validator checks>.

    Args:
        param1: Description of param1.
        param2: Description of param2.
        from_context: If True, resolve param1 from context dict.
    """

    name = "<ValidatorName>"

    def __init__(
        self,
        param1: str,
        param2: int = 0,
        from_context: bool = False,
    ):
        self.param1 = param1
        self.param2 = param2
        self.from_context = from_context

    def _resolve_param(self, context: dict) -> str:
        """Resolve param1, optionally from context."""
        if self.from_context:
            value = context.get(self.param1)
            if value is None:
                raise ValueError(f"Context key not found: {self.param1}")
            return str(value)
        return self.param1

    def check(self, context: dict) -> ValidationResult:
        """Check if <condition>.

        Args:
            context: Pipeline context dictionary.

        Returns:
            ValidationResult indicating pass/fail.
        """
        try:
            resolved = self._resolve_param(context)

            # Validation logic here
            if <condition_passes>:
                return ValidationResult.success(
                    self.name,
                    f"<Success message>: {resolved}",
                )

            return ValidationResult.failure(
                self.name,
                f"<Failure message>: {resolved}",
            )

        except Exception as e:
            return ValidationResult.failure(
                self.name,
                f"Error checking <what>: {e}",
            )
```

## Test Template

```python
"""Tests for <ValidatorName>."""

import pytest
from harness.validators.<category> import <ValidatorName>


class Test<ValidatorName>:
    """Tests for <ValidatorName>."""

    def test_passes_when_valid(self):
        """Should pass when <condition>."""
        validator = <ValidatorName>("param")
        result = validator.check({})
        assert result.passed

    def test_fails_when_invalid(self):
        """Should fail when <condition>."""
        validator = <ValidatorName>("param")
        result = validator.check({})
        assert not result.passed
        assert "<expected message>" in result.message

    def test_from_context(self):
        """Should resolve parameter from context."""
        validator = <ValidatorName>("key", from_context=True)
        result = validator.check({"key": "value"})
        assert result.passed

    def test_missing_context_key(self):
        """Should fail if context key missing."""
        validator = <ValidatorName>("missing", from_context=True)
        result = validator.check({})
        assert not result.passed
```

## After Generation

1. Add the validator to the appropriate file in `harness/validators/`
2. Export it in `harness/validators/__init__.py`
3. Add tests to `tests/test_validators/test_<category>.py`
4. Run `/test-validators` to verify
