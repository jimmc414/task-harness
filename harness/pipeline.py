"""Pipeline abstraction for Task Harness.

A Pipeline is a collection of tasks that run sequentially.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

from harness.models import PipelineConfig

if TYPE_CHECKING:
    from harness.task import Task


class Pipeline:
    """A pipeline is a sequence of tasks to execute.

    Pipelines define:
    - Configuration (name, timeouts, logging, etc.)
    - An ordered list of tasks to execute

    Tasks are executed sequentially. Each task's postconditions are checked
    after execution, and data from TaskResult.data is merged into the
    shared context for subsequent tasks.

    Example:
        from harness import Pipeline, PipelineConfig

        pipeline = Pipeline(
            config=PipelineConfig(
                name="daily_report",
                description="Generate daily report",
                log_directory="./logs",
            ),
            tasks=[
                ValidateEnvironment(),
                FetchData(),
                ProcessData(),
                GenerateReport(),
                SendNotification(),
            ],
        )
    """

    def __init__(
        self,
        config: PipelineConfig,
        tasks: list[Task],
    ):
        """Initialize a pipeline.

        Args:
            config: Pipeline configuration.
            tasks: Ordered list of tasks to execute.

        Raises:
            ValueError: If tasks list is empty or contains duplicates.
        """
        if not tasks:
            raise ValueError("Pipeline must have at least one task")

        # Check for duplicate task names
        task_names = [t.name for t in tasks]
        if len(task_names) != len(set(task_names)):
            duplicates = [n for n in task_names if task_names.count(n) > 1]
            raise ValueError(f"Duplicate task names: {set(duplicates)}")

        self.config = config
        self._tasks = list(tasks)
        self._task_index = {t.name: i for i, t in enumerate(tasks)}

    @property
    def name(self) -> str:
        """Get the pipeline name."""
        return self.config.name

    @property
    def description(self) -> str:
        """Get the pipeline description."""
        return self.config.description

    @property
    def tasks(self) -> list[Task]:
        """Get the list of tasks (read-only copy)."""
        return list(self._tasks)

    def __len__(self) -> int:
        """Return the number of tasks in the pipeline."""
        return len(self._tasks)

    def __iter__(self) -> Iterator[Task]:
        """Iterate over tasks in the pipeline."""
        return iter(self._tasks)

    def __getitem__(self, key: int | str) -> Task:
        """Get a task by index or name.

        Args:
            key: Task index (int) or name (str).

        Returns:
            The requested task.

        Raises:
            IndexError: If index is out of range.
            KeyError: If task name is not found.
        """
        if isinstance(key, int):
            return self._tasks[key]
        if key in self._task_index:
            return self._tasks[self._task_index[key]]
        raise KeyError(f"Task not found: {key}")

    def __contains__(self, key: str) -> bool:
        """Check if a task name exists in the pipeline."""
        return key in self._task_index

    def get_task_index(self, task_name: str) -> int:
        """Get the index of a task by name.

        Args:
            task_name: Name of the task.

        Returns:
            Zero-based index of the task.

        Raises:
            KeyError: If task name is not found.
        """
        if task_name not in self._task_index:
            raise KeyError(f"Task not found: {task_name}")
        return self._task_index[task_name]

    def get_task_names(self) -> list[str]:
        """Get list of all task names in order."""
        return [t.name for t in self._tasks]

    def get_tasks_from(self, start_task: str) -> list[Task]:
        """Get tasks starting from a specific task.

        Args:
            start_task: Name of the task to start from (inclusive).

        Returns:
            List of tasks from start_task to the end.

        Raises:
            KeyError: If start_task is not found.
        """
        start_index = self.get_task_index(start_task)
        return self._tasks[start_index:]

    def __repr__(self) -> str:
        """Return a string representation of the pipeline."""
        return f"Pipeline(name={self.config.name!r}, tasks={len(self._tasks)})"

    def get_info(self) -> dict[str, Any]:
        """Get pipeline information for display purposes."""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "task_count": len(self._tasks),
            "tasks": [t.get_info() for t in self._tasks],
            "default_timeout_seconds": self.config.default_timeout_seconds,
            "default_retries": self.config.default_retries,
            "max_runtime_seconds": self.config.max_runtime_seconds,
            "log_directory": str(self.config.log_directory),
        }
