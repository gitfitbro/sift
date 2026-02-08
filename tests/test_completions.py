"""Tests for shell completion functions."""
import pytest
from unittest.mock import MagicMock
from sift.completions import (
    complete_session_name,
    complete_template_name,
    complete_phase_id,
    complete_provider_name,
    complete_format,
)


class TestCompleteSessionName:
    def test_returns_matching(self, sample_session):
        results = complete_session_name("test")
        assert "test-session" in results

    def test_returns_empty_on_no_match(self, sample_session):
        results = complete_session_name("zzz")
        assert results == []

    def test_returns_all_on_empty(self, sample_session):
        results = complete_session_name("")
        assert "test-session" in results


class TestCompleteTemplateName:
    def test_returns_matching(self, sample_template_path):
        results = complete_template_name("test")
        assert "test-template" in results

    def test_returns_empty_on_no_match(self, sample_template_path):
        results = complete_template_name("zzz")
        assert results == []

    def test_multi_template_plus_syntax(self, sift_home, sample_template_path):
        import shutil
        shutil.copy(
            sample_template_path,
            sift_home / "templates" / "other-template.yaml",
        )
        results = complete_template_name("test-template+oth")
        assert "test-template+other-template" in results

    def test_multi_template_plus_empty_suffix(self, sift_home, sample_template_path):
        results = complete_template_name("test-template+")
        assert any(r.startswith("test-template+") for r in results)


class TestCompletePhaseId:
    def test_returns_phase_ids(self, sample_session):
        ctx = MagicMock()
        ctx.params = {"session": "test-session"}
        results = complete_phase_id(ctx, "")
        assert "gather-info" in results
        assert "review" in results

    def test_filters_by_prefix(self, sample_session):
        ctx = MagicMock()
        ctx.params = {"session": "test-session"}
        results = complete_phase_id(ctx, "ga")
        assert "gather-info" in results
        assert "review" not in results

    def test_no_session_returns_empty(self):
        ctx = MagicMock()
        ctx.params = {}
        results = complete_phase_id(ctx, "")
        assert results == []

    def test_bad_session_returns_empty(self):
        ctx = MagicMock()
        ctx.params = {"session": "nonexistent"}
        results = complete_phase_id(ctx, "")
        assert results == []


class TestCompleteStatic:
    def test_provider_name(self):
        assert "anthropic" in complete_provider_name("")
        assert "gemini" in complete_provider_name("")
        assert complete_provider_name("a") == ["anthropic"]
        assert complete_provider_name("g") == ["gemini"]
        assert complete_provider_name("x") == []

    def test_format(self):
        assert "yaml" in complete_format("")
        assert "markdown" in complete_format("")
        assert "all" in complete_format("")
        assert complete_format("y") == ["yaml"]
        assert complete_format("x") == []
