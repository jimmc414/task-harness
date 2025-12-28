"""User-defined pipelines directory.

Place pipeline modules here. Each module should define a `create_pipeline()` function
that returns a Pipeline instance.

Example pipeline module (my_pipeline.py):

    from harness import Pipeline, PipelineConfig, Task, TaskResult

    class MyTask(Task):
        name = "my_task"
        description = "Does something useful"

        def run(self, context: dict) -> TaskResult:
            return TaskResult(success=True, message="Done")

    def create_pipeline() -> Pipeline:
        return Pipeline(
            config=PipelineConfig(name="my_pipeline"),
            tasks=[MyTask()],
        )
"""
