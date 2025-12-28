"""Configuration management for Task Harness.

This module provides utilities for finding the harness root directory
and managing global configuration settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def get_harness_root() -> Path:
    """Get the harness root directory.

    Search order:
    1. HARNESS_ROOT environment variable
    2. Walk up from current directory looking for pipelines/ folder
    3. Current working directory (fallback)

    Returns:
        Path to the harness root directory.
    """
    # 1. Check environment variable
    if env_root := os.environ.get("HARNESS_ROOT"):
        root = Path(env_root)
        if root.exists():
            return root.resolve()

    # 2. Walk up from current directory looking for pipelines/
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pipelines").is_dir():
            return parent.resolve()

    # 3. Fallback to current working directory
    return cwd.resolve()


def get_pipelines_dir() -> Path:
    """Get the pipelines directory.

    Returns:
        Path to the pipelines directory.
    """
    return get_harness_root() / "pipelines"


def get_logs_dir() -> Path:
    """Get the logs directory.

    Returns:
        Path to the logs directory (created if it doesn't exist).
    """
    logs_dir = get_harness_root() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_locks_dir() -> Path:
    """Get the locks directory.

    Returns:
        Path to the locks directory (created if it doesn't exist).
    """
    locks_dir = get_harness_root() / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return locks_dir


def get_harness_dir() -> Path:
    """Get the .harness directory (for secrets, cache, etc).

    Returns:
        Path to the .harness directory (created if it doesn't exist).
    """
    harness_dir = get_harness_root() / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    return harness_dir


def get_history_file() -> Path:
    """Get the path to the run history file.

    Returns:
        Path to run_history.jsonl file.
    """
    return get_harness_root() / "run_history.jsonl"


def get_secrets_file() -> Path:
    """Get the path to the secrets file.

    Override with HARNESS_SECRETS_FILE environment variable.

    Returns:
        Path to secrets.enc file.
    """
    if env_path := os.environ.get("HARNESS_SECRETS_FILE"):
        return Path(env_path)
    return get_harness_dir() / "secrets.enc"


@dataclass
class HarnessConfig:
    """Global configuration for Task Harness.

    These settings affect the entire harness runtime and can be
    overridden via environment variables.

    Attributes:
        root_dir: Harness root directory.
        pipelines_dir: Directory containing pipeline modules.
        logs_dir: Directory for log files.
        locks_dir: Directory for lock files.
        harness_dir: Directory for harness internal files.
        history_file: Path to run history file.
        secrets_file: Path to encrypted secrets file.
        verbose: Default verbosity (auto-detected if None).
        color: Whether to use colored output.
    """

    root_dir: Path = field(default_factory=get_harness_root)
    pipelines_dir: Path = field(default_factory=get_pipelines_dir)
    logs_dir: Path = field(default_factory=get_logs_dir)
    locks_dir: Path = field(default_factory=get_locks_dir)
    harness_dir: Path = field(default_factory=get_harness_dir)
    history_file: Path = field(default_factory=get_history_file)
    secrets_file: Path = field(default_factory=get_secrets_file)
    verbose: bool | None = None  # None = auto-detect from TTY
    color: bool = True

    def __post_init__(self) -> None:
        """Auto-detect verbosity if not set."""
        if self.verbose is None:
            # Verbose by default if running interactively (TTY)
            import sys

            self.verbose = sys.stdout.isatty()

        # Check environment variable for color
        if os.environ.get("NO_COLOR"):
            self.color = False
        elif os.environ.get("FORCE_COLOR"):
            self.color = True

    @classmethod
    def from_env(cls) -> HarnessConfig:
        """Create configuration from environment variables.

        Environment variables:
        - HARNESS_ROOT: Root directory
        - HARNESS_SECRETS_FILE: Secrets file path
        - HARNESS_VERBOSE: Force verbose output (1/0)
        - NO_COLOR: Disable colored output
        - FORCE_COLOR: Force colored output

        Returns:
            HarnessConfig instance.
        """
        config = cls()

        if verbose_env := os.environ.get("HARNESS_VERBOSE"):
            config.verbose = verbose_env.lower() in ("1", "true", "yes")

        return config


# Global configuration instance (lazy-loaded)
_config: HarnessConfig | None = None


def get_config() -> HarnessConfig:
    """Get the global configuration instance.

    Returns:
        The global HarnessConfig instance.
    """
    global _config
    if _config is None:
        _config = HarnessConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None
