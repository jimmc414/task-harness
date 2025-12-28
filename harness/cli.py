"""Command-line interface for Task Harness.

Provides commands for running pipelines, viewing history, and managing secrets.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Try to import colorama for colored output
try:
    from colorama import init as colorama_init, Fore, Style

    colorama_init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

    class Fore:
        GREEN = RED = YELLOW = CYAN = RESET = ""

    class Style:
        BRIGHT = RESET_ALL = ""


from harness import __version__
from harness.config import get_config, get_pipelines_dir
from harness.exceptions import (
    HarnessError,
    PipelineAlreadyRunningError,
    PipelineNotFoundError,
    SecretsKeyError,
    TaskNotFoundError,
)
from harness.history import RunHistory
from harness.pipeline import Pipeline
from harness.runner import PipelineRunner
from harness.secrets import SecretsStore


# Exit codes
EXIT_SUCCESS = 0
EXIT_PIPELINE_FAILURE = 1
EXIT_CLI_ERROR = 2
EXIT_LOCK_CONTENTION = 3


def discover_pipelines() -> dict[str, callable]:
    """Discover pipeline modules in the pipelines directory.

    Returns:
        Dict mapping pipeline names to their create_pipeline functions.
    """
    pipelines = {}
    pipelines_dir = get_pipelines_dir()

    if not pipelines_dir.exists():
        return pipelines

    for path in pipelines_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue

        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "create_pipeline"):
                # Get name from module constant or by calling create_pipeline
                if hasattr(module, "PIPELINE_NAME"):
                    name = module.PIPELINE_NAME
                else:
                    pipeline = module.create_pipeline()
                    name = pipeline.config.name

                pipelines[name] = module.create_pipeline

        except Exception as e:
            # Log error but continue discovering
            print(f"{Fore.YELLOW}Warning: Failed to load {path}: {e}{Style.RESET_ALL}")

    return pipelines


def get_pipeline(name: str) -> Pipeline:
    """Get a pipeline by name.

    Args:
        name: Pipeline name.

    Returns:
        Pipeline instance.

    Raises:
        PipelineNotFoundError: If pipeline doesn't exist.
    """
    pipelines = discover_pipelines()

    if name not in pipelines:
        raise PipelineNotFoundError(name, list(pipelines.keys()))

    return pipelines[name]()


def print_success(message: str) -> None:
    """Print a success message in green."""
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")


def print_error(message: str) -> None:
    """Print an error message in red."""
    print(f"{Fore.RED}{message}{Style.RESET_ALL}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")


def print_info(message: str) -> None:
    """Print an info message in cyan."""
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")


# --------------------------------------------------------------------------
# Command handlers
# --------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """Run a pipeline."""
    try:
        pipeline = get_pipeline(args.pipeline)
    except PipelineNotFoundError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR

    # Parse context arguments
    context = {}
    if args.context:
        for item in args.context:
            key, _, value = item.partition("=")
            if not key:
                print_error(f"Invalid context format: {item}")
                return EXIT_CLI_ERROR
            context[key] = value

    # Determine verbosity
    if args.verbose:
        verbose = True
    elif args.quiet:
        verbose = False
    else:
        verbose = None  # Auto-detect

    # Run pipeline
    runner = PipelineRunner()

    try:
        record = runner.run(
            pipeline,
            dry_run=args.dry_run,
            start_from=args.start_from,
            initial_context=context,
            force_lock=args.force,
            verbose=verbose,
        )

        if record.status == "success":
            if args.dry_run:
                print_success("Dry run completed - all preconditions passed")
            else:
                print_success(
                    f"Pipeline completed successfully: "
                    f"{record.tasks_completed} tasks in "
                    f"{record.duration_seconds:.1f}s"
                )
            return EXIT_SUCCESS
        else:
            print_error(f"Pipeline failed: {record.error_message}")
            return EXIT_PIPELINE_FAILURE

    except PipelineAlreadyRunningError as e:
        print_error(str(e))
        return EXIT_LOCK_CONTENTION

    except TaskNotFoundError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR


def cmd_list(args: argparse.Namespace) -> int:
    """List available pipelines."""
    pipelines = discover_pipelines()

    if not pipelines:
        print_warning("No pipelines found in pipelines/ directory")
        return EXIT_SUCCESS

    print_info("Available pipelines:")
    for name in sorted(pipelines.keys()):
        print(f"  {name}")

    return EXIT_SUCCESS


def cmd_show(args: argparse.Namespace) -> int:
    """Show pipeline details."""
    try:
        pipeline = get_pipeline(args.pipeline)
    except PipelineNotFoundError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR

    print_info(f"Pipeline: {pipeline.name}")
    print(f"  Description: {pipeline.description or '(none)'}")
    print(f"  Tasks: {len(pipeline.tasks)}")
    print()

    for i, task in enumerate(pipeline.tasks, 1):
        print(f"  {i}. {task.name}")
        if task.description:
            print(f"     {task.description}")
        if task.task_preconditions:
            print(f"     Preconditions: {len(task.task_preconditions)}")
        if task.task_postconditions:
            print(f"     Postconditions: {len(task.task_postconditions)}")

    return EXIT_SUCCESS


def cmd_history(args: argparse.Namespace) -> int:
    """Show run history."""
    history = RunHistory()
    records = history.get_recent(
        limit=args.limit,
        pipeline=args.pipeline,
        status=args.status,
    )

    if not records:
        print_warning("No history records found")
        return EXIT_SUCCESS

    print_info(f"Recent runs (showing {len(records)}):")
    print()

    for record in records:
        status_color = Fore.GREEN if record.status == "success" else Fore.RED
        print(f"  {record.run_id}")
        print(f"    Pipeline: {record.pipeline_name}")
        print(f"    Status: {status_color}{record.status}{Style.RESET_ALL}")
        print(f"    Started: {record.started_at}")
        if record.duration_seconds:
            print(f"    Duration: {record.duration_seconds:.1f}s")
        print(f"    Tasks: {record.tasks_completed} completed, {record.tasks_failed} failed")
        if record.error_message:
            print(f"    Error: {record.error_message}")
        print()

    return EXIT_SUCCESS


def cmd_secrets_init(args: argparse.Namespace) -> int:
    """Initialize secrets store."""
    config = get_config()

    if config.secrets_file.exists():
        print_warning(f"Secrets store already exists at {config.secrets_file}")
        return EXIT_CLI_ERROR

    key = SecretsStore.init_store(config.secrets_file)

    print_success("Secrets store initialized!")
    print()
    print("Key saved to system keyring.")
    print()
    print("For Task Scheduler or CI environments, set this environment variable:")
    print(f"  HARNESS_SECRETS_KEY={key}")
    print()
    print_warning("IMPORTANT: Save this key in a secure location. It cannot be recovered!")

    return EXIT_SUCCESS


def cmd_secrets_set(args: argparse.Namespace) -> int:
    """Store a secret."""
    try:
        store = SecretsStore()

        print(f"Enter JSON value for '{args.name}':")
        value_str = input()

        try:
            value = json.loads(value_str)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON: {e}")
            return EXIT_CLI_ERROR

        store.set(args.name, value)
        print_success(f"Secret '{args.name}' stored successfully")
        return EXIT_SUCCESS

    except SecretsKeyError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR


def cmd_secrets_get(args: argparse.Namespace) -> int:
    """Retrieve a secret."""
    try:
        store = SecretsStore()
        value = store.get(args.name)

        print_warning("WARNING: This will display sensitive data!")
        confirm = input("Continue? [y/N]: ")

        if confirm.lower() != "y":
            print("Cancelled")
            return EXIT_SUCCESS

        print(json.dumps(value, indent=2))
        return EXIT_SUCCESS

    except SecretsKeyError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR
    except HarnessError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR


def cmd_secrets_list(args: argparse.Namespace) -> int:
    """List secret names."""
    try:
        store = SecretsStore()
        names = store.list_names()

        if not names:
            print_warning("No secrets stored")
            return EXIT_SUCCESS

        print_info("Stored secrets:")
        for name in sorted(names):
            print(f"  {name}")

        return EXIT_SUCCESS

    except SecretsKeyError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR


def cmd_secrets_delete(args: argparse.Namespace) -> int:
    """Delete a secret."""
    try:
        store = SecretsStore()

        if not store.exists(args.name):
            print_error(f"Secret not found: {args.name}")
            return EXIT_CLI_ERROR

        store.delete(args.name)
        print_success(f"Secret '{args.name}' deleted")
        return EXIT_SUCCESS

    except SecretsKeyError as e:
        print_error(str(e))
        return EXIT_CLI_ERROR


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Task Harness - Task orchestration with validation",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Task Harness {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Execute a pipeline")
    run_parser.add_argument("pipeline", help="Pipeline name to run")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate preconditions without executing tasks",
    )
    run_parser.add_argument(
        "--start-from",
        metavar="TASK",
        help="Skip tasks before TASK",
    )
    run_parser.add_argument(
        "--force",
        action="store_true",
        help="Force acquire lock (dangerous)",
    )
    run_parser.add_argument(
        "--context",
        action="append",
        metavar="KEY=VAL",
        help="Pass context values (repeatable)",
    )
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Force verbose output",
    )
    run_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Force quiet output",
    )

    # list command
    subparsers.add_parser("list", help="List available pipelines")

    # show command
    show_parser = subparsers.add_parser("show", help="Show pipeline details")
    show_parser.add_argument("pipeline", help="Pipeline name to show")

    # history command
    history_parser = subparsers.add_parser("history", help="Show run history")
    history_parser.add_argument(
        "--pipeline",
        help="Filter by pipeline name",
    )
    history_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of records to show (default: 10)",
    )
    history_parser.add_argument(
        "--status",
        choices=["success", "failed", "cancelled"],
        help="Filter by status",
    )

    # secrets command
    secrets_parser = subparsers.add_parser("secrets", help="Manage encrypted secrets")
    secrets_subparsers = secrets_parser.add_subparsers(dest="secrets_command")

    secrets_subparsers.add_parser("init", help="Initialize secrets store")

    set_parser = secrets_subparsers.add_parser("set", help="Store a secret")
    set_parser.add_argument("name", help="Secret name")

    get_parser = secrets_subparsers.add_parser("get", help="Retrieve a secret")
    get_parser.add_argument("name", help="Secret name")

    secrets_subparsers.add_parser("list", help="List secret names")

    delete_parser = secrets_subparsers.add_parser("delete", help="Delete a secret")
    delete_parser.add_argument("name", help="Secret name")

    return parser


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return EXIT_CLI_ERROR

    # Route to command handlers
    if parsed.command == "run":
        return cmd_run(parsed)
    elif parsed.command == "list":
        return cmd_list(parsed)
    elif parsed.command == "show":
        return cmd_show(parsed)
    elif parsed.command == "history":
        return cmd_history(parsed)
    elif parsed.command == "secrets":
        if parsed.secrets_command == "init":
            return cmd_secrets_init(parsed)
        elif parsed.secrets_command == "set":
            return cmd_secrets_set(parsed)
        elif parsed.secrets_command == "get":
            return cmd_secrets_get(parsed)
        elif parsed.secrets_command == "list":
            return cmd_secrets_list(parsed)
        elif parsed.secrets_command == "delete":
            return cmd_secrets_delete(parsed)
        else:
            parser.parse_args(["secrets", "--help"])
            return EXIT_CLI_ERROR

    return EXIT_CLI_ERROR


if __name__ == "__main__":
    sys.exit(main())
