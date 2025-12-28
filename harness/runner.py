"""Pipeline runner for Task Harness.

Executes pipelines with locking, logging, validation, and history tracking.
"""

from __future__ import annotations

import atexit
import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from harness.config import get_config
from harness.exceptions import (
    PipelineAlreadyRunningError,
    PipelineTimeoutError,
    PreconditionError,
    PostconditionError,
    TaskTimeoutError,
    TaskExecutionError,
    TaskNotFoundError,
)
from harness.history import RunHistory
from harness.locking import PipelineLock
from harness.logging_setup import setup_logging, TaskLogger
from harness.models import RunRecord, TaskResult, ValidationResult
from harness.notification import NoOpNotifier, Notifier
from harness.pipeline import Pipeline
from harness.task import Task


class PipelineRunner:
    """Executes pipelines with full lifecycle management.

    Handles:
    - Concurrency control via file locking
    - Per-run logging
    - Precondition/postcondition validation
    - Task execution with timeouts
    - Retry logic
    - Context passing between tasks
    - History recording
    - Failure notifications

    Example:
        runner = PipelineRunner()
        record = runner.run(pipeline)

        if record.status == "success":
            print("Pipeline completed successfully!")
        else:
            print(f"Pipeline failed: {record.error_message}")
    """

    def __init__(
        self,
        notifier: Notifier | None = None,
        history: RunHistory | None = None,
    ):
        """Initialize the runner.

        Args:
            notifier: Notification handler (default: NoOpNotifier).
            history: History storage (default: from config).
        """
        self.notifier = notifier or NoOpNotifier()
        self.history = history or RunHistory()
        self._current_lock: PipelineLock | None = None
        self._cleanup_registered = False

    def run(
        self,
        pipeline: Pipeline,
        dry_run: bool = False,
        start_from: str | None = None,
        initial_context: dict[str, Any] | None = None,
        force_lock: bool = False,
        verbose: bool | None = None,
    ) -> RunRecord:
        """Execute a pipeline.

        Args:
            pipeline: The pipeline to execute.
            dry_run: If True, only validate preconditions without executing.
            start_from: Task name to start from (skips earlier tasks).
            initial_context: Initial context values.
            force_lock: If True, force acquire lock (dangerous).
            verbose: Override verbosity (None = auto-detect).

        Returns:
            RunRecord with execution results.

        Raises:
            PipelineAlreadyRunningError: If another instance is running.
            TaskNotFoundError: If start_from task doesn't exist.
        """
        config = get_config()

        # Validate start_from
        if start_from and start_from not in pipeline:
            raise TaskNotFoundError(
                start_from,
                pipeline.name,
                pipeline.get_task_names(),
            )

        # Create run record
        record = RunRecord(
            pipeline_name=pipeline.name,
            dry_run=dry_run,
        )

        # Determine verbosity
        if verbose is None:
            verbose = config.verbose

        # Set up logging
        logger, log_file = setup_logging(
            pipeline.name,
            record.run_id,
            logs_dir=pipeline.config.log_directory,
            verbose=verbose,
        )

        try:
            # Acquire lock
            self._current_lock = PipelineLock(
                pipeline.name,
                locks_dir=config.locks_dir,
                retry_attempts=pipeline.config.lock_retry_attempts,
                retry_delay_seconds=pipeline.config.lock_retry_delay_seconds,
            )

            if not self._current_lock.acquire(force=force_lock):
                lock_info = self._current_lock.get_lock_info()
                holder_pid = lock_info.get("pid") if lock_info else None
                raise PipelineAlreadyRunningError(pipeline.name, holder_pid)

            # Register cleanup
            self._register_cleanup(record)

            # Record pipeline start time for timeout tracking
            start_time = datetime.now(timezone.utc)

            # Initialize context
            context = dict(initial_context or {})

            # Get tasks to run
            if start_from:
                tasks = pipeline.get_tasks_from(start_from)
                skipped_count = pipeline.get_task_index(start_from)
                record.tasks_skipped = skipped_count
                logger.info(f"Starting from task '{start_from}', skipping {skipped_count} tasks")
            else:
                tasks = pipeline.tasks

            # Execute tasks
            for task in tasks:
                # Check pipeline timeout
                if pipeline.config.max_runtime_seconds:
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    if elapsed > pipeline.config.max_runtime_seconds:
                        raise PipelineTimeoutError(
                            pipeline.name, elapsed, pipeline.config.max_runtime_seconds
                        )

                # Execute task
                success, message = self._execute_task(
                    task, context, logger, dry_run, pipeline.config
                )

                if success:
                    record.increment_completed()
                else:
                    record.increment_failed()
                    record.mark_complete("failed", message)

                    # Notify on failure
                    if pipeline.config.notify_on_failure:
                        self._notify_failure(pipeline, record)

                    self.history.record(record)
                    return record

            # All tasks completed successfully
            record.mark_complete("success")

            if dry_run:
                logger.info("Dry run completed - all preconditions passed")
            else:
                logger.info(
                    f"Pipeline completed successfully: "
                    f"{record.tasks_completed} tasks in "
                    f"{record.duration_seconds:.1f}s"
                )

            # Notify on success
            if pipeline.config.notify_on_success:
                self._notify_success(pipeline, record)

        except PipelineAlreadyRunningError:
            record.mark_complete("failed", "Pipeline is already running")
            logger.error("Failed to acquire lock - pipeline is already running")
            raise

        except PipelineTimeoutError as e:
            record.mark_complete("failed", str(e))
            logger.error(str(e))
            if pipeline.config.notify_on_failure:
                self._notify_failure(pipeline, record)

        except Exception as e:
            record.mark_complete("failed", str(e))
            logger.exception(f"Pipeline failed with unexpected error: {e}")
            if pipeline.config.notify_on_failure:
                self._notify_failure(pipeline, record)

        finally:
            # Release lock
            if self._current_lock:
                self._current_lock.release()
                self._current_lock = None

            # Record history
            self.history.record(record)

        return record

    def _execute_task(
        self,
        task: Task,
        context: dict[str, Any],
        logger: logging.Logger,
        dry_run: bool,
        pipeline_config,
    ) -> tuple[bool, str]:
        """Execute a single task with validation and retries.

        Args:
            task: The task to execute.
            context: Shared context dictionary.
            logger: Logger for this run.
            dry_run: If True, only validate preconditions.
            pipeline_config: Pipeline configuration.

        Returns:
            Tuple of (success, message).
        """
        task_logger = TaskLogger(logger, task.name)
        task_logger.info(f"Running task: {task.description or task.name}")

        # Get effective config (task config with pipeline defaults)
        timeout = task.task_config.timeout_seconds or pipeline_config.default_timeout_seconds
        retries = task.task_config.retries or pipeline_config.default_retries

        # Check preconditions
        task_logger.debug("Checking preconditions")
        for validator in task.task_preconditions:
            try:
                result = validator.check(context)
                if not result.passed:
                    task_logger.error(f"Precondition failed: {validator.name} - {result.message}")
                    return False, f"Precondition failed: [{validator.name}] {result.message}"
                task_logger.debug(f"Precondition passed: {validator.name}")
            except Exception as e:
                task_logger.error(f"Precondition error: {validator.name} - {e}")
                return False, f"Precondition error: [{validator.name}] {e}"

        # Dry run - stop after preconditions
        if dry_run:
            task_logger.info("Dry run - preconditions passed, skipping execution")
            return True, "Dry run - preconditions passed"

        # Execute with retries
        max_attempts = 1 + retries
        last_error = ""

        for attempt in range(max_attempts):
            if attempt > 0:
                delay = task.task_config.retry_delay_seconds
                task_logger.info(f"Retry {attempt}/{retries} after {delay}s delay")
                time.sleep(delay)

            try:
                # Execute task with timeout
                result = self._run_with_timeout(task, context, timeout)

                if not result.success:
                    last_error = result.message
                    task_logger.warning(f"Task returned failure: {result.message}")
                    continue

                # Update context with result data
                if result.data:
                    context.update(result.data)

                # Check postconditions
                post_ok, post_msg = self._check_postconditions(
                    task, context, task_logger
                )

                if post_ok:
                    task_logger.info(
                        f"Task completed successfully in {result.duration_seconds:.2f}s"
                    )
                    return True, result.message

                # Postcondition failed
                last_error = post_msg
                task_logger.warning(f"Postcondition failed: {post_msg}")

                if not task.task_config.retry_on_postcondition_failure:
                    return False, post_msg

            except FuturesTimeoutError:
                last_error = f"Task timed out after {timeout}s"
                task_logger.warning(last_error)

            except Exception as e:
                last_error = str(e)
                task_logger.exception(f"Task error: {e}")

        # All attempts failed
        return False, f"Failed after {max_attempts} attempts: {last_error}"

    def _run_with_timeout(
        self, task: Task, context: dict[str, Any], timeout: float
    ) -> TaskResult:
        """Run a task with timeout using ThreadPoolExecutor.

        Args:
            task: The task to run.
            context: Shared context.
            timeout: Timeout in seconds.

        Returns:
            TaskResult from the task.

        Raises:
            TimeoutError: If task exceeds timeout.
        """
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(task.run, context)
            try:
                result = future.result(timeout=timeout)
                result.duration_seconds = time.time() - start_time
                return result
            except FuturesTimeoutError:
                # Note: The thread continues running in background
                # This is a known limitation documented in the spec
                raise

    def _check_postconditions(
        self, task: Task, context: dict[str, Any], task_logger: TaskLogger
    ) -> tuple[bool, str]:
        """Check all postconditions for a task.

        Args:
            task: The task.
            context: Current context.
            task_logger: Logger for the task.

        Returns:
            Tuple of (success, message).
        """
        if not task.task_postconditions:
            return True, "No postconditions"

        task_logger.debug("Checking postconditions")

        for validator in task.task_postconditions:
            try:
                result = validator.check(context)
                if not result.passed:
                    return False, f"[{validator.name}] {result.message}"
                task_logger.debug(f"Postcondition passed: {validator.name}")
            except Exception as e:
                return False, f"[{validator.name}] Error: {e}"

        return True, "All postconditions passed"

    def _notify_failure(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Send failure notification."""
        try:
            self.notifier.notify_failure(pipeline, record)
        except Exception as e:
            # Log but don't fail on notification error
            logging.getLogger("harness").warning(f"Notification failed: {e}")

    def _notify_success(self, pipeline: Pipeline, record: RunRecord) -> None:
        """Send success notification."""
        try:
            self.notifier.notify_success(pipeline, record)
        except Exception as e:
            # Log but don't fail on notification error
            logging.getLogger("harness").warning(f"Notification failed: {e}")

    def _register_cleanup(self, record: RunRecord) -> None:
        """Register cleanup handlers for graceful shutdown."""
        if self._cleanup_registered:
            return

        def cleanup(signum=None, frame=None):
            """Clean up on interrupt or termination."""
            if self._current_lock:
                self._current_lock.release()
            record.mark_complete("cancelled", "Interrupted by signal")
            self.history.record(record)

        # Register signal handlers
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, cleanup)
            try:
                signal.signal(signal.SIGBREAK, cleanup)
            except AttributeError:
                pass  # SIGBREAK not available in all contexts
        else:
            signal.signal(signal.SIGINT, cleanup)
            signal.signal(signal.SIGTERM, cleanup)

        self._cleanup_registered = True


def run_pipeline(
    pipeline: Pipeline,
    dry_run: bool = False,
    start_from: str | None = None,
    initial_context: dict[str, Any] | None = None,
    force_lock: bool = False,
    verbose: bool | None = None,
) -> RunRecord:
    """Convenience function to run a pipeline.

    Args:
        pipeline: The pipeline to execute.
        dry_run: If True, only validate preconditions.
        start_from: Task name to start from.
        initial_context: Initial context values.
        force_lock: If True, force acquire lock.
        verbose: Override verbosity.

    Returns:
        RunRecord with execution results.
    """
    runner = PipelineRunner()
    return runner.run(
        pipeline,
        dry_run=dry_run,
        start_from=start_from,
        initial_context=initial_context,
        force_lock=force_lock,
        verbose=verbose,
    )
