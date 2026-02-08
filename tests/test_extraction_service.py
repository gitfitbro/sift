"""Tests for ExtractionService."""

from unittest.mock import patch

import pytest

from sift.core.extraction_service import ExtractionService
from sift.errors import CaptureError, ExtractionError, PhaseNotFoundError, SessionNotFoundError
from sift.models import Session


class TestCaptureText:
    def test_capture_text(self, sample_session):
        svc = ExtractionService()
        result = svc.capture_text("test-session", "gather-info", "Hello world")

        assert result.phase_id == "gather-info"
        assert result.status == "transcribed"
        assert result.file_type == "text"
        assert result.char_count == 11

        # Verify session state was updated
        s = Session.load("test-session")
        assert s.phases["gather-info"].status == "transcribed"
        assert s.phases["gather-info"].transcript_file == "transcript.txt"

    def test_capture_text_empty(self, sample_session):
        svc = ExtractionService()
        with pytest.raises(CaptureError):
            svc.capture_text("test-session", "gather-info", "   ")

    def test_capture_text_bad_phase(self, sample_session):
        svc = ExtractionService()
        with pytest.raises(PhaseNotFoundError):
            svc.capture_text("test-session", "nonexistent", "test")

    def test_capture_text_bad_session(self):
        svc = ExtractionService()
        with pytest.raises(SessionNotFoundError):
            svc.capture_text("nonexistent", "phase", "test")


class TestCaptureFile:
    def test_capture_text_file(self, sample_session, tmp_path):
        text_file = tmp_path / "notes.txt"
        text_file.write_text("Some notes here")

        svc = ExtractionService()
        result = svc.capture_file("test-session", "gather-info", text_file)

        assert result.status == "transcribed"
        assert result.file_type == "text"

    def test_capture_audio_file(self, sample_session, tmp_path):
        audio_file = tmp_path / "recording.mp3"
        audio_file.write_bytes(b"\x00" * 100)  # fake audio

        svc = ExtractionService()
        result = svc.capture_file("test-session", "gather-info", audio_file)

        assert result.status == "captured"
        assert result.file_type == "audio"

    def test_capture_unsupported_file(self, sample_session, tmp_path):
        bad_file = tmp_path / "data.xlsx"
        bad_file.write_bytes(b"\x00")

        svc = ExtractionService()
        with pytest.raises(CaptureError):
            svc.capture_file("test-session", "gather-info", bad_file)

    def test_capture_missing_file(self, sample_session, tmp_path):
        svc = ExtractionService()
        with pytest.raises(CaptureError):
            svc.capture_file("test-session", "gather-info", tmp_path / "nope.txt")


class TestExtractPhase:
    def test_extract_with_mock_provider(self, sample_session, mock_provider):
        # First, capture some text
        svc = ExtractionService()
        svc.capture_text("test-session", "gather-info", "We discussed points A, B, and C.")

        # Mock the provider
        with patch("sift.engine.get_provider", return_value=mock_provider):
            result = svc.extract_phase("test-session", "gather-info")

        assert result.phase_id == "gather-info"
        assert result.phase_name == "Gather Information"
        assert "key_points" in result.fields
        assert result.field_count > 0

        # Verify session state
        s = Session.load("test-session")
        assert s.phases["gather-info"].status == "extracted"

    def test_extract_no_transcript(self, sample_session):
        svc = ExtractionService()
        with pytest.raises(ExtractionError):
            svc.extract_phase("test-session", "gather-info")

    def test_extract_no_fields(self, sample_session, sift_home):
        """Phase with no extraction fields should mark as complete."""
        import yaml

        # Create a template with a phase that has no extract fields
        tmpl_data = {
            "name": "No Extract",
            "description": "Testing",
            "phases": [
                {
                    "id": "simple",
                    "name": "Simple Phase",
                    "prompt": "Just capture.",
                    "capture": [{"type": "text"}],
                    "extract": [],
                },
            ],
            "outputs": [],
        }
        path = sift_home / "templates" / "no-extract.yaml"
        with open(path, "w") as f:
            yaml.dump(tmpl_data, f)

        from sift.core.session_service import SessionService

        ssvc = SessionService()
        ssvc.create_session("no-extract", name="ne-test")

        svc = ExtractionService()
        svc.capture_text("ne-test", "simple", "Some text here")
        result = svc.extract_phase("ne-test", "simple")

        assert result.fields == {}
        assert result.field_count == 0

        s = Session.load("ne-test")
        assert s.phases["simple"].status == "complete"


class TestGetRemainingPhases:
    def test_all_pending(self, sample_session):
        svc = ExtractionService()
        remaining = svc.get_remaining_phases("test-session")
        assert len(remaining) == 2

    def test_some_done(self, sample_session, mock_provider):
        svc = ExtractionService()
        svc.capture_text("test-session", "gather-info", "Some content")

        with patch("sift.engine.get_provider", return_value=mock_provider):
            svc.extract_phase("test-session", "gather-info")

        remaining = svc.get_remaining_phases("test-session")
        assert len(remaining) == 1
        assert remaining[0]["phase_id"] == "review"
