"""Tests for the sift MCP server tool functions."""
from __future__ import annotations

import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sift.mcp.server import (
    sift_list_templates,
    sift_create_session,
    sift_list_sessions,
    sift_session_status,
    sift_capture_text,
    sift_extract_phase,
    sift_build_outputs,
    sift_export_session,
    sift_analyze_project,
    _serialize,
    _clean_paths,
)


def run(coro):
    """Helper to run async tool functions in sync tests."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestSerializationHelpers:
    def test_clean_paths_converts_path(self):
        assert _clean_paths(Path("/foo/bar")) == "/foo/bar"

    def test_clean_paths_handles_nested(self):
        data = {"path": Path("/x"), "items": [Path("/y"), "z"]}
        result = _clean_paths(data)
        assert result == {"path": "/x", "items": ["/y", "z"]}

    def test_clean_paths_passthrough(self):
        assert _clean_paths(42) == 42
        assert _clean_paths("hello") == "hello"

    def test_serialize_dataclass(self):
        from sift.core import TemplateInfo
        info = TemplateInfo(
            name="Test", stem="test", description="A test",
            phase_count=2, output_count=1,
        )
        result = _serialize(info)
        assert result["name"] == "Test"
        assert result["phase_count"] == 2

    def test_serialize_non_dataclass(self):
        assert _serialize("hello") == "hello"
        assert _serialize(42) == 42


# ---------------------------------------------------------------------------
# Template tool tests
# ---------------------------------------------------------------------------

class TestSiftListTemplates:
    def test_returns_templates(self, sample_template_path):
        result = run(sift_list_templates())
        assert "templates" in result
        assert len(result["templates"]) >= 1
        tmpl = result["templates"][0]
        assert "name" in tmpl
        assert "phase_count" in tmpl

    def test_empty_when_no_templates(self, sift_home):
        # Remove any template files
        import shutil
        templates_dir = sift_home / "templates"
        for f in templates_dir.iterdir():
            f.unlink()
        result = run(sift_list_templates())
        assert result["templates"] == []


# ---------------------------------------------------------------------------
# Session tool tests
# ---------------------------------------------------------------------------

class TestSiftCreateSession:
    def test_create_session(self, sample_template_path):
        result = run(sift_create_session(template="test-template", name="mcp-test"))
        assert result["status"] == "created"
        assert result["session"]["name"] == "mcp-test"
        assert result["session"]["total_phases"] == 2

    def test_create_session_not_found(self):
        result = run(sift_create_session(template="nonexistent"))
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_create_session_duplicate(self, sample_template_path):
        run(sift_create_session(template="test-template", name="dup-test"))
        result = run(sift_create_session(template="test-template", name="dup-test"))
        assert result["status"] == "error"
        assert "already exists" in result["error"]


class TestSiftListSessions:
    def test_empty_list(self):
        result = run(sift_list_sessions())
        assert result["sessions"] == []

    def test_list_with_session(self, sample_session):
        result = run(sift_list_sessions())
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["name"] == "test-session"


class TestSiftSessionStatus:
    def test_get_status(self, sample_session):
        result = run(sift_session_status(session_name="test-session"))
        assert result["status"] == "ok"
        assert result["session"]["name"] == "test-session"
        assert len(result["session"]["phases"]) == 2

    def test_not_found(self):
        result = run(sift_session_status(session_name="nonexistent"))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Capture & extraction tool tests
# ---------------------------------------------------------------------------

class TestSiftCaptureText:
    def test_capture_text(self, sample_session):
        result = run(sift_capture_text(
            session_name="test-session",
            phase_id="gather-info",
            text="Some captured text for testing.",
        ))
        assert result["status"] == "ok"
        assert result["capture"]["phase_id"] == "gather-info"
        assert result["capture"]["char_count"] > 0

    def test_capture_bad_session(self):
        result = run(sift_capture_text(
            session_name="nonexistent",
            phase_id="foo",
            text="text",
        ))
        assert result["status"] == "error"

    def test_capture_bad_phase(self, sample_session):
        result = run(sift_capture_text(
            session_name="test-session",
            phase_id="nonexistent-phase",
            text="text",
        ))
        assert result["status"] == "error"


class TestSiftExtractPhase:
    def test_extract_no_transcript(self, sample_session):
        result = run(sift_extract_phase(
            session_name="test-session",
            phase_id="gather-info",
        ))
        assert result["status"] == "error"
        assert "transcript" in result["error"].lower() or "No transcript" in result["error"]

    def test_extract_after_capture(self, sample_session, mock_provider):
        # Capture text first
        run(sift_capture_text(
            session_name="test-session",
            phase_id="gather-info",
            text="The main points are: scalability and performance.",
        ))

        # Mock the AI extraction
        with patch("sift.engine.extract_structured_data") as mock_extract:
            mock_extract.return_value = {
                "key_points": ["scalability", "performance"],
                "summary": "Discussion focused on scalability and performance",
            }
            result = run(sift_extract_phase(
                session_name="test-session",
                phase_id="gather-info",
            ))

        assert result["status"] == "ok"
        assert result["extraction"]["field_count"] == 2


# ---------------------------------------------------------------------------
# Build tool tests
# ---------------------------------------------------------------------------

class TestSiftBuildOutputs:
    def test_build_no_data(self, sample_session):
        result = run(sift_build_outputs(session_name="test-session"))
        assert result["status"] == "error"
        assert "extracted data" in result["error"].lower() or "extraction" in result["error"].lower()

    def test_build_after_extraction(self, sample_session):
        # Capture and fake extract
        run(sift_capture_text(
            session_name="test-session",
            phase_id="gather-info",
            text="Test content.",
        ))
        with patch("sift.engine.extract_structured_data") as mock_extract:
            mock_extract.return_value = {
                "key_points": ["point 1"],
                "summary": "Test summary",
            }
            run(sift_extract_phase(
                session_name="test-session",
                phase_id="gather-info",
            ))

        result = run(sift_build_outputs(session_name="test-session"))
        assert result["status"] == "ok"
        assert len(result["files"]) >= 1
        assert "output_dir" in result


# ---------------------------------------------------------------------------
# Export tool tests
# ---------------------------------------------------------------------------

class TestSiftExportSession:
    def test_export(self, sample_session):
        result = run(sift_export_session(session_name="test-session"))
        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["session"]["name"] == "test-session"
        assert "phases" in result["data"]

    def test_export_not_found(self):
        result = run(sift_export_session(session_name="nonexistent"))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Project analysis tool tests
# ---------------------------------------------------------------------------

class TestSiftAnalyzeProject:
    def test_analyze_project(self, tmp_path):
        # Create a minimal project
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "utils.py").write_text("def helper():\n    pass\n")

        result = run(sift_analyze_project(project_path=str(tmp_path)))
        assert result["status"] == "ok"
        assert result["project"]["total_files"] >= 2
        assert "python" in str(result["project"]["languages"]).lower() or "py" in str(result["project"]["languages"]).lower()

    def test_analyze_bad_path(self):
        result = run(sift_analyze_project(project_path="/nonexistent/path"))
        assert result["status"] == "error"
