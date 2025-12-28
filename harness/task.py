"""Task abstraction for Task Harness.

Tasks are the units of work in a pipeline. Each task defines:
- Preconditions: Validators that must pass before the task runs
- Postconditions: Validators that must pass after the task runs
- run(): The actual work to perform
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from harness.models import TaskConfig, TaskResult

if TYPE_CHECKING:
    from harness.validators.base import Validator


class Task(ABC):
    """Abstract base class for all tasks.

    Subclasses must implement:
        - run(context) -> TaskResult

    Subclasses should define:
        - name: str - Unique identifier for the task
        - description: str - Human-readable description

    Subclasses may define:
        - config: TaskConfig - Execution configuration
        - preconditions: list[Validator] - Validators to check before running
        - postconditions: list[Validator] - Validators to check after running

    Example:
        class ProcessData(Task):
            name = "process_data"
            description = "Process input data files"
            config = TaskConfig(timeout_seconds=60.0, retries=2)
            preconditions = [
                FileExists("data/input.csv"),
            ]
            postconditions = [
                FileExists("data/output.csv"),
            ]

            def run(self, context: dict) -> TaskResult:
                # Do processing...
                return TaskResult.ok("Processed 100 rows", {"row_count": 100})
    """

    # Class-level attributes (can be overridden by subclasses)
    name: ClassVar[str] = "unnamed_task"
    description: ClassVar[str] = ""
    config: ClassVar[TaskConfig] = TaskConfig()
    preconditions: ClassVar[list[Validator]] = []
    postconditions: ClassVar[list[Validator]] = []

    def __init__(self) -> None:
        """Initialize the task.

        Subclasses can override to accept constructor arguments,
        but should call super().__init__().
        """
        # Make instance copies of class-level lists to avoid mutation issues
        if self.__class__.preconditions is Task.preconditions:
            self._preconditions: list[Validator] = []
        else:
            self._preconditions = list(self.__class__.preconditions)

        if self.__class__.postconditions is Task.postconditions:
            self._postconditions: list[Validator] = []
        else:
            self._postconditions = list(self.__class__.postconditions)

        # Make instance copy of config if it's the default
        if self.__class__.config is Task.config:
            self._config = TaskConfig()
        else:
            self._config = self.__class__.config

    @property
    def task_preconditions(self) -> list[Validator]:
        """Get the task's preconditions."""
        return self._preconditions

    @property
    def task_postconditions(self) -> list[Validator]:
        """Get the task's postconditions."""
        return self._postconditions

    @property
    def task_config(self) -> TaskConfig:
        """Get the task's configuration."""
        return self._config

    @abstractmethod
    def run(self, context: dict[str, Any]) -> TaskResult:
        """Execute the task's main logic.

        Args:
            context: Shared context dictionary. Contains:
                - Initial context values passed via CLI
                - Data from previous tasks (via TaskResult.data)
                - Any values set by precondition validators

        Returns:
            TaskResult indicating success or failure.
            The result's data dict will be merged into context.

        Raises:
            Any exception will be caught and converted to a failed TaskResult.
        """
        pass

    def __repr__(self) -> str:
        """Return a string representation of the task."""
        return f"{self.__class__.__name__}(name={self.name!r})"

    def get_info(self) -> dict[str, Any]:
        """Get task information for display purposes."""
        return {
            "name": self.name,
            "description": self.description,
            "timeout_seconds": self._config.timeout_seconds,
            "retries": self._config.retries,
            "preconditions": [repr(v) for v in self._preconditions],
            "postconditions": [repr(v) for v in self._postconditions],
        }


class CallableTask(Task):
    """A task created from a callable function.

    Useful for simple tasks that don't need a full class definition.

    Example:
        def my_task(context: dict) -> TaskResult:
            return TaskResult.ok("Done")

        task = CallableTask(
            name="my_task",
            description="A simple task",
            func=my_task,
        )
    """

    def __init__(
        self,
        name: str,
        func: callable,
        description: str = "",
        config: TaskConfig | None = None,
        preconditions: list[Validator] | None = None,
        postconditions: list[Validator] | None = None,
    ):
        """Initialize a callable task.

        Args:
            name: Task name.
            func: Callable that takes context dict and returns TaskResult.
            description: Task description.
            config: Task configuration.
            preconditions: List of precondition validators.
            postconditions: List of postcondition validators.
        """
        # Set class attributes before calling super().__init__
        self.__class__.name = name
        self.__class__.description = description

        super().__init__()

        self._func = func
        self.name = name
        self.description = description

        if config:
            self._config = config
        if preconditions:
            self._preconditions = list(preconditions)
        if postconditions:
            self._postconditions = list(postconditions)

    def run(self, context: dict[str, Any]) -> TaskResult:
        """Execute the wrapped callable."""
        return self._func(context)
