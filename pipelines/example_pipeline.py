"""Example pipeline for Task Harness.

This demonstrates a simple data processing workflow with:
- Environment validation
- File operations
- Context passing between tasks
"""

from pathlib import Path

from harness.models import PipelineConfig, TaskConfig, TaskResult
from harness.pipeline import Pipeline
from harness.task import Task
from harness.validators import (
    DirectoryExists,
    FileExists,
    PythonPackageAvailable,
)


# Optional: Define pipeline name at module level for faster discovery
PIPELINE_NAME = "example"


class ValidateEnvironment(Task):
    """Validate that the environment is ready."""

    name = "validate_environment"
    description = "Check runtime environment and dependencies"
    preconditions = [
        PythonPackageAvailable("pandas"),
    ]

    def run(self, context: dict) -> TaskResult:
        return TaskResult.ok("Environment validated")


class SetupDirectories(Task):
    """Create working directories if needed."""

    name = "setup_directories"
    description = "Ensure output directories exist"

    def run(self, context: dict) -> TaskResult:
        # Get directories from context or use defaults
        data_dir = Path(context.get("data_dir", "./data"))
        output_dir = Path(context.get("output_dir", "./output"))

        data_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        return TaskResult.ok(
            f"Directories ready: {data_dir}, {output_dir}",
            data={
                "data_dir": str(data_dir),
                "output_dir": str(output_dir),
            },
        )


class ProcessData(Task):
    """Process input data (demonstration)."""

    name = "process_data"
    description = "Demonstrate data processing"
    config = TaskConfig(
        timeout_seconds=60.0,
        retries=1,
    )

    def run(self, context: dict) -> TaskResult:
        # This is a demonstration - in real use, you'd do actual processing
        output_dir = Path(context.get("output_dir", "./output"))

        # Create a sample output file
        output_file = output_dir / "result.txt"
        output_file.write_text(f"Processed at: {__import__('datetime').datetime.now()}\n")

        return TaskResult.ok(
            "Data processed successfully",
            data={
                "output_file": str(output_file),
                "records_processed": 42,
            },
        )


class GenerateReport(Task):
    """Generate a summary report."""

    name = "generate_report"
    description = "Create summary report"
    preconditions = [
        FileExists("output_file", from_context=True),
    ]

    def run(self, context: dict) -> TaskResult:
        records = context.get("records_processed", 0)

        return TaskResult.ok(
            f"Report generated: {records} records processed",
            data={"report_status": "complete"},
        )


def create_pipeline() -> Pipeline:
    """Create the example pipeline.

    Returns:
        Configured Pipeline instance.
    """
    return Pipeline(
        config=PipelineConfig(
            name=PIPELINE_NAME,
            description="Example data processing pipeline",
            log_directory=Path("./logs"),
            default_timeout_seconds=120.0,
        ),
        tasks=[
            ValidateEnvironment(),
            SetupDirectories(),
            ProcessData(),
            GenerateReport(),
        ],
    )


if __name__ == "__main__":
    # Allow running directly for testing
    from harness.runner import run_pipeline

    pipeline = create_pipeline()
    record = run_pipeline(pipeline)

    print(f"Pipeline {record.status}: {record.tasks_completed} tasks completed")
