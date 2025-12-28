"""Tests for network validators."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from harness.validators.network import HostReachable, SFTPConnectable


class TestHostReachable:
    """Tests for HostReachable validator."""

    def test_passes_when_host_reachable(self) -> None:
        """Should pass when connection succeeds."""
        with patch("socket.create_connection") as mock_conn:
            mock_socket = MagicMock()
            mock_conn.return_value = mock_socket

            validator = HostReachable("example.com", 443)
            result = validator.check({})

            assert result.passed
            assert "reachable" in result.message.lower()
            mock_socket.close.assert_called_once()

    def test_fails_on_timeout(self) -> None:
        """Should fail when connection times out."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.side_effect = socket.timeout("timed out")

            validator = HostReachable("slow.example.com", 80, timeout_seconds=1.0)
            result = validator.check({})

            assert not result.passed
            assert "timed out" in result.message.lower()
            assert result.details["error"] == "timeout"

    def test_fails_on_dns_error(self) -> None:
        """Should fail when DNS resolution fails."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.side_effect = socket.gaierror(8, "Name or service not known")

            validator = HostReachable("nonexistent.invalid", 80)
            result = validator.check({})

            assert not result.passed
            assert "dns" in result.message.lower() or "resolution" in result.message.lower()
            assert result.details["error"] == "dns_resolution"

    def test_fails_on_connection_refused(self) -> None:
        """Should fail when connection is refused."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError()

            validator = HostReachable("localhost", 9999)
            result = validator.check({})

            assert not result.passed
            assert "refused" in result.message.lower()
            assert result.details["error"] == "connection_refused"

    def test_fails_on_general_error(self) -> None:
        """Should fail on general OS errors."""
        with patch("socket.create_connection") as mock_conn:
            mock_conn.side_effect = OSError("Network unreachable")

            validator = HostReachable("10.0.0.1", 80)
            result = validator.check({})

            assert not result.passed
            assert "failed" in result.message.lower()
            assert result.details["error"] == "os_error"

    def test_invalid_host(self) -> None:
        """Should raise ValueError for empty host."""
        with pytest.raises(ValueError):
            HostReachable("", 80)

    def test_invalid_port_low(self) -> None:
        """Should raise ValueError for port < 1."""
        with pytest.raises(ValueError):
            HostReachable("example.com", 0)

    def test_invalid_port_high(self) -> None:
        """Should raise ValueError for port > 65535."""
        with pytest.raises(ValueError):
            HostReachable("example.com", 65536)

    def test_invalid_timeout(self) -> None:
        """Should raise ValueError for non-positive timeout."""
        with pytest.raises(ValueError):
            HostReachable("example.com", 80, timeout_seconds=0)

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = HostReachable("example.com", 443)
        assert "example.com" in repr(validator)
        assert "443" in repr(validator)

        validator2 = HostReachable("example.com", 80, timeout_seconds=10.0)
        assert "timeout_seconds" in repr(validator2)


class TestSFTPConnectable:
    """Tests for SFTPConnectable validator."""

    @pytest.fixture
    def mock_secrets(self) -> MagicMock:
        """Create a mock secrets store."""
        mock = MagicMock()
        return mock

    def test_passes_when_connection_succeeds(self) -> None:
        """Should pass when SFTP connection succeeds."""
        creds = {
            "host": "sftp.example.com",
            "username": "user",
            "password": "secret",
        }

        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = creds
            MockSecrets.return_value = mock_store

            with patch("paramiko.Transport") as MockTransport:
                mock_transport = MagicMock()
                MockTransport.return_value = mock_transport

                with patch("paramiko.SFTPClient.from_transport") as MockSFTP:
                    mock_sftp = MagicMock()
                    MockSFTP.return_value = mock_sftp

                    validator = SFTPConnectable("vendor_sftp")
                    result = validator.check({})

                    assert result.passed
                    assert "successful" in result.message.lower()
                    mock_transport.connect.assert_called_once()
                    mock_sftp.close.assert_called_once()

    def test_fails_when_credentials_not_found(self) -> None:
        """Should fail when credentials are not in secrets store."""
        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = None
            MockSecrets.return_value = mock_store

            validator = SFTPConnectable("nonexistent")
            result = validator.check({})

            assert not result.passed
            assert "not found" in result.message.lower()

    def test_fails_when_secrets_error(self) -> None:
        """Should fail when secrets store raises an error."""
        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.side_effect = Exception("No secrets key")
            MockSecrets.return_value = mock_store

            validator = SFTPConnectable("vendor_sftp")
            result = validator.check({})

            assert not result.passed
            assert "could not retrieve" in result.message.lower()

    def test_fails_when_missing_required_keys(self) -> None:
        """Should fail when credentials are missing required keys."""
        creds = {"host": "sftp.example.com"}  # missing username

        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = creds
            MockSecrets.return_value = mock_store

            validator = SFTPConnectable("incomplete")
            result = validator.check({})

            assert not result.passed
            assert "missing" in result.message.lower()

    def test_fails_when_no_auth_method(self) -> None:
        """Should fail when credentials have no password or key."""
        creds = {
            "host": "sftp.example.com",
            "username": "user",
            # No password or private_key_path
        }

        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = creds
            MockSecrets.return_value = mock_store

            validator = SFTPConnectable("no_auth")
            result = validator.check({})

            assert not result.passed
            assert "password" in result.message.lower() or "private_key" in result.message.lower()

    def test_fails_when_connection_fails(self) -> None:
        """Should fail when SFTP connection fails."""
        creds = {
            "host": "sftp.example.com",
            "username": "user",
            "password": "wrong",
        }

        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = creds
            MockSecrets.return_value = mock_store

            with patch("paramiko.Transport") as MockTransport:
                mock_transport = MagicMock()
                mock_transport.connect.side_effect = Exception("Auth failed")
                MockTransport.return_value = mock_transport

                validator = SFTPConnectable("vendor_sftp")
                result = validator.check({})

                assert not result.passed
                assert "failed" in result.message.lower()

    def test_uses_default_port(self) -> None:
        """Should use port 22 when not specified in credentials."""
        creds = {
            "host": "sftp.example.com",
            "username": "user",
            "password": "secret",
        }

        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = creds
            MockSecrets.return_value = mock_store

            with patch("paramiko.Transport") as MockTransport:
                mock_transport = MagicMock()
                MockTransport.return_value = mock_transport

                with patch("paramiko.SFTPClient.from_transport"):
                    validator = SFTPConnectable("vendor_sftp")
                    validator.check({})

                    MockTransport.assert_called_once_with(("sftp.example.com", 22))

    def test_uses_custom_port(self) -> None:
        """Should use custom port when specified in credentials."""
        creds = {
            "host": "sftp.example.com",
            "port": 2222,
            "username": "user",
            "password": "secret",
        }

        with patch("harness.secrets.SecretsStore") as MockSecrets:
            mock_store = MagicMock()
            mock_store.get.return_value = creds
            MockSecrets.return_value = mock_store

            with patch("paramiko.Transport") as MockTransport:
                mock_transport = MagicMock()
                MockTransport.return_value = mock_transport

                with patch("paramiko.SFTPClient.from_transport"):
                    validator = SFTPConnectable("vendor_sftp")
                    validator.check({})

                    MockTransport.assert_called_once_with(("sftp.example.com", 2222))

    def test_invalid_connection_name(self) -> None:
        """Should raise ValueError for empty connection_name."""
        with pytest.raises(ValueError):
            SFTPConnectable("")

    def test_invalid_timeout(self) -> None:
        """Should raise ValueError for non-positive timeout."""
        with pytest.raises(ValueError):
            SFTPConnectable("test", timeout_seconds=0)

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = SFTPConnectable("vendor_sftp")
        assert "vendor_sftp" in repr(validator)

        validator2 = SFTPConnectable("test", timeout_seconds=30.0)
        assert "timeout_seconds" in repr(validator2)
