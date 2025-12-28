"""Tests for composite validators."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.models import ValidationResult
from harness.validators.base import Validator
from harness.validators.composite import AllOf, AnyOf, ConditionalValidator, NoneOf


class PassingValidator(Validator):
    """A validator that always passes."""

    name = "PassingValidator"

    def check(self, context):
        return ValidationResult.success(self.name, "Always passes")


class FailingValidator(Validator):
    """A validator that always fails."""

    name = "FailingValidator"

    def check(self, context):
        return ValidationResult.failure(self.name, "Always fails")


class ErrorValidator(Validator):
    """A validator that always raises an exception."""

    name = "ErrorValidator"

    def check(self, context):
        raise RuntimeError("Always errors")


class TestAnyOf:
    """Tests for AnyOf validator."""

    def test_passes_when_first_passes(self) -> None:
        """Should pass when first validator passes."""
        validator = AnyOf(PassingValidator(), FailingValidator())
        result = validator.check({})

        assert result.passed
        assert "passed" in result.message.lower()

    def test_passes_when_any_passes(self) -> None:
        """Should pass when any validator passes."""
        validator = AnyOf(FailingValidator(), FailingValidator(), PassingValidator())
        result = validator.check({})

        assert result.passed

    def test_fails_when_all_fail(self) -> None:
        """Should fail when all validators fail."""
        validator = AnyOf(FailingValidator(), FailingValidator())
        result = validator.check({})

        assert not result.passed
        assert "none" in result.message.lower()
        assert len(result.details["failures"]) == 2

    def test_handles_errors(self) -> None:
        """Should treat errors as failures."""
        validator = AnyOf(ErrorValidator(), PassingValidator())
        result = validator.check({})

        assert result.passed  # Second one passes

    def test_fails_with_only_errors(self) -> None:
        """Should fail when all validators error."""
        validator = AnyOf(ErrorValidator(), ErrorValidator())
        result = validator.check({})

        assert not result.passed

    def test_requires_validators(self) -> None:
        """Should raise ValueError with no validators."""
        with pytest.raises(ValueError):
            AnyOf()

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = AnyOf(PassingValidator(), FailingValidator())
        assert "AnyOf" in repr(validator)


class TestAllOf:
    """Tests for AllOf validator."""

    def test_passes_when_all_pass(self) -> None:
        """Should pass when all validators pass."""
        validator = AllOf(PassingValidator(), PassingValidator())
        result = validator.check({})

        assert result.passed
        assert "all" in result.message.lower()

    def test_fails_when_first_fails(self) -> None:
        """Should fail on first failure (short-circuit)."""
        validator = AllOf(FailingValidator(), PassingValidator())
        result = validator.check({})

        assert not result.passed
        assert "failed" in result.message.lower()

    def test_fails_when_any_fails(self) -> None:
        """Should fail when any validator fails."""
        validator = AllOf(PassingValidator(), FailingValidator(), PassingValidator())
        result = validator.check({})

        assert not result.passed

    def test_handles_errors(self) -> None:
        """Should treat errors as failures."""
        validator = AllOf(PassingValidator(), ErrorValidator())
        result = validator.check({})

        assert not result.passed
        assert "error" in result.message.lower()

    def test_custom_name(self) -> None:
        """Should use custom name if provided."""
        validator = AllOf(PassingValidator(), name="CustomValidator")
        result = validator.check({})

        assert result.validator_name == "CustomValidator"

    def test_requires_validators(self) -> None:
        """Should raise ValueError with no validators."""
        with pytest.raises(ValueError):
            AllOf()

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = AllOf(PassingValidator(), FailingValidator())
        assert "AllOf" in repr(validator)


class TestNoneOf:
    """Tests for NoneOf validator."""

    def test_passes_when_all_fail(self) -> None:
        """Should pass when all validators fail."""
        validator = NoneOf(FailingValidator(), FailingValidator())
        result = validator.check({})

        assert result.passed
        assert "none" in result.message.lower()

    def test_fails_when_any_passes(self) -> None:
        """Should fail when any validator passes."""
        validator = NoneOf(FailingValidator(), PassingValidator())
        result = validator.check({})

        assert not result.passed
        assert "unexpected" in result.message.lower()

    def test_treats_errors_as_failure(self) -> None:
        """Should treat errors as 'not passing'."""
        validator = NoneOf(ErrorValidator(), ErrorValidator())
        result = validator.check({})

        assert result.passed  # Errors don't count as passing

    def test_requires_validators(self) -> None:
        """Should raise ValueError with no validators."""
        with pytest.raises(ValueError):
            NoneOf()


class TestConditionalValidator:
    """Tests for ConditionalValidator."""

    def test_runs_then_when_condition_passes(self) -> None:
        """Should run then_validator when condition passes."""
        validator = ConditionalValidator(
            condition=PassingValidator(),
            then_validator=PassingValidator(),
        )
        result = validator.check({})

        assert result.passed
        assert "condition met" in result.message.lower()

    def test_runs_else_when_condition_fails(self) -> None:
        """Should run else_validator when condition fails."""
        validator = ConditionalValidator(
            condition=FailingValidator(),
            then_validator=PassingValidator(),
            else_validator=FailingValidator(),
        )
        result = validator.check({})

        assert not result.passed
        assert "condition not met" in result.message.lower()

    def test_skips_when_no_else(self) -> None:
        """Should pass when condition fails and no else_validator."""
        validator = ConditionalValidator(
            condition=FailingValidator(),
            then_validator=PassingValidator(),
        )
        result = validator.check({})

        assert result.passed
        assert "skipping" in result.message.lower()

    def test_handles_condition_error(self) -> None:
        """Should treat condition error as condition failure."""
        validator = ConditionalValidator(
            condition=ErrorValidator(),
            then_validator=FailingValidator(),  # Should not run
        )
        result = validator.check({})

        assert result.passed  # Condition failed, no else, so skip

    def test_handles_then_error(self) -> None:
        """Should report error in then_validator."""
        validator = ConditionalValidator(
            condition=PassingValidator(),
            then_validator=ErrorValidator(),
        )
        result = validator.check({})

        assert not result.passed
        assert "error" in result.message.lower()

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = ConditionalValidator(
            condition=PassingValidator(),
            then_validator=FailingValidator(),
        )
        assert "ConditionalValidator" in repr(validator)
