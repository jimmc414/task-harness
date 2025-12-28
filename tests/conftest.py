"""Common test fixtures for Task Harness tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Generator
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from harness.models import PipelineConfig, TaskConfig


# --------------------------------------------------------------------------
# Path fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def temp_harness_root(tmp_path: Path) -> Path:
    """Create a temporary harness root with pipelines/ directory."""
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "__init__.py").write_text("")
    return tmp_path


@pytest.fixture
def temp_pipelines_dir(temp_harness_root: Path) -> Path:
    """Return the pipelines directory within temp harness root."""
    return temp_harness_root / "pipelines"


@pytest.fixture
def temp_logs_dir(temp_harness_root: Path) -> Path:
    """Create and return a temporary logs directory."""
    logs_dir = temp_harness_root / "logs"
    logs_dir.mkdir()
    return logs_dir


@pytest.fixture
def temp_locks_dir(temp_harness_root: Path) -> Path:
    """Create and return a temporary locks directory."""
    locks_dir = temp_harness_root / "locks"
    locks_dir.mkdir()
    return locks_dir


@pytest.fixture
def temp_data_dir(temp_harness_root: Path) -> Path:
    """Create and return a temporary data directory."""
    data_dir = temp_harness_root / "data"
    data_dir.mkdir()
    return data_dir


# --------------------------------------------------------------------------
# File fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def sample_csv_file(temp_data_dir: Path) -> Path:
    """Create a sample CSV file for testing."""
    csv_file = temp_data_dir / "sample.csv"
    csv_file.write_text("id,name,value\n1,foo,100\n2,bar,200\n3,baz,300\n")
    return csv_file


@pytest.fixture
def sample_csv_utf8_bom(temp_data_dir: Path) -> Path:
    """Create a CSV file with UTF-8 BOM."""
    csv_file = temp_data_dir / "sample_bom.csv"
    content = "id,name,value\n1,foo,100\n"
    csv_file.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    return csv_file


@pytest.fixture
def sample_excel_file(temp_data_dir: Path) -> Path:
    """Create a sample Excel file for testing."""
    try:
        import openpyxl

        xlsx_file = temp_data_dir / "sample.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["id", "name", "value"])
        ws.append([1, "foo", 100])
        ws.append([2, "bar", 200])
        wb.save(xlsx_file)
        return xlsx_file
    except ImportError:
        pytest.skip("openpyxl not installed")


@pytest.fixture
def empty_file(temp_data_dir: Path) -> Path:
    """Create an empty file."""
    empty = temp_data_dir / "empty.txt"
    empty.touch()
    return empty


# --------------------------------------------------------------------------
# Environment fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def clean_env() -> Generator[dict, None, None]:
    """Provide a clean copy of environment, restore after test."""
    original_env = os.environ.copy()
    yield os.environ
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate running inside a virtual environment."""
    monkeypatch.setattr(sys, "prefix", "/path/to/venv")
    monkeypatch.setattr(sys, "base_prefix", "/usr")


@pytest.fixture
def mock_no_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate running outside any virtual environment."""
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)


# --------------------------------------------------------------------------
# Network mocks
# --------------------------------------------------------------------------


@pytest.fixture
def mock_socket_success() -> Generator[MagicMock, None, None]:
    """Mock socket.create_connection to succeed."""
    with patch("socket.create_connection") as mock:
        mock_socket = MagicMock()
        mock_socket.close = MagicMock()
        mock.return_value = mock_socket
        yield mock


@pytest.fixture
def mock_socket_failure() -> Generator[MagicMock, None, None]:
    """Mock socket.create_connection to fail."""
    with patch("socket.create_connection") as mock:
        mock.side_effect = ConnectionRefusedError("Connection refused")
        yield mock


@pytest.fixture
def mock_sftp_success() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Mock paramiko Transport and SFTPClient to succeed."""
    with patch("paramiko.Transport") as mock_transport_cls:
        mock_transport = MagicMock()
        mock_transport_cls.return_value = mock_transport
        mock_transport.is_active.return_value = True

        with patch("paramiko.SFTPClient.from_transport") as mock_sftp:
            mock_sftp_client = MagicMock()
            mock_sftp.return_value = mock_sftp_client
            yield mock_transport, mock_sftp_client


@pytest.fixture
def mock_sftp_failure() -> Generator[MagicMock, None, None]:
    """Mock paramiko Transport to fail connection."""
    with patch("paramiko.Transport") as mock_transport_cls:
        mock_transport_cls.side_effect = Exception("Connection failed")
        yield mock_transport_cls


# --------------------------------------------------------------------------
# Secrets mocks
# --------------------------------------------------------------------------


@pytest.fixture
def mock_secrets_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a mock Fernet key via environment variable."""
    # This is a valid Fernet key (base64-encoded 32 bytes)
    key = "dGVzdC1rZXktZm9yLXRlc3RpbmctMTIzNDU2Nzg5MA=="
    # Generate a proper Fernet key
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HARNESS_SECRETS_KEY", key)
    return key


@pytest.fixture
def mock_keyring() -> Generator[MagicMock, None, None]:
    """Mock keyring module."""
    with patch.dict("sys.modules", {"keyring": MagicMock()}):
        import keyring

        keyring.get_password = MagicMock(return_value=None)
        keyring.set_password = MagicMock()
        yield keyring


@pytest.fixture
def temp_secrets_file(temp_harness_root: Path) -> Path:
    """Create .harness directory and return secrets file path."""
    harness_dir = temp_harness_root / ".harness"
    harness_dir.mkdir()
    return harness_dir / "secrets.enc"


# --------------------------------------------------------------------------
# History fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def temp_history_file(temp_harness_root: Path) -> Path:
    """Return path to temporary history file."""
    return temp_harness_root / "run_history.jsonl"


@pytest.fixture
def sample_history_file(temp_history_file: Path) -> Path:
    """Create a sample history file with some records."""
    records = [
        {
            "run_id": "run-001",
            "pipeline_name": "test_pipeline",
            "status": "success",
            "started_at": "2024-01-15T10:00:00+00:00",
            "completed_at": "2024-01-15T10:01:00+00:00",
            "tasks_completed": 3,
            "tasks_failed": 0,
            "error_message": None,
        },
        {
            "run_id": "run-002",
            "pipeline_name": "test_pipeline",
            "status": "failed",
            "started_at": "2024-01-15T11:00:00+00:00",
            "completed_at": "2024-01-15T11:00:30+00:00",
            "tasks_completed": 1,
            "tasks_failed": 1,
            "error_message": "Task 'process_data' failed",
        },
    ]
    with open(temp_history_file, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return temp_history_file


# --------------------------------------------------------------------------
# Lock fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def temp_lock_file(temp_locks_dir: Path) -> Path:
    """Return path to a temporary lock file."""
    return temp_locks_dir / "test_pipeline.lock"


@pytest.fixture
def active_lock_file(temp_lock_file: Path) -> Path:
    """Create a lock file for the current process."""
    import socket
    from datetime import datetime, timezone

    lock_data = {
        "pid": os.getpid(),
        "started": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
    }
    temp_lock_file.write_text(json.dumps(lock_data))
    return temp_lock_file


@pytest.fixture
def stale_lock_file(temp_lock_file: Path) -> Path:
    """Create a lock file with a non-existent PID."""
    import socket
    from datetime import datetime, timezone

    lock_data = {
        "pid": 999999,  # Very unlikely to be a real PID
        "started": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
    }
    temp_lock_file.write_text(json.dumps(lock_data))
    return temp_lock_file


# --------------------------------------------------------------------------
# Command fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def mock_which_found() -> Generator[MagicMock, None, None]:
    """Mock shutil.which to find a command."""
    with patch("shutil.which") as mock:
        mock.return_value = "/usr/bin/test_command"
        yield mock


@pytest.fixture
def mock_which_not_found() -> Generator[MagicMock, None, None]:
    """Mock shutil.which to not find a command."""
    with patch("shutil.which") as mock:
        mock.return_value = None
        yield mock


# --------------------------------------------------------------------------
# Pipeline fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def sample_pipeline_code() -> str:
    """Return Python code for a simple test pipeline."""
    return '''
from harness import Pipeline, PipelineConfig, Task, TaskResult, TaskConfig
from harness.validators import FileExists

class ValidateTask(Task):
    name = "validate"
    description = "Validation task"

    def run(self, context: dict) -> TaskResult:
        return TaskResult(success=True, message="Validated")


class ProcessTask(Task):
    name = "process"
    description = "Processing task"
    config = TaskConfig(timeout_seconds=10.0)

    def run(self, context: dict) -> TaskResult:
        context["processed"] = True
        return TaskResult(success=True, message="Processed", data={"count": 42})


def create_pipeline() -> Pipeline:
    return Pipeline(
        config=PipelineConfig(
            name="test_pipeline",
            description="A test pipeline",
        ),
        tasks=[
            ValidateTask(),
            ProcessTask(),
        ],
    )
'''


@pytest.fixture
def temp_pipeline_module(temp_pipelines_dir: Path, sample_pipeline_code: str) -> Path:
    """Create a test pipeline module file."""
    pipeline_file = temp_pipelines_dir / "test_pipeline.py"
    pipeline_file.write_text(sample_pipeline_code)
    return pipeline_file


# --------------------------------------------------------------------------
# Time fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def freeze_time():
    """Fixture for freezing time in tests. Usage: freeze_time("2024-01-15 10:00:00")"""
    try:
        from freezegun import freeze_time as _freeze_time

        return _freeze_time
    except ImportError:
        pytest.skip("freezegun not installed")
