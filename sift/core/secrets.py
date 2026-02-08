"""Secure secrets storage for sift API keys.

Stores API keys in ~/.config/sift/credentials with restricted file permissions.
Environment variables always override stored keys. Optional keyring integration
for OS-level secure storage.
"""
from __future__ import annotations

import logging
import os
import stat
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sift.secrets")

# Provider name -> environment variable mapping
PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": None,  # No API key needed
}


def _credentials_path() -> Path:
    """Return path to the credentials file."""
    return Path.home() / ".config" / "sift" / "credentials"


def _read_credentials() -> dict[str, str]:
    """Read credentials file. Format: KEY=VALUE per line."""
    path = _credentials_path()
    if not path.is_file():
        return {}
    creds = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            creds[key.strip()] = value.strip()
    return creds


def _write_credentials(creds: dict[str, str]) -> None:
    """Write credentials file with restricted permissions (0600)."""
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# sift credentials - DO NOT COMMIT THIS FILE"]
    for key, value in sorted(creds.items()):
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines) + "\n")

    # Set file permissions to owner-only read/write
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        logger.warning("Could not set permissions on %s", path)


def store_key(provider: str, api_key: str) -> None:
    """Store an API key for a provider.

    Args:
        provider: Provider name (anthropic, gemini, etc.)
        api_key: The API key to store
    """
    env_var = PROVIDER_KEY_ENV.get(provider)
    if env_var is None:
        raise ValueError(f"Provider '{provider}' does not use an API key")

    # Try keyring first if available
    if _store_keyring(provider, api_key):
        logger.info("Stored %s key in system keyring", provider)
        return

    # Fall back to credentials file
    creds = _read_credentials()
    creds[env_var] = api_key
    _write_credentials(creds)
    logger.info("Stored %s key in credentials file", provider)


def get_key(provider: str) -> Optional[str]:
    """Get the API key for a provider.

    Priority:
    1. Environment variable (always wins)
    2. System keyring (if keyring package installed)
    3. Credentials file (~/.config/sift/credentials)

    Args:
        provider: Provider name (anthropic, gemini, etc.)

    Returns:
        The API key or None if not found.
    """
    env_var = PROVIDER_KEY_ENV.get(provider)
    if env_var is None:
        return None  # Provider doesn't use keys

    # 1. Environment variable
    env_key = os.environ.get(env_var)
    if env_key:
        return env_key

    # 2. System keyring
    keyring_key = _get_keyring(provider)
    if keyring_key:
        return keyring_key

    # 3. Credentials file
    creds = _read_credentials()
    return creds.get(env_var)


def remove_key(provider: str) -> bool:
    """Remove a stored API key for a provider.

    Returns True if a key was removed, False if none existed.
    """
    env_var = PROVIDER_KEY_ENV.get(provider)
    if env_var is None:
        raise ValueError(f"Provider '{provider}' does not use an API key")

    removed = False

    # Remove from keyring
    if _remove_keyring(provider):
        removed = True

    # Remove from credentials file
    creds = _read_credentials()
    if env_var in creds:
        del creds[env_var]
        _write_credentials(creds)
        removed = True

    return removed


def list_stored_providers() -> dict[str, str]:
    """List providers with stored keys and their source.

    Returns dict of provider -> source ("env", "keyring", "file", or "not set").
    """
    result = {}
    for provider, env_var in PROVIDER_KEY_ENV.items():
        if env_var is None:
            result[provider] = "no key needed"
            continue
        if os.environ.get(env_var):
            result[provider] = "env"
        elif _get_keyring(provider):
            result[provider] = "keyring"
        elif _read_credentials().get(env_var):
            result[provider] = "file"
        else:
            result[provider] = "not set"
    return result


# --- Keyring integration (optional) ---

def _store_keyring(provider: str, api_key: str) -> bool:
    """Try to store key in system keyring. Returns True on success."""
    try:
        import keyring
        keyring.set_password("sift", provider, api_key)
        return True
    except (ImportError, Exception):
        return False


def _get_keyring(provider: str) -> Optional[str]:
    """Try to get key from system keyring. Returns None if unavailable."""
    try:
        import keyring
        return keyring.get_password("sift", provider)
    except (ImportError, Exception):
        return None


def _remove_keyring(provider: str) -> bool:
    """Try to remove key from system keyring. Returns True on success."""
    try:
        import keyring
        keyring.delete_password("sift", provider)
        return True
    except (ImportError, Exception):
        return False
