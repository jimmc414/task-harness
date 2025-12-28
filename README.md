# Task Harness

A Python-based task orchestration framework for running sequential automated processes with validation-based error handling.

## Overview

Task Harness executes pipelines of sequential tasks with robust pre/postcondition validation. Instead of attempting to handle all possible failure modes explicitly, it validates preconditions before task execution and postconditions after, providing clear feedback when something goes wrong.

**Target Environment:** Windows, Python 3.10+, invoked via Windows Task Scheduler or manual CLI execution.

## Features

- **Sequential Task Execution** - Run tasks in order with automatic context passing
- **Pre/Postcondition Validation** - 16 built-in validators for files, environment, network, and more
- **Retry Logic** - Configurable retries with delays for transient failures
- **Timeout Enforcement** - Per-task and per-pipeline timeout limits
- **Encrypted Secrets** - Secure storage for SFTP credentials, API keys, etc.
- **Concurrency Control** - File-based locking prevents duplicate runs
- **Run History** - JSON Lines history with filtering and status tracking
- **Failure Notifications** - Extensible notification system (email, etc.)
- **Comprehensive Logging** - Per-run log files with configurable verbosity

## Installation

```bash
pip install task-harness
```

Or install from source:

```bash
git clone https://github.com/yourusername/task-harness.git
cd task-harness
pip install -e .
```

## Quick Start

### 1. Create a Pipeline

Create `pipelines/my_pipeline.py`:

```python
from harness.task import Task, TaskConfig, TaskResult
from harness.pipeline import Pipeline, PipelineConfig
from harness.validators import FileExists, DirectoryExists, TabularFileValid

class ValidateEnvironment(Task):
    name = "validate_environment"
    description = "Check runtime environment"
    preconditions = [
        DirectoryExists("./data"),
        DirectoryExists("./output"),
    ]

    def run(self, context: dict) -> TaskResult:
        return TaskResult(success=True)


class ProcessData(Task):
    name = "process_data"
    description = "Transform input data"
    config = TaskConfig(timeout_seconds=60.0, retries=2)
    preconditions = [
        FileExists("data/input.csv"),
        TabularFileValid("data/input.csv", required_headers=["id", "value"]),
    ]
    postconditions = [
        FileExists("output/result.csv"),
    ]

    def run(self, context: dict) -> TaskResult:
        import pandas as pd

        df = pd.read_csv("data/input.csv")
        df["processed"] = df["value"] * 2
        df.to_csv("output/result.csv", index=False)

        return TaskResult(
            success=True,
            message=f"Processed {len(df)} rows",
            data={"row_count": len(df)}
        )


def create_pipeline() -> Pipeline:
    return Pipeline(
        config=PipelineConfig(
            name="my_pipeline",
            description="Example data processing pipeline",
            log_directory="./logs",
        ),
        tasks=[
            ValidateEnvironment(),
            ProcessData(),
        ],
    )
```

### 2. Run the Pipeline

```bash
# Execute the pipeline
harness run my_pipeline

# Dry run (validate preconditions only)
harness run my_pipeline --dry-run

# Start from a specific task (skip earlier tasks)
harness run my_pipeline --start-from process_data

# Pass context values
harness run my_pipeline --context input_file=data/custom.csv
```

### 3. Check Results

```bash
# View run history
harness history --pipeline my_pipeline --limit 5

# Show pipeline details
harness show my_pipeline

# List all pipelines
harness list
```

## CLI Reference

### `harness run <pipeline>`

Execute a pipeline.

| Option | Description |
|--------|-------------|
| `--dry-run` | Validate preconditions without executing tasks |
| `--start-from TASK` | Skip tasks before TASK |
| `--force` | Ignore concurrency lock (dangerous) |
| `--context KEY=VAL` | Pass initial context values (repeatable) |
| `--verbose` | Force verbose output |
| `--quiet` | Force quiet output |

**Exit Codes:**
- `0` - Pipeline completed successfully
- `1` - Pipeline failed (task or validation failure)
- `2` - CLI error (bad arguments, pipeline not found)
- `3` - Lock contention (another instance running)

### `harness list`

List all discovered pipelines.

### `harness show <pipeline>`

Display pipeline details including tasks and validators.

### `harness history`

Show run history.

| Option | Description |
|--------|-------------|
| `--pipeline NAME` | Filter by pipeline name |
| `--limit N` | Number of records (default 10) |
| `--status STATUS` | Filter by status (success/failed) |

### `harness secrets <command>`

Manage encrypted secrets store.

| Command | Description |
|---------|-------------|
| `init` | Create new secrets store and generate key |
| `set <name>` | Store a secret (prompts for JSON input) |
| `get <name>` | Retrieve a secret (requires confirmation) |
| `list` | List secret names (not values) |
| `delete <name>` | Remove a secret |

## Built-in Validators

### Environment Validators

| Validator | Description |
|-----------|-------------|
| `VirtualEnvActive(expected_path=None)` | Check if running in a virtual environment |
| `EnvVarSet(var_name)` | Check environment variable is set and non-empty |
| `EnvVarEquals(var_name, expected_value)` | Check environment variable has specific value |
| `PythonPackageAvailable(package, min_version=None)` | Check Python package is importable |

### Filesystem Validators

| Validator | Description |
|-----------|-------------|
| `FileExists(path, from_context=False)` | Check file exists |
| `DirectoryExists(path, from_context=False)` | Check directory exists |
| `FileModifiedWithin(path, max_age)` | Check file was modified recently |
| `FileSizeInRange(path, min_bytes=0, max_bytes=None)` | Check file size is within range |

### Tabular File Validators

| Validator | Description |
|-----------|-------------|
| `TabularFileValid(path, required_headers=None, min_data_rows=1, ...)` | Validate CSV/Excel has headers and data |
| `TabularFileRowCount(path, min_rows=0, max_rows=None)` | Check row count is within range |

### Network Validators

| Validator | Description |
|-----------|-------------|
| `HostReachable(host, port, timeout_seconds=5.0)` | Check TCP connectivity |
| `SFTPConnectable(connection_name)` | Validate SFTP connection using stored credentials |

### Process Validators

| Validator | Description |
|-----------|-------------|
| `CommandAvailable(command)` | Check external command is in PATH |

### Composite Validators

| Validator | Description |
|-----------|-------------|
| `AnyOf(*validators)` | Pass if any child validator passes |
| `AllOf(*validators, name="AllOf")` | Pass only if all child validators pass |

## Configuration

### TaskConfig

```python
@dataclass
class TaskConfig:
    timeout_seconds: float = 300.0          # Task execution timeout
    retries: int = 0                         # Additional attempts after failure
    retry_delay_seconds: float = 5.0         # Wait between retries
    retry_on_postcondition_failure: bool = True  # Retry if postcondition fails
    log_level: str = "INFO"                  # DEBUG, INFO, WARNING, ERROR
    notify_on_failure: bool = True           # Send notification on failure
```

### PipelineConfig

```python
@dataclass
class PipelineConfig:
    name: str                                 # Unique pipeline identifier
    description: str = ""
    default_timeout_seconds: float = 300.0
    default_retries: int = 0
    default_log_level: str = "INFO"
    max_runtime_seconds: float | None = None  # Pipeline-level timeout
    lock_retry_attempts: int = 3
    lock_retry_delay_seconds: float = 60.0
    log_directory: Path = Path("./logs")
    history_file: Path = Path("./run_history.jsonl")
    notify_on_failure: bool = True
    notify_on_success: bool = False
```

## Secrets Management

Task Harness includes an encrypted secrets store for sensitive credentials.

### Initialize Secrets Store

```bash
harness secrets init
```

This generates a Fernet encryption key and stores it in Windows Credential Manager. The key is also printed for backup - save it securely.

### Store Credentials

```bash
harness secrets set sftp_vendor
# Enter JSON: {"host": "sftp.vendor.com", "username": "user", "password": "pass"}
```

### Use in Validators

```python
from harness.validators import SFTPConnectable

class FetchData(Task):
    preconditions = [
        SFTPConnectable("sftp_vendor"),  # Uses stored credentials
    ]
```

### Environment Variable

For Task Scheduler or CI environments, set the key via environment variable:

```bash
set HARNESS_SECRETS_KEY=your-base64-encoded-key
```

## Scheduling with Windows Task Scheduler

1. Create a batch file `run_pipeline.bat`:

```batch
@echo off
cd /d C:\path\to\your\project
call venv\Scripts\activate
set HARNESS_SECRETS_KEY=your-key-here
harness run my_pipeline --quiet
```

2. Create a scheduled task:
   - Program: `C:\path\to\your\project\run_pipeline.bat`
   - Start in: `C:\path\to\your\project`
   - Run whether user is logged on or not

## Context Passing

Tasks can pass data to subsequent tasks via the context dictionary:

```python
class Task1(Task):
    def run(self, context: dict) -> TaskResult:
        # Receive initial context
        input_file = context.get("input_file", "default.csv")

        # Pass data to next task
        return TaskResult(
            success=True,
            data={"processed_count": 100, "output_file": "result.csv"}
        )


class Task2(Task):
    def run(self, context: dict) -> TaskResult:
        # Access data from previous task
        count = context["processed_count"]
        output = context["output_file"]
        ...
```

## Error Handling

### Validator Exceptions

If a validator's `check()` method raises an exception, it's automatically caught and converted to a failed validation result:

```python
class CustomValidator(Validator):
    def check(self, context: dict) -> ValidationResult:
        # If this raises, it becomes a failed result
        data = some_risky_operation()
        return ValidationResult(True, "OK", self.name)
```

### Task Timeouts

Tasks are executed with `concurrent.futures.ThreadPoolExecutor`. If a task exceeds its timeout:
- A `TimeoutError` is raised
- The task is marked as failed
- Retry logic is triggered (if configured)

**Note:** Python threads cannot be forcibly killed. A timed-out task continues running in the background. For critical processes, configure Task Scheduler with a hard timeout as a backup.

### Retry Logic

```python
class FlakeyTask(Task):
    config = TaskConfig(
        retries=3,                           # Try up to 4 times total
        retry_delay_seconds=30.0,            # Wait 30s between attempts
        retry_on_postcondition_failure=True  # Retry if postcondition fails
    )
```

## Logging

Each pipeline run creates a log file:

```
logs/
└── my_pipeline/
    ├── 20240115-143022.log
    ├── 20240116-090015.log
    └── ...
```

Log format:
```
2024-01-15 14:30:22 [INFO] [Pipeline] Starting pipeline: my_pipeline
2024-01-15 14:30:22 [INFO] [validate_environment] Running task
2024-01-15 14:30:22 [DEBUG] [validate_environment] Checking precondition: DirectoryExists
2024-01-15 14:30:22 [INFO] [validate_environment] Task completed in 0.02s
```

## Project Structure

```
your_project/
├── pipelines/
│   ├── __init__.py
│   ├── daily_report.py
│   └── weekly_summary.py
├── logs/                    # Created at runtime
├── locks/                   # Created at runtime
├── .harness/
│   └── secrets.enc          # Encrypted secrets
├── run_history.jsonl        # Run history
└── pyproject.toml
```

## Dependencies

- `cryptography>=41.0` - Secrets encryption
- `paramiko>=3.0` - SFTP connectivity
- `openpyxl>=3.1` - Excel file validation
- `pandas>=2.0` - Tabular data operations
- `psutil>=5.9` - Stale lock detection
- `colorama>=0.4` - CLI colors
- `keyring>=24.0` - Windows Credential Manager integration
- `packaging>=21.0` - Version comparison

## Development

### Running Tests

```bash
# Full test suite with coverage
pytest --cov=harness --cov-report=term-missing

# Just validator tests (fastest feedback)
pytest tests/test_validators/ -v

# Specific module
pytest tests/test_runner.py -v
```

### Claude Code Integration

This project includes Claude Code configuration for AI-assisted development.

#### Commands (`.claude/commands/`)

| Command | Description |
|---------|-------------|
| `/test` | Run full test suite with coverage |
| `/test-validators` | Run only validator tests |
| `/test-quick` | Run tests excluding slow ones |
| `/run-example` | Dry-run the example pipeline |
| `/check-pipelines` | Validate all pipelines load correctly |

#### Skills (`.claude/skills/`)

| Skill | Description |
|-------|-------------|
| `/harness-context` | Re-establish project knowledge when context is lost |
| `/new-pipeline` | Generate a new pipeline from template |
| `/new-validator` | Generate a new validator with tests |
| `/debug-run` | Analyze a failed pipeline run |

### Creating Custom Validators

Inherit from `Validator` and implement `check()`:

```python
from harness.validators.base import Validator
from harness.models import ValidationResult

class MyValidator(Validator):
    name = "MyValidator"

    def __init__(self, param: str, from_context: bool = False):
        self.param = param
        self.from_context = from_context

    def check(self, context: dict) -> ValidationResult:
        value = context.get(self.param) if self.from_context else self.param

        if some_condition(value):
            return ValidationResult.success(self.name, f"Check passed: {value}")

        return ValidationResult.failure(self.name, f"Check failed: {value}")
```

Add to `harness/validators/__init__.py` exports to make it available.

### Architecture Overview

```
PipelineRunner.run(pipeline)
    │
    ├── Acquire lock (PipelineLock)
    │
    ├── For each Task:
    │   ├── Check preconditions (Validator.check())
    │   ├── Execute task.run(context) with timeout
    │   ├── Merge TaskResult.data into context
    │   └── Check postconditions
    │
    ├── Record history (RunHistory)
    │
    └── Release lock
```

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## License

MIT License - see LICENSE file for details.
