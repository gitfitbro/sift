"""Layered configuration service for sift.

Priority (highest to lowest):
1. CLI flags (--provider, --model) — set via environment before service init
2. Environment variables (SIFT_*)
3. Project config (.sift.toml in current directory)
4. Global config (~/.config/sift/config.toml)
5. Built-in defaults
"""
from __future__ import annotations

import copy
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("sift.config")

# TOML reading — stdlib in 3.11+, tomli fallback for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]

# TOML writing — use tomli_w if available, else manual
try:
    import tomli_w

    def _write_toml(data: dict, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            tomli_w.dump(data, f)

except ImportError:

    def _write_toml(data: dict, path: Path) -> None:
        """Minimal TOML writer for simple key-value configs."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        _write_toml_section(data, lines, prefix="")
        path.write_text("\n".join(lines) + "\n")

    def _write_toml_section(data: dict, lines: list[str], prefix: str) -> None:
        # Write simple values first, then tables
        tables = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                tables.append((key, value, full_key))
            elif isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, int):
                lines.append(f"{key} = {value}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, list):
                items = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
                lines.append(f"{key} = [{items}]")
        for key, value, full_key in tables:
            lines.append(f"\n[{full_key}]")
            _write_toml_section(value, lines, prefix=full_key)


# Default configuration values
DEFAULTS: dict[str, Any] = {
    "providers": {
        "default": "anthropic",
        "anthropic": {
            "model": "claude-sonnet-4-5-20250514",
        },
        "gemini": {
            "model": "gemini-2.0-flash",
        },
        "ollama": {
            "model": "llama3.2",
            "endpoint": "http://localhost:11434",
        },
    },
    "session": {
        "default_template": "",
        "data_dir": "",
    },
    "ui": {
        "theme": "default",
        "plain_output": False,
    },
}

# Mapping of env vars to config paths
ENV_VAR_MAP = {
    "SIFT_PROVIDER": "providers.default",
    "AI_PROVIDER": "providers.default",
    "SIFT_MODEL": None,  # handled specially per-provider
    "SIFT_HOME": "session.data_dir",
    "SIFT_PLAIN": "ui.plain_output",
    "ANTHROPIC_MODEL": "providers.anthropic.model",
    "GEMINI_MODEL": "providers.gemini.model",
    "OLLAMA_MODEL": "providers.ollama.model",
    "OLLAMA_ENDPOINT": "providers.ollama.endpoint",
}


def _global_config_dir() -> Path:
    """Return the global config directory: ~/.config/sift/."""
    return Path.home() / ".config" / "sift"


def _global_config_path() -> Path:
    """Return the global config file path."""
    return _global_config_dir() / "config.toml"


def _project_config_path() -> Path:
    """Return the project config file path (.sift.toml in cwd)."""
    return Path.cwd() / ".sift.toml"


def _read_toml(path: Path) -> dict:
    """Read a TOML file, returning empty dict if missing or unreadable."""
    if not path.is_file():
        return {}
    if tomllib is None:
        logger.debug("No TOML reader available, skipping %s", path)
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base (override wins)."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_nested(data: dict, dotted_key: str, default: Any = None) -> Any:
    """Get a value from a nested dict using dotted key notation."""
    keys = dotted_key.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _set_nested(data: dict, dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using dotted key notation."""
    keys = dotted_key.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


@dataclass
class ResolvedConfig:
    """Fully resolved configuration after merging all layers."""
    data: dict = field(default_factory=dict)
    global_config_path: Optional[Path] = None
    project_config_path: Optional[Path] = None

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Get a config value using dotted key notation."""
        return _get_nested(self.data, dotted_key, default)


class ConfigService:
    """Layered configuration service.

    Resolves config from multiple sources with clear precedence:
    1. Environment variables (SIFT_*, AI_PROVIDER, etc.)
    2. Project config (.sift.toml)
    3. Global config (~/.config/sift/config.toml)
    4. Built-in defaults
    """

    def __init__(self):
        self._resolved: Optional[ResolvedConfig] = None

    def resolve(self, force: bool = False) -> ResolvedConfig:
        """Resolve the full config from all layers."""
        if self._resolved is not None and not force:
            return self._resolved

        # Start with defaults
        merged = copy.deepcopy(DEFAULTS)

        # Layer 4: Global config
        global_path = _global_config_path()
        global_data = _read_toml(global_path)
        if global_data:
            merged = _deep_merge(merged, global_data)
            logger.debug("Loaded global config from %s", global_path)

        # Layer 3: Project config
        project_path = _project_config_path()
        project_data = _read_toml(project_path)
        if project_data:
            merged = _deep_merge(merged, project_data)
            logger.debug("Loaded project config from %s", project_path)

        # Layer 2: Environment variables
        for env_var, config_path in ENV_VAR_MAP.items():
            env_value = os.environ.get(env_var)
            if env_value is not None and config_path is not None:
                # Convert string booleans
                if env_value.lower() in ("true", "1", "yes"):
                    env_value = True
                elif env_value.lower() in ("false", "0", "no"):
                    env_value = False
                _set_nested(merged, config_path, env_value)

        self._resolved = ResolvedConfig(
            data=merged,
            global_config_path=global_path if global_path.is_file() else None,
            project_config_path=project_path if project_path.is_file() else None,
        )
        return self._resolved

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Get a resolved config value."""
        return self.resolve().get(dotted_key, default)

    def get_provider_name(self) -> str:
        """Get the active provider name."""
        return self.get("providers.default", "anthropic")

    def get_provider_model(self, provider: Optional[str] = None) -> str:
        """Get the model for a provider."""
        provider = provider or self.get_provider_name()
        return self.get(f"providers.{provider}.model", "")

    def get_data_dir(self) -> Path:
        """Get the data directory, respecting SIFT_HOME and config."""
        # SIFT_HOME env var takes highest priority
        env_home = os.environ.get("SIFT_HOME")
        if env_home:
            return Path(env_home).expanduser()

        # Config-specified data dir
        config_dir = self.get("session.data_dir", "")
        if config_dir:
            return Path(config_dir).expanduser()

        # Default: project-local ./data/
        project_root = Path(__file__).parent.parent.parent
        project_data = project_root / "data"

        # Legacy fallback: ~/.sift
        global_home = Path.home() / ".sift"
        if global_home.exists() and not project_data.exists():
            return global_home

        return project_data

    def set_global(self, dotted_key: str, value: Any) -> None:
        """Set a value in the global config file."""
        path = _global_config_path()
        data = _read_toml(path)
        _set_nested(data, dotted_key, value)
        _write_toml(data, path)
        # Invalidate cache
        self._resolved = None
        logger.info("Set %s = %s in %s", dotted_key, value, path)

    def init_project_config(self) -> Path:
        """Create a .sift.toml in the current directory with defaults."""
        path = _project_config_path()
        if path.exists():
            raise FileExistsError(f"Project config already exists: {path}")

        data = {
            "session": {
                "default_template": "",
                "data_dir": "./sift-data",
            },
            "providers": {
                "default": "anthropic",
            },
        }
        _write_toml(data, path)
        logger.info("Created project config: %s", path)
        return path

    def show(self, redact_keys: bool = True) -> dict:
        """Return the resolved config as a dict, optionally redacting secrets."""
        resolved = self.resolve(force=True)
        result = {
            "resolved": resolved.data,
            "sources": {
                "global_config": str(resolved.global_config_path) if resolved.global_config_path else None,
                "project_config": str(resolved.project_config_path) if resolved.project_config_path else None,
            },
        }
        return result

    def config_paths(self) -> dict[str, str]:
        """Return all config file locations and their existence status."""
        global_path = _global_config_path()
        project_path = _project_config_path()
        credentials_path = _global_config_dir() / "credentials"
        return {
            "global_config": f"{global_path} ({'exists' if global_path.is_file() else 'not found'})",
            "project_config": f"{project_path} ({'exists' if project_path.is_file() else 'not found'})",
            "credentials": f"{credentials_path} ({'exists' if credentials_path.is_file() else 'not found'})",
            "data_dir": f"{self.get_data_dir()} ({'exists' if self.get_data_dir().exists() else 'not found'})",
        }


# Module-level singleton
_config_service: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    """Get or create the global ConfigService instance."""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


def reset_config_service() -> None:
    """Reset the global config service (useful for testing)."""
    global _config_service
    _config_service = None
