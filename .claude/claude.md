# Task Harness - Claude Code Context

## Project Overview

Task Harness is a Python-based task orchestration framework for running sequential automated processes with validation-based error handling. Target: Windows, Python 3.10+, Windows Task Scheduler.

## Architecture

```
Pipeline (sequential container)
    └── Task (unit of work)
            ├── preconditions: list[Validator]  # checked before run()
            ├── run(context) -> TaskResult      # actual work
            └── postconditions: list[Validator] # checked after run()
```

### Core Flow
1. `PipelineRunner.run(pipeline)` acquires lock
2. For each task: check preconditions → execute → check postconditions
3. Context dict passes data between tasks (TaskResult.data merged after each)
4. History recorded, lock released

## Key Files

| File | Purpose |
|------|---------|
| `harness/models.py` | Core dataclasses: ValidationResult, TaskConfig, TaskResult, PipelineConfig, RunRecord |
| `harness/task.py` | Task ABC - inherit and implement `run()` |
| `harness/pipeline.py` | Pipeline container class |
| `harness/runner.py` | PipelineRunner - orchestrates execution |
| `harness/validators/*.py` | 16 built-in validators |
| `harness/cli.py` | argparse CLI: run, list, show, history, secrets |
| `harness/secrets.py` | Fernet-encrypted secrets store |
| `harness/locking.py` | File-based concurrency lock with stale detection |
| `harness/history.py` | JSON Lines run history |
| `pipelines/*.py` | User pipelines with `create_pipeline()` function |

## Validators (16 built-in)

**Environment:** VirtualEnvActive, EnvVarSet, EnvVarEquals, PythonPackageAvailable
**Filesystem:** FileExists, DirectoryExists, FileModifiedWithin, FileSizeInRange
**Tabular:** TabularFileValid, TabularFileRowCount
**Network:** HostReachable, SFTPConnectable
**Process:** CommandAvailable
**Composite:** AnyOf, AllOf, NoneOf, ConditionalValidator

## Common Patterns

### Creating a Task
```python
from harness.task import Task
from harness.models import TaskResult, TaskConfig
from harness.validators import FileExists

class MyTask(Task):
    name = "my_task"
    description = "What this task does"
    config = TaskConfig(timeout_seconds=60.0, retries=2)
    preconditions = [FileExists("input.csv")]
    postconditions = [FileExists("output.csv")]

    def run(self, context: dict) -> TaskResult:
        # Do work here
        return TaskResult.ok("Done", data={"key": "value"})
```

### Creating a Validator
```python
from harness.validators.base import Validator
from harness.models import ValidationResult

class MyValidator(Validator):
    name = "MyValidator"

    def __init__(self, param: str):
        self.param = param

    def check(self, context: dict) -> ValidationResult:
        if some_condition:
            return ValidationResult.success(self.name)
        return ValidationResult.failure(self.name, "Why it failed")
```

### Creating a Pipeline
```python
PIPELINE_NAME = "my_pipeline"  # For fast discovery

def create_pipeline() -> Pipeline:
    return Pipeline(
        config=PipelineConfig(
            name=PIPELINE_NAME,
            description="What this pipeline does",
            log_directory=Path("./logs"),
        ),
        tasks=[Task1(), Task2(), Task3()],
    )
```

## Testing

```bash
# Full test suite with coverage
pytest --cov=harness --cov-report=term-missing

# Just validators (fastest)
pytest tests/test_validators/ -v

# Specific test file
pytest tests/test_runner.py -v
```

## CLI Commands

```bash
harness list                    # List pipelines
harness show <name>             # Show pipeline details
harness run <name>              # Execute pipeline
harness run <name> --dry-run    # Validate preconditions only
harness history                 # Show run history
harness secrets init            # Initialize secrets store
harness secrets set <name>      # Store a secret
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Pipeline failed |
| 2 | CLI error |
| 3 | Lock contention |

## Important Notes

- **Context is mutable:** Tasks modify a shared dict. Namespace keys to avoid collisions.
- **Timeouts use ThreadPoolExecutor:** Timed-out tasks continue running in background.
- **Validators must be stateless:** `check()` should have no side effects.
- **Lock files use psutil:** Stale locks from dead processes are automatically cleaned.
- **Secrets key:** Set `HARNESS_SECRETS_KEY` env var or use Windows keyring.
