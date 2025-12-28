"""Tests for environment validators."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from harness.validators.environment import (
    EnvVarEquals,
    EnvVarSet,
    PythonPackageAvailable,
    VirtualEnvActive,
)


class TestVirtualEnvActive:
    """Tests for VirtualEnvActive validator."""

    def test_passes_when_in_venv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when sys.prefix differs from sys.base_prefix."""
        monkeypatch.setattr(sys, "prefix", "/path/to/venv")
        monkeypatch.setattr(sys, "base_prefix", "/usr")

        validator = VirtualEnvActive()
        result = validator.check({})

        assert result.passed
        assert "virtual environment" in result.message.lower()

    def test_passes_when_virtual_env_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when VIRTUAL_ENV environment variable is set."""
        monkeypatch.setattr(sys, "prefix", "/usr")
        monkeypatch.setattr(sys, "base_prefix", "/usr")
        monkeypatch.setenv("VIRTUAL_ENV", "/path/to/venv")

        validator = VirtualEnvActive()
        result = validator.check({})

        assert result.passed

    def test_passes_when_conda_prefix_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when CONDA_PREFIX environment variable is set."""
        monkeypatch.setattr(sys, "prefix", "/usr")
        monkeypatch.setattr(sys, "base_prefix", "/usr")
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setenv("CONDA_PREFIX", "/path/to/conda/env")

        validator = VirtualEnvActive()
        result = validator.check({})

        assert result.passed

    def test_fails_when_not_in_venv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when not in any virtual environment."""
        monkeypatch.setattr(sys, "prefix", "/usr")
        monkeypatch.setattr(sys, "base_prefix", "/usr")
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.delenv("CONDA_PREFIX", raising=False)

        validator = VirtualEnvActive()
        result = validator.check({})

        assert not result.passed
        assert "not running inside" in result.message.lower()

    def test_expected_path_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when expected_path matches current venv."""
        expected = "/path/to/my/venv"
        monkeypatch.setenv("VIRTUAL_ENV", expected)
        monkeypatch.setattr(sys, "prefix", expected)
        monkeypatch.setattr(sys, "base_prefix", "/usr")

        validator = VirtualEnvActive(expected_path=expected)
        result = validator.check({})

        assert result.passed

    def test_expected_path_mismatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when expected_path doesn't match current venv."""
        monkeypatch.setenv("VIRTUAL_ENV", "/path/to/other/venv")
        monkeypatch.setattr(sys, "prefix", "/path/to/other/venv")
        monkeypatch.setattr(sys, "base_prefix", "/usr")

        validator = VirtualEnvActive(expected_path="/path/to/my/venv")
        result = validator.check({})

        assert not result.passed
        assert "wrong virtual environment" in result.message.lower()

    def test_repr(self) -> None:
        """Should have correct string representation."""
        assert repr(VirtualEnvActive()) == "VirtualEnvActive()"
        assert "expected_path" in repr(VirtualEnvActive(expected_path="/path"))


class TestEnvVarSet:
    """Tests for EnvVarSet validator."""

    def test_passes_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when variable is set and non-empty."""
        monkeypatch.setenv("MY_VAR", "some_value")

        validator = EnvVarSet("MY_VAR")
        result = validator.check({})

        assert result.passed
        assert "MY_VAR" in result.message

    def test_fails_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when variable is not set."""
        monkeypatch.delenv("MY_VAR", raising=False)

        validator = EnvVarSet("MY_VAR")
        result = validator.check({})

        assert not result.passed
        assert "not set" in result.message.lower()

    def test_fails_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when variable is set but empty."""
        monkeypatch.setenv("MY_VAR", "")

        validator = EnvVarSet("MY_VAR")
        result = validator.check({})

        assert not result.passed
        assert "empty" in result.message.lower()

    def test_fails_when_whitespace_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when variable contains only whitespace."""
        monkeypatch.setenv("MY_VAR", "   ")

        validator = EnvVarSet("MY_VAR")
        result = validator.check({})

        assert not result.passed
        assert "empty" in result.message.lower()

    def test_requires_var_name(self) -> None:
        """Should raise ValueError if var_name is empty."""
        with pytest.raises(ValueError):
            EnvVarSet("")

    def test_repr(self) -> None:
        """Should have correct string representation."""
        assert repr(EnvVarSet("MY_VAR")) == "EnvVarSet('MY_VAR')"


class TestEnvVarEquals:
    """Tests for EnvVarEquals validator."""

    def test_passes_when_equal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when variable equals expected value."""
        monkeypatch.setenv("ENV", "production")

        validator = EnvVarEquals("ENV", "production")
        result = validator.check({})

        assert result.passed
        assert "production" in result.message

    def test_fails_when_different(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when variable has different value."""
        monkeypatch.setenv("ENV", "development")

        validator = EnvVarEquals("ENV", "production")
        result = validator.check({})

        assert not result.passed
        assert "wrong value" in result.message.lower()
        assert result.details["expected"] == "production"
        assert result.details["actual"] == "development"

    def test_fails_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fail when variable is not set."""
        monkeypatch.delenv("ENV", raising=False)

        validator = EnvVarEquals("ENV", "production")
        result = validator.check({})

        assert not result.passed
        assert "not set" in result.message.lower()

    def test_case_sensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should be case-sensitive."""
        monkeypatch.setenv("ENV", "Production")

        validator = EnvVarEquals("ENV", "production")
        result = validator.check({})

        assert not result.passed

    def test_requires_var_name(self) -> None:
        """Should raise ValueError if var_name is empty."""
        with pytest.raises(ValueError):
            EnvVarEquals("", "value")

    def test_repr(self) -> None:
        """Should have correct string representation."""
        assert repr(EnvVarEquals("ENV", "prod")) == "EnvVarEquals('ENV', 'prod')"


class TestPythonPackageAvailable:
    """Tests for PythonPackageAvailable validator."""

    def test_passes_for_installed_package(self) -> None:
        """Should pass for an installed package."""
        # pytest is definitely installed since we're running tests
        validator = PythonPackageAvailable("pytest")
        result = validator.check({})

        assert result.passed
        assert "pytest" in result.message

    def test_fails_for_missing_package(self) -> None:
        """Should fail for a package that doesn't exist."""
        validator = PythonPackageAvailable("definitely_not_a_real_package_xyz123")
        result = validator.check({})

        assert not result.passed
        assert "not installed" in result.message.lower()

    def test_min_version_passes(self) -> None:
        """Should pass when installed version >= min_version."""
        # pytest is >= 1.0.0
        validator = PythonPackageAvailable("pytest", min_version="1.0.0")
        result = validator.check({})

        assert result.passed

    def test_min_version_fails(self) -> None:
        """Should fail when installed version < min_version."""
        # No package has version 9999.0.0
        validator = PythonPackageAvailable("pytest", min_version="9999.0.0")
        result = validator.check({})

        assert not result.passed
        assert "below minimum" in result.message.lower()

    def test_max_version_passes(self) -> None:
        """Should pass when installed version < max_version."""
        validator = PythonPackageAvailable("pytest", max_version="9999.0.0")
        result = validator.check({})

        assert result.passed

    def test_max_version_fails(self) -> None:
        """Should fail when installed version >= max_version."""
        validator = PythonPackageAvailable("pytest", max_version="0.0.1")
        result = validator.check({})

        assert not result.passed
        assert "maximum" in result.message.lower()

    def test_version_range(self) -> None:
        """Should validate version within range."""
        validator = PythonPackageAvailable(
            "pytest", min_version="1.0.0", max_version="9999.0.0"
        )
        result = validator.check({})

        assert result.passed

    def test_requires_package_name(self) -> None:
        """Should raise ValueError if package name is empty."""
        with pytest.raises(ValueError):
            PythonPackageAvailable("")

    def test_repr(self) -> None:
        """Should have correct string representation."""
        assert "pytest" in repr(PythonPackageAvailable("pytest"))
        assert "min_version" in repr(
            PythonPackageAvailable("pytest", min_version="1.0")
        )
        assert "max_version" in repr(
            PythonPackageAvailable("pytest", max_version="2.0")
        )
