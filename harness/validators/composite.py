"""Composite validators for Task Harness.

These validators combine multiple validators with logical operators.
"""

from __future__ import annotations

from typing import Any

from harness.models import ValidationResult
from harness.validators.base import Validator, ValidatorGroup


class AnyOf(ValidatorGroup):
    """Pass if any child validator passes.

    Short-circuits on first success.

    Example:
        preconditions = [
            # At least one of these files must exist
            AnyOf(
                FileExists("data.csv"),
                FileExists("data.json"),
                FileExists("data.xml"),
            ),
        ]
    """

    name = "AnyOf"

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if any child validator passes."""
        failures = []

        for validator in self.validators:
            try:
                result = validator.check(context)
                if result.passed:
                    return ValidationResult.success(
                        self.name,
                        f"Passed: {validator.name}",
                        details={"passed_validator": repr(validator)},
                    )
                failures.append((validator, result))
            except Exception as e:
                failures.append((validator, str(e)))

        # All failed - report all failures
        failure_messages = []
        for validator, failure in failures:
            if isinstance(failure, ValidationResult):
                failure_messages.append(f"{validator.name}: {failure.message}")
            else:
                failure_messages.append(f"{validator.name}: {failure}")

        return ValidationResult.failure(
            self.name,
            f"None of {len(self.validators)} validators passed",
            details={
                "failures": failure_messages,
                "validators": [repr(v) for v in self.validators],
            },
        )


class AllOf(ValidatorGroup):
    """Pass only if all child validators pass.

    Short-circuits on first failure.

    Example:
        preconditions = [
            # All of these must be true
            AllOf(
                FileExists("data.csv"),
                TabularFileValid("data.csv", required_headers=["id"]),
                TabularFileRowCount("data.csv", min_rows=10),
                name="ValidDataFile",  # Custom name for error messages
            ),
        ]
    """

    name = "AllOf"

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if all child validators pass."""
        for validator in self.validators:
            try:
                result = validator.check(context)
                if not result.passed:
                    return ValidationResult.failure(
                        self.name,
                        f"Failed at {validator.name}: {result.message}",
                        details={
                            "failed_validator": repr(validator),
                            "original_message": result.message,
                        },
                    )
            except Exception as e:
                return ValidationResult.failure(
                    self.name,
                    f"Error in {validator.name}: {e}",
                    details={"failed_validator": repr(validator), "error": str(e)},
                )

        return ValidationResult.success(
            self.name,
            f"All {len(self.validators)} validators passed",
        )


class NoneOf(ValidatorGroup):
    """Pass only if none of the child validators pass.

    Useful for checking that certain conditions are NOT met.

    Example:
        preconditions = [
            # Make sure we're not in production
            NoneOf(
                EnvVarEquals("ENV", "production"),
                EnvVarEquals("ENVIRONMENT", "prod"),
            ),
        ]
    """

    name = "NoneOf"

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check that no child validators pass."""
        for validator in self.validators:
            try:
                result = validator.check(context)
                if result.passed:
                    return ValidationResult.failure(
                        self.name,
                        f"Unexpected pass: {validator.name}",
                        details={"passed_validator": repr(validator)},
                    )
            except Exception:
                pass  # Errors count as "not passed"

        return ValidationResult.success(
            self.name,
            f"None of {len(self.validators)} validators passed (as expected)",
        )


class ConditionalValidator(Validator):
    """Run a validator only if a condition is met.

    Example:
        preconditions = [
            # Only check SFTP if we're in production
            ConditionalValidator(
                condition=EnvVarEquals("ENV", "production"),
                then_validator=SFTPConnectable("vendor_sftp"),
            ),
        ]
    """

    name = "Conditional"

    def __init__(
        self,
        condition: Validator,
        then_validator: Validator,
        else_validator: Validator | None = None,
    ):
        """Initialize the conditional validator.

        Args:
            condition: Validator that determines which path to take.
            then_validator: Validator to run if condition passes.
            else_validator: Optional validator to run if condition fails.
        """
        self.condition = condition
        self.then_validator = then_validator
        self.else_validator = else_validator

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check the condition and run appropriate validator."""
        try:
            condition_result = self.condition.check(context)
        except Exception as e:
            # Condition error - treat as condition failed
            condition_result = ValidationResult.failure(
                self.condition.name, str(e)
            )

        if condition_result.passed:
            # Run then_validator
            try:
                result = self.then_validator.check(context)
                return ValidationResult(
                    passed=result.passed,
                    message=f"[condition met] {result.message}",
                    validator_name=self.name,
                    details={"condition": "met", "result": result.message},
                )
            except Exception as e:
                return ValidationResult.failure(
                    self.name,
                    f"[condition met] Error: {e}",
                )
        else:
            # Run else_validator if provided
            if self.else_validator:
                try:
                    result = self.else_validator.check(context)
                    return ValidationResult(
                        passed=result.passed,
                        message=f"[condition not met] {result.message}",
                        validator_name=self.name,
                        details={"condition": "not met", "result": result.message},
                    )
                except Exception as e:
                    return ValidationResult.failure(
                        self.name,
                        f"[condition not met] Error: {e}",
                    )
            else:
                # No else_validator - pass by default
                return ValidationResult.success(
                    self.name,
                    "Condition not met, skipping validation",
                )

    def __repr__(self) -> str:
        if self.else_validator:
            return (
                f"ConditionalValidator({self.condition!r}, "
                f"{self.then_validator!r}, else={self.else_validator!r})"
            )
        return f"ConditionalValidator({self.condition!r}, {self.then_validator!r})"
