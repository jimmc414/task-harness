"""Secrets management for Task Harness.

Provides encrypted storage for sensitive credentials using Fernet symmetric encryption.
This is a stub implementation that will be fully implemented in Step 15.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from harness.exceptions import SecretsKeyError, SecretsNotFoundError, SecretsDecryptionError


class SecretsStore:
    """Encrypted secrets store using Fernet symmetric encryption.

    Key retrieval order:
    1. HARNESS_SECRETS_KEY environment variable
    2. Keyring (Windows Credential Manager)

    The store file location is determined by:
    1. HARNESS_SECRETS_FILE environment variable
    2. Default: .harness/secrets.enc relative to HARNESS_ROOT or cwd
    """

    DEFAULT_STORE_PATH = Path(".harness/secrets.enc")
    KEYRING_SERVICE = "harness"
    KEYRING_KEY = "master_key"

    def __init__(self, store_path: Path | None = None):
        """Initialize the secrets store.

        Args:
            store_path: Optional path to the secrets file.
                       If not provided, uses environment or default.
        """
        if store_path:
            self.store_path = Path(store_path)
        elif env_path := os.environ.get("HARNESS_SECRETS_FILE"):
            self.store_path = Path(env_path)
        else:
            self.store_path = self.DEFAULT_STORE_PATH

        self._key: bytes | None = None
        self._data: dict[str, Any] | None = None

    def _get_master_key(self) -> bytes:
        """Get the master encryption key.

        Returns:
            The Fernet-compatible key bytes.

        Raises:
            SecretsKeyError: If no key is available.
        """
        if self._key is not None:
            return self._key

        # Try environment variable first
        env_key = os.environ.get("HARNESS_SECRETS_KEY")
        if env_key:
            self._key = env_key.encode()  # Fernet expects base64-encoded bytes
            return self._key

        # Try keyring
        try:
            import keyring

            stored = keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_KEY)
            if stored:
                self._key = stored.encode()
                return self._key
        except Exception:
            pass  # Keyring not available or failed

        raise SecretsKeyError()

    def _load(self) -> dict[str, Any]:
        """Load and decrypt the secrets store.

        Returns:
            Dictionary of secrets.

        Raises:
            SecretsDecryptionError: If decryption fails.
        """
        if self._data is not None:
            return self._data

        if not self.store_path.exists():
            self._data = {}
            return self._data

        try:
            from cryptography.fernet import Fernet, InvalidToken

            key = self._get_master_key()
            fernet = Fernet(key)

            encrypted = self.store_path.read_bytes()
            decrypted = fernet.decrypt(encrypted)
            self._data = json.loads(decrypted.decode())
            return self._data

        except InvalidToken:
            raise SecretsDecryptionError("Invalid key or corrupted data")
        except Exception as e:
            raise SecretsDecryptionError(str(e))

    def _save(self) -> None:
        """Encrypt and save the secrets store."""
        from cryptography.fernet import Fernet

        key = self._get_master_key()
        fernet = Fernet(key)

        data = self._data or {}
        encrypted = fernet.encrypt(json.dumps(data).encode())

        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_bytes(encrypted)

    def get(self, name: str) -> Any:
        """Get a secret by name.

        Args:
            name: Name of the secret.

        Returns:
            The secret value (usually a dict for credentials).

        Raises:
            SecretsNotFoundError: If the secret doesn't exist.
        """
        data = self._load()
        if name not in data:
            raise SecretsNotFoundError(name)
        return data[name]

    def set(self, name: str, value: Any) -> None:
        """Store a secret.

        Args:
            name: Name of the secret.
            value: Value to store (must be JSON-serializable).
        """
        self._load()
        self._data[name] = value
        self._save()

    def delete(self, name: str) -> None:
        """Delete a secret.

        Args:
            name: Name of the secret.

        Raises:
            SecretsNotFoundError: If the secret doesn't exist.
        """
        data = self._load()
        if name not in data:
            raise SecretsNotFoundError(name)
        del self._data[name]
        self._save()

    def list_names(self) -> list[str]:
        """List all secret names.

        Returns:
            List of secret names (not values).
        """
        return list(self._load().keys())

    def exists(self, name: str) -> bool:
        """Check if a secret exists.

        Args:
            name: Name of the secret.

        Returns:
            True if the secret exists.
        """
        return name in self._load()

    @classmethod
    def generate_key(cls) -> str:
        """Generate a new Fernet key.

        Returns:
            Base64-encoded key string suitable for HARNESS_SECRETS_KEY.
        """
        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()

    @classmethod
    def init_store(cls, store_path: Path | None = None, save_to_keyring: bool = True) -> str:
        """Initialize a new secrets store.

        Args:
            store_path: Optional path for the secrets file.
            save_to_keyring: Whether to save the key to keyring.

        Returns:
            The generated key (for backup/env var use).
        """
        key = cls.generate_key()

        if save_to_keyring:
            try:
                import keyring

                keyring.set_password(cls.KEYRING_SERVICE, cls.KEYRING_KEY, key)
            except Exception:
                pass  # Keyring not available

        # Create empty store
        store = cls(store_path)
        store._key = key.encode()
        store._data = {}
        store._save()

        return key
