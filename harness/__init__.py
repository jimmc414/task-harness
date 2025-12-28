"""Task Harness - Task orchestration framework with validation-based error handling."""

__version__ = "0.1.0"
__author__ = "Jim McMahon"

# Convenience imports for users
from harness.models import (
    ValidationResult,
    TaskConfig,
    TaskResult,
    PipelineConfig,
    RunRecord,
)
from harness.task import Task
from harness.pipeline import Pipeline
from harness.exceptions import (
    HarnessError,
    PipelineError,
    TaskError,
    ValidationError,
    LockError,
    SecretsError,
    ConfigurationError,
)

__all__ = [
    # Version
    "__version__",
    # Models
    "ValidationResult",
    "TaskConfig",
    "TaskResult",
    "PipelineConfig",
    "RunRecord",
    # Core classes
    "Task",
    "Pipeline",
    # Exceptions
    "HarnessError",
    "PipelineError",
    "TaskError",
    "ValidationError",
    "LockError",
    "SecretsError",
    "ConfigurationError",
]
