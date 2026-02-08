"""Tests for the plugin discovery system."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

from sift.plugins import (
    discover_plugins,
    discover_providers,
    list_all_plugins,
    get_provider_names,
    PROVIDER_GROUP,
    ANALYZER_GROUP,
    FORMATTER_GROUP,
    PluginInfo,
)


def _make_entry_point(name: str, value: str, group: str):
    """Create a mock entry point."""
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.group = group
    return ep


class TestDiscoverPlugins:
    """Tests for discover_plugins function."""

    def test_discovers_entry_points(self):
        """Should load plugins from entry points."""
        mock_class = type("MockProvider", (), {})
        ep = _make_entry_point("mock", "mock_pkg:MockProvider", PROVIDER_GROUP)
        ep.load.return_value = mock_class

        with patch("sift.plugins.entry_points", return_value=[ep]):
            result = discover_plugins(PROVIDER_GROUP)

        assert "mock" in result
        assert result["mock"] is mock_class

    def test_handles_load_error(self):
        """Should skip plugins that fail to load."""
        ep = _make_entry_point("broken", "broken_pkg:Bad", PROVIDER_GROUP)
        ep.load.side_effect = ImportError("no module")

        with patch("sift.plugins.entry_points", return_value=[ep]):
            result = discover_plugins(PROVIDER_GROUP)

        assert result == {}

    def test_empty_group(self):
        """Should return empty dict when no entry points exist."""
        with patch("sift.plugins.entry_points", return_value=[]):
            result = discover_plugins(PROVIDER_GROUP)

        assert result == {}


class TestDiscoverProviders:
    """Tests for discover_providers convenience function."""

    def test_calls_with_provider_group(self):
        """Should call discover_plugins with the providers group."""
        with patch("sift.plugins.discover_plugins", return_value={"test": object}) as mock:
            result = discover_providers()

        mock.assert_called_once_with(PROVIDER_GROUP)
        assert result == {"test": object}


class TestListAllPlugins:
    """Tests for list_all_plugins function."""

    def test_lists_plugins_from_all_groups(self):
        """Should return PluginInfo for every entry point across groups."""
        ep1 = _make_entry_point("anthropic", "sift.providers.anthropic_provider:AnthropicProvider", PROVIDER_GROUP)
        ep1.load.return_value = object
        ep2 = _make_entry_point("broken", "bad:Thing", ANALYZER_GROUP)
        ep2.load.side_effect = ImportError("no module")

        def fake_entry_points(group):
            return {PROVIDER_GROUP: [ep1], ANALYZER_GROUP: [ep2], FORMATTER_GROUP: []}[group]

        with patch("sift.plugins.entry_points", side_effect=fake_entry_points):
            result = list_all_plugins()

        assert len(result) == 2

        loaded = [p for p in result if p.loaded]
        failed = [p for p in result if not p.loaded]
        assert len(loaded) == 1
        assert loaded[0].name == "anthropic"
        assert len(failed) == 1
        assert failed[0].name == "broken"
        assert "no module" in failed[0].error


class TestGetProviderNames:
    """Tests for get_provider_names function."""

    def test_returns_sorted_names(self):
        """Should return sorted list of provider names."""
        eps = [
            _make_entry_point("ollama", "sift.providers.ollama_provider:OllamaProvider", PROVIDER_GROUP),
            _make_entry_point("anthropic", "sift.providers.anthropic_provider:AnthropicProvider", PROVIDER_GROUP),
            _make_entry_point("gemini", "sift.providers.gemini_provider:GeminiProvider", PROVIDER_GROUP),
        ]
        with patch("sift.plugins.entry_points", return_value=eps):
            names = get_provider_names()

        assert names == ["anthropic", "gemini", "ollama"]


class TestProviderRegistryIntegration:
    """Tests that provider registry uses plugin discovery."""

    def test_providers_register_from_entry_points(self, monkeypatch):
        """Provider registry should populate via entry points."""
        from sift import providers

        # Reset registry
        monkeypatch.setattr(providers, "PROVIDERS", {})
        monkeypatch.setattr(providers, "_active_provider", None)

        mock_cls = MagicMock()
        mock_cls.return_value = MagicMock(name="test", model="m1")

        with patch("sift.plugins.discover_providers", return_value={"test_prov": mock_cls}):
            providers._register_defaults()

        assert "test_prov" in providers.PROVIDERS

    def test_fallback_when_no_entry_points(self, monkeypatch):
        """Should fall back to direct imports when no entry points found."""
        from sift import providers

        monkeypatch.setattr(providers, "PROVIDERS", {})
        monkeypatch.setattr(providers, "_active_provider", None)

        with patch("sift.plugins.discover_providers", return_value={}):
            providers._register_defaults()

        # Should have loaded at least the built-in providers via direct import
        assert len(providers.PROVIDERS) > 0

    def test_get_provider_names_dynamic(self, monkeypatch):
        """get_provider_names should return dynamically discovered names."""
        from sift import providers

        monkeypatch.setattr(providers, "PROVIDERS", {"alpha": object, "beta": object})

        names = providers.get_provider_names()
        assert names == ["alpha", "beta"]
