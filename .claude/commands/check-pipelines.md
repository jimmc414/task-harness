# Check Pipelines

Validate all pipelines can be discovered and loaded without errors.

```bash
python -m harness.cli list
```

For each pipeline found, show its details:

```bash
python -m harness.cli show <pipeline_name>
```

Report any pipelines that fail to load or have configuration issues.
