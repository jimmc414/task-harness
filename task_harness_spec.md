# Task Running Harness Specification

## Overview

A Python-based task orchestration framework for running sequential automated processes with validation-based error handling. The harness validates preconditions before task execution and postconditions after, rather than attempting to handle all possible failure modes explicitly.

**Target environment:** Windows, Python 3.10+, invoked via Windows Task Scheduler or manual CLI execution.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                           │
│  (run, dry-run, list, force-complete, show-history)             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Pipeline Runner                          │
│  - Loads pipeline definition                                    │
│  - Checks concurrency lock                                      │
│  - Iterates tasks sequentially                                  │
│  - Manages retries and timeouts                                 │
│  - Records run history                                          │
│  - Triggers notifications on failure                            │
└─────────────────────────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Validators     │  │     Tasks        │  │   Notifier       │
│  (pre/post)      │  │  (user-defined)  │  │  (mail service)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
          │                     │                     │
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Secrets Store   │  │   Run History    │  │    Log Files     │
│  (encrypted)     │  │     (JSON)       │  │(per-run, central)│
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| CLI Interface | Parse arguments, invoke runner, display output |
| Pipeline Runner | Orchestrate execution, enforce timeouts, manage locks |
| Validators | Check pre/postconditions, return pass/fail with message |
| Tasks | User-defined work units with declared validators |
| Notifier | Abstract interface for sending failure notifications |
| Secrets Store | Encrypted storage for credentials (SFTP, API keys, etc.) |
| Run History | Persistent record of pipeline executions |
| Log Files | Per-task and per-run logging with configurable levels |

---

## 2. Data Models

### 2.1 ValidationResult

```python
@dataclass
class ValidationResult:
    passed: bool
    message: str
    validator_name: str
```

### 2.2 Validator (Abstract Base)

```python
class Validator(ABC):
    @abstractmethod
    def check(self, context: dict) -> ValidationResult:
        """Execute validation check against current context."""
        pass
    
    @property
    def name(self) -> str:
        """Human-readable validator name for logging."""
        return self.__class__.__name__
```

### 2.3 TaskConfig

```python
@dataclass
class TaskConfig:
    timeout_seconds: float = 300.0          # 5 minutes default
    retries: int = 0                         # additional attempts after first failure
    retry_delay_seconds: float = 5.0         # wait between retries
    log_level: str = "INFO"                  # DEBUG, INFO, WARNING, ERROR
    notify_on_failure: bool = True           # send notification if this task fails
```

### 2.4 TaskResult

```python
@dataclass
class TaskResult:
    success: bool
    message: str = ""
    data: dict = field(default_factory=dict)  # passed to context for subsequent tasks
    duration_seconds: float = 0.0
```

### 2.5 Task (Abstract Base)

```python
class Task(ABC):
    name: str = ""                            # override or defaults to class name
    description: str = ""                     # human-readable description for logs/UI
    preconditions: list[Validator] = []
    postconditions: list[Validator] = []
    config: TaskConfig = field(default_factory=TaskConfig)
    
    @abstractmethod
    def run(self, context: dict) -> TaskResult:
        """Execute task logic. Has access to shared context dict."""
        pass
```

### 2.6 PipelineConfig

```python
@dataclass
class PipelineConfig:
    name: str                                 # unique identifier for this pipeline
    description: str = ""
    default_timeout_seconds: float = 300.0    # applies to tasks without explicit timeout
    default_retries: int = 0
    default_log_level: str = "INFO"
    lock_retry_attempts: int = 3              # retries if pipeline already running
    lock_retry_delay_seconds: float = 60.0    # wait between lock retries
    log_directory: Path = Path("./logs")      # per-run logs stored here
    central_log_file: Path | None = None      # optional central log aggregation
    history_file: Path = Path("./run_history.json")
    notify_on_failure: bool = True
    notify_on_success: bool = False
```

### 2.7 Pipeline

```python
class Pipeline:
    config: PipelineConfig
    tasks: list[Task]
    context: dict                             # shared state across tasks
    notifier: Notifier | None                 # optional notification handler
```

### 2.8 RunRecord

```python
@dataclass
class RunRecord:
    pipeline_name: str
    run_id: str                               # UUID or timestamp-based
    start_time: datetime
    end_time: datetime | None
    status: Literal["running", "success", "failed"]
    completed_tasks: list[str]
    failed_task: str | None
    failure_reason: str
    log_file: Path
```

### 2.9 Notifier (Abstract Base)

```python
class Notifier(ABC):
    @abstractmethod
    def send(
        self,
        subject: str,
        body: str,
        severity: Literal["info", "warning", "critical"] = "critical"
    ) -> bool:
        """Send notification. Returns True if successful."""
        pass
```

### 2.10 MailNotifier (Concrete Implementation)

```python
class MailNotifier(Notifier):
    """
    Adapter for the user's existing mail sending program.
    Invokes the external mail script via subprocess or imports it directly.
    """
    
    def __init__(
        self,
        mail_script_path: Path | None = None,  # if invoking via subprocess
        mail_module: ModuleType | None = None,  # if importing directly
        default_recipient: str = "",
        throttle_seconds: float = 0             # minimum time between notifications
    ):
        pass
    
    def send(self, subject: str, body: str, severity: str = "critical") -> bool:
        # Implementation calls existing mail infrastructure
        pass
```

---

## 3. Validator Catalog

### 3.1 Environment Validators

#### VirtualEnvActive

Checks whether Python is currently running inside a virtual environment.

```python
class VirtualEnvActive(Validator):
    """
    Validates that a Python virtual environment is active.
    
    Checks for the presence of sys.prefix != sys.base_prefix (standard venv)
    or the VIRTUAL_ENV environment variable (works with most venv tools).
    
    Optionally validates that a specific venv is active by name/path.
    """
    
    def __init__(self, expected_venv_path: str | None = None):
        """
        Args:
            expected_venv_path: Optional. If provided, validates that this specific
                                venv is active (matches VIRTUAL_ENV env var or sys.prefix).
                                Can be a full path or just the venv directory name.
        """
        self.expected_venv_path = expected_venv_path
    
    def check(self, context: dict) -> ValidationResult:
        import sys
        import os
        
        # Check if any venv is active
        in_venv = sys.prefix != sys.base_prefix or os.environ.get("VIRTUAL_ENV")
        
        if not in_venv:
            return ValidationResult(
                False, 
                "No virtual environment is active", 
                self.name
            )
        
        # If specific venv required, validate it matches
        if self.expected_venv_path:
            active_venv = os.environ.get("VIRTUAL_ENV", sys.prefix)
            if self.expected_venv_path not in active_venv:
                return ValidationResult(
                    False,
                    f"Wrong venv active. Expected '{self.expected_venv_path}', "
                    f"got '{active_venv}'",
                    self.name
                )
        
        return ValidationResult(
            True,
            f"Virtual environment active: {os.environ.get('VIRTUAL_ENV', sys.prefix)}",
            self.name
        )
```

**Usage:**
```python
class MyTask(Task):
    preconditions = [
        VirtualEnvActive(),                          # any venv is fine
        # or
        VirtualEnvActive("my_project_venv"),         # specific venv required
        # or  
        VirtualEnvActive("C:/venvs/my_project"),     # full path
    ]
```

#### EnvVarSet

```python
class EnvVarSet(Validator):
    """Checks that an environment variable is set and non-empty."""
    
    def __init__(self, var_name: str):
        self.var_name = var_name
    
    def check(self, context: dict) -> ValidationResult:
        import os
        value = os.environ.get(self.var_name)
        if value:
            return ValidationResult(True, f"${self.var_name} is set", self.name)
        return ValidationResult(False, f"${self.var_name} not set or empty", self.name)
```

#### EnvVarEquals

```python
class EnvVarEquals(Validator):
    """Checks that an environment variable has a specific value."""
    
    def __init__(self, var_name: str, expected_value: str):
        self.var_name = var_name
        self.expected_value = expected_value
    
    def check(self, context: dict) -> ValidationResult:
        import os
        value = os.environ.get(self.var_name, "")
        if value == self.expected_value:
            return ValidationResult(True, f"${self.var_name} == '{self.expected_value}'", self.name)
        return ValidationResult(
            False, 
            f"${self.var_name} is '{value}', expected '{self.expected_value}'", 
            self.name
        )
```

#### PythonPackageAvailable

```python
class PythonPackageAvailable(Validator):
    """Checks that a Python package can be imported."""
    
    def __init__(self, package_name: str, min_version: str | None = None):
        self.package_name = package_name
        self.min_version = min_version
    
    def check(self, context: dict) -> ValidationResult:
        try:
            module = importlib.import_module(self.package_name)
            if self.min_version:
                from packaging import version
                actual = getattr(module, "__version__", "0.0.0")
                if version.parse(actual) < version.parse(self.min_version):
                    return ValidationResult(
                        False,
                        f"{self.package_name} version {actual} < required {self.min_version}",
                        self.name
                    )
            return ValidationResult(True, f"{self.package_name} is available", self.name)
        except ImportError:
            return ValidationResult(False, f"{self.package_name} not installed", self.name)
```

### 3.2 File System Validators

#### FileExists

```python
class FileExists(Validator):
    """Checks that a file exists at the specified path."""
    
    def __init__(self, path: str | Path, from_context: bool = False):
        """
        Args:
            path: File path, or context key if from_context=True
            from_context: If True, 'path' is a key to look up in context dict
        """
        self.path = path
        self.from_context = from_context
    
    def check(self, context: dict) -> ValidationResult:
        path = Path(context.get(self.path, self.path) if self.from_context else self.path)
        if path.is_file():
            return ValidationResult(True, f"File exists: {path}", self.name)
        return ValidationResult(False, f"File not found: {path}", self.name)
```

#### DirectoryExists

```python
class DirectoryExists(Validator):
    """Checks that a directory exists at the specified path."""
    
    def __init__(self, path: str | Path):
        self.path = Path(path)
    
    def check(self, context: dict) -> ValidationResult:
        if self.path.is_dir():
            return ValidationResult(True, f"Directory exists: {self.path}", self.name)
        return ValidationResult(False, f"Directory not found: {self.path}", self.name)
```

#### FileModifiedWithin

```python
class FileModifiedWithin(Validator):
    """Checks that a file was modified within a specified time window."""
    
    def __init__(self, path: str | Path, max_age: timedelta):
        self.path = Path(path)
        self.max_age = max_age
    
    def check(self, context: dict) -> ValidationResult:
        if not self.path.exists():
            return ValidationResult(False, f"File not found: {self.path}", self.name)
        
        mtime = datetime.fromtimestamp(self.path.stat().st_mtime)
        age = datetime.now() - mtime
        
        if age <= self.max_age:
            return ValidationResult(True, f"{self.path} modified {age} ago", self.name)
        return ValidationResult(
            False, 
            f"{self.path} is {age} old, exceeds max age {self.max_age}", 
            self.name
        )
```

#### FileSizeInRange

```python
class FileSizeInRange(Validator):
    """Checks that a file's size falls within an expected range."""
    
    def __init__(self, path: str | Path, min_bytes: int = 0, max_bytes: int | None = None):
        self.path = Path(path)
        self.min_bytes = min_bytes
        self.max_bytes = max_bytes
    
    def check(self, context: dict) -> ValidationResult:
        if not self.path.exists():
            return ValidationResult(False, f"File not found: {self.path}", self.name)
        
        size = self.path.stat().st_size
        
        if size < self.min_bytes:
            return ValidationResult(
                False,
                f"{self.path} is {size} bytes, below minimum {self.min_bytes}",
                self.name
            )
        
        if self.max_bytes is not None and size > self.max_bytes:
            return ValidationResult(
                False,
                f"{self.path} is {size} bytes, exceeds maximum {self.max_bytes}",
                self.name
            )
        
        return ValidationResult(True, f"{self.path} is {size} bytes", self.name)
```

### 3.3 Tabular File Validators

#### TabularFileValid

Validates CSV and Excel files for required headers and presence of data rows.

```python
class TabularFileValid(Validator):
    """
    Validates that a CSV or Excel file has required headers and contains data.
    
    Supports .csv, .xlsx, and .xls files. Automatically detects format by extension.
    """
    
    def __init__(
        self,
        path: str | Path,
        required_headers: list[str] | None = None,
        min_data_rows: int = 1,
        sheet_name: str | int = 0,               # for Excel files
        case_sensitive_headers: bool = False,
        from_context: bool = False               # if True, path is a context key
    ):
        """
        Args:
            path: File path or context key
            required_headers: List of column names that must be present. 
                              If None, only checks that file has headers and data.
            min_data_rows: Minimum number of data rows (excluding header). Default 1.
            sheet_name: For Excel files, which sheet to validate. Default is first sheet.
            case_sensitive_headers: Whether header matching is case-sensitive.
            from_context: If True, 'path' is looked up in the context dict.
        """
        self.path = path
        self.required_headers = required_headers
        self.min_data_rows = min_data_rows
        self.sheet_name = sheet_name
        self.case_sensitive_headers = case_sensitive_headers
        self.from_context = from_context
    
    def check(self, context: dict) -> ValidationResult:
        path = Path(context.get(self.path, self.path) if self.from_context else self.path)
        
        if not path.exists():
            return ValidationResult(False, f"File not found: {path}", self.name)
        
        try:
            headers, row_count = self._read_file(path)
        except Exception as e:
            return ValidationResult(False, f"Failed to read {path}: {e}", self.name)
        
        # Check headers exist
        if not headers:
            return ValidationResult(False, f"{path} has no headers", self.name)
        
        # Check required headers present
        if self.required_headers:
            if self.case_sensitive_headers:
                actual = set(headers)
                required = set(self.required_headers)
            else:
                actual = set(h.lower() for h in headers)
                required = set(h.lower() for h in self.required_headers)
            
            missing = required - actual
            if missing:
                return ValidationResult(
                    False,
                    f"{path} missing required headers: {missing}",
                    self.name
                )
        
        # Check data rows
        if row_count < self.min_data_rows:
            return ValidationResult(
                False,
                f"{path} has {row_count} data rows, minimum required is {self.min_data_rows}",
                self.name
            )
        
        return ValidationResult(
            True,
            f"{path} valid: {len(headers)} columns, {row_count} data rows",
            self.name
        )
    
    def _read_file(self, path: Path) -> tuple[list[str], int]:
        """Returns (headers, data_row_count)."""
        suffix = path.suffix.lower()
        
        if suffix == ".csv":
            return self._read_csv(path)
        elif suffix in (".xlsx", ".xls"):
            return self._read_excel(path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    def _read_csv(self, path: Path) -> tuple[list[str], int]:
        import csv
        with open(path, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            row_count = sum(1 for row in reader if any(cell.strip() for cell in row))
        return headers, row_count
    
    def _read_excel(self, path: Path) -> tuple[list[str], int]:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        
        if isinstance(self.sheet_name, int):
            sheet = wb.worksheets[self.sheet_name]
        else:
            sheet = wb[self.sheet_name]
        
        rows = list(sheet.iter_rows(values_only=True))
        wb.close()
        
        if not rows:
            return [], 0
        
        headers = [str(h) if h is not None else "" for h in rows[0]]
        
        # Count non-empty data rows
        data_rows = rows[1:]
        row_count = sum(1 for row in data_rows if any(cell is not None for cell in row))
        
        return headers, row_count
```

**Usage Examples:**

```python
class ProcessSalesData(Task):
    preconditions = [
        # Input file must have these columns and at least one row of data
        TabularFileValid(
            "data/sales_input.csv",
            required_headers=["date", "product_id", "quantity", "price"],
            min_data_rows=1
        ),
    ]
    postconditions = [
        # Output file must have report columns and data
        TabularFileValid(
            "reports/sales_summary.xlsx",
            required_headers=["product_id", "total_quantity", "total_revenue"],
            min_data_rows=1,
            sheet_name="Summary"
        ),
    ]
```

```python
# Just check that file has headers and is not empty (no specific headers required)
TabularFileValid("output.csv", min_data_rows=1)

# Check headers case-insensitively
TabularFileValid(
    "data.xlsx",
    required_headers=["Customer ID", "Order Date"],
    case_sensitive_headers=False  # will match "customer id", "CUSTOMER ID", etc.
)

# Path comes from previous task's output stored in context
TabularFileValid("output_file_path", from_context=True, required_headers=["id", "value"])
```

#### TabularFileRowCount

For cases where you need to validate a specific row count range.

```python
class TabularFileRowCount(Validator):
    """Validates that a tabular file has a row count within expected range."""
    
    def __init__(
        self,
        path: str | Path,
        min_rows: int = 0,
        max_rows: int | None = None,
        sheet_name: str | int = 0
    ):
        self.path = Path(path)
        self.min_rows = min_rows
        self.max_rows = max_rows
        self.sheet_name = sheet_name
    
    def check(self, context: dict) -> ValidationResult:
        # Implementation similar to TabularFileValid._read_file
        # Returns pass/fail based on row count range
        pass
```

### 3.4 Network/Service Validators

#### HostReachable

```python
class HostReachable(Validator):
    """Checks that a host is reachable via TCP connection."""
    
    def __init__(self, host: str, port: int, timeout_seconds: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout_seconds
    
    def check(self, context: dict) -> ValidationResult:
        import socket
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.close()
            return ValidationResult(True, f"{self.host}:{self.port} is reachable", self.name)
        except (socket.timeout, socket.error) as e:
            return ValidationResult(False, f"Cannot reach {self.host}:{self.port}: {e}", self.name)
```

#### SFTPConnectable

```python
class SFTPConnectable(Validator):
    """Validates that SFTP connection can be established using stored credentials."""
    
    def __init__(self, connection_name: str):
        """
        Args:
            connection_name: Key in secrets store for SFTP credentials
        """
        self.connection_name = connection_name
    
    def check(self, context: dict) -> ValidationResult:
        from harness.secrets import get_secret
        import paramiko
        
        try:
            creds = get_secret(self.connection_name)
            transport = paramiko.Transport((creds["host"], creds.get("port", 22)))
            transport.connect(username=creds["username"], password=creds["password"])
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.close()
            transport.close()
            return ValidationResult(True, f"SFTP connection '{self.connection_name}' OK", self.name)
        except Exception as e:
            return ValidationResult(
                False, 
                f"SFTP connection '{self.connection_name}' failed: {e}", 
                self.name
            )
```

### 3.5 Process Validators

#### CommandAvailable

```python
class CommandAvailable(Validator):
    """Checks that an external command is available in PATH."""
    
    def __init__(self, command: str):
        self.command = command
    
    def check(self, context: dict) -> ValidationResult:
        import shutil
        if shutil.which(self.command):
            return ValidationResult(True, f"Command '{self.command}' found", self.name)
        return ValidationResult(False, f"Command '{self.command}' not in PATH", self.name)
```

### 3.6 Composite Validators

#### AnyOf

```python
class AnyOf(Validator):
    """Passes if any of the child validators pass."""
    
    def __init__(self, *validators: Validator):
        self.validators = validators
    
    def check(self, context: dict) -> ValidationResult:
        failures = []
        for v in self.validators:
            result = v.check(context)
            if result.passed:
                return ValidationResult(True, f"Passed: {result.message}", self.name)
            failures.append(f"{v.name}: {result.message}")
        return ValidationResult(False, f"All failed: {'; '.join(failures)}", self.name)
```

#### AllOf

```python
class AllOf(Validator):
    """Passes only if all child validators pass. Useful for grouping with custom name."""
    
    def __init__(self, *validators: Validator, name: str = "AllOf"):
        self.validators = validators
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    def check(self, context: dict) -> ValidationResult:
        for v in self.validators:
            result = v.check(context)
            if not result.passed:
                return ValidationResult(False, f"{v.name}: {result.message}", self.name)
        return ValidationResult(True, "All validations passed", self.name)
```

---

## 4. Notification System

### 4.1 Interface

```python
class Notifier(ABC):
    @abstractmethod
    def send(
        self,
        subject: str,
        body: str,
        severity: Literal["info", "warning", "critical"] = "critical"
    ) -> bool:
        """
        Send a notification.
        
        Args:
            subject: Short summary (email subject or message title)
            body: Full notification content
            severity: Importance level (may affect delivery or formatting)
        
        Returns:
            True if notification was sent successfully
        """
        pass
```

### 4.2 Mail Notifier Implementation

```python
class MailNotifier(Notifier):
    """
    Integrates with user's existing mail sending script/module.
    """
    
    def __init__(
        self,
        send_function: Callable[[str, str, str], bool] | None = None,
        mail_script_path: Path | None = None,
        default_recipient: str = "",
    ):
        """
        Two modes of operation:
        
        1. Direct function: Pass a callable that sends mail
           send_function(recipient, subject, body) -> bool
        
        2. Script invocation: Pass path to existing mail script
           Script will be called as: python script.py --to <recipient> --subject <subject> --body <body>
        """
        self.send_function = send_function
        self.mail_script_path = mail_script_path
        self.default_recipient = default_recipient
    
    def send(self, subject: str, body: str, severity: str = "critical") -> bool:
        prefixed_subject = f"[{severity.upper()}] {subject}"
        
        if self.send_function:
            return self.send_function(self.default_recipient, prefixed_subject, body)
        
        if self.mail_script_path:
            import subprocess
            result = subprocess.run(
                [
                    "python", str(self.mail_script_path),
                    "--to", self.default_recipient,
                    "--subject", prefixed_subject,
                    "--body", body
                ],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        
        raise RuntimeError("MailNotifier not configured: provide send_function or mail_script_path")
```

### 4.3 Notification Triggers

The Pipeline Runner sends notifications based on `PipelineConfig` settings:

| Trigger | Config Field | Default |
|---------|--------------|---------|
| Any task fails (after retries exhausted) | `notify_on_failure` | True |
| Pipeline completes successfully | `notify_on_success` | False |
| Task-level override | `TaskConfig.notify_on_failure` | True |

### 4.4 Notification Content Template

```
Subject: [CRITICAL] Pipeline 'daily_report' failed at task 'fetch_sftp_data'

Pipeline: daily_report
Status: FAILED
Run ID: 20240115-143022-a1b2c3
Started: 2024-01-15 14:30:22
Failed at: 2024-01-15 14:32:15

Failed Task: fetch_sftp_data
Failure Reason: Postcondition failed: FileExists - File not found: data/raw_input.csv

Completed Tasks:
  ✓ validate_environment
  ✓ check_sftp_connection

Log File: C:\pipelines\daily_report\logs\20240115-143022.log
```

---

## 5. Secrets Store

### 5.1 Design

Encrypted JSON file storing credentials for external services. Uses `cryptography` library with Fernet symmetric encryption.

**Master key handling options:**
1. Environment variable (`HARNESS_SECRETS_KEY`)
2. Windows Credential Manager (via `keyring` library)
3. File-based (less secure, for development only)

### 5.2 Interface

```python
# secrets.py

def init_secrets_store(store_path: Path, key_source: str = "env") -> None:
    """Initialize or load secrets store."""
    pass

def set_secret(name: str, value: dict) -> None:
    """Store a secret (e.g., SFTP credentials)."""
    pass

def get_secret(name: str) -> dict:
    """Retrieve a secret by name. Raises KeyError if not found."""
    pass

def delete_secret(name: str) -> None:
    """Remove a secret."""
    pass

def list_secrets() -> list[str]:
    """List all secret names (not values)."""
    pass
```

### 5.3 Credential Structure

```python
# SFTP credentials example
set_secret("sftp_vendor_upload", {
    "host": "sftp.vendor.com",
    "port": 22,
    "username": "uploader",
    "password": "secretpass",
    # or
    "private_key_path": "C:/keys/vendor_rsa",
    "private_key_passphrase": "keypass"
})

# API credentials example
set_secret("api_reporting_service", {
    "base_url": "https://api.example.com",
    "api_key": "ak_live_xxxxx",
    "api_secret": "sk_live_xxxxx"
})
```

### 5.4 CLI for Secrets Management

```
harness secrets set <name>        # prompts for JSON input
harness secrets get <name>        # prints secret (requires confirmation)
harness secrets list              # shows secret names only
harness secrets delete <name>
harness secrets init              # create new secrets store with new key
```

---

## 6. Concurrency Control

### 6.1 Lock Mechanism

File-based locking to prevent concurrent pipeline execution.

```python
class PipelineLock:
    """
    File-based lock to prevent concurrent pipeline runs.
    
    Creates a .lock file containing PID and start time.
    On acquisition, checks if existing lock is stale (process dead).
    """
    
    def __init__(
        self, 
        pipeline_name: str, 
        lock_dir: Path = Path("./locks"),
        retry_attempts: int = 3,
        retry_delay_seconds: float = 60.0
    ):
        self.lock_file = lock_dir / f"{pipeline_name}.lock"
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay_seconds
    
    def acquire(self) -> bool:
        """
        Attempt to acquire lock with retries.
        Returns True if lock acquired, False if another instance is running.
        """
        pass
    
    def release(self) -> None:
        """Release the lock."""
        pass
    
    def is_stale(self) -> bool:
        """Check if existing lock is from a dead process."""
        pass
    
    def __enter__(self):
        if not self.acquire():
            raise PipelineAlreadyRunningError(f"Pipeline locked: {self.lock_file}")
        return self
    
    def __exit__(self, *args):
        self.release()
```

### 6.2 Lock File Format

```json
{
    "pid": 12345,
    "started": "2024-01-15T14:30:22",
    "hostname": "WORKSTATION01"
}
```

---

## 7. Run History

### 7.1 Storage Format

JSON Lines file (one JSON object per line) for simple append-only storage.

```
{"pipeline_name": "daily_report", "run_id": "20240115-143022-a1b2c3", "start_time": "2024-01-15T14:30:22", "end_time": "2024-01-15T14:35:10", "status": "success", "completed_tasks": ["validate_env", "fetch_data", "process", "upload"], "failed_task": null, "failure_reason": "", "log_file": "logs/20240115-143022.log"}
{"pipeline_name": "daily_report", "run_id": "20240116-143018-d4e5f6", "start_time": "2024-01-16T14:30:18", "end_time": "2024-01-16T14:32:45", "status": "failed", "completed_tasks": ["validate_env", "fetch_data"], "failed_task": "process", "failure_reason": "Postcondition failed: TabularFileValid - output.csv missing required headers: {'revenue'}", "log_file": "logs/20240116-143018.log"}
```

### 7.2 History API

```python
class RunHistory:
    def __init__(self, history_file: Path):
        self.history_file = history_file
    
    def record(self, run: RunRecord) -> None:
        """Append a run record."""
        pass
    
    def get_recent(self, pipeline_name: str | None = None, limit: int = 10) -> list[RunRecord]:
        """Get recent runs, optionally filtered by pipeline."""
        pass
    
    def get_by_id(self, run_id: str) -> RunRecord | None:
        """Look up specific run."""
        pass
```

---

## 8. Logging

### 8.1 Log Structure

Each pipeline run creates a log file in the configured log directory:

```
logs/
├── daily_report/
│   ├── 20240115-143022.log
│   ├── 20240116-143018.log
│   └── ...
└── weekly_summary/
    ├── 20240113-080000.log
    └── ...
```

### 8.2 Log Format

```
2024-01-15 14:30:22 [INFO] [Pipeline] Starting pipeline: daily_report
2024-01-15 14:30:22 [INFO] [Pipeline] Run ID: 20240115-143022-a1b2c3
2024-01-15 14:30:22 [INFO] [validate_env] Running task
2024-01-15 14:30:22 [DEBUG] [validate_env] Checking precondition: VirtualEnvActive
2024-01-15 14:30:22 [DEBUG] [validate_env] VirtualEnvActive passed: Virtual environment active: C:\venvs\reporting
2024-01-15 14:30:22 [INFO] [validate_env] Task completed in 0.02s
2024-01-15 14:30:23 [INFO] [fetch_sftp_data] Running task
2024-01-15 14:30:23 [DEBUG] [fetch_sftp_data] Checking precondition: SFTPConnectable
2024-01-15 14:30:25 [INFO] [fetch_sftp_data] Downloaded 3 files from SFTP
2024-01-15 14:30:25 [DEBUG] [fetch_sftp_data] Checking postcondition: TabularFileValid
2024-01-15 14:30:25 [INFO] [fetch_sftp_data] Task completed in 2.31s
```

### 8.3 Central Log Aggregation (Optional)

If `PipelineConfig.central_log_file` is set, all runs also append to a single file for easier searching across runs.

### 8.4 Per-Task Log Levels

```python
class FetchData(Task):
    config = TaskConfig(log_level="DEBUG")  # verbose logging for this task

class ProcessData(Task):
    config = TaskConfig(log_level="WARNING")  # only warnings and errors
```

---

## 9. CLI Interface

### 9.1 Commands

```
harness run <pipeline> [OPTIONS]
    Run a pipeline.
    
    Options:
        --dry-run           Validate all pre/postconditions without executing tasks
        --start-from TASK   Skip tasks before TASK (useful after manual intervention)
        --force             Ignore concurrency lock (dangerous)
        --context KEY=VAL   Pass initial context values (can repeat)

harness list
    List all available pipelines.

harness show <pipeline>
    Show pipeline details: tasks, validators, configuration.

harness history [OPTIONS]
    Show run history.
    
    Options:
        --pipeline NAME     Filter by pipeline name
        --limit N           Number of records (default 10)
        --status STATUS     Filter by status (success/failed)

harness force-complete <pipeline> <task>
    Mark a task as complete without running it.
    Creates a marker file that the runner checks.
    Next run will skip this task if marker exists.
    
    Options:
        --clear             Remove force-complete marker

harness secrets <subcommand>
    Manage secrets store. See section 5.4.
```

### 9.2 Example Usage

```powershell
# Normal run
harness run daily_report

# Dry run to check validators
harness run daily_report --dry-run

# After manually fixing an issue, restart from failed task
harness run daily_report --start-from process_data

# Pass runtime context
harness run daily_report --context report_date=2024-01-15

# Check what happened
harness history --pipeline daily_report --limit 5

# Mark a task complete so next run skips it
harness force-complete daily_report fetch_sftp_data
```

---

## 10. File/Directory Structure

```
task_harness/
├── harness/
│   ├── __init__.py
│   ├── cli.py                    # CLI entry point (argparse or click)
│   ├── runner.py                 # Pipeline and task execution logic
│   ├── validators/
│   │   ├── __init__.py           # exports all validators
│   │   ├── base.py               # Validator ABC, ValidationResult
│   │   ├── environment.py        # VirtualEnvActive, EnvVarSet, etc.
│   │   ├── filesystem.py         # FileExists, FileModifiedWithin, etc.
│   │   ├── tabular.py            # TabularFileValid, TabularFileRowCount
│   │   ├── network.py            # HostReachable, SFTPConnectable
│   │   └── composite.py          # AnyOf, AllOf
│   ├── task.py                   # Task ABC, TaskConfig, TaskResult
│   ├── pipeline.py               # Pipeline, PipelineConfig
│   ├── notification.py           # Notifier ABC, MailNotifier
│   ├── secrets.py                # Secrets store
│   ├── locking.py                # PipelineLock
│   ├── history.py                # RunHistory, RunRecord
│   └── logging_setup.py          # Configure logging for runs
├── pipelines/
│   ├── __init__.py
│   ├── daily_report.py           # Example pipeline definition
│   └── weekly_summary.py         # Another pipeline
├── logs/                         # Created at runtime
├── locks/                        # Created at runtime
├── run_history.jsonl             # Created at runtime
├── secrets.enc                   # Created via CLI
├── pyproject.toml                # Project config, dependencies
└── README.md
```

---

## 11. Example Pipeline Definition

```python
# pipelines/daily_report.py

from datetime import timedelta
from pathlib import Path

from harness.task import Task, TaskConfig, TaskResult
from harness.pipeline import Pipeline, PipelineConfig
from harness.validators import (
    VirtualEnvActive,
    EnvVarSet,
    FileExists,
    DirectoryExists,
    TabularFileValid,
    SFTPConnectable,
)
from harness.notification import MailNotifier
from harness.secrets import get_secret


# ============ Tasks ============

class ValidateEnvironment(Task):
    name = "validate_environment"
    description = "Check that runtime environment is correctly configured"
    preconditions = [
        VirtualEnvActive("reporting_venv"),
        EnvVarSet("HARNESS_SECRETS_KEY"),
        DirectoryExists(Path("./data")),
        DirectoryExists(Path("./output")),
    ]
    
    def run(self, context: dict) -> TaskResult:
        # Nothing to do, validators handle everything
        return TaskResult(success=True)


class FetchSFTPData(Task):
    name = "fetch_sftp_data"
    description = "Download latest data files from vendor SFTP"
    config = TaskConfig(
        timeout_seconds=120.0,
        retries=2,
        retry_delay_seconds=30.0,
        log_level="DEBUG"
    )
    preconditions = [
        SFTPConnectable("sftp_vendor"),
    ]
    postconditions = [
        FileExists("data/vendor_data.csv"),
        TabularFileValid(
            "data/vendor_data.csv",
            required_headers=["order_id", "product_sku", "quantity", "price", "order_date"],
            min_data_rows=1
        ),
    ]
    
    def run(self, context: dict) -> TaskResult:
        import paramiko
        
        creds = get_secret("sftp_vendor")
        
        transport = paramiko.Transport((creds["host"], creds.get("port", 22)))
        transport.connect(username=creds["username"], password=creds["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        sftp.get("/outbound/daily_orders.csv", "data/vendor_data.csv")
        
        sftp.close()
        transport.close()
        
        return TaskResult(
            success=True,
            message="Downloaded vendor_data.csv",
            data={"sftp_file_count": 1}
        )


class ProcessData(Task):
    name = "process_data"
    description = "Transform raw vendor data into report format"
    config = TaskConfig(timeout_seconds=60.0)
    preconditions = [
        TabularFileValid(
            "data/vendor_data.csv",
            required_headers=["order_id", "product_sku", "quantity", "price"],
            min_data_rows=1
        ),
    ]
    postconditions = [
        TabularFileValid(
            "output/daily_summary.xlsx",
            required_headers=["product_sku", "total_quantity", "total_revenue"],
            min_data_rows=1
        ),
    ]
    
    def run(self, context: dict) -> TaskResult:
        import pandas as pd
        
        df = pd.read_csv("data/vendor_data.csv")
        
        summary = df.groupby("product_sku").agg(
            total_quantity=("quantity", "sum"),
            total_revenue=("price", "sum")
        ).reset_index()
        
        summary.to_excel("output/daily_summary.xlsx", index=False)
        
        return TaskResult(
            success=True,
            message=f"Processed {len(df)} orders into {len(summary)} product summaries",
            data={"order_count": len(df), "product_count": len(summary)}
        )


class SendReport(Task):
    name = "send_report"
    description = "Email the daily report to stakeholders"
    config = TaskConfig(notify_on_failure=True)
    preconditions = [
        FileExists("output/daily_summary.xlsx"),
    ]
    
    def run(self, context: dict) -> TaskResult:
        # Integration with existing mail system
        from my_mail_module import send_mail
        
        order_count = context.get("order_count", "N/A")
        
        send_mail(
            to="team@company.com",
            subject=f"Daily Sales Report - {order_count} orders processed",
            body="Please find attached the daily sales summary.",
            attachments=["output/daily_summary.xlsx"]
        )
        
        return TaskResult(success=True, message="Report emailed")


# ============ Pipeline Definition ============

def create_pipeline() -> Pipeline:
    config = PipelineConfig(
        name="daily_report",
        description="Fetch vendor data, process, and email daily summary",
        default_timeout_seconds=300.0,
        lock_retry_attempts=3,
        lock_retry_delay_seconds=60.0,
        log_directory=Path("./logs/daily_report"),
        history_file=Path("./run_history.jsonl"),
        notify_on_failure=True,
        notify_on_success=False,
    )
    
    notifier = MailNotifier(
        mail_script_path=Path("./scripts/send_mail.py"),
        default_recipient="ops@company.com"
    )
    
    return Pipeline(
        config=config,
        tasks=[
            ValidateEnvironment(),
            FetchSFTPData(),
            ProcessData(),
            SendReport(),
        ],
        notifier=notifier,
    )
```

---

## 12. Dependencies

```toml
# pyproject.toml

[project]
name = "task-harness"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "cryptography>=41.0",      # secrets encryption
    "paramiko>=3.0",           # SFTP connectivity
    "openpyxl>=3.1",           # Excel file validation
    "keyring>=24.0",           # Windows credential manager (optional)
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
]

[project.scripts]
harness = "harness.cli:main"
```

---

## 13. Implementation Notes for Claude Code

1. **Start with core abstractions**: Implement `Validator`, `Task`, `Pipeline`, `RunRecord` classes first. Get a minimal pipeline running before adding features.

2. **Validators are independent**: Each validator should be fully testable in isolation. Write unit tests for each.

3. **Timeout implementation**: Use `concurrent.futures.ThreadPoolExecutor` with `future.result(timeout=X)` for task timeouts. Catch `TimeoutError` and treat as failure.

4. **Lock file robustness**: Handle stale locks by checking if the PID is still running (`psutil.pid_exists()` or checking `/proc` on Linux, `tasklist` on Windows).

5. **Secrets store**: Use `cryptography.fernet.Fernet` for encryption. Key derivation from password: `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC`.

6. **CLI framework**: `argparse` is fine for this scope. `click` is cleaner if you want to add a dependency.

7. **Windows paths**: Use `pathlib.Path` everywhere. Avoid hardcoded slashes.

8. **TabularFileValid**: Depends on `openpyxl` for Excel. For CSV, use stdlib `csv`. Consider `pandas` as optional optimization for large files.

9. **Testing strategy**: 
   - Unit tests for validators (mock file system, mock network)
   - Integration test with a simple 2-task pipeline
   - Test timeout behavior with a deliberately slow task

10. **Error messages**: Make validator failure messages actionable. "File not found: data/input.csv" is better than "Precondition failed".

---

## 14. Future Enhancements (Out of Scope for Initial Build)

- DAG-based parallel execution
- Web dashboard for run history
- Remote execution via SSH
- Pipeline scheduling (built-in cron alternative)
- Webhook notifications (Slack, Teams)
- Metrics export (Prometheus)
