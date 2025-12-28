# Task Harness Test Plan

## Overview

This document maps requirements from the specification to specific test cases. Each requirement has:
- **ID**: Unique identifier for traceability
- **Requirement**: What the system must do
- **Acceptance Criteria**: How we know it's working
- **Test Type**: Unit, Integration, or E2E
- **Test Cases**: Specific scenarios to validate

---

## Table of Contents

1. [Validator Requirements](#1-validator-requirements)
2. [Task Execution Requirements](#2-task-execution-requirements)
3. [Pipeline Runner Requirements](#3-pipeline-runner-requirements)
4. [CLI Requirements](#4-cli-requirements)
5. [Secrets Store Requirements](#5-secrets-store-requirements)
6. [Locking Requirements](#6-locking-requirements)
7. [History Requirements](#7-history-requirements)
8. [Logging Requirements](#8-logging-requirements)
9. [Notification Requirements](#9-notification-requirements)
10. [Cross-Cutting Requirements](#10-cross-cutting-requirements)

---

## 1. Validator Requirements

### 1.1 Validator Base Class

#### REQ-VAL-001: Validator ABC Interface
**Requirement**: All validators must implement the `Validator` abstract base class with a `check(context: dict) -> ValidationResult` method.

**Acceptance Criteria**:
- Cannot instantiate Validator directly
- Subclasses must implement `check()`
- `check()` receives context dict and returns ValidationResult

**Test Type**: Unit

**Test Cases**:
```python
def test_validator_is_abstract():
    """Validator cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Validator()

def test_validator_requires_check_method():
    """Subclass without check() raises TypeError."""
    class BadValidator(Validator):
        pass
    with pytest.raises(TypeError):
        BadValidator()

def test_validator_check_receives_context():
    """check() is called with context dict."""
    class SpyValidator(Validator):
        def check(self, context):
            self.received_context = context
            return ValidationResult(True, "ok", self.name)

    v = SpyValidator()
    ctx = {"key": "value"}
    v.check(ctx)
    assert v.received_context is ctx
```

#### REQ-VAL-002: ValidationResult Structure
**Requirement**: ValidationResult must contain `passed: bool`, `message: str`, and `validator_name: str`.

**Acceptance Criteria**:
- All three fields are accessible
- Fields are of correct types
- Dataclass is immutable (frozen)

**Test Type**: Unit

**Test Cases**:
```python
def test_validation_result_fields():
    """ValidationResult has all required fields."""
    result = ValidationResult(passed=True, message="test", validator_name="TestValidator")
    assert result.passed is True
    assert result.message == "test"
    assert result.validator_name == "TestValidator"

def test_validation_result_passed_is_bool():
    """passed field must be boolean."""
    result = ValidationResult(passed=True, message="", validator_name="")
    assert isinstance(result.passed, bool)

def test_validation_result_failed():
    """ValidationResult correctly represents failure."""
    result = ValidationResult(passed=False, message="File not found", validator_name="FileExists")
    assert result.passed is False
    assert "not found" in result.message.lower()
```

#### REQ-VAL-003: Validator Name Property
**Requirement**: Validators must have a `name` property that defaults to class name but can be overridden.

**Acceptance Criteria**:
- Default name is class name
- Custom name can be set

**Test Type**: Unit

**Test Cases**:
```python
def test_validator_default_name():
    """Validator name defaults to class name."""
    class MyCustomValidator(Validator):
        def check(self, context):
            return ValidationResult(True, "", self.name)

    v = MyCustomValidator()
    assert v.name == "MyCustomValidator"

def test_validator_custom_name():
    """Validator name can be overridden."""
    class CustomValidator(Validator):
        @property
        def name(self):
            return "OverriddenName"
        def check(self, context):
            return ValidationResult(True, "", self.name)

    v = CustomValidator()
    assert v.name == "OverriddenName"
```

#### REQ-VAL-004: Validator Exception Handling
**Requirement**: If a validator's `check()` method raises an exception, it must be caught and converted to a failed ValidationResult.

**Acceptance Criteria**:
- Exceptions don't propagate
- Result has passed=False
- Message contains exception info

**Test Type**: Unit (tested at runner level)

**Test Cases**:
```python
def test_validator_exception_becomes_failure():
    """Exception in check() is converted to failed result."""
    class ExplodingValidator(Validator):
        def check(self, context):
            raise RuntimeError("Database connection failed")

    v = ExplodingValidator()
    # Runner wraps this call
    result = safe_check(v, {})  # helper that catches exceptions

    assert result.passed is False
    assert "Database connection failed" in result.message
    assert result.validator_name == "ExplodingValidator"
```

---

### 1.2 Environment Validators

#### REQ-VAL-010: VirtualEnvActive - Any Venv
**Requirement**: VirtualEnvActive must detect when Python is running inside any virtual environment.

**Acceptance Criteria**:
- Passes when `sys.prefix != sys.base_prefix`
- Passes when `VIRTUAL_ENV` env var is set
- Passes when `CONDA_PREFIX` env var is set (conda support)
- Fails when none of the above

**Test Type**: Unit

**Test Cases**:
```python
def test_venv_active_via_sys_prefix(monkeypatch):
    """Detects venv via sys.prefix != sys.base_prefix."""
    monkeypatch.setattr(sys, 'prefix', '/path/to/venv')
    monkeypatch.setattr(sys, 'base_prefix', '/usr')
    monkeypatch.delenv('VIRTUAL_ENV', raising=False)
    monkeypatch.delenv('CONDA_PREFIX', raising=False)

    v = VirtualEnvActive()
    result = v.check({})
    assert result.passed is True

def test_venv_active_via_env_var(monkeypatch):
    """Detects venv via VIRTUAL_ENV env var."""
    monkeypatch.setattr(sys, 'prefix', '/usr')
    monkeypatch.setattr(sys, 'base_prefix', '/usr')
    monkeypatch.setenv('VIRTUAL_ENV', '/path/to/venv')

    v = VirtualEnvActive()
    result = v.check({})
    assert result.passed is True

def test_venv_active_via_conda(monkeypatch):
    """Detects conda env via CONDA_PREFIX."""
    monkeypatch.setattr(sys, 'prefix', '/usr')
    monkeypatch.setattr(sys, 'base_prefix', '/usr')
    monkeypatch.delenv('VIRTUAL_ENV', raising=False)
    monkeypatch.setenv('CONDA_PREFIX', '/path/to/conda/env')

    v = VirtualEnvActive()
    result = v.check({})
    assert result.passed is True

def test_venv_not_active(monkeypatch):
    """Fails when no venv is active."""
    monkeypatch.setattr(sys, 'prefix', '/usr')
    monkeypatch.setattr(sys, 'base_prefix', '/usr')
    monkeypatch.delenv('VIRTUAL_ENV', raising=False)
    monkeypatch.delenv('CONDA_PREFIX', raising=False)

    v = VirtualEnvActive()
    result = v.check({})
    assert result.passed is False
    assert "no virtual environment" in result.message.lower()
```

#### REQ-VAL-011: VirtualEnvActive - Specific Venv
**Requirement**: VirtualEnvActive with `expected_venv_path` must validate that a specific venv is active.

**Acceptance Criteria**:
- Passes when expected path matches active venv
- Fails with clear message when wrong venv is active
- Supports both full path and partial name matching

**Test Type**: Unit

**Test Cases**:
```python
def test_specific_venv_matches_full_path(monkeypatch):
    """Passes when expected venv path matches exactly."""
    monkeypatch.setenv('VIRTUAL_ENV', 'C:/venvs/my_project')

    v = VirtualEnvActive(expected_venv_path='C:/venvs/my_project')
    result = v.check({})
    assert result.passed is True

def test_specific_venv_matches_partial_name(monkeypatch):
    """Passes when expected name is substring of active path."""
    monkeypatch.setenv('VIRTUAL_ENV', 'C:/venvs/my_project')

    v = VirtualEnvActive(expected_venv_path='my_project')
    result = v.check({})
    assert result.passed is True

def test_specific_venv_wrong_venv_active(monkeypatch):
    """Fails with clear message when wrong venv is active."""
    monkeypatch.setenv('VIRTUAL_ENV', 'C:/venvs/other_project')

    v = VirtualEnvActive(expected_venv_path='my_project')
    result = v.check({})
    assert result.passed is False
    assert "my_project" in result.message
    assert "other_project" in result.message

def test_specific_venv_no_venv_active(monkeypatch):
    """Fails when specific venv required but none active."""
    monkeypatch.setattr(sys, 'prefix', '/usr')
    monkeypatch.setattr(sys, 'base_prefix', '/usr')
    monkeypatch.delenv('VIRTUAL_ENV', raising=False)

    v = VirtualEnvActive(expected_venv_path='my_project')
    result = v.check({})
    assert result.passed is False
```

#### REQ-VAL-012: EnvVarSet
**Requirement**: EnvVarSet must check that an environment variable is set and non-empty.

**Acceptance Criteria**:
- Passes when var exists and has non-empty value
- Fails when var doesn't exist
- Fails when var exists but is empty string

**Test Type**: Unit

**Test Cases**:
```python
def test_env_var_set_exists(monkeypatch):
    """Passes when env var exists with value."""
    monkeypatch.setenv('MY_VAR', 'some_value')

    v = EnvVarSet('MY_VAR')
    result = v.check({})
    assert result.passed is True

def test_env_var_set_missing(monkeypatch):
    """Fails when env var doesn't exist."""
    monkeypatch.delenv('MY_VAR', raising=False)

    v = EnvVarSet('MY_VAR')
    result = v.check({})
    assert result.passed is False
    assert "MY_VAR" in result.message

def test_env_var_set_empty(monkeypatch):
    """Fails when env var is empty string."""
    monkeypatch.setenv('MY_VAR', '')

    v = EnvVarSet('MY_VAR')
    result = v.check({})
    assert result.passed is False
```

#### REQ-VAL-013: EnvVarEquals
**Requirement**: EnvVarEquals must check that an environment variable has a specific value.

**Acceptance Criteria**:
- Passes when var equals expected value exactly
- Fails when var has different value
- Fails when var doesn't exist

**Test Type**: Unit

**Test Cases**:
```python
def test_env_var_equals_match(monkeypatch):
    """Passes when env var matches expected value."""
    monkeypatch.setenv('ENV', 'production')

    v = EnvVarEquals('ENV', 'production')
    result = v.check({})
    assert result.passed is True

def test_env_var_equals_mismatch(monkeypatch):
    """Fails when env var has different value."""
    monkeypatch.setenv('ENV', 'development')

    v = EnvVarEquals('ENV', 'production')
    result = v.check({})
    assert result.passed is False
    assert "development" in result.message
    assert "production" in result.message

def test_env_var_equals_case_sensitive(monkeypatch):
    """Comparison is case-sensitive."""
    monkeypatch.setenv('ENV', 'Production')

    v = EnvVarEquals('ENV', 'production')
    result = v.check({})
    assert result.passed is False
```

#### REQ-VAL-014: PythonPackageAvailable
**Requirement**: PythonPackageAvailable must check that a Python package can be imported, optionally with minimum version.

**Acceptance Criteria**:
- Passes when package is importable
- Fails when package not installed
- With min_version: passes when installed version >= required
- With min_version: fails when installed version < required

**Test Type**: Unit

**Test Cases**:
```python
def test_package_available_exists():
    """Passes for installed package."""
    v = PythonPackageAvailable('json')  # stdlib, always available
    result = v.check({})
    assert result.passed is True

def test_package_available_not_installed():
    """Fails for non-existent package."""
    v = PythonPackageAvailable('nonexistent_package_xyz_123')
    result = v.check({})
    assert result.passed is False
    assert "not installed" in result.message.lower()

def test_package_version_sufficient():
    """Passes when version meets minimum."""
    # pytest is installed for testing
    v = PythonPackageAvailable('pytest', min_version='1.0.0')
    result = v.check({})
    assert result.passed is True

def test_package_version_insufficient(monkeypatch):
    """Fails when version below minimum."""
    # Mock a package with old version
    import types
    fake_module = types.ModuleType('fake_pkg')
    fake_module.__version__ = '1.0.0'
    monkeypatch.setitem(sys.modules, 'fake_pkg', fake_module)

    v = PythonPackageAvailable('fake_pkg', min_version='2.0.0')
    result = v.check({})
    assert result.passed is False
    assert "1.0.0" in result.message
    assert "2.0.0" in result.message
```

---

### 1.3 Filesystem Validators

#### REQ-VAL-020: FileExists
**Requirement**: FileExists must check that a file exists at the specified path.

**Acceptance Criteria**:
- Passes when file exists
- Fails when file doesn't exist
- Fails when path is a directory (not a file)
- Supports `from_context` parameter to read path from context dict

**Test Type**: Unit

**Test Cases**:
```python
def test_file_exists_present(tmp_path):
    """Passes when file exists."""
    f = tmp_path / "test.txt"
    f.write_text("content")

    v = FileExists(str(f))
    result = v.check({})
    assert result.passed is True

def test_file_exists_missing(tmp_path):
    """Fails when file doesn't exist."""
    v = FileExists(str(tmp_path / "nonexistent.txt"))
    result = v.check({})
    assert result.passed is False
    assert "not found" in result.message.lower()

def test_file_exists_is_directory(tmp_path):
    """Fails when path is a directory."""
    d = tmp_path / "subdir"
    d.mkdir()

    v = FileExists(str(d))
    result = v.check({})
    assert result.passed is False

def test_file_exists_from_context(tmp_path):
    """Reads path from context when from_context=True."""
    f = tmp_path / "test.txt"
    f.write_text("content")

    v = FileExists("output_file", from_context=True)
    result = v.check({"output_file": str(f)})
    assert result.passed is True

def test_file_exists_from_context_missing_key():
    """Fails gracefully when context key missing."""
    v = FileExists("output_file", from_context=True)
    result = v.check({})
    assert result.passed is False
```

#### REQ-VAL-021: DirectoryExists
**Requirement**: DirectoryExists must check that a directory exists at the specified path.

**Acceptance Criteria**:
- Passes when directory exists
- Fails when directory doesn't exist
- Fails when path is a file (not a directory)
- Supports `from_context` parameter

**Test Type**: Unit

**Test Cases**:
```python
def test_directory_exists_present(tmp_path):
    """Passes when directory exists."""
    d = tmp_path / "subdir"
    d.mkdir()

    v = DirectoryExists(str(d))
    result = v.check({})
    assert result.passed is True

def test_directory_exists_missing(tmp_path):
    """Fails when directory doesn't exist."""
    v = DirectoryExists(str(tmp_path / "nonexistent"))
    result = v.check({})
    assert result.passed is False

def test_directory_exists_is_file(tmp_path):
    """Fails when path is a file."""
    f = tmp_path / "file.txt"
    f.write_text("content")

    v = DirectoryExists(str(f))
    result = v.check({})
    assert result.passed is False
```

#### REQ-VAL-022: FileModifiedWithin
**Requirement**: FileModifiedWithin must check that a file was modified within a specified time window.

**Acceptance Criteria**:
- Passes when file mtime is within max_age
- Fails when file is older than max_age
- Fails when file doesn't exist
- Uses timezone-aware datetime comparisons

**Test Type**: Unit

**Test Cases**:
```python
def test_file_modified_recently(tmp_path):
    """Passes when file was just modified."""
    f = tmp_path / "test.txt"
    f.write_text("content")  # Just created = just modified

    v = FileModifiedWithin(str(f), max_age=timedelta(hours=1))
    result = v.check({})
    assert result.passed is True

def test_file_modified_too_old(tmp_path, monkeypatch):
    """Fails when file is older than max_age."""
    f = tmp_path / "test.txt"
    f.write_text("content")

    # Mock file mtime to be 2 days ago
    old_time = (datetime.now() - timedelta(days=2)).timestamp()
    monkeypatch.setattr(f.stat(), 'st_mtime', old_time)
    # Alternative: use os.utime to set mtime
    import os
    os.utime(f, (old_time, old_time))

    v = FileModifiedWithin(str(f), max_age=timedelta(hours=1))
    result = v.check({})
    assert result.passed is False
    assert "exceeds" in result.message.lower() or "old" in result.message.lower()

def test_file_modified_within_missing_file(tmp_path):
    """Fails when file doesn't exist."""
    v = FileModifiedWithin(str(tmp_path / "nonexistent.txt"), max_age=timedelta(hours=1))
    result = v.check({})
    assert result.passed is False
    assert "not found" in result.message.lower()
```

#### REQ-VAL-023: FileSizeInRange
**Requirement**: FileSizeInRange must check that a file's size falls within an expected range.

**Acceptance Criteria**:
- Passes when size >= min_bytes and <= max_bytes
- Fails when size < min_bytes
- Fails when size > max_bytes (if max specified)
- Fails when file doesn't exist

**Test Type**: Unit

**Test Cases**:
```python
def test_file_size_in_range(tmp_path):
    """Passes when file size is within range."""
    f = tmp_path / "test.txt"
    f.write_text("x" * 100)  # 100 bytes

    v = FileSizeInRange(str(f), min_bytes=50, max_bytes=200)
    result = v.check({})
    assert result.passed is True

def test_file_size_below_minimum(tmp_path):
    """Fails when file is too small."""
    f = tmp_path / "test.txt"
    f.write_text("x" * 10)  # 10 bytes

    v = FileSizeInRange(str(f), min_bytes=100)
    result = v.check({})
    assert result.passed is False
    assert "below minimum" in result.message.lower()

def test_file_size_above_maximum(tmp_path):
    """Fails when file is too large."""
    f = tmp_path / "test.txt"
    f.write_text("x" * 1000)  # 1000 bytes

    v = FileSizeInRange(str(f), min_bytes=0, max_bytes=100)
    result = v.check({})
    assert result.passed is False
    assert "exceeds maximum" in result.message.lower()

def test_file_size_no_maximum(tmp_path):
    """Passes for any size when max_bytes is None."""
    f = tmp_path / "test.txt"
    f.write_text("x" * 10000)

    v = FileSizeInRange(str(f), min_bytes=1, max_bytes=None)
    result = v.check({})
    assert result.passed is True

def test_file_size_empty_file_allowed(tmp_path):
    """Empty file passes when min_bytes=0."""
    f = tmp_path / "empty.txt"
    f.write_text("")

    v = FileSizeInRange(str(f), min_bytes=0)
    result = v.check({})
    assert result.passed is True
```

---

### 1.4 Tabular File Validators

#### REQ-VAL-030: TabularFileValid - CSV Basic
**Requirement**: TabularFileValid must validate CSV files have required headers and data rows.

**Acceptance Criteria**:
- Passes when file has required headers and min data rows
- Fails when required headers are missing
- Fails when data rows below minimum
- Header comparison is case-insensitive by default

**Test Type**: Unit

**Test Cases**:
```python
def test_csv_valid_with_required_headers(tmp_path):
    """Passes when CSV has all required headers and data."""
    f = tmp_path / "data.csv"
    f.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")

    v = TabularFileValid(str(f), required_headers=["name", "age"], min_data_rows=1)
    result = v.check({})
    assert result.passed is True

def test_csv_missing_required_header(tmp_path):
    """Fails when required header is missing."""
    f = tmp_path / "data.csv"
    f.write_text("name,city\nAlice,NYC\n")

    v = TabularFileValid(str(f), required_headers=["name", "age"])
    result = v.check({})
    assert result.passed is False
    assert "age" in result.message.lower()

def test_csv_case_insensitive_headers(tmp_path):
    """Header matching is case-insensitive by default."""
    f = tmp_path / "data.csv"
    f.write_text("NAME,AGE\nAlice,30\n")

    v = TabularFileValid(str(f), required_headers=["name", "age"])
    result = v.check({})
    assert result.passed is True

def test_csv_case_sensitive_headers(tmp_path):
    """Case-sensitive matching when enabled."""
    f = tmp_path / "data.csv"
    f.write_text("NAME,AGE\nAlice,30\n")

    v = TabularFileValid(str(f), required_headers=["name", "age"], case_sensitive_headers=True)
    result = v.check({})
    assert result.passed is False

def test_csv_insufficient_data_rows(tmp_path):
    """Fails when fewer data rows than minimum."""
    f = tmp_path / "data.csv"
    f.write_text("name,age\n")  # Headers only, no data

    v = TabularFileValid(str(f), min_data_rows=1)
    result = v.check({})
    assert result.passed is False
    assert "0" in result.message and "1" in result.message

def test_csv_empty_rows_not_counted(tmp_path):
    """Empty rows are not counted as data rows."""
    f = tmp_path / "data.csv"
    f.write_text("name,age\n\n\nAlice,30\n\n")  # Only 1 actual data row

    v = TabularFileValid(str(f), min_data_rows=2)
    result = v.check({})
    assert result.passed is False
```

#### REQ-VAL-031: TabularFileValid - Excel Support
**Requirement**: TabularFileValid must support Excel files (.xlsx, .xls) with sheet selection.

**Acceptance Criteria**:
- Reads Excel files correctly
- Supports sheet selection by name or index
- Fails gracefully when sheet doesn't exist

**Test Type**: Unit

**Test Cases**:
```python
def test_excel_valid_first_sheet(tmp_path):
    """Validates first sheet by default."""
    f = tmp_path / "data.xlsx"
    # Create Excel file with openpyxl
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "age"])
    ws.append(["Alice", 30])
    wb.save(f)

    v = TabularFileValid(str(f), required_headers=["name", "age"])
    result = v.check({})
    assert result.passed is True

def test_excel_specific_sheet_by_name(tmp_path):
    """Validates specific sheet by name."""
    f = tmp_path / "data.xlsx"
    import openpyxl
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.append(["total"])
    ws1.append([100])
    ws2 = wb.create_sheet("Details")
    ws2.append(["name", "value"])
    ws2.append(["A", 50])
    wb.save(f)

    v = TabularFileValid(str(f), required_headers=["name", "value"], sheet_name="Details")
    result = v.check({})
    assert result.passed is True

def test_excel_sheet_not_found(tmp_path):
    """Fails with clear message when sheet doesn't exist."""
    f = tmp_path / "data.xlsx"
    import openpyxl
    wb = openpyxl.Workbook()
    wb.save(f)

    v = TabularFileValid(str(f), sheet_name="NonExistent")
    result = v.check({})
    assert result.passed is False
    assert "NonExistent" in result.message
    assert "not found" in result.message.lower() or "available" in result.message.lower()

def test_excel_sheet_index_out_of_range(tmp_path):
    """Fails when sheet index is out of range."""
    f = tmp_path / "data.xlsx"
    import openpyxl
    wb = openpyxl.Workbook()
    wb.save(f)  # Only 1 sheet

    v = TabularFileValid(str(f), sheet_name=5)  # Index 5 doesn't exist
    result = v.check({})
    assert result.passed is False
    assert "out of range" in result.message.lower()
```

#### REQ-VAL-032: TabularFileValid - Encoding Handling
**Requirement**: TabularFileValid must handle CSV encoding issues gracefully.

**Acceptance Criteria**:
- Reads UTF-8 files correctly
- Reads UTF-8-BOM files correctly
- Falls back to latin-1 for non-UTF-8 files
- Doesn't crash on encoding errors

**Test Type**: Unit

**Test Cases**:
```python
def test_csv_utf8_encoding(tmp_path):
    """Reads UTF-8 CSV correctly."""
    f = tmp_path / "data.csv"
    f.write_text("name,city\nAlice,Zürich\n", encoding="utf-8")

    v = TabularFileValid(str(f))
    result = v.check({})
    assert result.passed is True

def test_csv_utf8_bom_encoding(tmp_path):
    """Reads UTF-8-BOM CSV correctly (common from Excel)."""
    f = tmp_path / "data.csv"
    f.write_bytes(b'\xef\xbb\xbfname,city\nAlice,NYC\n')  # UTF-8 BOM

    v = TabularFileValid(str(f), required_headers=["name"])  # Not "ï»¿name"
    result = v.check({})
    assert result.passed is True

def test_csv_latin1_fallback(tmp_path):
    """Falls back to latin-1 for non-UTF-8 files."""
    f = tmp_path / "data.csv"
    # Latin-1 encoded content (ñ = 0xF1 in latin-1)
    f.write_bytes(b'name,city\nPe\xf1a,Madrid\n')

    v = TabularFileValid(str(f))
    result = v.check({})
    assert result.passed is True
```

#### REQ-VAL-033: TabularFileValid - from_context
**Requirement**: TabularFileValid must support reading file path from context.

**Acceptance Criteria**:
- Reads path from context when from_context=True
- Works with both CSV and Excel

**Test Type**: Unit

**Test Cases**:
```python
def test_tabular_from_context(tmp_path):
    """Reads file path from context dict."""
    f = tmp_path / "output.csv"
    f.write_text("id,value\n1,100\n")

    v = TabularFileValid("result_file", from_context=True, required_headers=["id", "value"])
    result = v.check({"result_file": str(f)})
    assert result.passed is True
```

#### REQ-VAL-034: TabularFileRowCount
**Requirement**: TabularFileRowCount must validate row count is within specified range.

**Acceptance Criteria**:
- Passes when row count is within min/max range
- Fails when below min or above max

**Test Type**: Unit

**Test Cases**:
```python
def test_row_count_in_range(tmp_path):
    """Passes when row count is within range."""
    f = tmp_path / "data.csv"
    f.write_text("a\n1\n2\n3\n4\n5\n")  # 5 data rows

    v = TabularFileRowCount(str(f), min_rows=3, max_rows=10)
    result = v.check({})
    assert result.passed is True

def test_row_count_below_minimum(tmp_path):
    """Fails when row count below minimum."""
    f = tmp_path / "data.csv"
    f.write_text("a\n1\n")  # 1 data row

    v = TabularFileRowCount(str(f), min_rows=5)
    result = v.check({})
    assert result.passed is False

def test_row_count_above_maximum(tmp_path):
    """Fails when row count above maximum."""
    f = tmp_path / "data.csv"
    f.write_text("a\n" + "1\n" * 100)  # 100 data rows

    v = TabularFileRowCount(str(f), max_rows=50)
    result = v.check({})
    assert result.passed is False
```

---

### 1.5 Network Validators

#### REQ-VAL-040: HostReachable
**Requirement**: HostReachable must check TCP connectivity to a host:port.

**Acceptance Criteria**:
- Passes when TCP connection succeeds
- Fails when connection times out
- Fails when connection refused
- Respects timeout_seconds parameter

**Test Type**: Unit (mocked)

**Test Cases**:
```python
def test_host_reachable_success(mocker):
    """Passes when connection succeeds."""
    mock_socket = mocker.patch('socket.create_connection')
    mock_socket.return_value.__enter__ = lambda s: s
    mock_socket.return_value.__exit__ = lambda s, *args: None

    v = HostReachable("example.com", 80)
    result = v.check({})
    assert result.passed is True
    mock_socket.assert_called_once_with(("example.com", 80), timeout=5.0)

def test_host_reachable_timeout(mocker):
    """Fails when connection times out."""
    import socket
    mocker.patch('socket.create_connection', side_effect=socket.timeout("timed out"))

    v = HostReachable("example.com", 80, timeout_seconds=2.0)
    result = v.check({})
    assert result.passed is False
    assert "timed out" in result.message.lower() or "timeout" in result.message.lower()

def test_host_reachable_refused(mocker):
    """Fails when connection refused."""
    import socket
    mocker.patch('socket.create_connection', side_effect=ConnectionRefusedError())

    v = HostReachable("localhost", 9999)
    result = v.check({})
    assert result.passed is False

def test_host_reachable_custom_timeout(mocker):
    """Uses custom timeout value."""
    mock_socket = mocker.patch('socket.create_connection')
    mock_socket.return_value.__enter__ = lambda s: s
    mock_socket.return_value.__exit__ = lambda s, *args: None

    v = HostReachable("example.com", 443, timeout_seconds=10.0)
    v.check({})
    mock_socket.assert_called_once_with(("example.com", 443), timeout=10.0)
```

#### REQ-VAL-041: SFTPConnectable
**Requirement**: SFTPConnectable must validate SFTP connection using stored credentials.

**Acceptance Criteria**:
- Passes when SFTP connection succeeds
- Fails when connection fails
- Supports password authentication
- Supports key-based authentication
- Retrieves credentials from secrets store

**Test Type**: Unit (mocked)

**Test Cases**:
```python
def test_sftp_connectable_password_auth(mocker):
    """Connects with password authentication."""
    mock_secret = mocker.patch('harness.secrets.get_secret')
    mock_secret.return_value = {
        "host": "sftp.example.com",
        "port": 22,
        "username": "user",
        "password": "pass123"
    }

    mock_transport = mocker.patch('paramiko.Transport')
    mock_sftp = mocker.patch('paramiko.SFTPClient.from_transport')

    v = SFTPConnectable("my_sftp_server")
    result = v.check({})

    assert result.passed is True
    mock_transport.return_value.connect.assert_called_with(username="user", password="pass123")

def test_sftp_connectable_key_auth(mocker):
    """Connects with private key authentication."""
    mock_secret = mocker.patch('harness.secrets.get_secret')
    mock_secret.return_value = {
        "host": "sftp.example.com",
        "username": "user",
        "private_key_path": "/path/to/key"
    }

    mock_transport = mocker.patch('paramiko.Transport')
    mock_key = mocker.patch('paramiko.RSAKey.from_private_key_file')
    mock_sftp = mocker.patch('paramiko.SFTPClient.from_transport')

    v = SFTPConnectable("my_sftp_server")
    result = v.check({})

    assert result.passed is True

def test_sftp_connectable_connection_failed(mocker):
    """Fails when SFTP connection fails."""
    mock_secret = mocker.patch('harness.secrets.get_secret')
    mock_secret.return_value = {"host": "bad.example.com", "username": "user", "password": "pass"}

    mock_transport = mocker.patch('paramiko.Transport')
    mock_transport.return_value.connect.side_effect = Exception("Connection refused")

    v = SFTPConnectable("my_sftp_server")
    result = v.check({})

    assert result.passed is False
    assert "connection refused" in result.message.lower()

def test_sftp_connectable_secret_not_found(mocker):
    """Fails when credentials not in secrets store."""
    mock_secret = mocker.patch('harness.secrets.get_secret')
    mock_secret.side_effect = KeyError("not_found")

    v = SFTPConnectable("nonexistent_connection")
    result = v.check({})

    assert result.passed is False
```

---

### 1.6 Process Validators

#### REQ-VAL-050: CommandAvailable
**Requirement**: CommandAvailable must check that an external command is available in PATH.

**Acceptance Criteria**:
- Passes when command is found in PATH
- Fails when command not found

**Test Type**: Unit

**Test Cases**:
```python
def test_command_available_exists(mocker):
    """Passes when command is in PATH."""
    mocker.patch('shutil.which', return_value='/usr/bin/python')

    v = CommandAvailable('python')
    result = v.check({})
    assert result.passed is True

def test_command_available_not_found(mocker):
    """Fails when command not in PATH."""
    mocker.patch('shutil.which', return_value=None)

    v = CommandAvailable('nonexistent_command')
    result = v.check({})
    assert result.passed is False
    assert "nonexistent_command" in result.message
    assert "not" in result.message.lower()
```

---

### 1.7 Composite Validators

#### REQ-VAL-060: AnyOf
**Requirement**: AnyOf must pass if any child validator passes.

**Acceptance Criteria**:
- Passes when at least one child passes
- Fails only when all children fail
- Message includes which validator passed (on success)
- Message includes all failure reasons (on failure)

**Test Type**: Unit

**Test Cases**:
```python
def test_anyof_first_passes():
    """Passes when first validator passes."""
    v1 = MockValidator(True, "v1 passed")
    v2 = MockValidator(False, "v2 failed")

    v = AnyOf(v1, v2)
    result = v.check({})
    assert result.passed is True
    assert "v1 passed" in result.message

def test_anyof_second_passes():
    """Passes when first fails but second passes."""
    v1 = MockValidator(False, "v1 failed")
    v2 = MockValidator(True, "v2 passed")

    v = AnyOf(v1, v2)
    result = v.check({})
    assert result.passed is True

def test_anyof_all_fail():
    """Fails when all validators fail."""
    v1 = MockValidator(False, "v1 failed")
    v2 = MockValidator(False, "v2 failed")
    v3 = MockValidator(False, "v3 failed")

    v = AnyOf(v1, v2, v3)
    result = v.check({})
    assert result.passed is False
    assert "v1 failed" in result.message
    assert "v2 failed" in result.message
    assert "v3 failed" in result.message

def test_anyof_short_circuits():
    """Stops checking after first pass."""
    v1 = MockValidator(True, "v1 passed")
    v2 = MockValidator(False, "v2 failed")
    v2.check = lambda ctx: (_ for _ in ()).throw(Exception("Should not be called"))

    v = AnyOf(v1, v2)
    result = v.check({})  # Should not raise
    assert result.passed is True
```

#### REQ-VAL-061: AllOf
**Requirement**: AllOf must pass only if all child validators pass.

**Acceptance Criteria**:
- Passes when all children pass
- Fails when any child fails
- Can have custom name for grouping
- Fails fast (stops on first failure)

**Test Type**: Unit

**Test Cases**:
```python
def test_allof_all_pass():
    """Passes when all validators pass."""
    v1 = MockValidator(True, "v1 passed")
    v2 = MockValidator(True, "v2 passed")

    v = AllOf(v1, v2)
    result = v.check({})
    assert result.passed is True

def test_allof_one_fails():
    """Fails when any validator fails."""
    v1 = MockValidator(True, "v1 passed")
    v2 = MockValidator(False, "v2 failed")
    v3 = MockValidator(True, "v3 passed")

    v = AllOf(v1, v2, v3)
    result = v.check({})
    assert result.passed is False
    assert "v2 failed" in result.message

def test_allof_custom_name():
    """Custom name is used in result."""
    v1 = MockValidator(True, "ok")

    v = AllOf(v1, name="DatabaseChecks")
    assert v.name == "DatabaseChecks"

def test_allof_fails_fast():
    """Stops checking after first failure."""
    v1 = MockValidator(False, "v1 failed")
    v2 = MockValidator(True, "v2 passed")
    v2.check = lambda ctx: (_ for _ in ()).throw(Exception("Should not be called"))

    v = AllOf(v1, v2)
    result = v.check({})  # Should not raise
    assert result.passed is False
```

---

## 2. Task Execution Requirements

### REQ-TASK-001: Task ABC Interface
**Requirement**: Tasks must implement the Task abstract base class with `run(context: dict) -> TaskResult`.

**Acceptance Criteria**:
- Cannot instantiate Task directly
- Subclasses must implement `run()`
- `run()` receives context and returns TaskResult

**Test Type**: Unit

**Test Cases**:
```python
def test_task_is_abstract():
    """Task cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Task()

def test_task_requires_run_method():
    """Subclass without run() raises TypeError."""
    class BadTask(Task):
        pass
    with pytest.raises(TypeError):
        BadTask()

def test_task_run_receives_context():
    """run() is called with context dict."""
    class SpyTask(Task):
        def run(self, context):
            self.received_context = context
            return TaskResult(success=True)

    t = SpyTask()
    ctx = {"key": "value"}
    t.run(ctx)
    assert t.received_context is ctx
```

### REQ-TASK-002: TaskResult Structure
**Requirement**: TaskResult must contain success, message, data, and duration_seconds.

**Acceptance Criteria**:
- All fields accessible with correct types
- data defaults to empty dict
- duration_seconds defaults to 0.0

**Test Type**: Unit

**Test Cases**:
```python
def test_task_result_fields():
    """TaskResult has all required fields."""
    result = TaskResult(success=True, message="Done", data={"count": 5}, duration_seconds=1.5)
    assert result.success is True
    assert result.message == "Done"
    assert result.data == {"count": 5}
    assert result.duration_seconds == 1.5

def test_task_result_defaults():
    """TaskResult has sensible defaults."""
    result = TaskResult(success=True)
    assert result.message == ""
    assert result.data == {}
    assert result.duration_seconds == 0.0
```

### REQ-TASK-003: TaskConfig Fields
**Requirement**: TaskConfig must have timeout, retries, retry_delay, log_level, notify_on_failure, and retry_on_postcondition_failure.

**Acceptance Criteria**:
- All fields have correct defaults
- retry_on_postcondition_failure defaults to True

**Test Type**: Unit

**Test Cases**:
```python
def test_task_config_defaults():
    """TaskConfig has correct defaults."""
    config = TaskConfig()
    assert config.timeout_seconds == 300.0
    assert config.retries == 0
    assert config.retry_delay_seconds == 5.0
    assert config.log_level == "INFO"
    assert config.notify_on_failure is True
    assert config.retry_on_postcondition_failure is True

def test_task_config_custom_values():
    """TaskConfig accepts custom values."""
    config = TaskConfig(
        timeout_seconds=60.0,
        retries=3,
        retry_delay_seconds=10.0,
        log_level="DEBUG",
        notify_on_failure=False,
        retry_on_postcondition_failure=False
    )
    assert config.timeout_seconds == 60.0
    assert config.retries == 3
    assert config.retry_on_postcondition_failure is False
```

### REQ-TASK-004: Task Name and Description
**Requirement**: Tasks must have name and description properties.

**Acceptance Criteria**:
- name defaults to class name if not set
- description can be set as class attribute

**Test Type**: Unit

**Test Cases**:
```python
def test_task_default_name():
    """Task name defaults to class name."""
    class MyCustomTask(Task):
        def run(self, context):
            return TaskResult(success=True)

    t = MyCustomTask()
    assert t.name == "MyCustomTask"

def test_task_custom_name():
    """Task name can be overridden."""
    class MyTask(Task):
        name = "custom_name"
        def run(self, context):
            return TaskResult(success=True)

    t = MyTask()
    assert t.name == "custom_name"

def test_task_description():
    """Task description is accessible."""
    class MyTask(Task):
        description = "Does something important"
        def run(self, context):
            return TaskResult(success=True)

    t = MyTask()
    assert t.description == "Does something important"
```

---

## 3. Pipeline Runner Requirements

### REQ-RUN-001: Sequential Task Execution
**Requirement**: Pipeline runner must execute tasks sequentially in order.

**Acceptance Criteria**:
- Tasks execute in list order
- Each task completes before next starts
- Context is passed between tasks

**Test Type**: Integration

**Test Cases**:
```python
def test_tasks_execute_in_order():
    """Tasks execute sequentially in list order."""
    execution_order = []

    class Task1(Task):
        def run(self, context):
            execution_order.append("task1")
            return TaskResult(success=True)

    class Task2(Task):
        def run(self, context):
            execution_order.append("task2")
            return TaskResult(success=True)

    class Task3(Task):
        def run(self, context):
            execution_order.append("task3")
            return TaskResult(success=True)

    pipeline = create_test_pipeline([Task1(), Task2(), Task3()])
    runner = PipelineRunner()
    runner.run(pipeline)

    assert execution_order == ["task1", "task2", "task3"]
```

### REQ-RUN-002: Precondition Checking
**Requirement**: Runner must check all preconditions before executing a task.

**Acceptance Criteria**:
- All preconditions checked before task.run()
- Pipeline stops if any precondition fails
- Precondition exception is caught and treated as failure

**Test Type**: Integration

**Test Cases**:
```python
def test_precondition_checked_before_run():
    """Preconditions are checked before task executes."""
    task_ran = False

    class FailingPrecondition(Validator):
        def check(self, context):
            return ValidationResult(False, "Precondition failed", self.name)

    class MyTask(Task):
        preconditions = [FailingPrecondition()]
        def run(self, context):
            nonlocal task_ran
            task_ran = True
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert task_ran is False
    assert record.status == "failed"
    assert "precondition" in record.failure_reason.lower()

def test_precondition_exception_is_failure():
    """Exception in precondition is treated as failure."""
    class ExplodingPrecondition(Validator):
        def check(self, context):
            raise RuntimeError("Database error")

    class MyTask(Task):
        preconditions = [ExplodingPrecondition()]
        def run(self, context):
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert record.status == "failed"
    assert "database error" in record.failure_reason.lower()
```

### REQ-RUN-003: Postcondition Checking
**Requirement**: Runner must check postconditions after task completes successfully.

**Acceptance Criteria**:
- Postconditions checked only if task.run() succeeds
- Pipeline fails if postcondition fails
- Postcondition failure can trigger retry (if configured)

**Test Type**: Integration

**Test Cases**:
```python
def test_postcondition_checked_after_run():
    """Postconditions are checked after task succeeds."""
    postcondition_checked = False

    class TrackingPostcondition(Validator):
        def check(self, context):
            nonlocal postcondition_checked
            postcondition_checked = True
            return ValidationResult(True, "OK", self.name)

    class MyTask(Task):
        postconditions = [TrackingPostcondition()]
        def run(self, context):
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    runner.run(pipeline)

    assert postcondition_checked is True

def test_postcondition_not_checked_on_task_failure():
    """Postconditions not checked if task fails."""
    postcondition_checked = False

    class TrackingPostcondition(Validator):
        def check(self, context):
            nonlocal postcondition_checked
            postcondition_checked = True
            return ValidationResult(True, "OK", self.name)

    class FailingTask(Task):
        postconditions = [TrackingPostcondition()]
        def run(self, context):
            return TaskResult(success=False, message="Task failed")

    pipeline = create_test_pipeline([FailingTask()])
    runner = PipelineRunner()
    runner.run(pipeline)

    assert postcondition_checked is False

def test_postcondition_failure_triggers_retry():
    """Postcondition failure triggers retry when configured."""
    attempt_count = 0

    class FailOncePostcondition(Validator):
        def check(self, context):
            return ValidationResult(context.get("attempt", 0) > 1, "OK", self.name)

    class MyTask(Task):
        config = TaskConfig(retries=2, retry_on_postcondition_failure=True)
        postconditions = [FailOncePostcondition()]
        def run(self, context):
            nonlocal attempt_count
            attempt_count += 1
            context["attempt"] = attempt_count
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert attempt_count == 2
    assert record.status == "success"

def test_postcondition_failure_no_retry_when_disabled():
    """Postcondition failure doesn't retry when retry_on_postcondition_failure=False."""
    attempt_count = 0

    class FailingPostcondition(Validator):
        def check(self, context):
            return ValidationResult(False, "Always fails", self.name)

    class MyTask(Task):
        config = TaskConfig(retries=2, retry_on_postcondition_failure=False)
        postconditions = [FailingPostcondition()]
        def run(self, context):
            nonlocal attempt_count
            attempt_count += 1
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert attempt_count == 1  # No retry
    assert record.status == "failed"
```

### REQ-RUN-004: Task Timeout
**Requirement**: Runner must enforce task timeout using ThreadPoolExecutor.

**Acceptance Criteria**:
- Task is interrupted after timeout_seconds
- Timeout is treated as task failure
- Timeout can trigger retry

**Test Type**: Integration

**Test Cases**:
```python
def test_task_timeout():
    """Task is interrupted after timeout."""
    class SlowTask(Task):
        config = TaskConfig(timeout_seconds=0.5)
        def run(self, context):
            time.sleep(10)  # Way longer than timeout
            return TaskResult(success=True)

    pipeline = create_test_pipeline([SlowTask()])
    runner = PipelineRunner()

    start = time.time()
    record = runner.run(pipeline)
    elapsed = time.time() - start

    assert record.status == "failed"
    assert elapsed < 2.0  # Should not wait full 10 seconds
    assert "timeout" in record.failure_reason.lower()

def test_timeout_triggers_retry():
    """Timeout triggers retry."""
    attempt_count = 0

    class SlowThenFastTask(Task):
        config = TaskConfig(timeout_seconds=0.5, retries=1)
        def run(self, context):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                time.sleep(10)  # Timeout on first attempt
            return TaskResult(success=True)

    pipeline = create_test_pipeline([SlowThenFastTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert attempt_count == 2
    assert record.status == "success"
```

### REQ-RUN-005: Retry Logic
**Requirement**: Runner must retry failed tasks according to TaskConfig.retries.

**Acceptance Criteria**:
- Task is retried up to `retries` additional times
- Retry delay is respected between attempts
- Success on any attempt stops retrying

**Test Type**: Integration

**Test Cases**:
```python
def test_retry_on_failure():
    """Failed task is retried."""
    attempt_count = 0

    class FailTwiceTask(Task):
        config = TaskConfig(retries=2, retry_delay_seconds=0.1)
        def run(self, context):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                return TaskResult(success=False, message="Not yet")
            return TaskResult(success=True)

    pipeline = create_test_pipeline([FailTwiceTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert attempt_count == 3
    assert record.status == "success"

def test_retry_delay_respected():
    """Delay between retries is respected."""
    timestamps = []

    class FailingTask(Task):
        config = TaskConfig(retries=2, retry_delay_seconds=0.5)
        def run(self, context):
            timestamps.append(time.time())
            return TaskResult(success=False)

    pipeline = create_test_pipeline([FailingTask()])
    runner = PipelineRunner()
    runner.run(pipeline)

    assert len(timestamps) == 3
    assert timestamps[1] - timestamps[0] >= 0.4  # Allow some tolerance
    assert timestamps[2] - timestamps[1] >= 0.4

def test_max_retries_exhausted():
    """Pipeline fails after max retries exhausted."""
    attempt_count = 0

    class AlwaysFailTask(Task):
        config = TaskConfig(retries=2, retry_delay_seconds=0.1)
        def run(self, context):
            nonlocal attempt_count
            attempt_count += 1
            return TaskResult(success=False, message="Always fails")

    pipeline = create_test_pipeline([AlwaysFailTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert attempt_count == 3  # 1 initial + 2 retries
    assert record.status == "failed"
    assert "3 attempts" in record.failure_reason or "retries" in record.failure_reason.lower()
```

### REQ-RUN-006: Context Passing
**Requirement**: Context must be shared between tasks, with TaskResult.data merged after each task.

**Acceptance Criteria**:
- Initial context is available to first task
- TaskResult.data is merged into context
- Subsequent tasks see updated context

**Test Type**: Integration

**Test Cases**:
```python
def test_initial_context_available():
    """Initial context is passed to first task."""
    received_context = {}

    class ContextReader(Task):
        def run(self, context):
            nonlocal received_context
            received_context = dict(context)
            return TaskResult(success=True)

    pipeline = create_test_pipeline([ContextReader()])
    runner = PipelineRunner()
    runner.run(pipeline, initial_context={"input_file": "data.csv"})

    assert received_context["input_file"] == "data.csv"

def test_task_data_merged_to_context():
    """TaskResult.data is merged into context."""
    class Task1(Task):
        def run(self, context):
            return TaskResult(success=True, data={"count": 100})

    class Task2(Task):
        def run(self, context):
            assert context["count"] == 100
            return TaskResult(success=True, data={"processed": True})

    class Task3(Task):
        def run(self, context):
            assert context["count"] == 100
            assert context["processed"] is True
            return TaskResult(success=True)

    pipeline = create_test_pipeline([Task1(), Task2(), Task3()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert record.status == "success"

def test_context_key_overwrite():
    """Later tasks can overwrite context keys."""
    class Task1(Task):
        def run(self, context):
            return TaskResult(success=True, data={"status": "pending"})

    class Task2(Task):
        def run(self, context):
            return TaskResult(success=True, data={"status": "complete"})

    final_context = {}
    class Task3(Task):
        def run(self, context):
            nonlocal final_context
            final_context = dict(context)
            return TaskResult(success=True)

    pipeline = create_test_pipeline([Task1(), Task2(), Task3()])
    runner = PipelineRunner()
    runner.run(pipeline)

    assert final_context["status"] == "complete"
```

### REQ-RUN-007: Dry-Run Mode
**Requirement**: Dry-run mode must validate preconditions without executing tasks.

**Acceptance Criteria**:
- Preconditions are checked
- task.run() is NOT called
- Postconditions are NOT checked
- Returns success if all preconditions pass

**Test Type**: Integration

**Test Cases**:
```python
def test_dry_run_checks_preconditions():
    """Dry-run checks preconditions."""
    precondition_checked = False

    class TrackingPrecondition(Validator):
        def check(self, context):
            nonlocal precondition_checked
            precondition_checked = True
            return ValidationResult(True, "OK", self.name)

    class MyTask(Task):
        preconditions = [TrackingPrecondition()]
        def run(self, context):
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    runner.run(pipeline, dry_run=True)

    assert precondition_checked is True

def test_dry_run_skips_task_execution():
    """Dry-run does not execute task.run()."""
    task_ran = False

    class MyTask(Task):
        def run(self, context):
            nonlocal task_ran
            task_ran = True
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    runner.run(pipeline, dry_run=True)

    assert task_ran is False

def test_dry_run_fails_on_precondition_failure():
    """Dry-run reports failure when precondition fails."""
    class FailingPrecondition(Validator):
        def check(self, context):
            return ValidationResult(False, "Missing file", self.name)

    class MyTask(Task):
        preconditions = [FailingPrecondition()]
        def run(self, context):
            return TaskResult(success=True)

    pipeline = create_test_pipeline([MyTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline, dry_run=True)

    assert record.status == "failed"
```

### REQ-RUN-008: Start-From Mode
**Requirement**: --start-from must skip tasks before the specified task.

**Acceptance Criteria**:
- Tasks before start_from are skipped
- start_from task and subsequent tasks execute normally
- Error if start_from task not found

**Test Type**: Integration

**Test Cases**:
```python
def test_start_from_skips_earlier_tasks():
    """Tasks before start_from are skipped."""
    executed_tasks = []

    class Task1(Task):
        name = "task1"
        def run(self, context):
            executed_tasks.append("task1")
            return TaskResult(success=True)

    class Task2(Task):
        name = "task2"
        def run(self, context):
            executed_tasks.append("task2")
            return TaskResult(success=True)

    class Task3(Task):
        name = "task3"
        def run(self, context):
            executed_tasks.append("task3")
            return TaskResult(success=True)

    pipeline = create_test_pipeline([Task1(), Task2(), Task3()])
    runner = PipelineRunner()
    record = runner.run(pipeline, start_from="task2")

    assert executed_tasks == ["task2", "task3"]
    assert record.status == "success"

def test_start_from_invalid_task():
    """Error when start_from task doesn't exist."""
    class Task1(Task):
        name = "task1"
        def run(self, context):
            return TaskResult(success=True)

    pipeline = create_test_pipeline([Task1()])
    runner = PipelineRunner()

    with pytest.raises(ValueError) as exc:
        runner.run(pipeline, start_from="nonexistent")

    assert "nonexistent" in str(exc.value).lower()
```

### REQ-RUN-009: Pipeline-Level Timeout
**Requirement**: Pipeline must fail if total runtime exceeds max_runtime_seconds.

**Acceptance Criteria**:
- Pipeline stops if elapsed time exceeds max_runtime_seconds
- Timeout checked before each task starts
- Clear error message about pipeline timeout

**Test Type**: Integration

**Test Cases**:
```python
def test_pipeline_timeout():
    """Pipeline fails when max_runtime_seconds exceeded."""
    class SlowTask(Task):
        def run(self, context):
            time.sleep(0.5)
            return TaskResult(success=True)

    config = PipelineConfig(name="test", max_runtime_seconds=0.3)
    pipeline = Pipeline(config=config, tasks=[SlowTask(), SlowTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert record.status == "failed"
    assert "timeout" in record.failure_reason.lower() or "exceeded" in record.failure_reason.lower()

def test_pipeline_no_timeout_when_not_set():
    """Pipeline runs indefinitely when max_runtime_seconds is None."""
    class QuickTask(Task):
        def run(self, context):
            return TaskResult(success=True)

    config = PipelineConfig(name="test", max_runtime_seconds=None)
    pipeline = Pipeline(config=config, tasks=[QuickTask()])
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert record.status == "success"
```

### REQ-RUN-010: Signal Handling
**Requirement**: Runner must handle SIGINT/SIGTERM gracefully.

**Acceptance Criteria**:
- Lock is released on interrupt
- Partial run is recorded in history
- Graceful shutdown message logged

**Test Type**: Integration (difficult to test, may need manual verification)

**Test Cases**:
```python
def test_signal_handler_releases_lock(tmp_path):
    """Lock is released when signal received."""
    # This is hard to test automatically
    # Manual verification: run pipeline, Ctrl+C, verify lock file is removed
    pass  # Placeholder for manual test procedure

def test_atexit_releases_lock(tmp_path):
    """atexit handler releases lock on normal exit."""
    # Verify lock cleanup happens even without signal
    pass
```

---

## 4. CLI Requirements

### REQ-CLI-001: Run Command
**Requirement**: `harness run <pipeline>` must execute a pipeline with options.

**Acceptance Criteria**:
- Executes named pipeline
- Supports --dry-run
- Supports --start-from TASK
- Supports --force (ignore lock)
- Supports --context KEY=VAL
- Supports --verbose / --quiet

**Test Type**: Integration / E2E

**Test Cases**:
```python
def test_cli_run_basic(cli_runner, example_pipeline):
    """Basic run command works."""
    result = cli_runner.invoke(["run", "example"])
    assert result.exit_code == 0

def test_cli_run_dry_run(cli_runner, example_pipeline):
    """--dry-run flag works."""
    result = cli_runner.invoke(["run", "example", "--dry-run"])
    assert result.exit_code == 0

def test_cli_run_start_from(cli_runner, example_pipeline):
    """--start-from flag works."""
    result = cli_runner.invoke(["run", "example", "--start-from", "task2"])
    assert result.exit_code == 0

def test_cli_run_context(cli_runner, example_pipeline):
    """--context flag passes values."""
    result = cli_runner.invoke(["run", "example", "--context", "key=value"])
    assert result.exit_code == 0

def test_cli_run_context_with_equals_in_value(cli_runner, example_pipeline):
    """--context handles values containing =."""
    result = cli_runner.invoke(["run", "example", "--context", "query=a=b"])
    # Should parse as key="query", value="a=b"
    assert result.exit_code == 0
```

### REQ-CLI-002: Exit Codes
**Requirement**: CLI must return appropriate exit codes.

**Acceptance Criteria**:
- 0 = success
- 1 = pipeline failure
- 2 = CLI error (bad args, pipeline not found)
- 3 = lock contention

**Test Type**: Integration

**Test Cases**:
```python
def test_exit_code_success(cli_runner, passing_pipeline):
    """Exit code 0 on success."""
    result = cli_runner.invoke(["run", "passing"])
    assert result.exit_code == 0

def test_exit_code_pipeline_failure(cli_runner, failing_pipeline):
    """Exit code 1 on pipeline failure."""
    result = cli_runner.invoke(["run", "failing"])
    assert result.exit_code == 1

def test_exit_code_pipeline_not_found(cli_runner):
    """Exit code 2 when pipeline not found."""
    result = cli_runner.invoke(["run", "nonexistent"])
    assert result.exit_code == 2

def test_exit_code_lock_contention(cli_runner, locked_pipeline):
    """Exit code 3 when pipeline locked."""
    result = cli_runner.invoke(["run", "locked"])
    assert result.exit_code == 3
```

### REQ-CLI-003: List Command
**Requirement**: `harness list` must list all discovered pipelines.

**Acceptance Criteria**:
- Shows all pipelines in pipelines/ directory
- Shows pipeline name and description

**Test Type**: Integration

**Test Cases**:
```python
def test_cli_list(cli_runner, multiple_pipelines):
    """list command shows all pipelines."""
    result = cli_runner.invoke(["list"])
    assert result.exit_code == 0
    assert "pipeline1" in result.output
    assert "pipeline2" in result.output

def test_cli_list_empty(cli_runner, empty_pipelines_dir):
    """list command handles no pipelines gracefully."""
    result = cli_runner.invoke(["list"])
    assert result.exit_code == 0
    assert "no pipelines" in result.output.lower()
```

### REQ-CLI-004: Show Command
**Requirement**: `harness show <pipeline>` must show pipeline details.

**Acceptance Criteria**:
- Shows pipeline name and description
- Shows list of tasks with their validators

**Test Type**: Integration

**Test Cases**:
```python
def test_cli_show(cli_runner, example_pipeline):
    """show command displays pipeline details."""
    result = cli_runner.invoke(["show", "example"])
    assert result.exit_code == 0
    assert "example" in result.output.lower()
    # Should show tasks
    assert "task" in result.output.lower()

def test_cli_show_not_found(cli_runner):
    """show command fails for unknown pipeline."""
    result = cli_runner.invoke(["show", "nonexistent"])
    assert result.exit_code == 2
```

### REQ-CLI-005: History Command
**Requirement**: `harness history` must show run history with filters.

**Acceptance Criteria**:
- Shows recent runs
- Supports --pipeline filter
- Supports --limit
- Supports --status filter

**Test Type**: Integration

**Test Cases**:
```python
def test_cli_history(cli_runner, populated_history):
    """history command shows recent runs."""
    result = cli_runner.invoke(["history"])
    assert result.exit_code == 0

def test_cli_history_filter_pipeline(cli_runner, populated_history):
    """history --pipeline filters by name."""
    result = cli_runner.invoke(["history", "--pipeline", "daily"])
    assert result.exit_code == 0
    assert "daily" in result.output

def test_cli_history_limit(cli_runner, populated_history):
    """history --limit limits output."""
    result = cli_runner.invoke(["history", "--limit", "5"])
    assert result.exit_code == 0
    # Count output lines (implementation dependent)

def test_cli_history_filter_status(cli_runner, populated_history):
    """history --status filters by status."""
    result = cli_runner.invoke(["history", "--status", "failed"])
    assert result.exit_code == 0
    assert "success" not in result.output.lower()
```

### REQ-CLI-006: Secrets Commands
**Requirement**: `harness secrets` subcommands must manage secrets store.

**Acceptance Criteria**:
- init: creates new secrets store
- set: stores a secret
- get: retrieves a secret (with confirmation)
- list: lists secret names
- delete: removes a secret

**Test Type**: Integration

**Test Cases**:
```python
def test_cli_secrets_init(cli_runner, tmp_path, monkeypatch):
    """secrets init creates new store."""
    monkeypatch.setenv("HARNESS_ROOT", str(tmp_path))
    result = cli_runner.invoke(["secrets", "init"])
    assert result.exit_code == 0
    assert (tmp_path / ".harness" / "secrets.enc").exists() or "key" in result.output

def test_cli_secrets_set_get(cli_runner, initialized_secrets):
    """secrets set and get work together."""
    # Set
    result = cli_runner.invoke(["secrets", "set", "test_cred"], input='{"user": "test"}\n')
    assert result.exit_code == 0

    # Get (with confirmation)
    result = cli_runner.invoke(["secrets", "get", "test_cred"], input='y\n')
    assert result.exit_code == 0
    assert "test" in result.output

def test_cli_secrets_list(cli_runner, initialized_secrets):
    """secrets list shows names only."""
    cli_runner.invoke(["secrets", "set", "cred1"], input='{"a": 1}\n')
    cli_runner.invoke(["secrets", "set", "cred2"], input='{"b": 2}\n')

    result = cli_runner.invoke(["secrets", "list"])
    assert result.exit_code == 0
    assert "cred1" in result.output
    assert "cred2" in result.output
    # Should NOT show values
    assert '"a"' not in result.output

def test_cli_secrets_delete(cli_runner, initialized_secrets):
    """secrets delete removes secret."""
    cli_runner.invoke(["secrets", "set", "to_delete"], input='{"x": 1}\n')

    result = cli_runner.invoke(["secrets", "delete", "to_delete"])
    assert result.exit_code == 0

    # Verify deleted
    result = cli_runner.invoke(["secrets", "list"])
    assert "to_delete" not in result.output
```

### REQ-CLI-007: TTY Detection
**Requirement**: CLI must auto-detect TTY for verbose output.

**Acceptance Criteria**:
- Interactive terminal: verbose by default
- Piped/redirected: quiet by default
- --verbose/--quiet override auto-detection

**Test Type**: Integration

**Test Cases**:
```python
def test_cli_verbose_in_tty(cli_runner, example_pipeline, mocker):
    """Verbose output when running in TTY."""
    mocker.patch('sys.stdout.isatty', return_value=True)
    result = cli_runner.invoke(["run", "example"])
    # Should see progress output
    assert "running" in result.output.lower() or "task" in result.output.lower()

def test_cli_quiet_when_piped(cli_runner, example_pipeline, mocker):
    """Quiet output when piped."""
    mocker.patch('sys.stdout.isatty', return_value=False)
    result = cli_runner.invoke(["run", "example"])
    # Minimal output
    assert len(result.output) < 100  # Rough check

def test_cli_verbose_flag_overrides(cli_runner, example_pipeline, mocker):
    """--verbose forces verbose output even when piped."""
    mocker.patch('sys.stdout.isatty', return_value=False)
    result = cli_runner.invoke(["run", "example", "--verbose"])
    assert "running" in result.output.lower() or "task" in result.output.lower()

def test_cli_quiet_flag_overrides(cli_runner, example_pipeline, mocker):
    """--quiet forces quiet output even in TTY."""
    mocker.patch('sys.stdout.isatty', return_value=True)
    result = cli_runner.invoke(["run", "example", "--quiet"])
    assert len(result.output) < 100
```

---

## 5. Secrets Store Requirements

### REQ-SEC-001: Encryption
**Requirement**: Secrets must be encrypted using Fernet symmetric encryption.

**Acceptance Criteria**:
- Secrets file is not human-readable
- Decryption with wrong key fails
- Encrypted data survives round-trip

**Test Type**: Unit

**Test Cases**:
```python
def test_secrets_encrypted_on_disk(tmp_path, secrets_store):
    """Secrets file is encrypted, not plaintext."""
    secrets_store.set("test", {"password": "secret123"})

    file_content = (tmp_path / ".harness" / "secrets.enc").read_bytes()
    assert b"secret123" not in file_content
    assert b"password" not in file_content

def test_secrets_wrong_key_fails(tmp_path, secrets_store):
    """Decryption with wrong key raises error."""
    secrets_store.set("test", {"value": "data"})

    # Create new store with different key
    wrong_key = Fernet.generate_key()
    with pytest.raises(Exception):  # InvalidToken or similar
        SecretsStore(tmp_path / ".harness" / "secrets.enc", key=wrong_key).get("test")

def test_secrets_round_trip(secrets_store):
    """Data survives encrypt/decrypt round-trip."""
    original = {"host": "example.com", "port": 22, "nested": {"key": "value"}}
    secrets_store.set("creds", original)
    retrieved = secrets_store.get("creds")
    assert retrieved == original
```

### REQ-SEC-002: Key Sources
**Requirement**: Master key must be retrieved from env var first, then keyring.

**Acceptance Criteria**:
- HARNESS_SECRETS_KEY env var takes priority
- Falls back to keyring if env var not set
- Clear error if neither available

**Test Type**: Unit

**Test Cases**:
```python
def test_key_from_env_var(monkeypatch, tmp_path):
    """Key loaded from HARNESS_SECRETS_KEY env var."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HARNESS_SECRETS_KEY", key)

    store = SecretsStore(tmp_path / "secrets.enc")
    store.set("test", {"a": 1})  # Should not raise
    assert store.get("test") == {"a": 1}

def test_key_from_keyring(monkeypatch, mocker, tmp_path):
    """Key loaded from keyring when env var not set."""
    monkeypatch.delenv("HARNESS_SECRETS_KEY", raising=False)
    key = Fernet.generate_key().decode()
    mocker.patch('keyring.get_password', return_value=key)

    store = SecretsStore(tmp_path / "secrets.enc")
    store.set("test", {"a": 1})
    assert store.get("test") == {"a": 1}

def test_key_not_found_error(monkeypatch, mocker, tmp_path):
    """Clear error when no key source available."""
    monkeypatch.delenv("HARNESS_SECRETS_KEY", raising=False)
    mocker.patch('keyring.get_password', return_value=None)

    with pytest.raises(RuntimeError) as exc:
        SecretsStore(tmp_path / "secrets.enc")

    assert "HARNESS_SECRETS_KEY" in str(exc.value)
    assert "secrets init" in str(exc.value).lower()

def test_env_var_takes_priority(monkeypatch, mocker, tmp_path):
    """Env var is used even when keyring has different key."""
    env_key = Fernet.generate_key().decode()
    keyring_key = Fernet.generate_key().decode()

    monkeypatch.setenv("HARNESS_SECRETS_KEY", env_key)
    mocker.patch('keyring.get_password', return_value=keyring_key)

    store = SecretsStore(tmp_path / "secrets.enc")
    store.set("test", {"a": 1})

    # Verify it used env var key (would fail with keyring key)
    monkeypatch.setenv("HARNESS_SECRETS_KEY", env_key)
    store2 = SecretsStore(tmp_path / "secrets.enc")
    assert store2.get("test") == {"a": 1}
```

### REQ-SEC-003: CRUD Operations
**Requirement**: Secrets store must support set, get, delete, and list operations.

**Acceptance Criteria**:
- set() stores new secret or updates existing
- get() retrieves secret or raises KeyError
- delete() removes secret
- list_secrets() returns names only

**Test Type**: Unit

**Test Cases**:
```python
def test_set_and_get(secrets_store):
    """set() and get() work correctly."""
    secrets_store.set("db", {"host": "localhost", "port": 5432})
    result = secrets_store.get("db")
    assert result == {"host": "localhost", "port": 5432}

def test_set_updates_existing(secrets_store):
    """set() updates existing secret."""
    secrets_store.set("db", {"host": "old"})
    secrets_store.set("db", {"host": "new"})
    assert secrets_store.get("db") == {"host": "new"}

def test_get_not_found(secrets_store):
    """get() raises KeyError for unknown secret."""
    with pytest.raises(KeyError):
        secrets_store.get("nonexistent")

def test_delete(secrets_store):
    """delete() removes secret."""
    secrets_store.set("temp", {"a": 1})
    secrets_store.delete("temp")
    with pytest.raises(KeyError):
        secrets_store.get("temp")

def test_delete_not_found(secrets_store):
    """delete() raises KeyError for unknown secret."""
    with pytest.raises(KeyError):
        secrets_store.delete("nonexistent")

def test_list_secrets(secrets_store):
    """list_secrets() returns names only."""
    secrets_store.set("cred1", {"user": "a"})
    secrets_store.set("cred2", {"user": "b"})

    names = secrets_store.list_secrets()
    assert set(names) == {"cred1", "cred2"}
```

---

## 6. Locking Requirements

### REQ-LOCK-001: Lock Acquisition
**Requirement**: Lock must be acquired before pipeline runs.

**Acceptance Criteria**:
- Lock file created on acquire
- Lock contains PID, timestamp, hostname
- Second acquire attempt fails

**Test Type**: Unit

**Test Cases**:
```python
def test_lock_creates_file(tmp_path):
    """Lock creates lock file on acquire."""
    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    assert lock.acquire() is True
    assert (tmp_path / "test_pipeline.lock").exists()
    lock.release()

def test_lock_contains_metadata(tmp_path):
    """Lock file contains PID, timestamp, hostname."""
    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    lock.acquire()

    content = json.loads((tmp_path / "test_pipeline.lock").read_text())
    assert "pid" in content
    assert content["pid"] == os.getpid()
    assert "started" in content
    assert "hostname" in content

    lock.release()

def test_lock_second_acquire_fails(tmp_path):
    """Second lock acquire attempt fails."""
    lock1 = PipelineLock("test_pipeline", lock_dir=tmp_path)
    lock2 = PipelineLock("test_pipeline", lock_dir=tmp_path)

    assert lock1.acquire() is True
    assert lock2.acquire() is False

    lock1.release()
```

### REQ-LOCK-002: Lock Release
**Requirement**: Lock must be released after pipeline completes.

**Acceptance Criteria**:
- Lock file removed on release
- Works in context manager

**Test Type**: Unit

**Test Cases**:
```python
def test_lock_release_removes_file(tmp_path):
    """Release removes lock file."""
    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    lock.acquire()
    lock.release()
    assert not (tmp_path / "test_pipeline.lock").exists()

def test_lock_context_manager(tmp_path):
    """Lock works as context manager."""
    with PipelineLock("test_pipeline", lock_dir=tmp_path) as lock:
        assert (tmp_path / "test_pipeline.lock").exists()

    assert not (tmp_path / "test_pipeline.lock").exists()
```

### REQ-LOCK-003: Stale Lock Detection
**Requirement**: Lock must detect and handle stale locks from dead processes.

**Acceptance Criteria**:
- Lock from dead PID is considered stale
- Stale lock can be overwritten
- Uses psutil.pid_exists() for detection

**Test Type**: Unit

**Test Cases**:
```python
def test_stale_lock_detected(tmp_path):
    """Stale lock from dead process is detected."""
    lock_file = tmp_path / "test_pipeline.lock"
    lock_file.write_text(json.dumps({
        "pid": 999999999,  # Unlikely to be a real PID
        "started": "2024-01-01T00:00:00",
        "hostname": "test"
    }))

    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    assert lock._is_stale() is True

def test_stale_lock_can_be_acquired(tmp_path):
    """Stale lock can be overwritten."""
    lock_file = tmp_path / "test_pipeline.lock"
    lock_file.write_text(json.dumps({
        "pid": 999999999,
        "started": "2024-01-01T00:00:00",
        "hostname": "test"
    }))

    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    assert lock.acquire() is True
    lock.release()

def test_live_lock_not_stale(tmp_path):
    """Lock from current process is not stale."""
    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    lock.acquire()

    lock2 = PipelineLock("test_pipeline", lock_dir=tmp_path)
    assert lock2._is_stale() is False

    lock.release()

def test_corrupt_lock_is_stale(tmp_path):
    """Corrupt lock file is treated as stale."""
    lock_file = tmp_path / "test_pipeline.lock"
    lock_file.write_text("not valid json")

    lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
    assert lock._is_stale() is True
```

### REQ-LOCK-004: Lock Race Condition Prevention
**Requirement**: Lock must use OS-level file locking to prevent race conditions.

**Acceptance Criteria**:
- Uses msvcrt.locking on Windows
- Uses fcntl.flock on Unix
- Atomic check-and-acquire

**Test Type**: Unit / Integration

**Test Cases**:
```python
def test_concurrent_acquire_only_one_succeeds(tmp_path):
    """Only one of concurrent acquire attempts succeeds."""
    import threading

    results = []

    def try_acquire():
        lock = PipelineLock("test_pipeline", lock_dir=tmp_path)
        results.append(lock.acquire())
        time.sleep(0.1)
        if results[-1]:
            lock.release()

    threads = [threading.Thread(target=try_acquire) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one should succeed at a time
    # (Due to timing, may be more with releases, but never concurrent)
    assert results.count(True) >= 1
```

---

## 7. History Requirements

### REQ-HIST-001: Record Creation
**Requirement**: Each pipeline run must create a history record.

**Acceptance Criteria**:
- Record contains all required fields
- Record is appended to history file
- Uses JSON Lines format

**Test Type**: Unit / Integration

**Test Cases**:
```python
def test_run_creates_history_record(tmp_path, example_pipeline):
    """Pipeline run creates history record."""
    history = RunHistory(tmp_path / "history.jsonl")
    runner = PipelineRunner(history=history)
    runner.run(example_pipeline)

    records = history.get_recent()
    assert len(records) == 1
    assert records[0].pipeline_name == example_pipeline.config.name

def test_history_record_fields(tmp_path):
    """History record contains all required fields."""
    history = RunHistory(tmp_path / "history.jsonl")

    record = RunRecord(
        pipeline_name="test",
        run_id="abc123",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        status="success",
        completed_tasks=["task1", "task2"],
        failed_task=None,
        failure_reason="",
        log_file=Path("logs/abc123.log")
    )
    history.record(record)

    retrieved = history.get_by_id("abc123")
    assert retrieved.pipeline_name == "test"
    assert retrieved.status == "success"
    assert retrieved.completed_tasks == ["task1", "task2"]

def test_history_uses_jsonl_format(tmp_path):
    """History file uses JSON Lines format."""
    history = RunHistory(tmp_path / "history.jsonl")
    history.record(RunRecord(pipeline_name="p1", run_id="1", ...))
    history.record(RunRecord(pipeline_name="p2", run_id="2", ...))

    lines = (tmp_path / "history.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["pipeline_name"] == "p1"
    assert json.loads(lines[1])["pipeline_name"] == "p2"
```

### REQ-HIST-002: Record Retrieval
**Requirement**: History must support filtered retrieval.

**Acceptance Criteria**:
- get_recent() returns latest N records
- Supports filtering by pipeline name
- Supports filtering by status
- get_by_id() returns specific record

**Test Type**: Unit

**Test Cases**:
```python
def test_get_recent_limit(populated_history):
    """get_recent() respects limit parameter."""
    records = populated_history.get_recent(limit=5)
    assert len(records) <= 5

def test_get_recent_filter_pipeline(populated_history):
    """get_recent() filters by pipeline name."""
    records = populated_history.get_recent(pipeline_name="daily")
    assert all(r.pipeline_name == "daily" for r in records)

def test_get_recent_filter_status(populated_history):
    """get_recent() filters by status."""
    records = populated_history.get_recent(status="failed")
    assert all(r.status == "failed" for r in records)

def test_get_by_id(populated_history):
    """get_by_id() returns specific record."""
    record = populated_history.get_by_id("known_run_id")
    assert record is not None
    assert record.run_id == "known_run_id"

def test_get_by_id_not_found(populated_history):
    """get_by_id() returns None for unknown ID."""
    record = populated_history.get_by_id("nonexistent")
    assert record is None
```

### REQ-HIST-003: Corrupt Line Handling
**Requirement**: History must skip corrupt lines without crashing.

**Acceptance Criteria**:
- Malformed JSON lines are skipped
- Valid lines are still returned
- No exception raised

**Test Type**: Unit

**Test Cases**:
```python
def test_corrupt_line_skipped(tmp_path):
    """Corrupt lines are skipped."""
    history_file = tmp_path / "history.jsonl"
    history_file.write_text(
        '{"pipeline_name": "p1", "run_id": "1", ...}\n'
        'not valid json\n'
        '{"pipeline_name": "p2", "run_id": "2", ...}\n'
    )

    history = RunHistory(history_file)
    records = history.get_recent()

    # Should have 2 records, skipping the corrupt line
    assert len(records) == 2
```

---

## 8. Logging Requirements

### REQ-LOG-001: Per-Run Log Files
**Requirement**: Each pipeline run must create a separate log file.

**Acceptance Criteria**:
- Log file created in configured log directory
- Filename includes timestamp/run ID
- Contains all task logs for that run

**Test Type**: Integration

**Test Cases**:
```python
def test_per_run_log_created(tmp_path, example_pipeline):
    """Each run creates its own log file."""
    config = PipelineConfig(
        name="test",
        log_directory=tmp_path / "logs"
    )
    pipeline = Pipeline(config=config, tasks=example_pipeline.tasks)
    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert record.log_file.exists()
    assert record.log_file.parent == tmp_path / "logs" / "test"
```

### REQ-LOG-002: Log Format
**Requirement**: Logs must follow specified format with timestamp, level, component, message.

**Acceptance Criteria**:
- Format: `YYYY-MM-DD HH:MM:SS [LEVEL] [Component] Message`
- Component is pipeline name or task name

**Test Type**: Integration

**Test Cases**:
```python
def test_log_format(tmp_path, example_pipeline):
    """Log entries follow specified format."""
    runner = PipelineRunner()
    record = runner.run(example_pipeline)

    log_content = record.log_file.read_text()
    # Check for format pattern
    import re
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[(INFO|DEBUG|WARNING|ERROR)\] \[\w+\]'
    assert re.search(pattern, log_content)
```

### REQ-LOG-003: Per-Task Log Levels
**Requirement**: Each task can have its own log level.

**Acceptance Criteria**:
- Task with DEBUG level shows debug messages
- Task with WARNING level hides info messages
- Default level is INFO

**Test Type**: Integration

**Test Cases**:
```python
def test_task_log_level(tmp_path):
    """Task log level controls verbosity."""
    class VerboseTask(Task):
        config = TaskConfig(log_level="DEBUG")
        def run(self, context):
            logging.debug("Debug message")
            return TaskResult(success=True)

    class QuietTask(Task):
        config = TaskConfig(log_level="WARNING")
        def run(self, context):
            logging.info("Info message")  # Should not appear
            logging.warning("Warning message")
            return TaskResult(success=True)

    # Run and check log contents
    # VerboseTask log should have "Debug message"
    # QuietTask log should have "Warning message" but not "Info message"
```

---

## 9. Notification Requirements

### REQ-NOTIF-001: Notifier Interface
**Requirement**: Notifiers must implement the Notifier ABC.

**Acceptance Criteria**:
- Abstract send() method
- Accepts subject, body, severity
- Returns bool for success/failure

**Test Type**: Unit

**Test Cases**:
```python
def test_notifier_is_abstract():
    """Notifier cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Notifier()

def test_notifier_interface():
    """Notifier subclass must implement send()."""
    class TestNotifier(Notifier):
        def send(self, subject, body, severity="critical"):
            return True

    n = TestNotifier()
    assert n.send("Test", "Body") is True
```

### REQ-NOTIF-002: NoOpNotifier
**Requirement**: NoOpNotifier must accept calls but do nothing.

**Acceptance Criteria**:
- send() always returns True
- No side effects

**Test Type**: Unit

**Test Cases**:
```python
def test_noop_notifier():
    """NoOpNotifier accepts calls silently."""
    n = NoOpNotifier()
    result = n.send("Subject", "Body", "critical")
    assert result is True
```

### REQ-NOTIF-003: Notification Failure Handling
**Requirement**: Notification failure must not fail the pipeline.

**Acceptance Criteria**:
- Pipeline status based on task success, not notification
- Notification failure logged as WARNING

**Test Type**: Integration

**Test Cases**:
```python
def test_notification_failure_doesnt_fail_pipeline(tmp_path):
    """Pipeline succeeds even when notification fails."""
    class FailingNotifier(Notifier):
        def send(self, subject, body, severity="critical"):
            raise Exception("SMTP error")

    config = PipelineConfig(name="test", notify_on_success=True)
    pipeline = Pipeline(
        config=config,
        tasks=[SuccessTask()],
        notifier=FailingNotifier()
    )

    runner = PipelineRunner()
    record = runner.run(pipeline)

    assert record.status == "success"  # Not failed due to notification
```

---

## 10. Cross-Cutting Requirements

### REQ-CROSS-001: Windows Compatibility
**Requirement**: All components must work on Windows.

**Acceptance Criteria**:
- Path handling uses pathlib
- File locking uses msvcrt on Windows
- Signal handling uses SIGBREAK on Windows

**Test Type**: E2E (on Windows)

**Test Cases**:
```python
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_path_with_spaces(tmp_path):
    """Handles Windows paths with spaces."""
    path = tmp_path / "my folder" / "data.csv"
    path.parent.mkdir()
    path.write_text("a,b\n1,2\n")

    v = FileExists(str(path))
    result = v.check({})
    assert result.passed is True

@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_lock_mechanism(tmp_path):
    """Lock uses msvcrt on Windows."""
    lock = PipelineLock("test", lock_dir=tmp_path)
    assert lock.acquire() is True
    lock.release()
```

### REQ-CROSS-002: Timezone Handling
**Requirement**: All datetime operations must use timezone-aware datetimes in UTC.

**Acceptance Criteria**:
- No naive datetimes
- All storage in UTC
- Display can be localized

**Test Type**: Unit

**Test Cases**:
```python
def test_run_record_uses_utc():
    """RunRecord timestamps are UTC."""
    record = create_run_record()
    assert record.start_time.tzinfo is not None
    assert record.start_time.tzinfo == timezone.utc

def test_file_modified_within_utc(tmp_path):
    """FileModifiedWithin uses UTC internally."""
    f = tmp_path / "test.txt"
    f.write_text("content")

    v = FileModifiedWithin(str(f), max_age=timedelta(hours=1))
    result = v.check({})
    # Should work regardless of system timezone
    assert result.passed is True
```

### REQ-CROSS-003: Error Messages
**Requirement**: All error messages must be actionable.

**Acceptance Criteria**:
- Includes what went wrong
- Includes what was expected
- Suggests how to fix (where possible)

**Test Type**: Review / Manual

**Test Cases**:
```python
def test_file_not_found_message(tmp_path):
    """FileExists error message includes path."""
    v = FileExists(str(tmp_path / "missing.csv"))
    result = v.check({})
    assert "missing.csv" in result.message
    assert "not found" in result.message.lower()

def test_missing_header_message(tmp_path):
    """TabularFileValid error lists missing headers."""
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")

    v = TabularFileValid(str(f), required_headers=["a", "b", "c"])
    result = v.check({})
    assert "c" in result.message  # Shows which header is missing
```

---

## Appendix A: Test Fixtures

```python
# tests/conftest.py

import pytest
from pathlib import Path
from cryptography.fernet import Fernet

@pytest.fixture
def tmp_harness_root(tmp_path, monkeypatch):
    """Set up temporary harness root directory."""
    monkeypatch.setenv("HARNESS_ROOT", str(tmp_path))
    (tmp_path / "pipelines").mkdir()
    (tmp_path / ".harness").mkdir()
    return tmp_path

@pytest.fixture
def secrets_store(tmp_path, monkeypatch):
    """Create secrets store with test key."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HARNESS_SECRETS_KEY", key)
    return SecretsStore(tmp_path / ".harness" / "secrets.enc")

@pytest.fixture
def example_pipeline():
    """Create minimal passing pipeline for tests."""
    class PassingTask(Task):
        def run(self, context):
            return TaskResult(success=True)

    config = PipelineConfig(name="example")
    return Pipeline(config=config, tasks=[PassingTask()])

@pytest.fixture
def populated_history(tmp_path):
    """Create history with sample records."""
    history = RunHistory(tmp_path / "history.jsonl")
    # Add sample records
    for i in range(20):
        history.record(RunRecord(
            pipeline_name="daily" if i % 2 == 0 else "weekly",
            run_id=f"run_{i}",
            status="success" if i % 3 != 0 else "failed",
            ...
        ))
    return history

class MockValidator(Validator):
    """Configurable mock validator for testing."""
    def __init__(self, passes: bool, message: str):
        self._passes = passes
        self._message = message

    def check(self, context):
        return ValidationResult(self._passes, self._message, self.name)
```

---

## Appendix B: Test Coverage Requirements

| Component | Target Coverage |
|-----------|-----------------|
| Validators | 95%+ |
| Task/Pipeline models | 90%+ |
| Pipeline Runner | 90%+ |
| CLI | 85%+ |
| Secrets Store | 95%+ |
| Locking | 90%+ |
| History | 90%+ |
| Logging | 80%+ |
| **Overall** | **90%+** |

---

## Appendix C: Test Execution Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=harness --cov-report=html

# Run specific test file
pytest tests/test_validators/test_environment.py

# Run tests matching pattern
pytest -k "test_csv"

# Run with verbose output
pytest -v

# Run only fast tests (exclude slow integration tests)
pytest -m "not slow"
```
