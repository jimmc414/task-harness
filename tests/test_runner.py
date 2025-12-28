"""Tests for pipeline runner."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from harness.history import RunHistory
from harness.models import PipelineConfig, TaskConfig, TaskResult, ValidationResult
from harness.pipeline import Pipeline
from harness.runner import PipelineRunner, run_pipeline
from harness.task import Task
from harness.validators.base import Validator


# Test validators
class AlwaysPass(Validator):
    name = "AlwaysPass"

    def check(self, context):
        return ValidationResult.success(self.name)


class AlwaysFail(Validator):
    name = "AlwaysFail"

    def check(self, context):
        return ValidationResult.failure(self.name, "Always fails")


class RaiseError(Validator):
    name = "RaiseError"

    def check(self, context):
        raise RuntimeError("Validator error")


class CheckContext(Validator):
    name = "CheckContext"

    def __init__(self, key: str, expected: Any):
        self.key = key
        self.expected = expected

    def check(self, context):
        if context.get(self.key) == self.expected:
            return ValidationResult.success(self.name)
        return ValidationResult.failure(
            self.name, f"Expected {self.key}={self.expected}, got {context.get(self.key)}"
        )


# Test tasks
class SuccessTask(Task):
    name = "success_task"
    description = "A task that succeeds"

    def run(self, context):
        return TaskResult.ok("Success")


class FailTask(Task):
    name = "fail_task"
    description = "A task that fails"

    def run(self, context):
        return TaskResult.fail("Intentional failure")


class ErrorTask(Task):
    name = "error_task"
    description = "A task that raises an error"

    def run(self, context):
        raise RuntimeError("Task error")


class SlowTask(Task):
    name = "slow_task"
    description = "A slow task"
    config = TaskConfig(timeout_seconds=0.5)

    def run(self, context):
        time.sleep(2)  # Will timeout
        return TaskResult.ok("Done")


class ContextTask(Task):
    name = "context_task"
    description = "A task that uses and modifies context"

    def run(self, context):
        value = context.get("input", 0) + 1
        return TaskResult.ok("Incremented", data={"output": value})


class PreconditionTask(Task):
    name = "precondition_task"
    description = "Task with precondition"

    def __init__(self, precondition: Validator):
        super().__init__()
        self._preconditions = [precondition]

    def run(self, context):
        return TaskResult.ok("Done")


class PostconditionTask(Task):
    name = "postcondition_task"
    description = "Task with postcondition"

    def __init__(self, postcondition: Validator, data: dict = None):
        super().__init__()
        self._postconditions = [postcondition]
        self._data = data or {}

    def run(self, context):
        return TaskResult.ok("Done", data=self._data)


class RetryTask(Task):
    name = "retry_task"
    description = "Task that fails then succeeds"
    config = TaskConfig(retries=2, retry_delay_seconds=0.1)

    def __init__(self):
        super().__init__()
        self.attempts = 0

    def run(self, context):
        self.attempts += 1
        if self.attempts < 2:
            return TaskResult.fail(f"Attempt {self.attempts} failed")
        return TaskResult.ok(f"Succeeded on attempt {self.attempts}")


@pytest.fixture
def temp_runner(tmp_path: Path) -> PipelineRunner:
    """Create a runner with temp directories."""
    history = RunHistory(tmp_path / "history.jsonl")
    runner = PipelineRunner(history=history)
    return runner


@pytest.fixture
def simple_pipeline(tmp_path: Path) -> Pipeline:
    """Create a simple test pipeline."""
    return Pipeline(
        config=PipelineConfig(
            name="test_pipeline",
            log_directory=tmp_path / "logs",
        ),
        tasks=[SuccessTask()],
    )


class TestPipelineRunner:
    """Tests for PipelineRunner."""

    def test_successful_run(self, temp_runner: PipelineRunner, simple_pipeline: Pipeline) -> None:
        """Should run a simple pipeline successfully."""
        record = temp_runner.run(simple_pipeline)

        assert record.status == "success"
        assert record.tasks_completed == 1
        assert record.tasks_failed == 0

    def test_failed_task(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should handle task failure."""
        pipeline = Pipeline(
            config=PipelineConfig(name="fail_test", log_directory=tmp_path / "logs"),
            tasks=[FailTask()],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "failed"
        assert record.tasks_failed == 1
        assert "Intentional failure" in record.error_message

    def test_task_error(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should handle task exceptions."""
        pipeline = Pipeline(
            config=PipelineConfig(name="error_test", log_directory=tmp_path / "logs"),
            tasks=[ErrorTask()],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "failed"
        assert record.tasks_failed == 1

    def test_precondition_failure(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should fail on precondition failure."""
        pipeline = Pipeline(
            config=PipelineConfig(name="pre_test", log_directory=tmp_path / "logs"),
            tasks=[PreconditionTask(AlwaysFail())],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "failed"
        assert "Precondition failed" in record.error_message

    def test_postcondition_failure(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should fail on postcondition failure."""
        pipeline = Pipeline(
            config=PipelineConfig(name="post_test", log_directory=tmp_path / "logs"),
            tasks=[PostconditionTask(AlwaysFail())],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "failed"
        assert "AlwaysFail" in record.error_message

    def test_context_passing(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should pass context between tasks."""
        pipeline = Pipeline(
            config=PipelineConfig(name="context_test", log_directory=tmp_path / "logs"),
            tasks=[
                ContextTask(),
                PostconditionTask(CheckContext("output", 1)),
            ],
        )

        record = temp_runner.run(pipeline, initial_context={"input": 0})

        assert record.status == "success"
        assert record.tasks_completed == 2

    def test_initial_context(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should use initial context values."""
        pipeline = Pipeline(
            config=PipelineConfig(name="init_ctx_test", log_directory=tmp_path / "logs"),
            tasks=[PreconditionTask(CheckContext("key", "value"))],
        )

        record = temp_runner.run(pipeline, initial_context={"key": "value"})

        assert record.status == "success"

    def test_dry_run(self, temp_runner: PipelineRunner, simple_pipeline: Pipeline) -> None:
        """Should only check preconditions in dry run."""
        record = temp_runner.run(simple_pipeline, dry_run=True)

        assert record.status == "success"
        assert record.dry_run is True

    def test_start_from(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should skip tasks before start_from."""
        task1 = SuccessTask()
        task1.name = "task1"
        task2 = SuccessTask()
        task2.name = "task2"
        task3 = SuccessTask()
        task3.name = "task3"

        pipeline = Pipeline(
            config=PipelineConfig(name="start_from_test", log_directory=tmp_path / "logs"),
            tasks=[task1, task2, task3],
        )

        record = temp_runner.run(pipeline, start_from="task2")

        assert record.status == "success"
        assert record.tasks_completed == 2  # task2 and task3
        assert record.tasks_skipped == 1    # task1

    def test_start_from_invalid_task(self, temp_runner: PipelineRunner, simple_pipeline: Pipeline) -> None:
        """Should raise error for invalid start_from task."""
        from harness.exceptions import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            temp_runner.run(simple_pipeline, start_from="nonexistent")

    def test_retry_logic(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should retry failed tasks."""
        retry_task = RetryTask()
        pipeline = Pipeline(
            config=PipelineConfig(name="retry_test", log_directory=tmp_path / "logs"),
            tasks=[retry_task],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "success"
        assert retry_task.attempts == 2

    def test_timeout(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should timeout slow tasks."""
        pipeline = Pipeline(
            config=PipelineConfig(name="timeout_test", log_directory=tmp_path / "logs"),
            tasks=[SlowTask()],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "failed"
        assert "timed out" in record.error_message.lower()

    def test_pipeline_timeout(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should enforce pipeline-level timeout."""
        class SlowerTask1(Task):
            name = "slower1"
            config = TaskConfig(timeout_seconds=10)

            def run(self, context):
                time.sleep(0.5)  # First task completes
                return TaskResult.ok("Done")

        class SlowerTask2(Task):
            name = "slower2"
            config = TaskConfig(timeout_seconds=10)

            def run(self, context):
                time.sleep(0.5)
                return TaskResult.ok("Done")

        pipeline = Pipeline(
            config=PipelineConfig(
                name="pipeline_timeout_test",
                log_directory=tmp_path / "logs",
                max_runtime_seconds=0.3,  # Short pipeline timeout
            ),
            tasks=[SlowerTask1(), SlowerTask2()],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "failed"
        assert "exceeded" in record.error_message.lower()

    def test_history_recorded(self, tmp_path: Path) -> None:
        """Should record run in history."""
        history = RunHistory(tmp_path / "history.jsonl")
        runner = PipelineRunner(history=history)

        pipeline = Pipeline(
            config=PipelineConfig(name="history_test", log_directory=tmp_path / "logs"),
            tasks=[SuccessTask()],
        )

        record = runner.run(pipeline)

        # Check history
        recorded = history.get_last_run("history_test")
        assert recorded is not None
        assert recorded.run_id == record.run_id
        assert recorded.status == "success"

    def test_multiple_tasks(self, temp_runner: PipelineRunner, tmp_path: Path) -> None:
        """Should run multiple tasks in sequence."""
        task1 = SuccessTask()
        task1.name = "task1"
        task2 = SuccessTask()
        task2.name = "task2"
        task3 = SuccessTask()
        task3.name = "task3"

        pipeline = Pipeline(
            config=PipelineConfig(name="multi_test", log_directory=tmp_path / "logs"),
            tasks=[task1, task2, task3],
        )

        record = temp_runner.run(pipeline)

        assert record.status == "success"
        assert record.tasks_completed == 3


class TestRunPipelineFunction:
    """Tests for run_pipeline convenience function."""

    def test_convenience_function(self, tmp_path: Path) -> None:
        """Should work as a convenience function."""
        pipeline = Pipeline(
            config=PipelineConfig(name="convenience_test", log_directory=tmp_path / "logs"),
            tasks=[SuccessTask()],
        )

        record = run_pipeline(pipeline)

        assert record.status == "success"


class TestLocking:
    """Tests for locking behavior."""

    def test_creates_lock_file(self, tmp_path: Path) -> None:
        """Should create lock file during execution."""
        history = RunHistory(tmp_path / "history.jsonl")
        locks_dir = tmp_path / "locks"

        with patch("harness.runner.get_config") as mock_config:
            config = MagicMock()
            config.verbose = False
            config.locks_dir = locks_dir
            mock_config.return_value = config

            runner = PipelineRunner(history=history)

            class LockCheckTask(Task):
                name = "lock_check"

                def run(self, context):
                    # Lock file should exist during execution
                    lock_file = locks_dir / "lock_test.lock"
                    context["lock_existed"] = lock_file.exists()
                    return TaskResult.ok("Done", data={"lock_check": True})

            pipeline = Pipeline(
                config=PipelineConfig(name="lock_test", log_directory=tmp_path / "logs"),
                tasks=[LockCheckTask()],
            )

            record = runner.run(pipeline)
            assert record.status == "success"

    def test_force_lock(self, tmp_path: Path) -> None:
        """Should allow force lock acquisition."""
        history = RunHistory(tmp_path / "history.jsonl")
        locks_dir = tmp_path / "locks"
        locks_dir.mkdir()

        # Create a fake lock file
        lock_file = locks_dir / "force_test.lock"
        lock_file.write_text('{"pid": 99999}')

        with patch("harness.runner.get_config") as mock_config:
            config = MagicMock()
            config.verbose = False
            config.locks_dir = locks_dir
            mock_config.return_value = config

            runner = PipelineRunner(history=history)
            pipeline = Pipeline(
                config=PipelineConfig(name="force_test", log_directory=tmp_path / "logs"),
                tasks=[SuccessTask()],
            )

            # Should succeed with force_lock
            record = runner.run(pipeline, force_lock=True)
            assert record.status == "success"
