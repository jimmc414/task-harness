"""Tests for secrets store."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.secrets import SecretsStore
from harness.exceptions import SecretsKeyError, SecretsNotFoundError, SecretsDecryptionError


class TestSecretsStore:
    """Tests for SecretsStore."""

    @pytest.fixture
    def mock_fernet_key(self) -> str:
        """Generate a valid Fernet key."""
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()

    @pytest.fixture
    def store_with_key(self, tmp_path: Path, mock_fernet_key: str, monkeypatch) -> SecretsStore:
        """Create a store with a valid key in environment."""
        monkeypatch.setenv("HARNESS_SECRETS_KEY", mock_fernet_key)
        return SecretsStore(tmp_path / "secrets.enc")

    def test_set_and_get_secret(self, store_with_key: SecretsStore) -> None:
        """Should store and retrieve a secret."""
        secret_value = {"username": "admin", "password": "secret123"}

        store_with_key.set("my_secret", secret_value)
        retrieved = store_with_key.get("my_secret")

        assert retrieved == secret_value

    def test_get_nonexistent_secret(self, store_with_key: SecretsStore) -> None:
        """Should raise SecretsNotFoundError for missing secret."""
        with pytest.raises(SecretsNotFoundError):
            store_with_key.get("nonexistent")

    def test_delete_secret(self, store_with_key: SecretsStore) -> None:
        """Should delete a secret."""
        store_with_key.set("to_delete", {"key": "value"})
        assert store_with_key.exists("to_delete")

        store_with_key.delete("to_delete")
        assert not store_with_key.exists("to_delete")

    def test_delete_nonexistent_secret(self, store_with_key: SecretsStore) -> None:
        """Should raise SecretsNotFoundError when deleting missing secret."""
        with pytest.raises(SecretsNotFoundError):
            store_with_key.delete("nonexistent")

    def test_list_names(self, store_with_key: SecretsStore) -> None:
        """Should list all secret names."""
        store_with_key.set("secret1", {"a": 1})
        store_with_key.set("secret2", {"b": 2})
        store_with_key.set("secret3", {"c": 3})

        names = store_with_key.list_names()

        assert set(names) == {"secret1", "secret2", "secret3"}

    def test_exists(self, store_with_key: SecretsStore) -> None:
        """Should check if secret exists."""
        assert not store_with_key.exists("missing")

        store_with_key.set("present", {"key": "value"})
        assert store_with_key.exists("present")

    def test_overwrite_secret(self, store_with_key: SecretsStore) -> None:
        """Should overwrite existing secret."""
        store_with_key.set("my_secret", {"version": 1})
        store_with_key.set("my_secret", {"version": 2})

        retrieved = store_with_key.get("my_secret")
        assert retrieved == {"version": 2}

    def test_complex_secret_values(self, store_with_key: SecretsStore) -> None:
        """Should handle complex nested values."""
        complex_value = {
            "host": "sftp.example.com",
            "port": 22,
            "credentials": {
                "username": "user",
                "password": "pass",
            },
            "paths": ["/path/1", "/path/2"],
        }

        store_with_key.set("complex", complex_value)
        retrieved = store_with_key.get("complex")

        assert retrieved == complex_value

    def test_no_key_raises_error(self, tmp_path: Path, monkeypatch) -> None:
        """Should raise SecretsKeyError when no key is available."""
        monkeypatch.delenv("HARNESS_SECRETS_KEY", raising=False)

        # Mock keyring to return None
        with patch("keyring.get_password", return_value=None):
            store = SecretsStore(tmp_path / "secrets.enc")

            with pytest.raises(SecretsKeyError):
                store._get_master_key()

    def test_wrong_key_raises_error(self, tmp_path: Path, mock_fernet_key: str, monkeypatch) -> None:
        """Should raise SecretsDecryptionError when using wrong key."""
        from cryptography.fernet import Fernet

        # Create store with one key
        monkeypatch.setenv("HARNESS_SECRETS_KEY", mock_fernet_key)
        store1 = SecretsStore(tmp_path / "secrets.enc")
        store1.set("secret", {"data": "value"})

        # Try to read with different key
        new_key = Fernet.generate_key().decode()
        monkeypatch.setenv("HARNESS_SECRETS_KEY", new_key)

        store2 = SecretsStore(tmp_path / "secrets.enc")
        store2._data = None  # Reset cached data
        store2._key = None   # Reset cached key

        with pytest.raises(SecretsDecryptionError):
            store2.get("secret")

    def test_generate_key(self) -> None:
        """Should generate a valid Fernet key."""
        from cryptography.fernet import Fernet

        key = SecretsStore.generate_key()

        # Should be valid base64-encoded 32 bytes
        assert len(key) == 44  # Base64-encoded 32 bytes

        # Should be usable as a Fernet key
        fernet = Fernet(key.encode())
        encrypted = fernet.encrypt(b"test")
        assert fernet.decrypt(encrypted) == b"test"

    def test_init_store(self, tmp_path: Path, monkeypatch) -> None:
        """Should initialize a new secrets store."""
        # Mock keyring to avoid actual system interaction
        with patch("keyring.set_password"):
            key = SecretsStore.init_store(tmp_path / "new_secrets.enc", save_to_keyring=False)

        assert len(key) == 44
        assert (tmp_path / "new_secrets.enc").exists()

    def test_key_from_env_var(self, tmp_path: Path, mock_fernet_key: str, monkeypatch) -> None:
        """Should use key from environment variable."""
        monkeypatch.setenv("HARNESS_SECRETS_KEY", mock_fernet_key)

        store = SecretsStore(tmp_path / "secrets.enc")
        store.set("test", {"value": 123})

        # Should work
        assert store.get("test") == {"value": 123}

    def test_custom_store_path(self, tmp_path: Path, mock_fernet_key: str, monkeypatch) -> None:
        """Should use custom store path."""
        monkeypatch.setenv("HARNESS_SECRETS_KEY", mock_fernet_key)
        custom_path = tmp_path / "custom" / "location" / "secrets.enc"

        store = SecretsStore(custom_path)
        store.set("secret", {"value": "test"})

        assert custom_path.exists()

    def test_store_path_from_env(self, tmp_path: Path, mock_fernet_key: str, monkeypatch) -> None:
        """Should use store path from environment variable."""
        custom_path = tmp_path / "from_env" / "secrets.enc"
        monkeypatch.setenv("HARNESS_SECRETS_KEY", mock_fernet_key)
        monkeypatch.setenv("HARNESS_SECRETS_FILE", str(custom_path))

        store = SecretsStore()  # No path argument
        store.set("secret", {"value": "test"})

        assert custom_path.exists()

    def test_empty_store(self, store_with_key: SecretsStore) -> None:
        """Should handle empty store gracefully."""
        assert store_with_key.list_names() == []
        assert not store_with_key.exists("anything")
