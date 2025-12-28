# Debug Run

Analyze a failed pipeline run to understand what went wrong.

## Instructions

1. First, get recent history:
```bash
python -m harness.cli history --limit 10
```

2. Ask the user which run to analyze (or use the most recent failed run)

3. Parse the run record to identify:
   - Pipeline name
   - Run ID
   - Status
   - Error message
   - Tasks completed vs failed

4. Find the corresponding log file:
```bash
ls -la logs/<pipeline_name>/
```

5. Read the log file for the specific run

6. Analyze the failure:

### Common Failure Patterns

**Precondition Failed**
- Error contains "Precondition failed"
- Check which validator failed and why
- Verify the expected file/env/connection exists

**Task Timeout**
- Error contains "timed out"
- Task exceeded `config.timeout_seconds`
- Consider increasing timeout or optimizing task

**Postcondition Failed**
- Error contains validator name after task ran
- Task completed but output not as expected
- Check if task actually produced expected output

**Task Exception**
- Error contains exception traceback
- Read the task's `run()` method
- Identify the bug in task logic

**Lock Contention**
- Exit code 3 or "already running"
- Another pipeline instance is running
- Check for stale locks in `locks/` directory

### Resolution Steps

For each failure type, suggest:
1. What to verify manually
2. Potential fixes
3. How to re-run (with `--start-from` if applicable)

## Example Analysis

```
Run: abc123
Pipeline: daily_report
Status: failed
Error: Precondition failed: [FileExists] File not found: data/input.csv

Analysis:
- The FileExists validator on task "process_data" failed
- The file data/input.csv does not exist

Possible causes:
1. Previous task didn't create the file
2. Wrong path configured
3. File was deleted externally

To fix:
1. Verify data/input.csv should exist at this point
2. Check if path should be absolute or relative
3. Check previous task output

To re-run after fixing:
  harness run daily_report --start-from process_data
```
