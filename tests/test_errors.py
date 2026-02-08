"""Tests for custom exception hierarchy."""

from sift.errors import (
    CaptureError,
    ConfigError,
    ExtractionError,
    PhaseNotFoundError,
    ProviderAuthError,
    ProviderError,
    ProviderModelError,
    ProviderQuotaError,
    ProviderUnavailableError,
    SchemaVersionError,
    SessionNotFoundError,
    SiftError,
    TemplateNotFoundError,
)


class TestSiftErrorBase:
    def test_message(self):
        e = SiftError("test error")
        assert str(e) == "test error"

    def test_empty_context_by_default(self):
        e = SiftError("test error")
        assert e.context == {}

    def test_context_passed_through(self):
        e = SiftError("test error", context={"session": "my-session"})
        assert e.context == {"session": "my-session"}

    def test_exit_code_default(self):
        e = SiftError("test error")
        assert e.exit_code == 1

    def test_is_exception(self):
        assert issubclass(SiftError, Exception)


class TestNotFoundErrors:
    def test_session_not_found(self):
        e = SessionNotFoundError("demo-session")
        assert "demo-session" in str(e)
        assert e.context["session"] == "demo-session"
        assert isinstance(e, SiftError)

    def test_phase_not_found_basic(self):
        e = PhaseNotFoundError("bad-phase")
        assert "bad-phase" in str(e)
        assert e.context["phase"] == "bad-phase"

    def test_phase_not_found_with_available(self):
        e = PhaseNotFoundError("bad-phase", session_name="s1", available=["a", "b"])
        assert "bad-phase" in str(e)
        assert "a, b" in str(e)
        assert e.context["phase"] == "bad-phase"
        assert e.context["session"] == "s1"

    def test_template_not_found(self):
        e = TemplateNotFoundError("missing-tmpl")
        assert "missing-tmpl" in str(e)
        assert e.context["template"] == "missing-tmpl"

    def test_template_not_found_with_search_dir(self):
        e = TemplateNotFoundError("missing-tmpl", search_dir="/data/templates")
        assert "/data/templates" in str(e)


class TestProviderErrors:
    def test_hierarchy(self):
        assert issubclass(ProviderAuthError, ProviderError)
        assert issubclass(ProviderQuotaError, ProviderError)
        assert issubclass(ProviderModelError, ProviderError)
        assert issubclass(ProviderUnavailableError, ProviderError)
        assert issubclass(ProviderError, SiftError)

    def test_provider_error_context(self):
        e = ProviderAuthError("bad key", provider="anthropic", model="claude-3")
        assert e.context["provider"] == "anthropic"
        assert e.context["model"] == "claude-3"

    def test_provider_error_extra_context(self):
        e = ProviderError("err", provider="gemini", context={"extra": "data"})
        assert e.context["provider"] == "gemini"
        assert e.context["extra"] == "data"


class TestSchemaVersionError:
    def test_version_mismatch(self):
        e = SchemaVersionError("/path/session.yaml", found_version=5, expected_version=1)
        assert "v5" in str(e)
        assert "v1" in str(e)
        assert e.context["found_version"] == 5
        assert e.context["expected_version"] == 1
        assert e.context["file"] == "/path/session.yaml"


class TestOperationErrors:
    def test_extraction_error(self):
        e = ExtractionError("no data", phase_id="review", session_name="s1")
        assert "no data" in str(e)
        assert e.context["phase"] == "review"
        assert e.context["session"] == "s1"
        assert isinstance(e, SiftError)

    def test_capture_error(self):
        e = CaptureError("bad file", phase_id="gather", file_path="/tmp/x.zip")
        assert "bad file" in str(e)
        assert e.context["phase"] == "gather"
        assert e.context["file"] == "/tmp/x.zip"
        assert isinstance(e, SiftError)

    def test_config_error(self):
        e = ConfigError("bad config")
        assert "bad config" in str(e)
        assert isinstance(e, SiftError)
