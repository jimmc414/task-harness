"""Custom exceptions for Task Harness.

Exception hierarchy:
    HarnessError (base)
    ├── PipelineError
    │   ├── PipelineNotFoundError
    │   ├── PipelineAlreadyRunningError
    │   └── PipelineTimeoutError
    ├── TaskError
    │   ├── TaskNotFoundError
    │   ├── TaskTimeoutError
    │   └── TaskExecutionError
    ├── ValidationError
    │   ├── PreconditionError
    │   └── PostconditionError
    ├── LockError
    │   ├── LockAcquisitionError
    │   └── StaleLockError
    ├── SecretsError
    │   ├── SecretsKeyError
    │   ├── SecretsNotFoundError
    │   └── SecretsDecryptionError
    └── ConfigurationError
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base exception for all Task Harness errors."""

    pass


# Pipeline errors


class PipelineError(HarnessError):
    """Base exception for pipeline-related errors."""

    pass


class PipelineNotFoundError(PipelineError):
    """Raised when a requested pipeline cannot be found."""

    def __init__(self, pipeline_name: str, available: list[str] | None = None):
        self.pipeline_name = pipeline_name
        self.available = available or []
        msg = f"Pipeline not found: {pipeline_name}"
        if self.available:
            msg += f". Available pipelines: {', '.join(self.available)}"
        super().__init__(msg)


class PipelineAlreadyRunningError(PipelineError):
    """Raised when attempting to run a pipeline that is already running."""

    def __init__(self, pipeline_name: str, lock_holder_pid: int | None = None):
        self.pipeline_name = pipeline_name
        self.lock_holder_pid = lock_holder_pid
        msg = f"Pipeline '{pipeline_name}' is already running"
        if lock_holder_pid:
            msg += f" (PID: {lock_holder_pid})"
        super().__init__(msg)


class PipelineTimeoutError(PipelineError):
    """Raised when a pipeline exceeds its maximum runtime."""

    def __init__(self, pipeline_name: str, elapsed_seconds: float, max_seconds: float):
        self.pipeline_name = pipeline_name
        self.elapsed_seconds = elapsed_seconds
        self.max_seconds = max_seconds
        super().__init__(
            f"Pipeline '{pipeline_name}' exceeded maximum runtime: "
            f"{elapsed_seconds:.1f}s > {max_seconds:.1f}s"
        )


# Task errors


class TaskError(HarnessError):
    """Base exception for task-related errors."""

    pass


class TaskNotFoundError(TaskError):
    """Raised when a specified task cannot be found in the pipeline."""

    def __init__(self, task_name: str, pipeline_name: str, available: list[str] | None = None):
        self.task_name = task_name
        self.pipeline_name = pipeline_name
        self.available = available or []
        msg = f"Task '{task_name}' not found in pipeline '{pipeline_name}'"
        if self.available:
            msg += f". Available tasks: {', '.join(self.available)}"
        super().__init__(msg)


class TaskTimeoutError(TaskError):
    """Raised when a task exceeds its timeout."""

    def __init__(self, task_name: str, timeout_seconds: float):
        self.task_name = task_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Task '{task_name}' exceeded timeout of {timeout_seconds:.1f}s"
        )


class TaskExecutionError(TaskError):
    """Raised when a task fails during execution."""

    def __init__(self, task_name: str, message: str, original_error: Exception | None = None):
        self.task_name = task_name
        self.original_error = original_error
        super().__init__(f"Task '{task_name}' failed: {message}")


# Validation errors


class ValidationError(HarnessError):
    """Base exception for validation-related errors."""

    pass


class PreconditionError(ValidationError):
    """Raised when a precondition validation fails."""

    def __init__(self, task_name: str, validator_name: str, message: str):
        self.task_name = task_name
        self.validator_name = validator_name
        super().__init__(
            f"Precondition failed for task '{task_name}': "
            f"[{validator_name}] {message}"
        )


class PostconditionError(ValidationError):
    """Raised when a postcondition validation fails."""

    def __init__(self, task_name: str, validator_name: str, message: str):
        self.task_name = task_name
        self.validator_name = validator_name
        super().__init__(
            f"Postcondition failed for task '{task_name}': "
            f"[{validator_name}] {message}"
        )


# Lock errors


class LockError(HarnessError):
    """Base exception for lock-related errors."""

    pass


class LockAcquisitionError(LockError):
    """Raised when a lock cannot be acquired."""

    def __init__(self, pipeline_name: str, reason: str = "unknown"):
        self.pipeline_name = pipeline_name
        self.reason = reason
        super().__init__(
            f"Could not acquire lock for pipeline '{pipeline_name}': {reason}"
        )


class StaleLockError(LockError):
    """Raised when encountering a stale lock that cannot be cleaned."""

    def __init__(self, pipeline_name: str, lock_file: str):
        self.pipeline_name = pipeline_name
        self.lock_file = lock_file
        super().__init__(
            f"Stale lock detected for pipeline '{pipeline_name}' "
            f"but could not be removed: {lock_file}"
        )


# Secrets errors


class SecretsError(HarnessError):
    """Base exception for secrets-related errors."""

    pass


class SecretsKeyError(SecretsError):
    """Raised when the secrets encryption key is not available."""

    def __init__(self):
        super().__init__(
            "No secrets key found. Set HARNESS_SECRETS_KEY environment variable "
            "or run 'harness secrets init' to create a new key."
        )


class SecretsNotFoundError(SecretsError):
    """Raised when a requested secret does not exist."""

    def __init__(self, secret_name: str):
        self.secret_name = secret_name
        super().__init__(f"Secret not found: {secret_name}")


class SecretsDecryptionError(SecretsError):
    """Raised when secrets cannot be decrypted."""

    def __init__(self, reason: str = "invalid key or corrupted data"):
        self.reason = reason
        super().__init__(f"Could not decrypt secrets: {reason}")


# Configuration errors


class ConfigurationError(HarnessError):
    """Raised for configuration-related issues."""

    def __init__(self, message: str, config_key: str | None = None):
        self.config_key = config_key
        if config_key:
            message = f"Configuration error for '{config_key}': {message}"
        super().__init__(message)
