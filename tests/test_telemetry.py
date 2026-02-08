"""Tests for telemetry consent manager and service."""

import pytest

from sift.telemetry.consent import COLLECTED, NEVER_COLLECTED, ConsentManager
from sift.telemetry.service import CLITelemetry, NoOpSpan, get_telemetry, reset_telemetry


class TestConsentManager:
    """Tests for ConsentManager."""

    def test_disabled_by_default(self, tmp_path):
        consent = ConsentManager(config_dir=tmp_path)
        assert consent.is_enabled() is False

    def test_enable(self, tmp_path):
        consent = ConsentManager(config_dir=tmp_path)
        consent.enable()
        assert consent.is_enabled() is True
        assert consent.consent_file.exists()

    def test_disable(self, tmp_path):
        consent = ConsentManager(config_dir=tmp_path)
        consent.enable()
        assert consent.is_enabled() is True
        consent.disable()
        assert consent.is_enabled() is False

    def test_env_var_override_enables(self, tmp_path, monkeypatch):
        consent = ConsentManager(config_dir=tmp_path)
        monkeypatch.setenv("SIFT_TELEMETRY", "enabled")
        assert consent.is_enabled() is True

    def test_env_var_override_disables(self, tmp_path, monkeypatch):
        consent = ConsentManager(config_dir=tmp_path)
        consent.enable()
        monkeypatch.setenv("SIFT_TELEMETRY", "disabled")
        assert consent.is_enabled() is False

    def test_env_var_true_variant(self, tmp_path, monkeypatch):
        consent = ConsentManager(config_dir=tmp_path)
        monkeypatch.setenv("SIFT_TELEMETRY", "1")
        assert consent.is_enabled() is True

    def test_env_var_false_variant(self, tmp_path, monkeypatch):
        consent = ConsentManager(config_dir=tmp_path)
        monkeypatch.setenv("SIFT_TELEMETRY", "0")
        assert consent.is_enabled() is False

    def test_status_default(self, tmp_path):
        consent = ConsentManager(config_dir=tmp_path)
        info = consent.status()
        assert info["enabled"] is False
        assert info["source"] == "default"
        assert info["env_override"] is None
        assert len(info["collected"]) > 0
        assert len(info["never_collected"]) > 0

    def test_status_after_enable(self, tmp_path):
        consent = ConsentManager(config_dir=tmp_path)
        consent.enable()
        info = consent.status()
        assert info["enabled"] is True
        assert info["source"] == "consent_file"

    def test_status_with_env_override(self, tmp_path, monkeypatch):
        consent = ConsentManager(config_dir=tmp_path)
        monkeypatch.setenv("SIFT_TELEMETRY", "enabled")
        info = consent.status()
        assert info["source"] == "environment"
        assert info["env_override"] == "enabled"

    def test_creates_config_dir(self, tmp_path):
        config_dir = tmp_path / "nested" / "config"
        consent = ConsentManager(config_dir=config_dir)
        consent.enable()
        assert config_dir.exists()

    def test_collected_and_never_collected_are_nonempty(self):
        assert len(COLLECTED) >= 5
        assert len(NEVER_COLLECTED) >= 5


class TestCLITelemetry:
    """Tests for CLITelemetry service."""

    def test_disabled_telemetry_noop(self):
        tel = CLITelemetry(enabled=False)
        with tel.track_command("test") as span:
            assert isinstance(span, NoOpSpan)

    def test_disabled_telemetry_no_exception(self):
        tel = CLITelemetry(enabled=False)
        with tel.track_command("test"):
            pass
        tel.record_provider_used("anthropic", "claude-3")

    def test_track_command_propagates_exception(self):
        tel = CLITelemetry(enabled=False)
        with pytest.raises(ValueError, match="test error"), tel.track_command("test"):
            raise ValueError("test error")

    def test_noop_span_methods(self):
        span = NoOpSpan()
        span.set_attribute("key", "value")
        span.set_status("ok")
        span.record_exception(RuntimeError("test"))
        span.end()

    def test_noop_span_context_manager(self):
        span = NoOpSpan()
        with span as s:
            assert s is span


class TestGetTelemetry:
    """Tests for the singleton getter."""

    def test_returns_same_instance(self, tmp_path, monkeypatch):
        reset_telemetry()
        monkeypatch.setenv("SIFT_TELEMETRY", "disabled")
        t1 = get_telemetry()
        t2 = get_telemetry()
        assert t1 is t2
        reset_telemetry()

    def test_reset_clears_singleton(self, monkeypatch):
        reset_telemetry()
        monkeypatch.setenv("SIFT_TELEMETRY", "disabled")
        t1 = get_telemetry()
        reset_telemetry()
        t2 = get_telemetry()
        assert t1 is not t2
        reset_telemetry()
