"""Tests for internationalization support."""

from sift.i18n import _, ngettext, setup_i18n


class TestI18n:
    """Tests for i18n module."""

    def test_gettext_passthrough(self):
        """English strings pass through unchanged."""
        assert _("Hello") == "Hello"
        assert _("Session created successfully") == "Session created successfully"

    def test_gettext_with_format(self):
        """Translated strings support .format()."""
        result = _("No template found: {name}").format(name="test")
        assert result == "No template found: test"

    def test_ngettext_singular(self):
        """ngettext returns singular form for 1."""
        result = ngettext("{n} session", "{n} sessions", 1).format(n=1)
        assert result == "1 session"

    def test_ngettext_plural(self):
        """ngettext returns plural form for > 1."""
        result = ngettext("{n} session", "{n} sessions", 5).format(n=5)
        assert result == "5 sessions"

    def test_setup_with_nonexistent_lang(self):
        """Gracefully falls back for unknown languages."""
        translations = setup_i18n(lang="xx_NONEXISTENT")
        assert translations.gettext("Hello") == "Hello"

    def test_setup_with_none(self):
        """None lang uses fallback."""
        translations = setup_i18n(lang=None)
        assert translations.gettext("test") == "test"

    def test_setup_with_env_var(self, monkeypatch):
        """SIFT_LANG environment variable is respected."""
        monkeypatch.setenv("SIFT_LANG", "es")
        translations = setup_i18n()
        # No Spanish translations exist, so falls back to passthrough
        assert translations.gettext("Hello") == "Hello"
