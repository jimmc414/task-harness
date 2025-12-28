# New Pipeline

Generate a new pipeline for Task Harness.

## Instructions

Ask the user for:
1. **Pipeline name** (snake_case, e.g., `daily_report`)
2. **Description** (one sentence)
3. **Tasks** (list of task names and what each does)

Then generate a complete pipeline file following this template:

```python
"""<Description> pipeline for Task Harness."""

from pathlib import Path

from harness.models import PipelineConfig, TaskConfig, TaskResult
from harness.pipeline import Pipeline
from harness.task import Task
from harness.validators import (
    # Import validators as needed
    FileExists,
    DirectoryExists,
)


PIPELINE_NAME = "<pipeline_name>"


class <TaskName>(Task):
    """<Task description>."""

    name = "<task_name>"
    description = "<What this task does>"
    # config = TaskConfig(timeout_seconds=60.0, retries=1)  # Optional
    # preconditions = [FileExists("path")]  # Optional
    # postconditions = [FileExists("path")]  # Optional

    def run(self, context: dict) -> TaskResult:
        # Implementation here
        return TaskResult.ok("Done", data={})


def create_pipeline() -> Pipeline:
    """Create the <pipeline_name> pipeline.

    Returns:
        Configured Pipeline instance.
    """
    return Pipeline(
        config=PipelineConfig(
            name=PIPELINE_NAME,
            description="<Description>",
            log_directory=Path("./logs"),
            default_timeout_seconds=120.0,
        ),
        tasks=[
            # Add tasks in execution order
        ],
    )


if __name__ == "__main__":
    from harness.runner import run_pipeline

    pipeline = create_pipeline()
    record = run_pipeline(pipeline)

    print(f"Pipeline {record.status}: {record.tasks_completed} tasks completed")
```

## After Generation

1. Save the file to `pipelines/<pipeline_name>.py`
2. Run `/check-pipelines` to verify it loads correctly
3. Run `/run-example` style dry-run to test preconditions
