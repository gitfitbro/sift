"""Tests for BuildService."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from sift.core.build_service import BuildService
from sift.core.extraction_service import ExtractionService
from sift.models import Session


class TestGenerateOutputs:
    def _prepare_session(self, mock_provider):
        """Helper: capture + extract a phase so there's data to build from."""
        ext = ExtractionService()
        ext.capture_text("test-session", "gather-info", "We discussed A, B, and C.")
        with patch("sift.engine.get_provider", return_value=mock_provider):
            ext.extract_phase("test-session", "gather-info")

    def test_generate_all(self, sample_session, mock_provider):
        self._prepare_session(mock_provider)
        svc = BuildService()
        result = svc.generate_outputs("test-session", "all")

        assert len(result.generated_files) == 3
        labels = [label for label, _ in result.generated_files]
        assert "YAML Config" in labels
        assert "Markdown Summary" in labels
        assert "Consolidated Data" in labels

        # Files should actually exist
        for _, path in result.generated_files:
            assert Path(path).exists()

    def test_generate_yaml_only(self, sample_session, mock_provider):
        self._prepare_session(mock_provider)
        svc = BuildService()
        result = svc.generate_outputs("test-session", "yaml")

        labels = [label for label, _ in result.generated_files]
        assert "YAML Config" in labels
        assert "Consolidated Data" in labels
        assert "Markdown Summary" not in labels

    def test_generate_markdown_only(self, sample_session, mock_provider):
        self._prepare_session(mock_provider)
        svc = BuildService()
        result = svc.generate_outputs("test-session", "markdown")

        labels = [label for label, _ in result.generated_files]
        assert "Markdown Summary" in labels
        assert "YAML Config" not in labels

    def test_generate_no_data(self, sample_session):
        svc = BuildService()
        with pytest.raises(ValueError, match="No extracted data"):
            svc.generate_outputs("test-session")

    def test_generate_bad_session(self):
        svc = BuildService()
        with pytest.raises(FileNotFoundError):
            svc.generate_outputs("nonexistent")

    def test_output_dir_created(self, sample_session, mock_provider):
        self._prepare_session(mock_provider)
        svc = BuildService()
        result = svc.generate_outputs("test-session")

        assert result.output_dir.exists()
        assert result.output_dir.name == "outputs"


class TestGenerateSummary:
    def test_summary_no_data(self, sample_session):
        svc = BuildService()
        with pytest.raises(ValueError, match="No data"):
            svc.generate_summary("test-session")

    def test_summary_bad_session(self):
        svc = BuildService()
        with pytest.raises(FileNotFoundError):
            svc.generate_summary("nonexistent")

    def test_summary_with_data(self, sample_session, mock_provider):
        ext = ExtractionService()
        ext.capture_text("test-session", "gather-info", "We discussed A, B, and C.")
        with patch("sift.engine.get_provider", return_value=mock_provider):
            ext.extract_phase("test-session", "gather-info")

        svc = BuildService()
        with patch("sift.engine.generate_summary", return_value="This is the AI summary."):
            summary, path = svc.generate_summary("test-session")

        assert summary == "This is the AI summary."
        assert path.exists()
        assert path.name == "ai-summary.md"
        assert path.read_text() == "This is the AI summary."
