"""Environment validators for Task Harness.

These validators check the Python environment and environment variables.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from harness.models import ValidationResult
from harness.validators.base import Validator


class VirtualEnvActive(Validator):
    """Check if running inside a virtual environment.

    Detects:
    - Standard venv/virtualenv (sys.prefix != sys.base_prefix)
    - VIRTUAL_ENV environment variable
    - CONDA_PREFIX environment variable (conda environments)

    Example:
        preconditions = [
            VirtualEnvActive(),  # Any virtual environment
            VirtualEnvActive(expected_path="/path/to/venv"),  # Specific venv
        ]
    """

    name = "VirtualEnvActive"

    def __init__(self, expected_path: str | None = None):
        """Initialize the validator.

        Args:
            expected_path: Optional expected path to the virtual environment.
                          If provided, validates that we're in this specific venv.
        """
        self.expected_path = expected_path

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if running in a virtual environment."""
        # Check various indicators of virtual environment
        in_venv = (
            sys.prefix != sys.base_prefix
            or os.environ.get("VIRTUAL_ENV")
            or os.environ.get("CONDA_PREFIX")
        )

        if not in_venv:
            return ValidationResult.failure(
                self.name,
                "Not running inside a virtual environment",
                details={
                    "sys.prefix": sys.prefix,
                    "sys.base_prefix": sys.base_prefix,
                    "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV"),
                    "CONDA_PREFIX": os.environ.get("CONDA_PREFIX"),
                },
            )

        # If expected_path specified, verify we're in the right venv
        if self.expected_path:
            current_venv = (
                os.environ.get("VIRTUAL_ENV")
                or os.environ.get("CONDA_PREFIX")
                or sys.prefix
            )
            # Normalize paths for comparison
            expected_normalized = os.path.normcase(os.path.normpath(self.expected_path))
            current_normalized = os.path.normcase(os.path.normpath(current_venv))

            if expected_normalized != current_normalized:
                return ValidationResult.failure(
                    self.name,
                    f"Wrong virtual environment: expected {self.expected_path}, "
                    f"got {current_venv}",
                    details={
                        "expected": self.expected_path,
                        "actual": current_venv,
                    },
                )

        return ValidationResult.success(
            self.name,
            f"Running in virtual environment: {sys.prefix}",
        )

    def __repr__(self) -> str:
        if self.expected_path:
            return f"VirtualEnvActive(expected_path={self.expected_path!r})"
        return "VirtualEnvActive()"


class EnvVarSet(Validator):
    """Check if an environment variable is set and non-empty.

    Example:
        preconditions = [
            EnvVarSet("DATABASE_URL"),
            EnvVarSet("API_KEY"),
        ]
    """

    name = "EnvVarSet"

    def __init__(self, var_name: str):
        """Initialize the validator.

        Args:
            var_name: Name of the environment variable to check.
        """
        if not var_name:
            raise ValueError("var_name is required")
        self.var_name = var_name

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the environment variable is set and non-empty."""
        value = os.environ.get(self.var_name)

        if value is None:
            return ValidationResult.failure(
                self.name,
                f"Environment variable not set: {self.var_name}",
            )

        if not value.strip():
            return ValidationResult.failure(
                self.name,
                f"Environment variable is empty: {self.var_name}",
            )

        return ValidationResult.success(
            self.name,
            f"Environment variable '{self.var_name}' is set",
        )

    def __repr__(self) -> str:
        return f"EnvVarSet({self.var_name!r})"


class EnvVarEquals(Validator):
    """Check if an environment variable has a specific value.

    Example:
        preconditions = [
            EnvVarEquals("ENVIRONMENT", "production"),
            EnvVarEquals("DEBUG", "false"),
        ]
    """

    name = "EnvVarEquals"

    def __init__(self, var_name: str, expected_value: str):
        """Initialize the validator.

        Args:
            var_name: Name of the environment variable to check.
            expected_value: Expected value of the variable.
        """
        if not var_name:
            raise ValueError("var_name is required")
        self.var_name = var_name
        self.expected_value = expected_value

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the environment variable equals the expected value."""
        actual_value = os.environ.get(self.var_name)

        if actual_value is None:
            return ValidationResult.failure(
                self.name,
                f"Environment variable not set: {self.var_name}",
                details={"expected": self.expected_value},
            )

        if actual_value != self.expected_value:
            return ValidationResult.failure(
                self.name,
                f"Environment variable '{self.var_name}' has wrong value: "
                f"expected '{self.expected_value}', got '{actual_value}'",
                details={
                    "expected": self.expected_value,
                    "actual": actual_value,
                },
            )

        return ValidationResult.success(
            self.name,
            f"Environment variable '{self.var_name}' equals '{self.expected_value}'",
        )

    def __repr__(self) -> str:
        return f"EnvVarEquals({self.var_name!r}, {self.expected_value!r})"


class PythonPackageAvailable(Validator):
    """Check if a Python package is installed and optionally meets version requirements.

    Example:
        preconditions = [
            PythonPackageAvailable("pandas"),
            PythonPackageAvailable("requests", min_version="2.28.0"),
            PythonPackageAvailable("numpy", min_version="1.20", max_version="2.0"),
        ]
    """

    name = "PythonPackageAvailable"

    def __init__(
        self,
        package: str,
        min_version: str | None = None,
        max_version: str | None = None,
    ):
        """Initialize the validator.

        Args:
            package: Name of the package to check.
            min_version: Minimum required version (inclusive).
            max_version: Maximum allowed version (exclusive).
        """
        if not package:
            raise ValueError("package name is required")
        self.package = package
        self.min_version = min_version
        self.max_version = max_version

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the package is available and meets version requirements."""
        try:
            from importlib.metadata import version as get_version
            from importlib.metadata import PackageNotFoundError
        except ImportError:
            # Python < 3.8 fallback (though we require 3.10+)
            from importlib_metadata import version as get_version
            from importlib_metadata import PackageNotFoundError

        try:
            installed_version = get_version(self.package)
        except PackageNotFoundError:
            return ValidationResult.failure(
                self.name,
                f"Package not installed: {self.package}",
            )

        # If no version constraints, we're done
        if not self.min_version and not self.max_version:
            return ValidationResult.success(
                self.name,
                f"Package '{self.package}' is installed (version {installed_version})",
            )

        # Version comparison using packaging library
        try:
            from packaging.version import Version, InvalidVersion

            try:
                current = Version(installed_version)
            except InvalidVersion:
                return ValidationResult.failure(
                    self.name,
                    f"Package '{self.package}' has invalid version: {installed_version}",
                )

            if self.min_version:
                try:
                    min_ver = Version(self.min_version)
                except InvalidVersion:
                    return ValidationResult.failure(
                        self.name,
                        f"Invalid min_version specified: {self.min_version}",
                    )
                if current < min_ver:
                    return ValidationResult.failure(
                        self.name,
                        f"Package '{self.package}' version {installed_version} "
                        f"is below minimum {self.min_version}",
                        details={
                            "installed": installed_version,
                            "minimum": self.min_version,
                        },
                    )

            if self.max_version:
                try:
                    max_ver = Version(self.max_version)
                except InvalidVersion:
                    return ValidationResult.failure(
                        self.name,
                        f"Invalid max_version specified: {self.max_version}",
                    )
                if current >= max_ver:
                    return ValidationResult.failure(
                        self.name,
                        f"Package '{self.package}' version {installed_version} "
                        f"is at or above maximum {self.max_version}",
                        details={
                            "installed": installed_version,
                            "maximum": self.max_version,
                        },
                    )

        except ImportError:
            # packaging not available, skip version checks with warning
            return ValidationResult.success(
                self.name,
                f"Package '{self.package}' is installed (version {installed_version}, "
                "version check skipped - 'packaging' not available)",
            )

        return ValidationResult.success(
            self.name,
            f"Package '{self.package}' version {installed_version} meets requirements",
        )

    def __repr__(self) -> str:
        parts = [f"{self.package!r}"]
        if self.min_version:
            parts.append(f"min_version={self.min_version!r}")
        if self.max_version:
            parts.append(f"max_version={self.max_version!r}")
        return f"PythonPackageAvailable({', '.join(parts)})"
