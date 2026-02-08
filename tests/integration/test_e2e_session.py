"""End-to-end integration tests for the full session lifecycle.

These tests exercise the complete flow: create session -> capture text ->
extract (with mocked AI) -> build outputs -> verify results.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.integration


class TestFullSessionLifecycle:
    """Test the complete session lifecycle end-to-end."""

    def test_complete_lifecycle(self, sample_template_path):
        """Create -> capture -> extract -> build -> verify outputs."""
        from sift.core.build_service import BuildService
        from sift.core.extraction_service import ExtractionService
        from sift.core.session_service import SessionService

        session_svc = SessionService()
        extraction_svc = ExtractionService()
        build_svc = BuildService()

        # 1. Create session
        detail = session_svc.create_session("test-template", "e2e-test")
        assert detail.name == "e2e-test"
        assert detail.total_phases == 2

        # 2. Capture text for phase 1
        result = extraction_svc.capture_text(
            "e2e-test",
            "gather-info",
            "The project uses Python and React. Key challenges are scalability.",
        )
        assert result.status == "transcribed"

        # 3. Extract with mocked provider
        with patch("sift.engine.extract_structured_data") as mock_extract:
            mock_extract.return_value = {
                "key_points": ["Python", "React", "scalability"],
                "summary": "Python/React project focused on scalability",
            }
            extraction_result = extraction_svc.extract_phase("e2e-test", "gather-info")
            assert extraction_result.field_count > 0

        # 4. Build outputs
        build_result = build_svc.generate_outputs("e2e-test", "all")
        assert len(build_result.generated_files) >= 1

        # 5. Verify output files exist and contain data
        for label, path in build_result.generated_files:
            assert path.exists(), f"Output file missing: {label}"
            content = path.read_text()
            assert len(content) > 0, f"Output file empty: {label}"

    def test_multi_phase_lifecycle(self, sample_template_path):
        """Test capturing and extracting across multiple phases."""
        from sift.core.extraction_service import ExtractionService
        from sift.core.session_service import SessionService
        from sift.models import Session

        session_svc = SessionService()
        extraction_svc = ExtractionService()

        # Create session
        session_svc.create_session("test-template", "multi-phase-test")

        # Capture phase 1
        extraction_svc.capture_text(
            "multi-phase-test",
            "gather-info",
            "This is the first phase content about data collection.",
        )

        # Capture phase 2
        extraction_svc.capture_text(
            "multi-phase-test",
            "review",
            "Review notes: looks good, no issues found.",
        )

        # Verify both phases are captured
        session = Session.load("multi-phase-test")
        assert session.phases["gather-info"].status == "transcribed"
        assert session.phases["review"].status == "transcribed"

    def test_session_status_tracking(self, sample_template_path):
        """Test that session status is tracked correctly through the lifecycle."""
        from sift.core.extraction_service import ExtractionService
        from sift.core.session_service import SessionService

        session_svc = SessionService()
        extraction_svc = ExtractionService()

        # Create
        detail = session_svc.create_session("test-template", "status-test")
        assert detail.status == "active"
        assert detail.done_phases == 0

        # Capture
        extraction_svc.capture_text(
            "status-test",
            "gather-info",
            "Some content for tracking.",
        )

        # Check status updated
        updated = session_svc.get_session_status("status-test")
        gather_phase = next(p for p in updated.phases if p.id == "gather-info")
        assert gather_phase.has_transcript is True


class TestDemoFlow:
    """Test the demo command's data writing flow."""

    def test_demo_data_writing(self, sift_home):
        """Test that demo data can be written and read back correctly."""
        from datetime import datetime

        from sift.models import TEMPLATES_DIR, Session, SessionTemplate

        # Create a hello-world-like template
        template_data = {
            "name": "Hello World",
            "description": "Test template",
            "phases": [
                {
                    "id": "describe",
                    "name": "Describe",
                    "prompt": "Describe something",
                    "capture": [{"type": "text", "required": True}],
                    "extract": [
                        {"id": "key_points", "type": "list", "prompt": "List points"},
                        {"id": "summary", "type": "text", "prompt": "Summarize"},
                    ],
                },
            ],
            "outputs": [
                {"type": "yaml", "template": "session-config"},
                {"type": "markdown", "template": "session-summary"},
            ],
        }
        template_path = TEMPLATES_DIR / "hello-world.yaml"
        with open(template_path, "w") as f:
            yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)

        # Create session
        template = SessionTemplate.from_file(template_path)
        session = Session.create("demo-test", template)

        # Write transcript directly (as demo_cmd does)
        phase_dir = session.phase_dir("describe")
        (phase_dir / "transcript.txt").write_text("Test content for demo")

        ps = session.phases["describe"]
        ps.status = "transcribed"
        ps.transcript_file = "transcript.txt"
        ps.captured_at = datetime.now().isoformat()
        session.save()

        # Write extraction directly
        extraction_data = {"key_points": ["point1", "point2"], "summary": "test summary"}
        with open(phase_dir / "extracted.yaml", "w") as f:
            yaml.dump(extraction_data, f)

        ps.status = "extracted"
        ps.extracted_file = "extracted.yaml"
        ps.extracted_at = datetime.now().isoformat()
        session.save()

        # Verify data round-trips
        loaded = Session.load("demo-test")
        assert loaded.phases["describe"].status == "extracted"

        extracted = loaded.get_extracted("describe")
        assert extracted is not None
        assert len(extracted["key_points"]) == 2

        transcript = loaded.get_transcript("describe")
        assert transcript == "Test content for demo"
