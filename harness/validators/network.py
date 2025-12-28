"""Network validators for Task Harness.

These validators check network connectivity to hosts and services.
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, TYPE_CHECKING

from harness.models import ValidationResult
from harness.validators.base import Validator

if TYPE_CHECKING:
    import paramiko


class HostReachable(Validator):
    """Check if a host is reachable via TCP connection.

    Example:
        preconditions = [
            HostReachable("api.example.com", 443),
            HostReachable("database.internal", 5432, timeout_seconds=10.0),
        ]
    """

    name = "HostReachable"

    def __init__(
        self,
        host: str,
        port: int,
        timeout_seconds: float = 5.0,
    ):
        """Initialize the validator.

        Args:
            host: Hostname or IP address to check.
            port: TCP port to connect to.
            timeout_seconds: Connection timeout in seconds.
        """
        if not host:
            raise ValueError("host is required")
        if not (1 <= port <= 65535):
            raise ValueError(f"port must be 1-65535, got {port}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the host is reachable."""
        try:
            sock = socket.create_connection(
                (self.host, self.port),
                timeout=self.timeout_seconds,
            )
            sock.close()
            return ValidationResult.success(
                self.name,
                f"Host reachable: {self.host}:{self.port}",
            )

        except socket.timeout:
            return ValidationResult.failure(
                self.name,
                f"Connection timed out: {self.host}:{self.port} "
                f"(timeout: {self.timeout_seconds}s)",
                details={
                    "host": self.host,
                    "port": self.port,
                    "timeout": self.timeout_seconds,
                    "error": "timeout",
                },
            )

        except socket.gaierror as e:
            return ValidationResult.failure(
                self.name,
                f"DNS resolution failed: {self.host} ({e})",
                details={
                    "host": self.host,
                    "port": self.port,
                    "error": "dns_resolution",
                    "message": str(e),
                },
            )

        except ConnectionRefusedError:
            return ValidationResult.failure(
                self.name,
                f"Connection refused: {self.host}:{self.port}",
                details={
                    "host": self.host,
                    "port": self.port,
                    "error": "connection_refused",
                },
            )

        except OSError as e:
            return ValidationResult.failure(
                self.name,
                f"Connection failed: {self.host}:{self.port} ({e})",
                details={
                    "host": self.host,
                    "port": self.port,
                    "error": "os_error",
                    "message": str(e),
                },
            )

    def __repr__(self) -> str:
        parts = [f"{self.host!r}", str(self.port)]
        if self.timeout_seconds != 5.0:
            parts.append(f"timeout_seconds={self.timeout_seconds}")
        return f"HostReachable({', '.join(parts)})"


class SFTPConnectable(Validator):
    """Check if an SFTP server is connectable using stored credentials.

    Credentials are retrieved from the secrets store using the connection_name.
    Expected credential format (JSON):
    {
        "host": "sftp.example.com",
        "port": 22,  # optional, defaults to 22
        "username": "user",
        "password": "secret",  # OR
        "private_key_path": "/path/to/key",  # with optional:
        "private_key_passphrase": "keypass"
    }

    Example:
        preconditions = [
            SFTPConnectable("vendor_sftp"),  # Uses credentials from secrets store
        ]
    """

    name = "SFTPConnectable"

    def __init__(
        self,
        connection_name: str,
        timeout_seconds: float = 10.0,
    ):
        """Initialize the validator.

        Args:
            connection_name: Name of the connection in the secrets store.
            timeout_seconds: Connection timeout in seconds.
        """
        if not connection_name:
            raise ValueError("connection_name is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.connection_name = connection_name
        self.timeout_seconds = timeout_seconds

    def check(self, context: dict[str, Any]) -> ValidationResult:
        """Check if the SFTP server is connectable."""
        # Import here to avoid circular dependency and handle missing secrets module
        try:
            from harness.secrets import SecretsStore
        except ImportError:
            return ValidationResult.failure(
                self.name,
                "Secrets module not available",
            )

        # Get credentials from secrets store
        try:
            secrets = SecretsStore()
            creds = secrets.get(self.connection_name)
        except Exception as e:
            return ValidationResult.failure(
                self.name,
                f"Could not retrieve credentials '{self.connection_name}': {e}",
            )

        if not creds:
            return ValidationResult.failure(
                self.name,
                f"Credentials not found: {self.connection_name}",
            )

        # Validate credential structure
        required_keys = {"host", "username"}
        if not required_keys.issubset(creds.keys()):
            missing = required_keys - creds.keys()
            return ValidationResult.failure(
                self.name,
                f"Invalid credentials: missing {missing}",
            )

        if "password" not in creds and "private_key_path" not in creds:
            return ValidationResult.failure(
                self.name,
                "Credentials must include 'password' or 'private_key_path'",
            )

        # Try to connect
        try:
            transport, sftp = self._connect(creds)
            sftp.close()
            transport.close()

            return ValidationResult.success(
                self.name,
                f"SFTP connection successful: {creds['host']}",
            )

        except Exception as e:
            return ValidationResult.failure(
                self.name,
                f"SFTP connection failed: {e}",
                details={
                    "host": creds.get("host"),
                    "username": creds.get("username"),
                    "error": str(e),
                },
            )

    def _connect(self, creds: dict) -> tuple[paramiko.Transport, paramiko.SFTPClient]:
        """Establish SFTP connection using credentials.

        Args:
            creds: Credential dictionary with host, username, and auth info.

        Returns:
            Tuple of (Transport, SFTPClient).

        Raises:
            Various exceptions on connection failure.
        """
        import paramiko

        host = creds["host"]
        port = creds.get("port", 22)
        username = creds["username"]

        transport = paramiko.Transport((host, port))

        try:
            if "password" in creds:
                transport.connect(username=username, password=creds["password"])
            elif "private_key_path" in creds:
                key_path = Path(creds["private_key_path"])
                passphrase = creds.get("private_key_passphrase")

                pkey = self._load_private_key(key_path, passphrase)
                transport.connect(username=username, pkey=pkey)
            else:
                raise ValueError("No authentication method provided")

            sftp = paramiko.SFTPClient.from_transport(transport)
            return transport, sftp

        except Exception:
            transport.close()
            raise

    def _load_private_key(
        self, key_path: Path, passphrase: str | None
    ) -> paramiko.PKey:
        """Load a private key from file, auto-detecting key type.

        Args:
            key_path: Path to the private key file.
            passphrase: Optional passphrase for encrypted keys.

        Returns:
            Loaded private key.

        Raises:
            ValueError: If key format is not supported.
        """
        import paramiko

        if not key_path.exists():
            raise FileNotFoundError(f"Private key not found: {key_path}")

        key_classes = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ]

        for key_class in key_classes:
            try:
                return key_class.from_private_key_file(
                    str(key_path), password=passphrase
                )
            except paramiko.SSHException:
                continue

        raise ValueError(f"Unsupported key format: {key_path}")

    def __repr__(self) -> str:
        parts = [f"{self.connection_name!r}"]
        if self.timeout_seconds != 10.0:
            parts.append(f"timeout_seconds={self.timeout_seconds}")
        return f"SFTPConnectable({', '.join(parts)})"
