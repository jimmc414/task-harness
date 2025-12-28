# Resume Prompt for Task Harness Implementation

Copy and paste this prompt to resume work after context compaction:

---

## Resume Prompt

I'm building **Task Harness**, a Python task orchestration framework. Planning is complete, ready for implementation.

**Read these files to understand the project:**

1. `checkpoint.md` - Current status and all decisions made
2. `task_harness_spec.md` - Original technical specification
3. `TEST_PLAN.md` - Test requirements (74 requirements, ~200 test cases)
4. `README.md` - User documentation
5. `/home/jim/.claude/plans/nifty-inventing-bubble.md` - Detailed implementation plan with code snippets

**Key context:**
- Target: Windows, Python 3.10+, Windows Task Scheduler
- CLI: argparse with colorama colors
- Secrets: Fernet encryption, env var + keyring for key
- Locking: File-based with psutil for stale detection
- Testing: Comprehensive (90%+ coverage target)

**Implementation order (20 steps in plan file):**
1. Project scaffolding (pyproject.toml, __init__.py, exceptions.py)
2. Core models (ValidationResult, TaskConfig, TaskResult, PipelineConfig, RunRecord)
3. Validator base class
4. Task & Pipeline abstractions
5. Environment validators (with tests)
6. Filesystem validators (with tests)
7. Tabular validators (with tests)
8. Network validators (with tests)
9. Composite validators (with tests)
10. Process validators (with tests)
11. Configuration module
12. Locking infrastructure (with tests)
13. History infrastructure (with tests)
14. Logging setup
15. Secrets store (with tests)
16. Pipeline runner (with tests)
17. CLI implementation (with tests)
18. Example pipeline
19. Documentation polish
20. Final validation

**Begin implementation starting from Step 1.**

---

## Alternative: Specific Phase Resume

If resuming mid-implementation, use this format:

```
I'm implementing Task Harness. Read checkpoint.md and the implementation plan at /home/jim/.claude/plans/nifty-inventing-bubble.md

Current status: Completed through Step [X]. Continue from Step [X+1]: [Step Name]

[Any specific notes about current state]
```

---

## Quick Reference

**Repository:** https://github.com/jimmc414/task-harness

**Directory structure to create:**
```
task_harness/
├── harness/
│   ├── __init__.py
│   ├── cli.py
│   ├── runner.py
│   ├── models.py
│   ├── task.py
│   ├── pipeline.py
│   ├── notification.py
│   ├── secrets.py
│   ├── locking.py
│   ├── history.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── exceptions.py
│   └── validators/
│       ├── __init__.py
│       ├── base.py
│       ├── environment.py
│       ├── filesystem.py
│       ├── tabular.py
│       ├── network.py
│       ├── process.py
│       └── composite.py
├── pipelines/
│   ├── __init__.py
│   └── example_pipeline.py
├── tests/
│   ├── conftest.py
│   └── test_validators/
│       └── ...
├── pyproject.toml
├── README.md
├── TEST_PLAN.md
├── checkpoint.md
└── task_harness_spec.md
```

**Exit codes:** 0=success, 1=pipeline failure, 2=CLI error, 3=lock contention
