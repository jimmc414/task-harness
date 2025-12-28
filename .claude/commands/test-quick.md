# Test Quick

Run tests excluding slow tests (network, timeouts).

```bash
pytest -v --ignore=tests/test_validators/test_network.py -x
```

Use `-x` to stop on first failure for faster iteration.
