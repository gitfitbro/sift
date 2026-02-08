"""Tests for the layered configuration service and secrets management."""

import stat

import pytest

from sift.core.config_service import (
    ConfigService,
    _deep_merge,
    _get_nested,
    _read_toml,
    _set_nested,
    _write_toml,
    get_config_service,
    reset_config_service,
)
from sift.core.secrets import (
    _read_credentials,
    _write_credentials,
    get_key,
    list_stored_providers,
    remove_key,
    store_key,
)

# ─── Helper utilities ───


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"providers": {"default": "anthropic", "anthropic": {"model": "old"}}}
        override = {"providers": {"anthropic": {"model": "new"}}}
        result = _deep_merge(base, override)
        assert result["providers"]["default"] == "anthropic"
        assert result["providers"]["anthropic"]["model"] == "new"

    def test_override_replaces_non_dict(self):
        base = {"a": {"nested": 1}}
        override = {"a": "flat"}
        result = _deep_merge(base, override)
        assert result["a"] == "flat"

    def test_does_not_mutate_base(self):
        base = {"a": 1}
        override = {"b": 2}
        _deep_merge(base, override)
        assert "b" not in base


class TestGetSetNested:
    def test_get_simple(self):
        data = {"a": 1}
        assert _get_nested(data, "a") == 1

    def test_get_dotted(self):
        data = {"providers": {"anthropic": {"model": "claude"}}}
        assert _get_nested(data, "providers.anthropic.model") == "claude"

    def test_get_missing_returns_default(self):
        data = {"a": 1}
        assert _get_nested(data, "b.c", "fallback") == "fallback"

    def test_set_simple(self):
        data = {}
        _set_nested(data, "a", 1)
        assert data == {"a": 1}

    def test_set_dotted_creates_intermediates(self):
        data = {}
        _set_nested(data, "providers.anthropic.model", "claude")
        assert data["providers"]["anthropic"]["model"] == "claude"

    def test_set_overwrites_existing(self):
        data = {"a": {"b": 1}}
        _set_nested(data, "a.b", 2)
        assert data["a"]["b"] == 2


# ─── TOML read/write ───


class TestTomlReadWrite:
    def test_write_and_read_roundtrip(self, tmp_path):
        path = tmp_path / "test.toml"
        data = {
            "providers": {
                "default": "anthropic",
                "anthropic": {"model": "claude-sonnet"},
            },
            "ui": {"plain_output": False},
        }
        _write_toml(data, path)
        assert path.exists()
        result = _read_toml(path)
        assert result["providers"]["default"] == "anthropic"
        assert result["providers"]["anthropic"]["model"] == "claude-sonnet"
        assert result["ui"]["plain_output"] is False

    def test_read_missing_file(self, tmp_path):
        result = _read_toml(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_write_creates_parents(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "config.toml"
        _write_toml({"a": 1}, path)
        assert path.exists()


# ─── ConfigService ───


class TestConfigService:
    def test_defaults_loaded(self, tmp_path, monkeypatch):
        # Isolate from real env and config files
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("SIFT_PROVIDER", raising=False)
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent2.toml",
        )
        svc = ConfigService()
        resolved = svc.resolve()
        assert resolved.get("providers.default") == "anthropic"
        assert resolved.get("providers.anthropic.model") == "claude-sonnet-4-5-20250514"
        assert resolved.get("providers.gemini.model") == "gemini-2.0-flash"

    def test_global_config_override(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        _write_toml({"providers": {"default": "gemini"}}, config_path)
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: config_path,
        )
        svc = ConfigService()
        assert svc.get_provider_name() == "gemini"

    def test_project_config_overrides_global(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("SIFT_PROVIDER", raising=False)
        global_path = tmp_path / "global.toml"
        project_path = tmp_path / ".sift.toml"
        _write_toml({"providers": {"default": "gemini"}}, global_path)
        _write_toml({"providers": {"default": "ollama"}}, project_path)
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: global_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: project_path,
        )
        svc = ConfigService()
        assert svc.get_provider_name() == "ollama"

    def test_env_var_overrides_config(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        _write_toml({"providers": {"default": "gemini"}}, config_path)
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: config_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        svc = ConfigService()
        assert svc.get_provider_name() == "anthropic"

    def test_sift_provider_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent2.toml",
        )
        monkeypatch.setenv("SIFT_PROVIDER", "gemini")
        svc = ConfigService()
        assert svc.get_provider_name() == "gemini"

    def test_get_provider_model(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent2.toml",
        )
        svc = ConfigService()
        assert svc.get_provider_model("anthropic") == "claude-sonnet-4-5-20250514"
        assert svc.get_provider_model("gemini") == "gemini-2.0-flash"

    def test_env_model_override(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent2.toml",
        )
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus")
        svc = ConfigService()
        assert svc.get_provider_model("anthropic") == "claude-opus"

    def test_set_global(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: config_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        svc = ConfigService()
        svc.set_global("providers.default", "ollama")
        # Re-read
        result = _read_toml(config_path)
        assert result["providers"]["default"] == "ollama"
        # Cache invalidated
        assert svc._resolved is None

    def test_init_project_config(self, tmp_path, monkeypatch):
        project_path = tmp_path / ".sift.toml"
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: project_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        svc = ConfigService()
        result_path = svc.init_project_config()
        assert result_path == project_path
        assert project_path.exists()
        data = _read_toml(project_path)
        assert "session" in data
        assert "providers" in data

    def test_init_project_config_already_exists(self, tmp_path, monkeypatch):
        project_path = tmp_path / ".sift.toml"
        project_path.write_text("")
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: project_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        svc = ConfigService()
        with pytest.raises(FileExistsError):
            svc.init_project_config()

    def test_config_paths(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "config.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / ".sift.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._global_config_dir",
            lambda: tmp_path,
        )
        svc = ConfigService()
        paths = svc.config_paths()
        assert "global_config" in paths
        assert "project_config" in paths
        assert "credentials" in paths
        assert "data_dir" in paths

    def test_show(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "config.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / ".sift.toml",
        )
        svc = ConfigService()
        info = svc.show()
        assert "resolved" in info
        assert "sources" in info
        assert "providers" in info["resolved"]

    def test_force_resolve(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("SIFT_PROVIDER", raising=False)
        config_path = tmp_path / "config.toml"
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: config_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        svc = ConfigService()
        # First resolve
        svc.resolve()
        assert svc._resolved is not None
        # Write new config
        _write_toml({"providers": {"default": "gemini"}}, config_path)
        # Without force, cached
        assert svc.get_provider_name() == "anthropic"
        # With force
        resolved = svc.resolve(force=True)
        assert resolved.get("providers.default") == "gemini"


class TestGetDataDir:
    def test_sift_home_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent2.toml",
        )
        custom_dir = tmp_path / "custom"
        monkeypatch.setenv("SIFT_HOME", str(custom_dir))
        svc = ConfigService()
        assert svc.get_data_dir() == custom_dir


class TestSingleton:
    def test_get_config_service_returns_same_instance(self, monkeypatch):
        reset_config_service()
        svc1 = get_config_service()
        svc2 = get_config_service()
        assert svc1 is svc2
        reset_config_service()

    def test_reset_clears_singleton(self, monkeypatch):
        reset_config_service()
        svc1 = get_config_service()
        reset_config_service()
        svc2 = get_config_service()
        assert svc1 is not svc2
        reset_config_service()


# ─── Secrets ───


class TestSecrets:
    def test_store_and_get_key(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        # No keyring
        monkeypatch.setattr("sift.core.secrets._store_keyring", lambda p, k: False)
        monkeypatch.setattr("sift.core.secrets._get_keyring", lambda p: None)
        # Clear env
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        store_key("anthropic", "sk-test-123")
        assert cred_path.exists()

        key = get_key("anthropic")
        assert key == "sk-test-123"

    def test_env_var_overrides_stored_key(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        monkeypatch.setattr("sift.core.secrets._store_keyring", lambda p, k: False)
        monkeypatch.setattr("sift.core.secrets._get_keyring", lambda p: None)

        store_key("anthropic", "sk-stored")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")

        key = get_key("anthropic")
        assert key == "sk-env"

    def test_remove_key(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        monkeypatch.setattr("sift.core.secrets._store_keyring", lambda p, k: False)
        monkeypatch.setattr("sift.core.secrets._get_keyring", lambda p: None)
        monkeypatch.setattr("sift.core.secrets._remove_keyring", lambda p: False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        store_key("anthropic", "sk-test-123")
        assert get_key("anthropic") == "sk-test-123"

        removed = remove_key("anthropic")
        assert removed is True
        assert get_key("anthropic") is None

    def test_remove_nonexistent_key(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        monkeypatch.setattr("sift.core.secrets._remove_keyring", lambda p: False)

        removed = remove_key("anthropic")
        assert removed is False

    def test_store_key_invalid_provider(self):
        with pytest.raises(ValueError, match="does not use an API key"):
            store_key("ollama", "some-key")

    def test_get_key_no_key_provider(self):
        assert get_key("ollama") is None

    def test_list_stored_providers(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        monkeypatch.setattr("sift.core.secrets._store_keyring", lambda p, k: False)
        monkeypatch.setattr("sift.core.secrets._get_keyring", lambda p: None)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        store_key("anthropic", "sk-test")

        result = list_stored_providers()
        assert result["anthropic"] == "file"
        assert result["gemini"] == "not set"
        assert result["ollama"] == "no key needed"

    def test_credentials_file_permissions(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)

        _write_credentials({"TEST_KEY": "value"})
        mode = cred_path.stat().st_mode
        # Check owner-only read/write (0600)
        assert mode & stat.S_IRUSR  # owner read
        assert mode & stat.S_IWUSR  # owner write
        assert not (mode & stat.S_IRGRP)  # no group read
        assert not (mode & stat.S_IROTH)  # no other read

    def test_credentials_roundtrip(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)

        creds = {"ANTHROPIC_API_KEY": "sk-abc", "GOOGLE_API_KEY": "gk-xyz"}
        _write_credentials(creds)
        result = _read_credentials()
        assert result["ANTHROPIC_API_KEY"] == "sk-abc"
        assert result["GOOGLE_API_KEY"] == "gk-xyz"

    def test_read_credentials_ignores_comments(self, tmp_path, monkeypatch):
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        cred_path.write_text("# comment\nKEY=value\n\n# another\n")
        result = _read_credentials()
        assert result == {"KEY": "value"}


# ─── Integration: Config delegates to secrets ───


class TestConfigIntegration:
    def test_config_get_provider_api_key_uses_secrets(self, tmp_path, monkeypatch):
        """Config.get_provider_api_key should resolve via secrets module."""
        cred_path = tmp_path / "credentials"
        monkeypatch.setattr("sift.core.secrets._credentials_path", lambda: cred_path)
        monkeypatch.setattr("sift.core.secrets._store_keyring", lambda p, k: False)
        monkeypatch.setattr("sift.core.secrets._get_keyring", lambda p: None)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        store_key("anthropic", "sk-from-creds")

        from sift.config import Config

        key = Config.get_provider_api_key("anthropic")
        assert key == "sk-from-creds"

    def test_config_get_ai_provider_uses_config_service(self, tmp_path, monkeypatch):
        """Config.get_ai_provider should delegate to ConfigService."""
        config_path = tmp_path / "config.toml"
        _write_toml({"providers": {"default": "gemini"}}, config_path)
        monkeypatch.setattr(
            "sift.core.config_service._global_config_path",
            lambda: config_path,
        )
        monkeypatch.setattr(
            "sift.core.config_service._project_config_path",
            lambda: tmp_path / "nonexistent.toml",
        )
        # Clear env vars that would override
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("SIFT_PROVIDER", raising=False)

        reset_config_service()
        from sift.config import Config

        assert Config.get_ai_provider() == "gemini"
        reset_config_service()
